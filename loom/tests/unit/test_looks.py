"""A person's look at the open files (plan 0.22.8): what the changes waiting on them are counted from, and keep and discard, the author's verbs on a change (`pending.py`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import json_of, ok, refused, run
from tests.unit._quilts import demo


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author("Tester")
    root = demo(tmp_path)
    (root / "notes").mkdir()
    (root / "notes" / "a.md").write_text("# A\n\nfirst\n", encoding="utf-8")
    (root / "notes" / "fig.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    return root


def changes(q: Path) -> dict[str, str]:
    """Each in-place change's path and new words: the demo's suggested edit aside."""
    return {c["path"]: c["new"] for c in json_of("changes", "--json", cwd=q)["changes"] if c["kind"] == "edit"}


def test_a_look_holds_every_open_text_file_and_nothing_else(q: Path) -> None:
    """Shown text files only, LaTeX included; an image, a hidden file and loom's own records are left out, and each text is kept by its hash."""
    from loom.looks import read_look
    from loom.records.snapshots import read_raw
    from loom.scan.quilt import load_quilt

    (q / ".hidden.md").write_text("no", encoding="utf-8")
    assert json_of("changes", "--json", cwd=q)["look"] is None
    assert ok("changes", "--keep-all", cwd=q).stdout.startswith("took your first look")
    look = read_look(q, "Tester")
    assert look is not None and look.who == "Tester"
    assert "notes/a.md" in look.files and "drafting/main.tex" in look.files
    assert not [p for p in look.files if p.startswith(".") or p.endswith(".png")]
    assert read_raw(q, look.files["notes/a.md"], load_quilt(q).history_dir) == "# A\n\nfirst\n"
    assert (q / ".loom/records/looked/tester.json").is_file()
    assert changes(q) == {}


def test_changes_since_the_look_are_in_changed_new_and_gone_files_each_with_its_patch(q: Path) -> None:
    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    (q / "notes/b.md").write_text("new\n", encoding="utf-8")
    (q / "README.md").unlink()
    assert changes(q) == {"notes/a.md": "second", "notes/b.md": "new", "README.md": ""}
    run("build", cwd=q)
    m = json.loads((q / ".loom/cache/site/manifest.json").read_text())
    assert m["changes_since"]["who"] == "Tester"
    row = next(c for c in m["changes"] if c["path"] == "notes/a.md")
    assert (row["old"], row["new"], row["documents"]) == ("first", "second", [])
    patch = (q / ".loom/cache/site" / row["diff"]).read_text()
    assert patch.startswith("--- a/notes/a.md") and "-first" in patch and "+second" in patch


def test_keep_takes_a_change_into_the_look_and_discard_puts_its_old_words_back(q: Path) -> None:
    """P7: what a discard sets aside is kept in the history first, and the ledger names the change; a file gone since the look comes back, and one new since is removed."""
    from loom.history.ledger import load_history
    from loom.records.snapshots import read_raw
    from loom.scan.quilt import load_quilt

    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.md").write_text("# A\n\nan agent's edit\n", encoding="utf-8")
    (q / "README.md").unlink()
    (q / "notes/b.md").write_text("new\n", encoding="utf-8")
    ok("changes", "--discard", "notes/a.md", cwd=q)
    assert (q / "notes/a.md").read_text() == "# A\n\nfirst\n"
    ok("changes", "--discard", "README.md", cwd=q)
    assert (q / "README.md").is_file()
    ok("changes", "--discard", "notes/b.md", cwd=q)
    assert not (q / "notes/b.md").exists() and changes(q) == {}
    quilt = load_quilt(q)
    undone = [e for e in load_history(quilt.history_dir).entries if e.action == "undo"]
    assert [e.data["path"] for e in undone] == ["notes/a.md", "README.md", "notes/b.md"]
    assert read_raw(q, undone[0].data["from"], quilt.history_dir) == "# A\n\nan agent's edit\n"
    assert undone[2].data["to"] is None and read_raw(q, undone[2].data["from"], quilt.history_dir) == "new\n"
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    ok("changes", "--keep", "notes/a.md", cwd=q)
    assert changes(q) == {} and (q / "notes/a.md").read_text() == "# A\n\nsecond\n"


def test_keeping_and_discarding_are_the_authors(q: Path) -> None:
    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.md").write_text("changed\n", encoding="utf-8")
    for args in (("--keep-all",), ("--discard", "notes/a.md")):
        refused("changes", *args, cwd=q, code=2, match="author's", env={"AI_AGENT": "1"})
    assert (q / "notes/a.md").read_text() == "changed\n"


