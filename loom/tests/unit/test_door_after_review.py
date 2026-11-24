"""What the independent review of the door's sixth step found, each held by a test: commands made of several writes are one act, a move keeps the file's mode and decides again under the lock, and a refusal names the person's file in words they can act on."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from tests.helpers import ok, refused
from tests.unit._quilts import demo


@pytest.fixture
def q(tmp_path: Path) -> Path:
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


# ---- D-4: what the history's store holds ----------------------------------------------------------------------


def test_an_imported_figure_is_journalled_by_its_digest_and_not_kept_in_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom import writes
    from tests.unit.test_paper import paper_dir

    p = paper_dir(tmp_path)
    figure = b"%PDF-1.4\n\xff\xfe" + bytes(range(256)) * 64
    (p / "figures" / "fig.pdf").write_bytes(figure)
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
    q = tmp_path / "q"
    (act,) = begun(q, "import")
    assert act["files"]["main/figures/fig.pdf"] == [None, writes.digest(figure)]
    hexd = writes.digest(figure).split(":", 1)[1]  # type: ignore[union-attr]
    assert not list((q / ".loom/records/history/texts").glob(f"{hexd}.*"))


def test_an_act_cut_short_after_making_a_binary_file_is_undone_by_its_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    root = demo(tmp_path)
    hist = load_quilt(root).history_dir
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        with writes.act(root, hist, "pdf-save") as w:
            w.replace("drafting/fig.bin", b"\xff\x00binary")
            w.replace("drafting/notes.md", b"# Notes\n")
    restore()
    assert (root / "drafting/fig.bin").is_file()
    said = writes.recover(root, hist)
    assert said and said[0].startswith("undid pdf-save:")
    assert not (root / "drafting/fig.bin").exists() and not (root / "drafting/notes.md").exists()


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


# ---- R-1: a later act over a left one ---------------------------------------------------------------------------


def test_a_left_act_whose_files_a_later_act_wrote_is_left_and_the_later_act_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An import cut short after one of its files, that file changed by the person, the import run again: the next recovery would see the first act's files holding its bytes, which are the second's, and put it back over the second. It leaves it (R-1)."""
    from loom import writes
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt
    from tests.helpers import run
    from tests.unit.test_paper import bare_quilt, paper_dir
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    p = paper_dir(tmp_path)
    q = bare_quilt(tmp_path)
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        run("import", str(p / "main.tex"), "--yes", "--no-check", cwd=q)
    restore()
    written = q / "main/refs.bib"  # the file the act wrote before it was cut short
    assert written.is_file()
    written.write_bytes(b"% the person's own bibliography\n")
    monkeypatch.setenv(
        "LOOM_FIXED_TIME", "2026-11-22T09:00:00Z"
    )  # a later moment, so its history line is not the first's
    ok("import", str(p / "main.tex"), "--yes", "--no-check", cwd=q)
    hist = load_quilt(q).history_dir
    said = writes.recover(q, hist)
    assert said and said[0].startswith("left import:") and "a later act wrote" in said[0]
    assert (q / "main/main.tex").is_file() and (q / "main/figures/fig.pdf").is_file() and written.is_file()
    h = load_history(hist)
    assert all((hist / e.dir).is_dir() for e in h.entries if e.dir)


# ---- R-8: a later act itself cut short --------------------------------------------------------------------------

#: The file-system calls a kill can fall before or after, as the review's kill harness counts them.
STEPS = ("replace", "rename", "unlink", "remove", "rmdir", "fsync", "mkdir", "chmod")


def dying_at_step(mp: pytest.MonkeyPatch, root: Path, k: int) -> list[int]:
    """Make the process die at the `k`-th file-system step it takes holding `root`'s door lock, just before or just after a call of `STEPS` or a full flush (0: never); returns the count, which a run that never dies reads for its number of steps."""
    import fcntl

    from loom.locks import holding
    from loom.paths import WRITES_LOCK
    from tests.unit.test_write_safety import Died

    lock = root / WRITES_LOCK
    count = [0]

    def point() -> None:
        if holding(lock):
            count[0] += 1
            if count[0] == k:
                raise Died

    def wrapped(real):  # type: ignore[no-untyped-def]
        def call(*a, **kw):  # type: ignore[no-untyped-def]
            point()
            out = real(*a, **kw)
            point()
            return out

        return call

    for name in STEPS:
        mp.setattr(os, name, wrapped(getattr(os, name)))
    real_fcntl = fcntl.fcntl
    full = getattr(fcntl, "F_FULLFSYNC", None)
    mp.setattr(fcntl, "fcntl", lambda fd, cmd, *a: (wrapped(real_fcntl) if cmd == full else real_fcntl)(fd, cmd, *a))
    return count


