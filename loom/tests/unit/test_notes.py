"""New note (`loom.notes`): the person's command, kept by quilt and never the quilt's, split with no shell, handed a request file; a Markdown note when none is set."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from loom import notes
from loom.identity import at_the_viewer
from loom.notes import NoteRefused
from loom.scan.quilt import load_quilt
from tests.unit._quilts import demo

#: A stand-in for the person's editor: it records the arguments it was given, and the request file's contents when its first argument names one.
STAND_IN = """
import json, sys
from pathlib import Path
args = sys.argv[1:]
out = {"argv": args}
if args and args[0].endswith(".json"):
    out["request"] = json.loads(Path(args[0]).read_text(encoding="utf-8"))
Path(sys.argv[0]).with_name("ran.json").write_text(json.dumps(out), encoding="utf-8")
"""

#: Words a shell, or an editor evaluating them, would act on.
HOSTILE = 'it\'s "x" $(touch pwned) `touch pwned2`; touch pwned3 ") (shell-command "touch pwned4") ("'


def stand_in(tmp_path: Path) -> tuple[str, Path]:
    script = tmp_path / "editor" / "new_note.py"
    script.parent.mkdir()
    script.write_text(STAND_IN, encoding="utf-8")
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}", script.with_name("ran.json")


def test_each_placeholder_is_replaced_inside_its_own_argument() -> None:
    req = notes.Request(link="quilt:a.md#quote=x", quote=HOSTILE, title="A p. 2", dir="/q/notes", quilt="/q")
    argv = notes.argv_for(
        "ed --link={link} '{quote}' -e '(f \"{request}\")' {title} {dir} {quilt} {other}", req, "/tmp/r.json"
    )
    assert argv == [
        "ed",
        "--link=quilt:a.md#quote=x",
        HOSTILE,
        "-e",
        '(f "/tmp/r.json")',
        "A p. 2",
        "/q/notes",
        "/q",
        "{other}",
    ]


def test_a_command_that_cannot_be_split_is_refused() -> None:
    with pytest.raises(NoteRefused, match="cannot be split") as got:
        notes.check_command("emacsclient -e '(unclosed")
    assert got.value.code == "bad-command"
    with pytest.raises(NoteRefused, match="one line"):
        notes.check_command("ed\nrm -rf x")
    # DEL too, which TOML refuses in a string, so one saved would leave every quilt's command unreadable
    with pytest.raises(NoteRefused, match="one line"):
        notes.check_command("ed\x7f {link}")


def test_new_note_neither_holds_the_publication_lock_nor_rebuilds() -> None:
    """A command may take seconds to answer, and the file it or the stub makes reaches the manifest through the watcher: no other write waits on it."""
    from loom.render.api import NO_REBUILD, OWN_LOCK

    assert {"new-note", "notes-settings"} <= set(OWN_LOCK)
    assert {"new-note", "notes-settings"} <= set(NO_REBUILD)


def test_the_command_runs_with_no_shell_and_is_handed_the_request_file(tmp_path: Path) -> None:
    q = demo(tmp_path)
    command, ran = stand_in(tmp_path)
    with at_the_viewer():
        notes.set_command(q, command + " {request} {quote}", actor=None)
        req = notes.request(q, "quilt:main.tex#dm-0003&quote=the%20words", HOSTILE, "Main, Theorem 1")
        done = notes.run(q, req, actor=None)
    assert done.how == "ran"
    said = json.loads(ran.read_text(encoding="utf-8"))
    assert said["argv"][1] == HOSTILE and len(said["argv"]) == 2
    assert said["request"] == {
        "link": "quilt:main.tex#dm-0003&quote=the%20words",
        "quote": HOSTILE,
        "title": "Main, Theorem 1",
        "dir": str((q / "notes").resolve()),
        "quilt": str(q.resolve()),
    }
    assert not any(tmp_path.rglob("pwned*")), "nothing in the quoted words ran"


def test_a_failing_command_says_so(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with at_the_viewer():
        notes.set_command(
            q, f"{shlex.quote(sys.executable)} -c 'import sys; print(\"no such capture\"); sys.exit(3)'", actor=None
        )
        with pytest.raises(NoteRefused, match="status 3: no such capture") as got:
            notes.run(q, notes.request(q, "quilt:main.tex"), actor=None)
        assert got.value.code == "command-failed"
        notes.set_command(q, "no-such-editor-anywhere {link}", actor=None)
        with pytest.raises(NoteRefused, match="not a program"):
            notes.run(q, notes.request(q, "quilt:main.tex"), actor=None)


def test_the_command_is_kept_for_the_person_by_quilt_and_never_read_from_the_quilt(tmp_path: Path, home: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = demo(tmp_path / "a"), demo(tmp_path / "b")
    with (a / "config.toml").open("a", encoding="utf-8") as f:
        f.write('\n[notes]\ndir = "jots"\ncommand = "touch from-the-repository"\n')
    config = load_quilt(a).config
    assert config.notes_dir == "jots"
    assert any("[notes] command is ignored" in w for w in config.warnings)
    assert notes.command_for(a) == ""
    with at_the_viewer():
        notes.set_command(a, "ed-a {link}", actor=None)
        notes.set_command(b, "ed-b {link}", actor=None)
    assert (notes.command_for(a), notes.command_for(b)) == ("ed-a {link}", "ed-b {link}")
    kept = notes.commands_path()
    assert kept.is_relative_to(home / ".config") and kept.stat().st_mode & 0o077 == 0
    with at_the_viewer():
        notes.set_command(a, "", actor=None)
    assert notes.command_for(a) == "" and notes.command_for(b) == "ed-b {link}"


def test_an_agent_neither_sets_the_command_nor_runs_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    q = demo(tmp_path)
    with pytest.raises(NoteRefused, match="only you") as got:
        notes.set_command(q, "ed {link}", actor="Reading Agent")
    assert got.value.code == "author-only"
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(NoteRefused, match="only you"):
        notes.set_command(q, "ed {link}", actor=None)
    with pytest.raises(NoteRefused, match="your click"):
        notes.run(q, notes.request(q, "quilt:main.tex"), actor=None)
    assert notes.command_for(q) == ""


def test_with_no_command_a_markdown_note_is_written_and_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom import files

    opened: list[list[str]] = []
    monkeypatch.setattr(files, "launch", opened.append)
    q = demo(tmp_path)
    req = notes.request(q, "quilt:main.tex#dm-0003&quote=two%20words", "two words", "Main, Theorem 1")
    with at_the_viewer():
        first = notes.run(q, req, actor=None)
        second = notes.run(q, req, actor=None)
    assert first.how == "wrote" and first.path.startswith("notes/") and first.path.endswith("-main-theorem-1.md")
    assert second.path.endswith("-main-theorem-1-2.md")
    text = (q / first.path).read_text(encoding="utf-8")
    assert text == "# Main, Theorem 1\n\n> two words\n\n[Main, Theorem 1](quilt:main.tex#dm-0003&quote=two%20words)\n\n"
    if sys.platform in ("darwin", "linux"):
        assert opened and opened[0][-1] == str(q / first.path)


@pytest.mark.parametrize("link", ["https://example.org", "quilt:a b", "quilt:a\nb", "cited:doi:10.1/x"])
def test_only_a_quilt_link_is_taken(tmp_path: Path, link: str) -> None:
    q = demo(tmp_path)
    with pytest.raises(NoteRefused, match="quilt: link"):
        notes.request(q, link)


def test_a_notes_folder_outside_the_quilt_is_not_taken(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with (q / "config.toml").open("a", encoding="utf-8") as f:
        f.write('\n[notes]\ndir = "../elsewhere"\n')
    config = load_quilt(q).config
    assert config.notes_dir == "notes" and any("outside the quilt" in w for w in config.warnings)
