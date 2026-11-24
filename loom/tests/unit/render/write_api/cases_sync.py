"""The cases of the endpoints for a pull and for an agent's copy."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.unit._quilts import demo
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    WHO,
    Serve,
    case,
    refuses,
    succeeds,
)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def pulled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A quilt mirroring a local Overleaf stand-in, a colleague's edit to `main.tex` fetched and awaiting incorporation."""
    import loom.sync as sync
    from loom.scan.quilt import load_quilt
    from tests.unit._mirror import SOURCE, colleague, edit, paired

    root, bare = paired(tmp_path)
    edit(colleague(tmp_path, bare), "edit statement", {"main.tex": SOURCE.replace("zk-0001}A", "zk-0001}B")})
    sync.fetch(load_quilt(root), sync.SyncState.read(root))
    return root


@case("sync-incorporate")
def _sync_incorporate(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.sync import SyncState

    (tmp_path / "unsynced").mkdir()
    s = serve(demo(tmp_path / "unsynced"))
    refuses(
        s,
        "sync-incorporate",
        {"incoming": "0" * 40, "base": "0" * 40},
        409,
        "sync-refused",
        "mirrors no Overleaf project",
    )
    root = pulled(tmp_path, monkeypatch)
    s = serve(root)
    state = SyncState.read(root)
    before = (root / "drafting" / "main.tex").read_bytes()
    # pinned to the revision the page displayed: a different one changes nothing
    refuses(
        s,
        "sync-incorporate",
        {"incoming": "0" * 40, "base": state.integrated},
        400,
        "revision-changed",
        "reload Review",
    )
    assert (root / "drafting" / "main.tex").read_bytes() == before
    said = succeeds(s, "sync-incorporate", {"incoming": state.incoming, "base": state.integrated})
    assert said["result"]["integrated"] == state.incoming
    assert b"zk-0001}B" in (root / "drafting" / "main.tex").read_bytes()
    assert said["result"]["paths"] == ["drafting/main.tex"]
    assert said["result"]["landmarks"] == [f"main-before-pull-{state.incoming[:12]}"]
    assert not (root / ".git").exists()  # nothing is committed: the quilt need not be a repository


@case("sync-preview")
def _sync_preview(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.records.store import Records
    from loom.scan.quilt import load_quilt, save_author
    from loom.sync import SyncState

    save_author(WHO)
    root = pulled(tmp_path, monkeypatch)
    s = serve(root)
    state = SyncState.read(root)
    body = {"incoming": state.incoming, "base": state.integrated, "reviewer": WHO}
    before = (root / "drafting/main.tex").read_bytes()
    refuses(s, "sync-preview", {**body, "reviewer": "Other"}, 409, "reviewer-changed", "reload Review")
    view = succeeds(s, "sync-preview", body)["result"]
    assert (root / "drafting/main.tex").read_bytes() == before
    assert [r["key"] for r in view["items"]] == ["zk-0001"]
    monkeypatch.setattr("loom.cli.review._master_compiles", lambda *_: (True, ""))
    answer = succeeds(s, "sync-incorporate", {**body, "review_token": view["token"], "accept": ["zk-0001"]})["result"]
    assert answer["accepted"] == ["zk-0001"]
    assert Records(root, load_quilt(root).history_dir).latest["zk-0001"].author == WHO


@case("adopt-decision")
@case("adopt-preview")
@case("adopt-finish")
def _adoption(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.adopt import comparison
    from loom.scan.quilt import load_quilt, save_author
    from loom.scan.scan import scan
    from tests.helpers import ok

    root = demo(tmp_path)
    save_author(WHO)
    ok("draft", "drafting/main.tex", "--ai", "contribution.tex", cwd=root)
    copy = root / ".loom/agents/copies/contribution.tex"
    text = copy.read_text()
    # An ordinary source change to an existing inline statement.
    text = text.replace("Closedness is where", "The revised closedness is where")
    copy.write_text(text)
    data = comparison(scan(load_quilt(root)), "contribution")
    s = serve(root)
    payload = {"copy": data["copy"], "reviewer": WHO, "fingerprint": data["fingerprint"]}
    for endpoint in ("adopt-decision", "adopt-preview", "adopt-finish"):
        refuses(s, endpoint, {**payload, "reviewer": "different"}, 409, "reviewer-changed", "reload Review")
    succeeds(s, "adopt-decision", {**payload, "keys": ["dm-0004"], "document": False})
    preview = succeeds(s, "adopt-preview", payload)["result"]
    assert preview["patch"]
    succeeds(s, "adopt-finish", {**payload, "token": preview["token"]})
    assert "The revised closedness" in (root / "drafting/main.tex").read_text()
    assert any(e.action == "adopt" for e in scan(load_quilt(root)).history.entries)


@case("adopt-close")
@case("adopt-reopen")
@case("adopt-refresh")
@case("adopt-paper")
def _section_lifecycle(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.scan.quilt import save_author
    from tests.helpers import ok
    from tests.unit.test_section_drafts import TEXT

    root = tmp_path / "sections"
    (root / "drafting").mkdir(parents=True)
    (root / "config.toml").write_text('[quilt]\nname="section-api"\nprefix="zk"\nmain="drafting/main.tex"\n')
    source = root / "drafting/main.tex"
    source.write_text(TEXT)
    save_author(WHO)
    ok("draft", "drafting/main.tex", "--ai", "first.tex", "--section", "zk-0100", cwd=root)
    draft = root / ".loom/agents/copies/first.tex"
    draft.write_text(draft.read_text().replace("First statement.", "Proposal."))
    s = serve(root)
    body = {"copy": ".loom/agents/copies/first.tex", "reviewer": WHO}
    for endpoint in ("adopt-close", "adopt-reopen", "adopt-refresh", "adopt-paper"):
        refuses(s, endpoint, {**body, "reviewer": "different"}, 409, "reviewer-changed", "reload Review")
    builds = s.builds
    data = json.loads(get(s.url + "build/manifest.json")[2])["contributions"][0]
    from loom.render.watch import snapshot

    watched = snapshot(root)
    selected = succeeds(
        s,
        "adopt-decision",
        {**body, "fingerprint": data["fingerprint"], "revision": 0, "keys": ["zk-0001"], "document": False},
    )["result"]
    assert selected["revision"] == 1 and s.builds == builds and snapshot(root) == watched
    refuses(
        s,
        "adopt-decision",
        {**body, "fingerprint": data["fingerprint"], "revision": 0, "keys": [], "document": False},
        409,
        "adoption-refused",
        "another tab",
    )
    succeeds(s, "adopt-paper", body)
    source.write_text(source.read_text().replace("Detail prose.", "Author detail."))
    succeeds(s, "adopt-refresh", body)
    assert "Author detail." in draft.read_text() and "Proposal." in draft.read_text()
    assert succeeds(s, "adopt-close", body)["result"]["confirmation_required"]
    succeeds(s, "adopt-close", {**body, "confirmed": True})
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert next(m for m in manifest["masters"] if m["path"] == body["copy"])["closed"]
    succeeds(s, "adopt-reopen", body)