def test_a_left_act_is_never_put_back_over_a_later_act_cut_short_at_any_of_its_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-1's sequence with the second import itself killed, at each step it takes holding the door: recovery finishes the second act, puts it back or leaves it, and never puts the left act back over a file the second wrote; the history names only folders that stand, and the draft is there exactly when the history says the paper came in (R-8)."""
    import shutil

    from loom import writes
    from loom.history.ledger import load_history
    from tests.helpers import run
    from tests.unit.test_paper import bare_quilt, paper_dir
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    p = paper_dir(tmp_path)
    base = bare_quilt(tmp_path)
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        run("import", str(p / "main.tex"), "--yes", "--no-check", cwd=base)
    restore()
    (base / "main/refs.bib").write_bytes(b"% the person's own bibliography\n")
    (first,) = begun(base, "import")
    # a later moment, so the second import's history line is not the first's
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-22T09:00:00Z")

    def second(k: int) -> Path:
        q = tmp_path / f"at-{k}"
        shutil.copytree(base, q, symlinks=True)
        with pytest.MonkeyPatch.context() as mp:
            count = dying_at_step(mp, q, k)
            try:
                run("import", str(p / "main.tex"), "--yes", "--no-check", cwd=q)
            except Died:
                pass
        assert k or count[0] > 20, count  # the whole import, counted
        steps.append(count[0])
        return q

    steps: list[int] = []
    second(0)
    for k in range(1, steps[0] + 1):
        q = second(k)
        later = [e for e in begun(q, "import") if e["act"] != first["act"]]
        files = later[0]["files"] if later else {}
        held = {rel: (q / rel).read_bytes() if (q / rel).is_file() else None for rel in files}
        hist = q / ".loom/records/history"
        said = writes.recover(q, hist)
        assert not any(s.startswith(f"undid {first['act']}") for s in said), (k, said)
        events = {e["event"] for e in writes_lines(q) if later and e["act"] == later[0]["act"]}
        for rel, (before, after) in files.items():
            if "done" in events:
                assert writes._holds(q, rel, after), (k, rel, said)
            elif "aborted" in events:
                assert not (q / rel).exists() if before is None else writes._holds(q, rel, before), (k, rel, said)
            else:
                assert ((q / rel).read_bytes() if (q / rel).is_file() else None) == held[rel], (k, rel, said)
        h = load_history(hist)
        assert all((hist / e.dir).is_dir() for e in h.entries if e.dir), (k, said)
        assert any(e.action == "import" for e in h.entries) == (q / "main/main.tex").is_file(), (k, said)
        shutil.rmtree(q)


def writes_lines(root: Path) -> list[dict]:
    p = root / ".loom/local/writes.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []


# ---- a file only this machine reads ------------------------------------------------------------------------------


def test_an_agent_app_s_mcp_file_keeps_its_texts_on_this_machine_and_none_in_the_history(tmp_path: Path) -> None:
    """An MCP file names this machine's loom and the quilt's absolute path: its texts stay beside the journal, so the committed history carries no machine's paths, and a quilt made twice, as the generated quilts are, is the same."""
    from loom import writes
    from loom.ai.clients import PROJECT_FILES

    root = tmp_path / "q"
    ok("init", str(root), "--prefix", "pp", "--ai", "none", "--yes", cwd=tmp_path)
    ok("ai", "init", cwd=root)  # through the door, as the generator writes them
    written = [rel for rel in PROJECT_FILES if (root / rel).is_file()]
    assert len(written) == len(PROJECT_FILES), written
    hist, here = root / ".loom/records/history", root / ".loom/local"
    for rel in written:
        d = writes.digest((root / rel).read_bytes())
        assert d is not None and writes.fetch(hist, d) is None and writes.fetch(here, d) is not None, rel
    places = {str(root), os.path.realpath(root)}
    named = [p.name for p in (hist / "texts").iterdir() if any(x in p.read_text(errors="replace") for x in places)]
    assert named == []