def test_keeping_one_change_leaves_the_time_of_the_look(q: Path) -> None:
    """The look's time is the person's last look at everything, so the changes still listed are still since it."""
    from loom.looks import read_look

    ok("changes", "--keep-all", cwd=q)
    when = read_look(q, "Tester").when  # type: ignore[union-attr]
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    (q / "notes/b.md").write_text("new\n", encoding="utf-8")
    ok("changes", "--keep", "notes/a.md", cwd=q)
    assert read_look(q, "Tester").when == when  # type: ignore[union-attr]
    assert changes(q) == {"notes/b.md": "new"}


NODE = "drafting/nodes/dm-0001.tex"


def test_accepting_keeps_only_the_changes_that_touch_nothing_else(q: Path) -> None:
    """What the viewer's Accept keeps: a change wholly inside the blocks accepted; one in no block stays."""
    from loom.pending import keep_accepted
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    ok("changes", "--keep-all", cwd=q)
    node = q / NODE
    text = node.read_text()
    inside = text[: text.index("\\end{")].rstrip().rsplit("\n", 1)[-1]
    node.write_text(text.replace(inside, inside + " Indeed.", 1), encoding="utf-8")
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    result = scan(load_quilt(q))
    key = next(c["key"] for c in json_of("changes", "--json", cwd=q)["changes"] if c["path"] == NODE)
    assert keep_accepted(result, "Tester", ["some-other-key"]) == []
    assert keep_accepted(result, "Tester", [key]) == [NODE]
    assert changes(q) == {"notes/a.md": "second"}


def test_serve_takes_a_first_look_when_there_is_none_and_leaves_one_that_stands(q: Path) -> None:
    from loom.looks import look_path, read_look
    from loom.render.serve import ServeSession
    from loom.scan.quilt import load_quilt

    assert read_look(q, "Tester") is None
    ServeSession(load_quilt(q), q, port=0, compile_masters=False).first_look()
    first = read_look(q, "Tester")
    assert first is not None
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    stamp = look_path(q, "Tester").stat().st_mtime_ns
    ServeSession(load_quilt(q), q, port=0, compile_masters=False).first_look()
    assert look_path(q, "Tester").stat().st_mtime_ns == stamp and changes(q) == {"notes/a.md": "second"}


