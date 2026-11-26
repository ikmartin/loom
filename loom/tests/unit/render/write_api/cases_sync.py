"""The cases of the endpoints for an agent's copy."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

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


# ---- the Overleaf mirror ---------------------------------------------------------------------------------------------


def published(root: Path) -> dict[str, Any]:
    """The manifest's `overleaf`, as the server last published it."""
    from loom.paths import MANIFEST

    return json.loads((root / MANIFEST).read_text())["overleaf"]  # type: ignore[no-any-return]


#: A link to the stand-in project, whose address leads where the test suite's isolation keeps it (`overleaf.BASE`).
LINK = "https://www.overleaf.com/project/5f1e0c2a9b3d4e6f7a8b9c0d"


@case("overleaf-pair")
def _overleaf_pair(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit import _mirror as mirror

    root = mirror.quilt_at(tmp_path)
    mirror.overleaf(tmp_path)
    link = LINK
    s = serve(root)
    refuses(s, "overleaf-pair", {"link": "https://www.overleaf.com/read/abcdefghijkl"}, 409, "sharing-link", "sharing")
    refuses(s, "overleaf-pair", {"link": link, "author": "Claude Agent"}, 403, "author-only", "author's")
    asked = succeeds(s, "overleaf-pair", {"link": link})["result"]["choose"]
    assert (asked["folder"], asked["mains"], asked["main"]) == ("paper", ["main.tex"], "main.tex")
    assert [a["name"] for a in asked["authors"]] == [mirror.PERSON[0]]
    done = succeeds(
        s, "overleaf-pair", {"link": link, "folder": "drafting", "main": "main.tex", "me": [mirror.PERSON[1]]}
    )
    assert done["result"]["paired"] == {"folder": "drafting", "main": "drafting/main.tex"}
    assert (root / "drafting/main.tex").read_text() == mirror.SOURCE
    shown = published(root)
    assert (shown["paired"], shown["folder"], shown["waiting"], shown["problem"]) == (True, "drafting", False, None)
    assert shown["link"] == LINK


@case("overleaf-token")
def _overleaf_token(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit._mirror import quilt_at
    from tests.unit._overleaf_server import TOKEN, serving

    root = quilt_at(tmp_path)
    (tmp_path / "srv").mkdir()
    with serving(tmp_path / "srv") as server:
        import loom.overleaf as overleaf

        monkeypatch.setattr(overleaf, "BASE", server.url("").rstrip("/"))
        link = LINK
        s = serve(root)
        refuses(s, "overleaf-token", {"link": link, "token": "two words"}, 400, "bad-token", "not a git token")
        assert succeeds(s, "overleaf-token", {"link": link, "token": TOKEN})["result"] == {"stored": True}
    assert TOKEN in (tmp_path / "keychain-stand-in").read_text()


@case("overleaf-update")
def _overleaf_update(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from tests.unit import _mirror as mirror

    (tmp_path / "plain").mkdir()
    refuses(serve(demo(tmp_path / "plain")), "overleaf-update", {}, 409, "not-paired", "mirrors no Overleaf project")
    root, bare = mirror.paired(tmp_path)
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": mirror.SOURCE.replace("}A", "}B")})
    s = serve(root)
    # the server fetches once as it starts, writes nothing of the person's, and says Overleaf has changes; the fetch runs in the background beside the first build, so a busy machine takes its time
    for _ in range(600):
        if published(root)["waiting"]:
            break
        time.sleep(0.05)
    assert published(root)["waiting"] is True and (root / "drafting/main.tex").read_text() == mirror.SOURCE
    said = succeeds(s, "overleaf-update", {})["result"]
    assert said == {
        "state": "updated",
        "files": 1,
        "by": ["Colleague"],
        "own": 0,
        "places": [],
        "here": [],
        "overwritten": [],
    }
    assert "}B" in (root / "drafting/main.tex").read_text()
    shown = published(root)
    assert shown["waiting"] is False and shown["last"]["by"] == ["Colleague"] and shown["last"]["files"] == 1
    assert succeeds(s, "overleaf-update", {})["result"] == {"state": "up-to-date"}


@case("overleaf-me")
def _overleaf_me(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A quilt that came without its `.loom/local/` knows no one on this machine: the server's fetch says to ask, the history's authors are given, and the answer is kept."""
    import shutil
    import time

    from tests.unit import _mirror as mirror

    (tmp_path / "plain").mkdir()
    refuses(serve(demo(tmp_path / "plain")), "overleaf-me", {}, 409, "not-paired", "mirrors no Overleaf project")
    root, _ = mirror.paired(tmp_path)
    shutil.rmtree(root / ".loom/local")
    s = serve(root)
    # the fetch runs in the background beside the first build, so a busy machine takes its time
    for _ in range(600):
        if published(root).get("ask_me"):
            break
        time.sleep(0.05)
    assert published(root)["ask_me"] is True
    asked = succeeds(s, "overleaf-me", {})["result"]["authors"]
    assert asked == [{"name": mirror.PERSON[0], "email": mirror.PERSON[1]}]
    refuses(s, "overleaf-me", {"me": "pat"}, 400, "bad-field", "list of addresses")
    assert succeeds(s, "overleaf-me", {"me": [mirror.PERSON[1]]})["result"] == {"me": [mirror.PERSON[1]]}
    assert published(root)["ask_me"] is False


@case("overleaf-unpair")
def _overleaf_unpair(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit import _mirror as mirror

    root, _ = mirror.paired(tmp_path)
    s = serve(root)
    assert succeeds(s, "overleaf-unpair", {})["result"] == {"paired": False}
    assert (root / "drafting/main.tex").read_text() == mirror.SOURCE
    assert not (root / ".loom/records/source-sync.json").exists() and not (root / ".loom/local/overleaf").exists()
    assert published(root) == {"paired": False}
    refuses(s, "overleaf-unpair", {}, 409, "not-paired", "mirrors no Overleaf project")


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