def test_an_act_cut_short_on_an_mcp_file_is_put_back_from_this_machine_s_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Recovery reads the texts kept beside the journal as it reads the history's, so an MCP file an act replaced comes back whole."""
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    root = tmp_path / "q"
    ok("init", str(root), "--prefix", "pp", "--ai", "claude", "--yes", cwd=tmp_path)
    before = (root / ".mcp.json").read_bytes()
    hist = load_quilt(root).history_dir
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        with writes.act(root, hist, "agents") as w:
            w.replace(".mcp.json", before.replace(b"loom", b"loom-elsewhere", 1))
            w.replace("notes.md", b"# Notes\n")
    restore()
    assert (root / ".mcp.json").read_bytes() != before
    said = writes.recover(root, hist)
    assert said and said[0].startswith("undid agents:"), said
    assert (root / ".mcp.json").read_bytes() == before


# ---- R-3 and R-4 ------------------------------------------------------------------------------------------------


def test_a_left_act_whose_made_file_was_changed_says_removing_it_settles_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file the act made needs no text to be undone, so the advice is not that the history lacks one (R-3)."""
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    root = demo(tmp_path)
    hist = load_quilt(root).history_dir
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        with writes.act(root, hist, "pdf-save") as w:
            w.replace("drafting/fig.bin", b"\xff\x00binary")
            w.replace("drafting/notes.md", b"# Notes\n")
    restore()
    made = next(rel for rel in ("drafting/fig.bin", "drafting/notes.md") if (root / rel).is_file())
    (root / made).write_bytes(b"the person's own\n")
    ((_, _, _, settles),) = writes.left(root, hist)
    assert f"For {made}, which the act made, removing it does that" in settles
    assert "texts the history lacks" not in settles
    (root / made).unlink()
    assert writes.recover(root, hist)[0].startswith("undid pdf-save:")


def test_a_skill_saved_while_loom_waited_is_never_written_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The skill writer passes what it read, as every other writer of the agent layer does (R-4)."""
    from loom import writes
    from loom.ai.clients import chosen
    from loom.ai.skills import write_skills

    root = tmp_path / "q"
    ok("init", str(root), "--prefix", "pp", "--ai", "claude", "--yes", cwd=tmp_path)
    skill = next(p for p in root.rglob("SKILL.md") if ".claude" in p.parts)
    rel = skill.relative_to(root).as_posix()
    skill.unlink()  # gone, so the next write makes it again
    real = writes.act
    done: list[bool] = []

    def act(*a: object, **k: object):  # type: ignore[no-untyped-def]
        if not done:
            done.append(True)
            skill.write_text("the person's own skill\n")
        return real(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(writes, "act", act)
    with pytest.raises(writes.WriteRefused, match="changed since loom read it"):
        write_skills(root, chosen(root, None))
    assert skill.read_text() == "the person's own skill\n", rel


def test_an_import_put_back_leaves_no_empty_folder_it_made(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The folders an act makes are in its journal line, and putting it back takes away those it leaves empty (R-5); a folder of the person's stays."""
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.helpers import run
    from tests.unit.test_paper import bare_quilt, paper_dir
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    p = paper_dir(tmp_path)
    q = bare_quilt(tmp_path)
    (q / "notes").mkdir()  # the person's own empty folder
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        run("import", str(p / "main.tex"), "--yes", "--no-check", cwd=q)
    restore()
    assert (q / "main").is_dir()
    said = writes.recover(q, load_quilt(q).history_dir)
    assert said and said[0].startswith("undid import:")
    assert not (q / "main").exists() and (q / "notes").is_dir()


# ---- R2-6: the person's acts that put their own words into the look, cut short at any step ----------------------


def _rows(root: Path) -> list[tuple[str, str]]:
    """The in-place changes Your Changes lists, by path and new words."""
    from loom.pending import in_place
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    return sorted((p.path or "", p.new) for p in in_place(scan(load_quilt(root)), "Tester"))


@pytest.mark.parametrize("which", ["keep", "undo of a keep", "discard", "tick"])
def test_an_act_that_puts_its_words_into_the_look_cut_short_at_any_step_lists_as_before_or_after(
    tmp_path: Path, which: str
) -> None:
    """Keep, its undo, Discard and a tick, each killed at every step it takes holding the door, with an agent's new note waiting: after recovery Your Changes lists what it listed before the act or what the act leaves, never the act's own words as the person's edit (R2-6)."""
    import shutil

    from loom import tasks, writes
    from loom.looks import take
    from loom.pending import unkeep
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.helpers import run
    from tests.unit.test_adopt import TEXT, made
    from tests.unit.test_write_safety import Died

    base = tmp_path / "base"
    base.mkdir()
    made(base, TEXT)
    (base / "notes").mkdir()
    (base / "notes/tasks.md").write_text("# Tasks\n\n- [ ] first\n- [ ] second\n", encoding="utf-8")
    take(load_quilt(base), "Tester")
    ok("suggest", "zk-0002", "--quote", "Second statement uses", "--with", "The second statement uses", "--as", "Referee Agent", cwd=base, env={"AI_AGENT": "1"})  # fmt: skip
    (base / "notes/agent.md").write_text("an agent's note\n", encoding="utf-8")  # waits throughout
    listed = json.loads(run("changes", "--json", cwd=base).stdout)["changes"]
    (edit,) = [c["id"] for c in listed if c["kind"] == "suggested"]
    if which == "undo of a keep":
        ok("changes", "--keep", edit, cwd=base)
    if which == "discard":
        doc = base / "drafting/main.tex"
        doc.write_text(doc.read_text().replace("Original introduction.", "Original introduction, as an agent put it."))
        listed = json.loads(run("changes", "--json", cwd=base).stdout)["changes"]
    task = tasks.items((base / "notes/tasks.md").read_text())[0].id  # the box of "first"
    changed = [c["id"] for c in listed if c["kind"] == "edit" and c["path"] == "drafting/main.tex"]

    def act(root: Path) -> None:
        if which == "keep":
            run("changes", "--keep", edit, cwd=root)
        elif which == "undo of a keep":
            unkeep(scan(load_quilt(root)), "Tester", [edit], ("human", "Tester"))
        elif which == "discard":
            run("changes", "--discard", *changed, cwd=root)
        else:
            tasks.tick(load_quilt(root), "Tester", "notes/tasks.md", task, True)

    before = _rows(base)
    whole = tmp_path / "whole"
    shutil.copytree(base, whole)
    with pytest.MonkeyPatch.context() as mp:
        count = dying_at_step(mp, whole, 0)
        act(whole)
    after = _rows(whole)
    assert count[0] > 5 and ("notes/agent.md", "an agent's note") in after, (count, after)
    for k in range(1, count[0] + 1):
        q = tmp_path / f"at-{k}"
        shutil.copytree(base, q)
        with pytest.MonkeyPatch.context() as mp:
            dying_at_step(mp, q, k)
            try:
                act(q)
            except Died:
                pass
        writes.recover(q, load_quilt(q).history_dir)
        assert _rows(q) in (before, after), (which, k, _rows(q))
        shutil.rmtree(q)


def test_a_keep_recovery_puts_back_opens_its_edit_again_and_takes_its_words_out_of_the_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Keep cut short after its records, its file then written back to its before bytes by the person's editor: recovery puts the act back, and the suggestion it kept is open again, with the look as before it, so the list is as before the Keep (the fourth look's remark on a put-back Keep's record)."""
    from loom import writes
    from loom.looks import take
    from loom.records.edits import find
    from loom.scan.quilt import load_quilt
    from tests.helpers import run
    from tests.unit.test_adopt import TEXT, made
    from tests.unit.test_write_safety import Died

    root = tmp_path / "q"
    root.mkdir()
    made(root, TEXT)
    take(load_quilt(root), "Tester")
    ok("suggest", "zk-0002", "--quote", "Second statement uses", "--with", "The second statement uses", "--as", "Referee Agent", cwd=root, env={"AI_AGENT": "1"})  # fmt: skip
    (edit,) = [c["id"] for c in json.loads(run("changes", "--json", cwd=root).stdout)["changes"]]
    rows = _rows(root)
    doc = root / "drafting/main.tex"
    was = doc.read_bytes()
    real = writes._append_journal

    def die(at: Path, entry: dict, *, full: bool = False) -> tuple[int, int]:
        if entry.get("event") == "done" and str(entry.get("act", "")).startswith("keep:"):
            raise Died
        return real(at, entry, full=full)

    monkeypatch.setattr(writes, "_append_journal", die)
    with pytest.raises(Died):
        run("changes", "--keep", edit, cwd=root)
    monkeypatch.undo()
    assert doc.read_bytes() != was and find(root, edit).status == "kept"  # type: ignore[union-attr]
    doc.write_bytes(was)  # the person's editor writes the file back before recovery runs
    said = writes.recover(root, load_quilt(root).history_dir)
    assert said and said[0].startswith("undid keep:"), said
    assert find(root, edit).status == "open"  # type: ignore[union-attr]
    assert [c["id"] for c in json.loads(run("changes", "--json", cwd=root).stdout)["changes"]] == [edit]
    assert _rows(root) == rows


def test_keep_all_cut_short_at_any_step_keeps_an_in_place_change_with_its_keep_line_or_not_at_all(
    tmp_path: Path,
) -> None:
    """Keep-all, killed at every step it takes holding the door with an agent's new note and a suggestion waiting: the note's change goes into the look in the act's follow-up and its keep line with the act, so after recovery the list is as before or after, and the note is listed exactly when no keep line names it (R2-18)."""
    import shutil

    from loom import writes
    from loom.history.ledger import load_history
    from loom.looks import take
    from loom.scan.quilt import load_quilt
    from tests.helpers import run
    from tests.unit.test_adopt import TEXT, made
    from tests.unit.test_write_safety import Died

    base = tmp_path / "base"
    base.mkdir()
    made(base, TEXT)
    take(load_quilt(base), "Tester")
    ok("suggest", "zk-0002", "--quote", "Second statement uses", "--with", "The second statement uses", "--as", "Referee Agent", cwd=base, env={"AI_AGENT": "1"})  # fmt: skip
    (base / "notes").mkdir()
    (base / "notes/agent.md").write_text("an agent's note\n", encoding="utf-8")
    note = ("notes/agent.md", "an agent's note")

    def kept_line(root: Path) -> bool:
        hist = load_quilt(root).history_dir
        return any(e.action == "keep" and e.data.get("path") == note[0] for e in load_history(hist).entries)

    before = _rows(base)
    whole = tmp_path / "whole"
    shutil.copytree(base, whole)
    with pytest.MonkeyPatch.context() as mp:
        count = dying_at_step(mp, whole, 0)
        run("changes", "--keep-all", cwd=whole)
    after = _rows(whole)
    assert note in before and note not in after and kept_line(whole) and count[0] > 5, (before, after, count)
    for k in range(1, count[0] + 1):
        q = tmp_path / f"at-{k}"
        shutil.copytree(base, q)
        with pytest.MonkeyPatch.context() as mp:
            dying_at_step(mp, q, k)
            try:
                run("changes", "--keep-all", cwd=q)
            except Died:
                pass
        writes.recover(q, load_quilt(q).history_dir)
        rows = _rows(q)
        assert rows in (before, after), (k, rows)
        assert (note in rows) is not kept_line(q), (k, rows, kept_line(q))
        shutil.rmtree(q)


# ---- R2-20: two acts on one file's in-place changes, each listed before the other ran --------------------------

#: The agent's two in-place changes in one file: an early one that lengthens the statement, and a later one in its proof.
EARLY = ("Let $(X,\\sigma)$ be a widget.", "Let $(X,\\sigma)$ be a finite widget, with its involution given.")
LATE = ("\\incomplete{Not yet attempted.", "\\incomplete{Not attempted yet.")


@pytest.mark.parametrize("pair", ["keep, keep", "accept, accept", "keep all, keep", "discard, keep"])
@pytest.mark.parametrize("first", ["early", "late"])
def test_two_acts_on_one_file_listed_before_each_other_leave_it_as_a_person_could_have_chosen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pair: str, first: str
) -> None:
    """Two acts on in-place changes of one file at once, as two quick clicks make them: the second lists its changes, then waits at the door while the first runs. Each cuts its changes again under the door, so neither splices at a stale offset: no change is listed after them that no one made, and once what is left is discarded the file is byte for byte one a person could have chosen (R2-20)."""
    import threading

    from loom import writes
    from loom.locks import locked
    from loom.looks import take
    from loom.paths import WRITES_LOCK
    from loom.pending import PendingRefused, discard, in_place, keep, keep_accepted
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.unit._quilts import demo, opened

    q = opened(demo(tmp_path))
    take(load_quilt(q), "Tester")
    node = q / "drafting/nodes/dm-0006.tex"
    base = node.read_text(encoding="utf-8")
    node.write_text(base.replace(*EARLY).replace(*LATE), encoding="utf-8")
    outcomes = {base, base.replace(*EARLY), base.replace(*LATE), base.replace(*EARLY).replace(*LATE)}
    who, writer = "Tester", ("human", "Tester")

    def listed() -> list:  # type: ignore[type-arg]
        return sorted(
            (p for p in in_place(scan(load_quilt(q)), who) if p.path == "drafting/nodes/dm-0006.tex"),
            key=lambda p: p.at,
        )

    rows = listed()
    assert len(rows) == 2, rows
    ids = {"early": rows[0].id, "late": rows[1].id}
    second = "late" if first == "early" else "early"

    def run_act(which: str) -> None:
        r = scan(load_quilt(q))
        if pair == "accept, accept":
            keep_accepted(r, who, ["dm-0006" if which == "early" else "dm-0006/proof"])
        elif pair == "discard, keep" and which == first:
            discard(r, who, [ids[which]], writer)
        elif pair == "keep all, keep" and which == first:
            keep(r, who, list(ids.values()), writer)
        else:
            keep(r, who, [ids[which]], writer)

    real = writes.act
    at_door = threading.Event()

    def act(*a, **k):  # type: ignore[no-untyped-def]
        if threading.current_thread() is not threading.main_thread():
            at_door.set()
        return real(*a, **k)

    monkeypatch.setattr(writes, "act", act)
    failed: list[BaseException] = []

    def later() -> None:
        try:
            run_act(second)
        except PendingRefused:
            pass  # refused, which is no damage
        except BaseException as exc:  # noqa: BLE001
            failed.append(exc)

    thread = threading.Thread(target=later)
    with locked(q / WRITES_LOCK):
        thread.start()
        assert at_door.wait(30), "the second act never reached the door"
        run_act(first)
    thread.join(60)
    assert not failed, failed
    monkeypatch.setattr(writes, "act", real)
    words = {(p.old, p.new) for p in rows}
    left = listed()
    assert {(p.old, p.new) for p in left} <= words, [(p.old, p.new) for p in left]
    if left:
        discard(scan(load_quilt(q)), who, [p.id for p in left], writer)
    assert node.read_text(encoding="utf-8") in outcomes


@pytest.mark.parametrize("which", ["a keep of one in-place change", "the viewer's accept"])
def test_an_act_with_a_look_and_no_file_cut_short_at_any_step_is_finished_or_put_back(
    tmp_path: Path, which: str
) -> None:
    """A Keep of in-place changes alone, and the viewer's Accept that keeps them, write no file, only the look and their keep lines; killed at every step they take holding the door, recovery finishes or puts back each, never leaves it, so the list is as before or after, the change is listed exactly when no keep line names it, and nothing is left to settle (R2-19)."""
    import shutil

    from loom import writes
    from loom.history.ledger import load_history
    from loom.looks import take
    from loom.pending import keep_accepted
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.helpers import run
    from tests.unit.test_adopt import DOC, TEXT, made
    from tests.unit.test_write_safety import Died

    base = tmp_path / "base"
    base.mkdir()
    made(base, TEXT)
    take(load_quilt(base), "Tester")
    doc = base / DOC
    doc.write_text(doc.read_text().replace("First statement.", "First statement, as an agent put it."))
    (change,) = [
        c["id"] for c in json.loads(run("changes", "--json", cwd=base).stdout)["changes"] if c["kind"] == "edit"
    ]

    def act(root: Path) -> None:
        if which == "the viewer's accept":
            keep_accepted(scan(load_quilt(root)), "Tester", ["zk-0001"])
        else:
            run("changes", "--keep", change, cwd=root)

    def kept_line(root: Path) -> bool:
        return any(e.action == "keep" and e.data.get("path") == DOC for e in load_history(load_quilt(root).history_dir).entries)  # fmt: skip

    def listed(root: Path) -> bool:
        return any(path == DOC for path, _ in _rows(root))

    whole = tmp_path / "whole"
    shutil.copytree(base, whole)
    with pytest.MonkeyPatch.context() as mp:
        count = dying_at_step(mp, whole, 0)
        act(whole)
    assert listed(base) and not listed(whole) and kept_line(whole) and count[0] > 5, count
    for k in range(1, count[0] + 1):
        q = tmp_path / f"at-{k}"
        shutil.copytree(base, q)
        with pytest.MonkeyPatch.context() as mp:
            dying_at_step(mp, q, k)
            try:
                act(q)
            except Died:
                pass
        hist = load_quilt(q).history_dir
        writes.recover(q, hist)
        assert writes.left(q, hist) == [], (k, writes.left(q, hist))
        assert listed(q) is not kept_line(q), (k, listed(q), kept_line(q))
        assert writes.recover(q, hist) == [], k
        shutil.rmtree(q)


# ---- R2-21: a journal line's look is checked as its files are -------------------------------------------------

#: The act a forged line names, as the review's did.
FORGED = "keep:f0f0f0f0f0f0f0f0"


def _forge(root: Path, look: dict, keeps: tuple[str, ...] = (), by: str = "person") -> None:
    """Append a `begin` line that names no file and carries `look`, with a `keep` line of `who`'s for each path of `keeps`: what a hand, an agent's shell or a copied quilt could leave in the journal."""
    from loom import writes
    from loom.history.acts import KEEP, ledger_line
    from loom.paths import JOURNAL
    from loom.scan.quilt import load_quilt

    hist = load_quilt(root).history_dir
    records = []
    for path in keeps:
        log, line = ledger_line(
            hist, KEEP, {"who": look.get("who"), "path": path, "changes": ["c-00000000"]}, look.get("who")
        )
        records.append({"log": writes._log_name(root, log), "line": line})
    line = {"event": "begin", "act": FORGED, "kind": "keep", "actor": "Tester", "by": by, "when": "2026-11-22T00:00:00Z", "files": {}, "edits": [], "records": records, "look": look}  # fmt: skip
    with (root / JOURNAL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line) + "\n")


