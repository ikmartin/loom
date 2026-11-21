"""What the independent review of the door's sixth step found, each held by a test: commands made of several writes are one act, a move keeps the file's mode and decides again under the lock, and a refusal names the person's file in words they can act on."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from tests.helpers import ok, refused
from tests.unit._quilts import demo

AGENT_MARKERS = ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX", "CURSOR_AGENT", "GEMINI_CLI")


@pytest.fixture
def q(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for marker in AGENT_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    return demo(tmp_path)


def begun(root: Path, kind: str) -> list[dict]:
    p = root / ".loom/local/writes.jsonl"
    lines = [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []
    return [e for e in lines if e["event"] == "begin" and e["kind"] == kind]


def history_lines(act: dict) -> list[str]:
    """The history's actions an act's journal line carries as its own records."""
    return [json.loads(r["line"])["action"] for r in act.get("records") or [] if r["log"].endswith("ledger.jsonl")]


# ---- D-8: one act, not two ------------------------------------------------------------------------------------


def test_a_restore_to_a_new_file_is_one_act_with_its_history_line(q: Path) -> None:
    ok("history", "restore", "widgets-v1", "--to", "drafting/restored.tex", cwd=q)
    (act,) = begun(q, "restore-to")
    assert "drafting/restored.tex" in act["files"] and history_lines(act) == ["restore"]


def test_a_flat_copy_is_one_act_with_its_history_line(q: Path) -> None:
    ok("linearize", "drafting/main.tex", "--to", "drafting/flat.tex", "--no-check", "--keep-shared", cwd=q)
    (act,) = begun(q, "linearize")
    assert "drafting/flat.tex" in act["files"] and history_lines(act) == ["linearize"]


def test_atomize_writes_its_files_retires_its_source_and_records_it_in_one_act(q: Path) -> None:
    ok("atomize", "drafting/main.tex", "--to", "drafting/spine.tex", "--retire", cwd=q)
    (act,) = begun(q, "atomize")
    files = set(act["files"])
    assert {"drafting/spine.tex", "drafting/main.tex", ".loom/records/retired/drafting/main.tex"} <= files
    assert history_lines(act) == ["atomize"]


def test_a_fork_is_one_act_with_its_node_file_and_history_line(q: Path) -> None:
    main = (q / "drafting/main.tex").read_text()
    (q / "drafting/talk.tex").write_text(
        main[: main.index("\\begin{document}")] + "\\begin{document}\n\\input{nodes/dm-0001}\n\\end{document}\n"
    )
    ok("fork", "dm-0001", "--in", "drafting/talk.tex", cwd=q)
    (act,) = begun(q, "fork")
    assert any(f.startswith("drafting/nodes/") for f in act["files"]) and history_lines(act) == ["fork"]


def test_an_import_writes_its_assets_its_draft_and_its_step_in_one_act(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_paper import paper_dir

    for marker in AGENT_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    p = paper_dir(tmp_path)
    ok(
        "init",
        str(tmp_path / "q"),
        "--from",
        str(p / "main.tex"),
        "--prefix",
        "pp",
        "--ai",
        "none",
        "--yes",
        cwd=tmp_path,
    )
    (act,) = begun(tmp_path / "q", "import")
    assert "main/main.tex" in act["files"] and "main/figures/fig.pdf" in act["files"]
    assert history_lines(act) == ["import"]


# ---- D-6 and D-14: a move ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", [0o600, 0o664])
def test_a_move_keeps_the_document_s_mode(q: Path, mode: int) -> None:
    os.chmod(q / "drafting/main.tex", mode)
    ok("mv", "drafting/main.tex", "drafting/paper.tex", cwd=q)
    assert stat.S_IMODE((q / "drafting/paper.tex").stat().st_mode) == mode


def test_a_move_decides_again_under_the_lock(tmp_path: Path) -> None:
    """A file put at the new path, or the old one taken away, after the command looked and before the act: refused, nothing moved (D-14)."""
    from loom import writes
    from loom.scan.quilt import load_quilt

    root = demo(tmp_path)
    quilt = load_quilt(root)
    (root / "drafting/paper.tex").write_text("someone's file\n")
    with pytest.raises(writes.WriteRefused, match="exists already"):
        with writes.act(root, quilt.history_dir, "mv") as w:
            w.move("drafting/main.tex", "drafting/paper.tex")
    assert (root / "drafting/paper.tex").read_text() == "someone's file\n" and (root / "drafting/main.tex").is_file()
    with pytest.raises(writes.WriteRefused, match="not there any more"):
        with writes.act(root, quilt.history_dir, "mv") as w:
            w.move("drafting/gone.tex", "drafting/other.tex")
    assert not (root / "drafting/other.tex").exists()


def test_a_restore_to_a_file_put_there_since_it_looked_is_refused(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The person saves a file at the path after the command looked and before its act: refused under the lock, theirs kept (D-14)."""
    from loom import writes

    real = writes.act
    done: list[bool] = []

    def act(*a: object, **k: object):  # type: ignore[no-untyped-def]
        if not done:
            done.append(True)
            (q / "drafting/restored.tex").write_text("the person's\n")
        return real(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(writes, "act", act)
    refused("history", "restore", "widgets-v1", "--to", "drafting/restored.tex", cwd=q, code=1, match="exists already")
    assert (q / "drafting/restored.tex").read_text() == "the person's\n"


# ---- D-13: refusals a person can act on ------------------------------------------------------------------------


def test_a_read_only_file_is_refused_by_name(tmp_path: Path) -> None:
    from loom import writes
    from loom.scan.quilt import load_quilt

    root = demo(tmp_path)
    doc = root / "drafting/main.tex"
    os.chmod(doc, 0o444)
    try:
        with pytest.raises(writes.WriteRefused, match="drafting/main.tex is read-only"):
            writes.put(root, load_quilt(root).history_dir, "drafting/main.tex", b"x\n", kind="settings")
    finally:
        os.chmod(doc, 0o644)


def test_a_folder_that_lets_no_file_be_made_is_refused_by_the_file_s_name(tmp_path: Path) -> None:
    from loom import writes
    from loom.scan.quilt import load_quilt

    root = demo(tmp_path)
    folder = root / "drafting"
    os.chmod(folder, 0o555)
    try:
        with pytest.raises(writes.WriteRefused) as refusal:
            writes.put(root, load_quilt(root).history_dir, "drafting/main.tex", b"x\n", kind="settings")
    finally:
        os.chmod(folder, 0o755)
    assert "drafting/main.tex" in str(refusal.value) and "loom-tmp" not in str(refusal.value)


# ---- D-12: an act cut short through a link out of the quilt ----------------------------------------------------


def test_an_act_left_on_a_link_out_of_the_quilt_names_the_file_and_claims_nothing_untouched(tmp_path: Path) -> None:
    from loom import writes
    from loom.scan.quilt import load_quilt

    root = demo(tmp_path)
    outside = tmp_path / "outside.tex"
    outside.write_text("the outside file\n")
    doc = root / "drafting/main.tex"
    doc.unlink()
    doc.symlink_to(outside)
    hist = load_quilt(root).history_dir
    a, b = writes.store(hist, b"before\n"), writes.store(hist, b"after\n")
    journal = root / ".loom/local/writes.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    line = {"event": "begin", "act": "keep:0123456789abcdef", "kind": "keep", "actor": "Pat", "when": "x"}
    journal.write_text(json.dumps({**line, "files": {"drafting/main.tex": [a, b]}, "records": []}) + "\n")
    ((kind, files, why, _kept),) = writes.left(root, hist)
    assert "drafting/main.tex" in why and "a link to a file outside the quilt" in why
    said = json.loads(ok("lint", "--json", cwd=root).stdout)["diagnostics"]
    (left,) = [d for d in said if d["code"] == "loom:write-left"]
    assert "drafting/main.tex" in left["message"] and "No file of yours was touched" not in left["message"]
