"""A person's look at the open files (plan 0.22.8): what the changes waiting on them are counted from, and keep and discard, the author's verbs on a change (`pending.py`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import json_of, ok, refused, run
from tests.unit._quilts import demo, denying, opened


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author("Tester")
    root = opened(demo(tmp_path))  # the paper open to agents, so the look watches it
    (root / "notes").mkdir()
    (root / "notes" / "a.tex").write_text("# A\n\nfirst\n", encoding="utf-8")
    (root / "notes" / "fig.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    return root


def changes(q: Path) -> dict[str, str]:
    """Each in-place change's path and new words: the demo's suggested edit aside."""
    return {c["path"]: c["new"] for c in json_of("changes", "--json", cwd=q)["changes"] if c["kind"] == "edit"}


def test_a_look_holds_every_open_latex_file_and_nothing_else(q: Path) -> None:
    """Shown LaTeX files only; an image, a hidden file and loom's own records are left out, and each text is kept by its hash."""
    from loom.looks import read_look
    from loom.records.snapshots import read_raw
    from loom.scan.quilt import load_quilt

    (q / ".hidden.tex").write_text("no", encoding="utf-8")
    assert json_of("changes", "--json", cwd=q)["look"] is None
    assert ok("changes", "--keep-all", cwd=q).stdout.startswith("took your first look")
    look = read_look(q, "Tester")
    assert look is not None and look.who == "Tester"
    assert "notes/a.tex" in look.files and "drafting/main.tex" in look.files
    assert not [p for p in look.files if p.startswith(".") or p.endswith(".png")]
    assert read_raw(q, look.files["notes/a.tex"], load_quilt(q).history_dir) == "# A\n\nfirst\n"
    assert (q / ".loom/records/looked/tester.json").is_file()
    assert changes(q) == {}