#: Each forged look, the `keep` lines its line carries, and the words recovery leaves it with.
FORGERIES = {
    "an agent's waiting change taken in with no keep line": (lambda h: {"looked": {"drafting/main.tex": h}}, (), "no keep line of the act names"),
    "a path outside the quilt": (lambda h: {"looked": {"../outside.txt": h}}, ("../outside.txt",), "not a file in the quilt"),
    "a hash the store does not hold": (lambda h: {"looked": {"drafting/main.tex": "sha256:" + "0" * 64}}, ("drafting/main.tex",), "a text the history does not hold"),
    "a hash that is not a hash": (lambda h: {"looked": {"drafting/main.tex": "not a hash"}}, ("drafting/main.tex",), "a text the history does not hold"),
    "a file it drops that is there": (lambda h: {"looked": {"drafting/main.tex": None}}, ("drafting/main.tex",), "drops drafting/main.tex, which is there"),
    "a file agents are denied": (lambda h: {"looked": {"config.toml": h}}, ("config.toml",), "in a place agents are denied"),
    "places in a file the act does not write": (lambda h: {"spans": {"drafting/main.tex": [[0, 10**6]]}}, (), "a file the act does not write"),
    "a tick in a file the act does not write": (lambda h: {"tick": {"path": "drafting/main.tex", "line": 0}}, (), "tick is not a line of a file the act writes"),
}  # fmt: skip