def test_latexs_auxiliary_files_are_in_no_look_and_an_old_look_holding_one_reports_nothing(q: Path) -> None:
    """What a compile writes beside its document, as an editor compiling in place leaves it, is neither in the look nor a change; a look taken before they were left out does not report one as gone."""
    from loom.looks import _write, read_look

    for name in ("main.aux", "main.log", "main.fls", "main.fdb_latexmk"):
        (q / "drafting" / name).write_text("written by a compile\n", encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    look = read_look(q, "Tester")
    assert look is not None and not [
        p for p in look.files if p.startswith("drafting/main.") and p != "drafting/main.tex"
    ]
    (q / "drafting/main.log").write_text("written again\n", encoding="utf-8")
    look.files["drafting/main.aux"] = look.files["notes/a.md"]
    _write(q, look)
    (q / "drafting/main.aux").unlink()
    assert changes(q) == {}


def test_a_save_after_the_scan_is_the_next_scans_change(q: Path) -> None:
    """A build's changes and their patches are cut from the texts its scan read: a file saved while the build runs waits for the next scan, so no change is drawn against a reading of its file that the scan never saw."""
    from loom.pending import in_place, patch_of
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    def edit(old: str, new: str) -> None:
        node.write_text(node.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    ok("changes", "--keep-all", cwd=q)
    path = "drafting/nodes/dm-0002.tex"
    node = q / path
    edit("one or two points", "one or two points, never three")
    result = scan(load_quilt(q))
    edit("never three", "never more")
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    edits = {c.path: c for c in in_place(result, "Tester")}
    mine = edits[path]
    assert mine.new == "never three," and result.files[path].text[mine.at[0] : mine.at[1]] == "never three,"
    assert "+Every orbit of a widget has one or two points, never three," in patch_of(result, mine, "Tester")
    assert edits["notes/a.md"].new == "second"
    assert {c.path: c.new for c in in_place(scan(load_quilt(q)), "Tester")}[path] == "never more,"


def test_a_look_under_a_name_no_longer_resolved_is_not_read(q: Path) -> None:
    """A look is the person's under the name they review as: another name has no look until it takes one, and the first is read again under its own."""
    from loom.scan.quilt import save_author

    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.md").write_text("# A\n\nsecond\n", encoding="utf-8")
    assert changes(q) == {"notes/a.md": "second"}
    save_author("Other")
    listed = json_of("changes", "--json", cwd=q)
    assert listed["look"] is None and not [c for c in listed["changes"] if c["kind"] == "edit"]
    save_author("Tester")
    assert changes(q) == {"notes/a.md": "second"}


def test_a_new_quilt_keeps_the_look_with_no_setting(tmp_path: Path) -> None:
    """`loom init` writes no setting for the look, and an edit in place since it waits in Your Changes."""
    from loom.scan.quilt import save_author

    save_author("Tester")
    q = tmp_path / "fresh"
    ok("init", str(q), "--prefix", "fr", "--ai", "none", "--yes", cwd=tmp_path)
    assert "[review]" not in (q / "config.toml").read_text(encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    (q / "README.md").write_text("an edit in place\n", encoding="utf-8")
    listed = json_of("changes", "--json", cwd=q)
    assert listed["look"] is not None and [c["path"] for c in listed["changes"]] == ["README.md"]


def test_a_review_table_left_in_a_config_is_unknown_and_warned_of() -> None:
    from loom.scan.quilt import QuiltConfig

    cfg = QuiltConfig.from_dict({"quilt": {"name": "x"}, "review": {"track_edits": True}})
    assert "config.toml: unknown table [review]; ignored" in cfg.warnings


# ---- the person's own acts go into their look (P-1) --------------------------------------------------------------

AGENT_MARKERS = ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX", "CURSOR_AGENT", "GEMINI_CLI")


@pytest.fixture
def person(q: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`q` with its look taken as `loom serve` takes it, in a shell no agent runs."""
    from loom.looks import take
    from loom.scan.quilt import load_quilt

    for marker in AGENT_MARKERS:
        monkeypatch.delenv(marker, raising=False)
    take(load_quilt(q), "Tester")
    return q


def edits(q: Path) -> list[str]:
    """The paths of the in-place changes waiting."""
    return sorted(c["path"] for c in json_of("changes", "--json", cwd=q)["changes"] if c["kind"] == "edit")


@pytest.mark.parametrize(
    "act",
    [
        ["mv", "drafting/main.tex", "drafting/paper.tex"],
        ["new", "lemma", "A new lemma"],
        ["history", "restore", "widgets-v1", "--to", "drafting/restored.tex"],
        ["linearize", "drafting/main.tex", "--to", "drafting/flat.tex", "--no-check", "--keep-shared"],
    ],
)
def test_the_person_s_own_act_is_not_listed_back_to_them(person: Path, act: list[str]) -> None:
    ok(*act, cwd=person)
    assert edits(person) == []


def test_a_settings_save_and_a_restore_are_not_listed_back(person: Path) -> None:
    from loom.config_edit import set_values
    from loom.render.api import handle
    from loom.scan.quilt import load_quilt

    set_values(load_quilt(person), {"quilt.name": "Renamed"})
    assert edits(person) == []
    handle(person, "history-restore", {"document": "drafting/main.tex", "version": "widgets-v1", "author": "Tester"})
    assert edits(person) == []


def test_an_agent_s_edit_waiting_in_a_file_stays_listed_when_the_person_s_act_writes_it_too(person: Path) -> None:
    """The act's change is merged into the look by lines; the agent's, elsewhere in the file, still waits."""
    from loom.config_edit import set_values
    from loom.scan.quilt import load_quilt

    cfg = person / "config.toml"
    cfg.write_text(cfg.read_text().rstrip("\n") + "\n# an agent's line\n")
    set_values(load_quilt(person), {"quilt.name": "Renamed"})
    rows = [c for c in json_of("changes", "--json", cwd=person)["changes"] if c["kind"] == "edit"]
    assert [c["path"] for c in rows] == ["config.toml"] and "an agent's line" in rows[0]["new"]
    assert not any("Renamed" in c["new"] for c in rows)


def test_an_agent_s_act_is_listed_for_the_person_to_keep(person: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_AGENT", "1")
    ok("new", "lemma", "An agent's lemma", "--as", "Referee Agent", cwd=person)
    monkeypatch.delenv("AI_AGENT")
    assert edits(person)