def test_only_latex_source_is_watched_so_a_change_to_markdown_notes_or_a_bibliography_is_never_listed(q: Path) -> None:
    """Proposed edits watch LaTeX documents only: a change made where agents may edit to Markdown, the research state, a bibliography or plain text is never listed, and one to a `.tex` file still is."""
    from loom.looks import read_look

    (q / "notes/a.md").write_text("# A\n\nfirst\n", encoding="utf-8")
    (q / "notes/refs.bib").write_text("@book{a, title={A}}\n", encoding="utf-8")
    (q / "notes/plain.txt").write_text("plain\n", encoding="utf-8")
    (q / "notes/b.tex").write_text("first\n", encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    look = read_look(q, "Tester")
    assert look is not None and sorted(p for p in look.files if p.startswith("notes/")) == [
        "notes/a.tex",
        "notes/b.tex",
    ]
    (q / "notes/a.md").write_text("# A\n\nmy own answer\n", encoding="utf-8")
    (q / "notes/new.md").write_text("a new note\n", encoding="utf-8")
    (q / "notes/refs.bib").write_text("@book{a, title={B}}\n", encoding="utf-8")
    (q / "notes/plain.txt").write_text("changed\n", encoding="utf-8")
    (q / "research-state.md").write_text("# State\n\nchanged\n", encoding="utf-8")
    (q / "notes/b.tex").write_text("second\n", encoding="utf-8")
    assert changes(q) == {"notes/b.tex": "second"}


def test_an_agent_s_suggested_edit_on_markdown_still_waits_and_keeps_though_markdown_is_not_watched(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A suggestion is an agent's record, not a change the look finds: one filed on a Markdown file is listed, and Keep writes it, with no in-place change listed after."""
    (q / "notes/answers.md").write_text("# Answers\n\nThe bound is two.\n", encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    monkeypatch.setenv("AI_AGENT", "1")
    ok("suggest", "notes/answers.md", "--quote", "is two", "--with", "is three", "--as", "Referee Agent", cwd=q)
    monkeypatch.delenv("AI_AGENT")
    (row,) = [c for c in json_of("changes", "--json", cwd=q)["changes"] if c["path"] == "notes/answers.md"]
    assert row["kind"] == "suggested"
    ok("changes", "--keep", row["id"], cwd=q)
    assert (q / "notes/answers.md").read_text(encoding="utf-8") == "# Answers\n\nThe bound is three.\n"
    assert [c for c in json_of("changes", "--json", cwd=q)["changes"] if c["path"] == "notes/answers.md"] == []


def test_an_svg_is_drawn_as_a_picture_and_never_listed(q: Path) -> None:
    """An SVG is text, but the viewer draws it as a picture: one changed, made or removed since the look is no change, nor one an older look held."""
    from loom.looks import Look, _write, read_look

    svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>\n'
    (q / "notes" / "fig.svg").write_text(svg, encoding="utf-8")
    (q / "notes" / "gone.svg").write_text(svg, encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    look = read_look(q, "Tester")
    assert look is not None and not [p for p in look.files if p.endswith(".svg")]
    (q / "notes" / "fig.svg").write_text(svg.replace('r="1"', 'r="2"'), encoding="utf-8")
    (q / "notes" / "new.svg").write_text(svg, encoding="utf-8")
    (q / "notes" / "gone.svg").unlink()
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    assert changes(q) == {"notes/a.tex": "second"}
    # a look that holds a picture, as one taken by an earlier loom does, lists no change to it either
    _write(q, Look(look.who, look.when, {**look.files, "notes/gone.svg": look.files["notes/a.tex"]}, deny=look.deny))
    assert changes(q) == {"notes/a.tex": "second"}


def test_changes_since_the_look_are_in_changed_new_and_gone_files_each_with_its_patch(q: Path) -> None:
    (q / "notes/gone.tex").write_text("to go\n", encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    (q / "notes/b.tex").write_text("new\n", encoding="utf-8")
    (q / "notes/gone.tex").unlink()
    assert changes(q) == {"notes/a.tex": "second", "notes/b.tex": "new", "notes/gone.tex": ""}
    run("build", cwd=q)
    m = json.loads((q / ".loom/cache/site/manifest.json").read_text())
    assert m["changes_since"]["who"] == "Tester"
    row = next(c for c in m["changes"] if c["path"] == "notes/a.tex")
    assert (row["old"], row["new"], row["documents"]) == ("first", "second", [])
    patch = (q / ".loom/cache/site" / row["diff"]).read_text()
    assert patch.startswith("--- a/notes/a.tex") and "-first" in patch and "+second" in patch


def test_keep_takes_a_change_into_the_look_and_discard_puts_its_old_words_back(q: Path) -> None:
    """P7: what a discard sets aside is kept in the history first, and the ledger names the change; a file gone since the look comes back, and one new since is removed."""
    from loom.history.ledger import load_history
    from loom.records.snapshots import read_raw
    from loom.scan.quilt import load_quilt

    (q / "notes/gone.tex").write_text("to go\n", encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.tex").write_text("# A\n\nan agent's edit\n", encoding="utf-8")
    (q / "notes/gone.tex").unlink()
    (q / "notes/b.tex").write_text("new\n", encoding="utf-8")
    ok("changes", "--discard", "notes/a.tex", cwd=q)
    assert (q / "notes/a.tex").read_text() == "# A\n\nfirst\n"
    ok("changes", "--discard", "notes/gone.tex", cwd=q)
    assert (q / "notes/gone.tex").is_file()
    ok("changes", "--discard", "notes/b.tex", cwd=q)
    assert not (q / "notes/b.tex").exists() and changes(q) == {}
    quilt = load_quilt(q)
    undone = [e for e in load_history(quilt.history_dir).entries if e.action == "undo"]
    assert [e.data["path"] for e in undone] == ["notes/a.tex", "notes/gone.tex", "notes/b.tex"]
    assert read_raw(q, undone[0].data["from"], quilt.history_dir) == "# A\n\nan agent's edit\n"
    assert undone[2].data["to"] is None and read_raw(q, undone[2].data["from"], quilt.history_dir) == "new\n"
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    ok("changes", "--keep", "notes/a.tex", cwd=q)
    assert changes(q) == {} and (q / "notes/a.tex").read_text() == "# A\n\nsecond\n"


def test_keeping_and_discarding_are_the_authors(q: Path) -> None:
    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.tex").write_text("changed\n", encoding="utf-8")
    for args in (("--keep-all",), ("--discard", "notes/a.tex")):
        refused("changes", *args, cwd=q, code=2, match="author's", env={"AI_AGENT": "1"})
    assert (q / "notes/a.tex").read_text() == "changed\n"


def test_keeping_one_change_leaves_the_time_of_the_look(q: Path) -> None:
    """The look's time is the person's last look at everything, so the changes still listed are still since it."""
    from loom.looks import read_look

    ok("changes", "--keep-all", cwd=q)
    when = read_look(q, "Tester").when  # type: ignore[union-attr]
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    (q / "notes/b.tex").write_text("new\n", encoding="utf-8")
    ok("changes", "--keep", "notes/a.tex", cwd=q)
    assert read_look(q, "Tester").when == when  # type: ignore[union-attr]
    assert changes(q) == {"notes/b.tex": "new"}


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
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    result = scan(load_quilt(q))
    key = next(c["key"] for c in json_of("changes", "--json", cwd=q)["changes"] if c["path"] == NODE)
    assert keep_accepted(result, "Tester", ["some-other-key"]) == []
    assert keep_accepted(result, "Tester", [key]) == [NODE]
    assert changes(q) == {"notes/a.tex": "second"}


def test_serve_takes_a_first_look_when_there_is_none_and_leaves_one_that_stands(q: Path) -> None:
    from loom.looks import look_path, read_look
    from loom.render.serve import ServeSession
    from loom.scan.quilt import load_quilt

    assert read_look(q, "Tester") is None
    ServeSession(load_quilt(q), q, port=0, compile_masters=False).first_look()
    first = read_look(q, "Tester")
    assert first is not None
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    stamp = look_path(q, "Tester").stat().st_mtime_ns
    ServeSession(load_quilt(q), q, port=0, compile_masters=False).first_look()
    assert look_path(q, "Tester").stat().st_mtime_ns == stamp and changes(q) == {"notes/a.tex": "second"}


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
    look.files["drafting/main.aux"] = look.files["notes/a.tex"]
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
    (q / "notes/a.tex").write_text("# A\n\nsecond\n", encoding="utf-8")
    edits = {c.path: c for c in in_place(result, "Tester")}
    mine = edits[path]
    assert mine.new == "never three," and result.files[path].text[mine.at[0] : mine.at[1]] == "never three,"
    assert "+Every orbit of a widget has one or two points, never three," in patch_of(result, mine, "Tester")
    assert "notes/a.tex" not in edits
    later = {c.path: c.new for c in in_place(scan(load_quilt(q)), "Tester")}
    assert later[path] == "never more," and later["notes/a.tex"] == "second"


def test_a_new_name_takes_the_newest_look_and_nothing_waiting_is_lost(q: Path) -> None:
    """A name set in Settings has no look of its own: it is given the newest one, saying whose, so the agent's edit waiting stays listed and Keep all takes in nothing unseen (P-2)."""
    from loom.looks import read_look
    from loom.scan.quilt import save_author

    ok("changes", "--keep-all", cwd=q)
    (q / "notes/a.tex").write_text("# A\n\nan agent's edit\n", encoding="utf-8")
    save_author("Isaac Martin")
    listed = json_of("changes", "--json", cwd=q)
    assert listed["look"]["carried"] == "Tester" and changes(q) == {"notes/a.tex": "an agent's edit"}
    assert "carried over from Tester's" in ok("changes", cwd=q).stdout
    look = read_look(q, "Isaac Martin")
    assert look is not None and look.carried == "Tester"
    save_author("Tester")
    assert changes(q) == {"notes/a.tex": "an agent's edit"}


def test_a_new_quilt_keeps_the_look_with_no_setting(tmp_path: Path) -> None:
    """`loom init` writes no setting for the look, and an edit in place since it waits in Your Changes."""
    from loom.scan.quilt import save_author

    save_author("Tester")
    q = tmp_path / "fresh"
    ok("init", str(q), "--prefix", "fr", "--ai", "none", "--yes", cwd=tmp_path)
    assert "[review]" not in (q / "config.toml").read_text(encoding="utf-8")
    ok("changes", "--keep-all", cwd=q)
    (q / "draft.tex").write_text("an edit in place\n", encoding="utf-8")
    listed = json_of("changes", "--json", cwd=q)
    assert listed["look"] is not None and [c["path"] for c in listed["changes"]] == ["draft.tex"]


def test_a_track_edits_left_in_a_config_says_the_look_is_kept_now_at_its_line(q: Path) -> None:
    """A quilt that had turned tracking off is told its own edits will be listed, at the table's line (P-8)."""
    cfg = q / "config.toml"
    cfg.write_text(cfg.read_text().rstrip("\n") + "\n\n[review]\ntrack_edits = false\n")
    line = cfg.read_text().splitlines().index("[review]") + 1
    said = json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"]
    (d,) = [x for x in said if "track_edits" in x["message"]]
    assert "your own edits in an editor wait in Your Changes" in d["message"]
    assert d["locations"][0]["line"] == line


# ---- the person's own acts go into their look (P-1) --------------------------------------------------------------


@pytest.fixture
def person(q: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`q` with its look taken as `loom serve` takes it, in a shell no agent runs."""
    from loom.looks import take
    from loom.scan.quilt import load_quilt

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
    from loom import writes
    from loom.scan.quilt import load_quilt

    note = person / "notes/a.tex"
    note.write_text("# A\n\nfirst\n\nan agent's line\n", encoding="utf-8")
    held = note.read_bytes()
    writes.put(
        person,
        load_quilt(person).history_dir,
        "notes/a.tex",
        held.replace(b"# A", b"# Renamed"),
        kind="page",
        expect=held,
    )
    rows = [c for c in json_of("changes", "--json", cwd=person)["changes"] if c["kind"] == "edit"]
    assert [c["path"] for c in rows] == ["notes/a.tex"] and "an agent's line" in rows[0]["new"]
    assert not any("Renamed" in c["new"] for c in rows)


def test_an_agent_s_act_is_listed_for_the_person_to_keep(person: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_AGENT", "1")
    ok("new", "lemma", "An agent's lemma", "--as", "Referee Agent", cwd=person)
    monkeypatch.delenv("AI_AGENT")
    assert edits(person)


def test_an_agent_s_edit_before_the_first_serve_is_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`init` takes the person's first look, so the edit an agent makes before `loom serve` ever runs is not taken in unseen (P-3)."""
    from loom.render.serve import ServeSession
    from loom.scan.quilt import load_quilt, save_author

    save_author("Tester")
    q = tmp_path / "fresh"
    ok("init", str(q), "--prefix", "fr", "--ai", "none", "--yes", cwd=tmp_path)
    (q / "draft.tex").write_text("an agent's edit before any serve\n", encoding="utf-8")
    ServeSession(load_quilt(q), q, port=0, compile_masters=False).first_look()
    assert edits(q) == ["draft.tex"]


def test_a_copied_quilt_s_server_file_does_not_start_loom_on_the_original(tmp_path: Path) -> None:
    """A client's server file names its quilt's path; started in a copy it would drive the original, so it is refused (P-7)."""
    import shutil

    from tests.helpers import refused

    original = demo(tmp_path)
    copy = tmp_path / "copy"
    shutil.copytree(original, copy)
    r = refused("mcp", "--as", "Codex Agent", "--quilt", str(original), cwd=copy, code=2, match="copied quilt")
    assert "loom ai init" in r.output


def test_keep_all_from_the_shell_says_what_its_act_settled(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep's act settles what a crash left as it begins, and says so on stderr, as a writer of the history and a command that draws an id do."""
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    ok("changes", "--keep-all", cwd=q)
    hist = load_quilt(q).history_dir
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        with writes.act(q, hist, "pdf-save") as w:
            w.replace("drafting/fig.bin", b"\xff\x00binary")
            w.replace("drafting/notes.md", b"# Notes\n")
    restore()
    (q / "notes/a.tex").write_text("# A\n\nan agent's edit\n", encoding="utf-8")
    said = ok("changes", "--keep-all", cwd=q).stderr
    assert said.count("loom: undid pdf-save:") == 1, said
    assert not writes.read_journal(q).begun and not (q / "drafting/fig.bin").exists()


def test_a_command_that_draws_an_id_says_a_left_act_once_though_its_act_settles_again(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`loom new` says what it settled as it takes the door's lock; the act it opens under that lock settles again and stays quiet."""
    from loom import writes
    from loom.scan.quilt import load_quilt
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    hist = load_quilt(q).history_dir
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        with writes.act(q, hist, "pdf-save") as w:
            w.replace("drafting/fig.bin", b"\xff\x00binary")
            w.replace("drafting/notes.md", b"# Notes\n")
    restore()
    (q / "drafting/fig.bin").write_bytes(b"the person's own\n")  # so recovery leaves the act
    said = ok("new", "Lemma", "A new lemma", cwd=q).stderr
    assert said.count("loom: left pdf-save:") == 1, said


# ---- the look watches only the places agents may edit (R2-1, R2-2) ----------------------------------------------

#: The second look's session: the person's eight saves in their editor, then an agent's two edits in place.
PERSON_SAVES = [
    ("drafting/main.tex", "We fix conventions here", "We fix our conventions here [P1]"),
    ("drafting/main.tex", "nice as one could hope", "nice as anyone could hope [P2]"),
    ("drafting/nodes/dm-0003.tex", "\\begin{proof}", "\\begin{proof}\n% [P3] the person's plan for this proof"),
    ("drafting/nodes/dm-0002.tex", "\\end{", "% [P4] a note to self\n\\end{"),
    ("drafting/main.tex", "\\section{Results}", "\\section{Results [P5]}"),
    ("drafting/outline.tex", "\\begin{document}", "\\begin{document}\n% [P6] reorder later"),
    ("drafting/nodes/dm-0001.tex", "fixed locus", "fixed-point locus [P7]"),
    ("drafting/main.tex", "\\bibliographystyle", "% [P8] check the bibliography style\n\\bibliographystyle"),
]
AGENT_EDITS = [
    ("drafting/nodes/dm-0006.tex", "\\end{", "% [A1] the agent's claim: this also holds for finite widgets\n\\end{"),
    ("drafting/nodes/dm-0007.tex", "\\end{", "% [A2] the agent's fix of a typo\n\\end{"),
]
THE_PERSON_S = [
    "/drafting/main.tex",
    "/drafting/outline.tex",
    "/drafting/nodes/dm-0001.tex",
    "/drafting/nodes/dm-0002.tex",
    "/drafting/nodes/dm-0003.tex",
]


def _edit(q: Path, rel: str, old: str, new: str) -> None:
    p = q / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, (rel, old)
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_the_person_s_saves_in_places_agents_are_denied_are_never_listed(person: Path) -> None:
    """The second look's session: the person saves eight edits in documents agents are denied, an agent edits two places open to it, the person takes in an agent's copy and saves a setting. Your Changes lists the agent's two edits and nothing of the person's, and says which places it leaves to them (R2-1)."""
    from loom.config_edit import set_values
    from loom.scan.quilt import load_quilt

    set_values(load_quilt(person), {"agents.deny": THE_PERSON_S})
    for rel, old, new in PERSON_SAVES + AGENT_EDITS:
        _edit(person, rel, old, new)
    ok("draft", "drafting/main.tex", "--ai", "prop", "--as", "Agent", cwd=person)
    _edit(person, ".loom/agents/copies/prop.tex", "Closedness is where", "Closedness (agent) is where")
    token = json_of("adopt", ".loom/agents/copies/prop.tex", "--json", cwd=person)["token"]
    ok("adopt", ".loom/agents/copies/prop.tex", "--incorporate", token, cwd=person)
    set_values(load_quilt(person), {"quilt.name": "Renamed"})
    rows = [c for c in json_of("changes", "--json", cwd=person)["changes"] if c["kind"] == "edit"]
    assert sorted(c["path"] for c in rows) == ["drafting/nodes/dm-0006.tex", "drafting/nodes/dm-0007.tex"], rows
    assert all("[A" in c["new"] for c in rows)
    said = ok("changes", cwd=person).stdout
    assert "your own, never listed: config.toml, /drafting/main.tex, /drafting/outline.tex" in " ".join(said.split())


def test_the_deny_list_decides_and_a_waiting_change_outlives_closing_its_place(person: Path) -> None:
    """The look watches by the predicate the door and the agents' permission files read (`agents.denied_by`). A place closed to agents keeps what the look held, so an agent's change waiting there is listed again once it is opened; a file made while it was the person's goes in as it stands when it is opened, and is listed from then on."""
    from loom.agents import denied_by
    from loom.config_edit import set_values
    from loom.scan.quilt import load_quilt

    note = person / "notes/a.tex"
    note.write_text("# A\n\nfirst\n\nan agent's line\n", encoding="utf-8")
    assert edits(person) == ["notes/a.tex"]
    set_values(load_quilt(person), {"agents.deny": ["notes/"]})
    assert denied_by(load_quilt(person).config, "notes/a.tex") == "notes/"
    assert edits(person) == []
    made = person / "notes/b.tex"
    made.write_text("the person's own note\n", encoding="utf-8")
    assert edits(person) == []
    set_values(load_quilt(person), {"agents.deny": []})
    rows = [c for c in json_of("changes", "--json", cwd=person)["changes"] if c["kind"] == "edit"]
    assert [c["path"] for c in rows] == ["notes/a.tex"] and "an agent's line" in rows[0]["new"]
    made.write_text("the person's own note\n\nan agent's word\n", encoding="utf-8")
    assert edits(person) == ["notes/a.tex", "notes/b.tex"]


def test_a_write_the_viewer_asks_for_is_the_person_s_whatever_shell_started_the_server(
    person: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `loom serve` started from an agent's terminal carries its markers; a restore the viewer asks for is still the person's act, so its words go into their look and its journal line says so (R2-2)."""
    from loom.looks import take
    from loom.render.api import handle
    from loom.scan.quilt import load_quilt

    # the document as the person last saw it differs from the version, so restoring it writes words the look must take
    _edit(person, "drafting/main.tex", "We fix conventions here", "We fix our conventions here")
    take(load_quilt(person), "Tester")
    before = (person / "drafting/main.tex").read_text(encoding="utf-8")
    monkeypatch.setenv("CLAUDECODE", "1")
    handle(person, "history-restore", {"document": "drafting/main.tex", "version": "widgets-v1"})
    monkeypatch.delenv("CLAUDECODE")
    assert (person / "drafting/main.tex").read_text(encoding="utf-8") != before
    assert edits(person) == []
    lines = [json.loads(x) for x in (person / ".loom/local/writes.jsonl").read_text().splitlines()]
    assert [e["by"] for e in lines if e["event"] == "begin" and e["kind"] == "restore"] == ["person"]


def test_the_demo_as_made_lists_none_of_the_person_s_saves_and_lists_an_agent_s_suggestions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The demo denies its paper to agents as a quilt made from a paper does: after the first look, the person's eight saves in it give no row, and an agent's two edits, made as suggestions since the paper is not its to edit, are listed under its name."""
    from loom.agents import denied_by
    from loom.looks import take
    from loom.scan.quilt import load_quilt, save_author

    save_author("Tester")
    q = demo(tmp_path)
    assert load_quilt(q).config.agents_deny == ["/drafting/"]
    assert denied_by(load_quilt(q).config, "drafting/nodes/dm-0006.tex") == "/drafting/"
    assert "Edit(/drafting/**)" in json.loads((q / ".claude/settings.json").read_text())["permissions"]["deny"]
    take(load_quilt(q), "Tester")
    for rel, old, new in PERSON_SAVES:
        _edit(q, rel, old, new)
    monkeypatch.setenv("AI_AGENT", "1")
    for key, quote, new in (
        ("dm-0006", "is invariant under", "is preserved by"),
        ("dm-0007", "has finitely many fixed points", "has only finitely many fixed points"),
    ):
        ok("suggest", key, "--quote", quote, "--with", new, "--as", "Referee Agent", cwd=q)
    monkeypatch.delenv("AI_AGENT")
    changes = json_of("changes", "--json", cwd=q)["changes"]
    assert [c for c in changes if c["kind"] == "edit"] == []
    agent = [c for c in changes if c["kind"] == "suggested" and c["author"] == "Referee Agent"]
    assert sorted(c["key"] for c in agent) == ["dm-0006", "dm-0007"]


@pytest.mark.parametrize("how", ["in Settings", "by hand"])
def test_an_agent_s_new_file_waiting_in_a_place_closed_and_opened_again_is_listed_again(person: Path, how: str) -> None:
    """A place closed to agents keeps what the look held of it, and holds a file made there since the look as absent at it, so when the place is opened again an agent's change, removal and new file are each listed as before; nothing an agent made is taken in without having been listed (R2-5), and the new file is discarded as one the look did not hold (R2-12)."""
    import re

    (person / "notes/gone.tex").write_text("to be removed\n", encoding="utf-8")
    from loom.looks import take
    from loom.scan.quilt import load_quilt

    take(load_quilt(person), "Tester")
    (person / "notes/a.tex").write_text("# A\n\nfirst, and an agent's word\n", encoding="utf-8")
    (person / "notes/gone.tex").unlink()
    (person / "notes/new.tex").write_text("an agent's new note\n", encoding="utf-8")
    waiting = ["notes/a.tex", "notes/gone.tex", "notes/new.tex"]
    assert edits(person) == waiting

    def set_deny(*entries: str) -> None:
        if how == "in Settings":
            denying(person, *entries)
        else:
            cfg = person / "config.toml"
            said = ", ".join(f'"{e}"' for e in entries)
            cfg.write_text(re.sub(r"(?m)^deny = \[.*\]$", f"deny = [{said}]", cfg.read_text()), encoding="utf-8")

    set_deny("notes/")
    assert edits(person) == []
    ok("changes", "--keep-all", cwd=person)  # keeping all while it is closed takes nothing of it in
    set_deny()
    assert edits(person) == waiting
    # the new file, held as absent at the look, is discarded as a file the look did not hold: it goes, and so does its row
    ok("changes", "--discard", "notes/new.tex", cwd=person)
    assert not (person / "notes/new.tex").exists() and edits(person) == ["notes/a.tex", "notes/gone.tex"]


def test_an_act_signed_as_an_agent_s_is_refused_a_denied_place_in_a_shell_with_no_marker(tmp_path: Path) -> None:
    """Whose act it is decides the refusal as it decides the look (`identity.agents_act`): `loom new` signed as an agent's is refused the paper agents are denied though no marker says an agent runs the shell, whether it names the file or not; the person's own is not (R2-11)."""
    from loom.scan.quilt import save_author

    save_author("Tester")
    q = denying(demo(tmp_path), "/drafting/")
    nodes = sorted(p.name for p in (q / "drafting/nodes").glob("*.tex"))
    refused("new", "lemma", "An agent's lemma", "--as", "Codex Agent", cwd=q, code=2, match="deny names /drafting/")
    refused("new", "theorem", "An agent's theorem", "--to", "drafting/agent.tex", "--as", "Codex Agent", cwd=q, code=2, match="/drafting/")  # fmt: skip
    assert sorted(p.name for p in (q / "drafting/nodes").glob("*.tex")) == nodes
    assert not (q / "drafting/agent.tex").exists()
    ok("new", "lemma", "The person's lemma", cwd=q)


@pytest.mark.parametrize("how", ["in Settings", "by hand"])
def test_a_file_renamed_while_its_place_is_closed_is_found_by_its_text_when_it_opens(person: Path, how: str) -> None:
    """A place closed to agents keeps the text each of its files held as it closed, so a file renamed meanwhile is found by it when the place opens: an agent's new file is listed as new at its new path, and an agent's change waiting in a file the look held is listed there, never taken in as the file stands (R2-14)."""
    import re

    (person / "notes/a.tex").write_text("# A\n\nfirst, and an agent's word\n", encoding="utf-8")
    (person / "notes/new.tex").write_text("an agent's new note\n", encoding="utf-8")
    assert edits(person) == ["notes/a.tex", "notes/new.tex"]

    def set_deny(*entries: str) -> None:
        if how == "in Settings":
            denying(person, *entries)
        else:
            cfg = person / "config.toml"
            said = ", ".join(f'"{e}"' for e in entries)
            cfg.write_text(re.sub(r"(?m)^deny = \[.*\]$", f"deny = [{said}]", cfg.read_text()), encoding="utf-8")

    set_deny("notes/")
    assert edits(person) == []  # read as the server reads it at once, so the place is seen closed before the renames
    (person / "notes/a.tex").rename(person / "notes/b.tex")
    (person / "notes/new.tex").rename(person / "notes/moved.tex")
    set_deny()
    rows = {c["path"]: c for c in json_of("changes", "--json", cwd=person)["changes"] if c["kind"] == "edit"}
    assert sorted(rows) == ["notes/b.tex", "notes/moved.tex"], sorted(rows)
    # a change against the text the look held, not the whole file as new
    assert rows["notes/b.tex"]["old"].strip() == "first" and "an agent's word" in rows["notes/b.tex"]["new"]
    assert rows["notes/moved.tex"]["new"].strip() == "an agent's new note"


def test_two_files_with_one_text_renamed_while_their_place_is_closed_are_both_found(person: Path) -> None:
    """Each gone file of a closed place is kept by its text, files that share a text each their own, so two of an agent's new files with the same text, both renamed while the place is closed, are both listed as new when it opens; nothing an agent made is taken in without having been listed (R2-17)."""
    for name in ("one.tex", "two.tex"):
        (person / f"notes/{name}").write_text("a stub\n", encoding="utf-8")
    assert edits(person) == ["notes/one.tex", "notes/two.tex"]
    denying(person, "notes/")
    assert edits(person) == []
    (person / "notes/one.tex").rename(person / "notes/first.tex")
    (person / "notes/two.tex").rename(person / "notes/second.tex")
    denying(person)
    assert edits(person) == ["notes/first.tex", "notes/second.tex"]


def test_a_lake_project_is_the_agents_own_and_nothing_in_it_is_ever_listed(person: Path) -> None:
    """A Lake project is the agents' own (`scan.source.lake_root`): its Lean files, its lakefile and manifest, and the paper's files the skills' linters copy into it are never proposed edits and never in a look, while an agent's edit beside it is listed."""
    from loom.looks import take
    from loom.scan.quilt import load_quilt

    made = {
        "lakefile.toml": 'name = "proof"\n',
        "lake-manifest.json": "{}\n",
        "Proof/Basic.lean": "theorem t : True := trivial\n",
        "source/nodes/dm-0006.tex": "\\begin{lemma}a copy\\end{lemma}\n",
    }
    for rel, text in made.items():
        p = person / "lean" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _edit(person, *AGENT_EDITS[0])
    assert edits(person) == ["drafting/nodes/dm-0006.tex"]
    (person / "lean" / "Proof" / "Basic.lean").write_text("theorem t : 1 = 1 := rfl\n", encoding="utf-8")
    assert edits(person) == ["drafting/nodes/dm-0006.tex"]
    look = take(load_quilt(person), "Tester")
    assert not [rel for rel in look.files if rel.startswith("lean/")], look.files