@pytest.mark.parametrize("which", [*FORGERIES, "another reviewer's look", "an agent's act", "a look that is a list"])
def test_a_journal_line_whose_look_recovery_may_not_write_is_left_and_said_and_takes_nothing_in(
    tmp_path: Path, which: str
) -> None:
    """A `begin` line that names no file and carries a look is checked as a line's files are: recovery writes it only when it is the reviewer's, from a person's act, each path it takes in a watched file in the quilt that a keep line of the act names, and each text one the store holds. Otherwise the line is left and said, the look stays as it was, and the list with it: the review's forged lines took an agent's waiting change in unseen, put `../outside.txt` into Review, and listed the whole of `main.tex` for a Discard that emptied it (R2-21)."""
    from loom import writes
    from loom.looks import look_path, take
    from loom.records.snapshots import write_raw
    from loom.scan.quilt import load_quilt
    from tests.helpers import run
    from tests.unit.test_adopt import DOC, TEXT, made

    root = tmp_path / "q"
    root.mkdir()
    made(root, TEXT)
    (tmp_path / "outside.txt").write_text("a file of the person's outside the quilt\n")
    take(load_quilt(root), "Tester")
    doc = root / DOC
    doc.write_text(doc.read_text().replace("First statement.", "First statement, as an agent put it."))
    hist = load_quilt(root).history_dir
    stored = write_raw(root, doc.read_text(), hist)
    if which == "another reviewer's look":
        _forge(root, {"who": "Somebody Else", "looked": {DOC: stored}}, (DOC,))
        why = "its look is not the reviewer's"
    elif which == "an agent's act":
        _forge(root, {"who": "Tester", "looked": {DOC: stored}}, (DOC,), by="agent")
        why = "an agent's act, which writes no look"
    elif which == "a look that is a list":
        _forge(root, [DOC, stored])  # type: ignore[arg-type]
        why = "its look is not a look"
    else:
        make, keeps, why = FORGERIES[which]
        _forge(root, {"who": "Tester", **make(stored)}, keeps)

    def listed() -> list[tuple[str, str]]:
        return sorted((c["path"], c["id"]) for c in json.loads(run("changes", "--json", cwd=root).stdout)["changes"])

    look = look_path(root, "Tester").read_bytes()
    rows = _rows(root)
    said = writes.recover(root, hist)
    assert all(not path.startswith("..") for path, _ in listed())
    assert _rows(root) == rows and any(path == DOC for path, _ in rows)
    assert look_path(root, "Tester").read_bytes() == look
    assert len(said) == 1 and said[0].startswith(f"left {FORGED}: ") and why in said[0], said
    assert said[0].endswith("recovery changed nothing"), said
    assert len(writes.left(root, hist)) == 1


def test_a_line_whose_look_passes_every_check_takes_in_only_what_its_keep_lines_name(tmp_path: Path) -> None:
    """The check leaves an honest act's line alone: a look of the reviewer's, on a watched file, with a stored text and the keep line naming it, is written as the act's follow-up would have written it, and the change it takes in is named in the history by that keep line."""
    from loom import writes
    from loom.history.ledger import load_history
    from loom.looks import read_look, take
    from loom.records.snapshots import write_raw
    from loom.scan.quilt import load_quilt
    from tests.unit.test_adopt import DOC, TEXT, made

    root = tmp_path / "q"
    root.mkdir()
    made(root, TEXT)
    take(load_quilt(root), "Tester")
    doc = root / DOC
    doc.write_text(doc.read_text().replace("First statement.", "First statement, as an agent put it."))
    hist = load_quilt(root).history_dir
    stored = write_raw(root, doc.read_text(), hist)
    _forge(root, {"who": "Tester", "looked": {DOC: stored}}, (DOC,))
    assert writes.recover(root, hist) == [f"finished {FORGED}"]
    assert read_look(root, "Tester").files[DOC] == stored  # type: ignore[union-attr]
    assert [e.data.get("path") for e in load_history(hist).entries if e.action == "keep"] == [DOC]
    assert not any(path == DOC for path, _ in _rows(root))


def test_the_journal_is_denied_to_agents_by_the_rule_that_denies_them_the_records_and_the_look(tmp_path: Path) -> None:
    """What keeps an agent from writing a journal line is the rule that keeps it from the records and the look: all sit in `.loom/`, which `agents.denied_by` denies an agent, and the permission file loom writes for Claude Code refuses its file tools each of their folders. That file refuses no shell command but `rm`, so an agent's shell is refused none of them, and another app is only told."""
    from loom.agents import claude_denies, denied_by
    from loom.paths import EDIT_LOG, JOURNAL, JOURNAL_INDEX, LOCAL, LOOKED
    from loom.scan.quilt import load_quilt

    q = demo(tmp_path)
    config = load_quilt(q).config
    ledger = f"{config.history}/ledger.jsonl"
    look = f"{LOOKED}/tester.json"
    assert {denied_by(config, rel) for rel in (JOURNAL, JOURNAL_INDEX, look, EDIT_LOG, ledger)} == {".loom/"}
    for folder in (LOCAL, LOOKED, os.path.dirname(EDIT_LOG), config.history):
        assert f"/{folder}/**" in claude_denies(config), folder
    deny = json.loads((q / ".claude/settings.json").read_text())["permissions"]["deny"]
    assert {f"Edit(/{LOCAL}/**)", f"Edit(/{LOOKED}/**)"} <= set(deny)
    assert [r for r in deny if r.startswith("Bash(") and not r.startswith("Bash(loom ")] == ["Bash(rm *)"]


def test_a_keep_that_kept_nothing_because_every_change_was_refused_exits_as_a_refusal(tmp_path: Path) -> None:
    """Every change a Keep names refused is a refusal, and the command exits 1 as one does, so a script reading the exit status never takes it for success; one kept beside one refused is a success that leaves work undone: exit 0, not ok."""
    from loom.scan.quilt import save_author
    from tests.helpers import json_of
    from tests.unit.records.test_edits import LEMMA, filed, suggest

    save_author("Tom")
    q = demo(tmp_path)
    old = filed(q, "dm-0002", "More.", "\\end{lemma}", "after")
    before = (q / LEMMA).read_text()
    r = refused("changes", "--keep", old, cwd=q, code=1, match="kept nothing")
    assert f"{old} not kept" in r.output and (q / LEMMA).read_text() == before
    good = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    data = json_of("changes", "--keep", old, "--keep", good, "--json", cwd=q)
    assert data["ok"] is False and data["exit"] == 0 and data["done"] == [good]
