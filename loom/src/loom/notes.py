"""New note: the person's own command run at their click, with a link to the place, or a Markdown note written and opened when they set none.

The command is the person's and never the quilt's: it is kept in `notes.toml` beside the person's own `config.toml`, by the quilt's resolved path, so it never arrives with a repository, and only the person sets it (`set_command` refuses an agent). It is split as a shell would split it (`shlex`) and run with no shell. Each `{link}`, `{quote}`, `{title}`, `{dir}`, `{quilt}` and `{request}` in an argument is replaced in that argument alone, so quoted words never become more arguments or shell syntax; `{request}` is the path of a JSON file holding exactly `link`, `quote`, `title`, `dir` and `quilt`, for an editor that evaluates what it is passed (`emacsclient -e`), where words spliced into the form would be evaluated.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

#: The placeholders a command may hold, each replaced inside the argument it stands in.
PLACEHOLDERS = ("link", "quote", "title", "dir", "quilt", "request")
#: The keys of the request file, and nothing else.
REQUEST_KEYS = ("link", "quote", "title", "dir", "quilt")
#: The longest quoted words and name taken: a selection, not a document.
MAX_QUOTE = 20_000
MAX_TITLE = 500
#: How long loom waits for the command to say how it went before leaving it running; the server's other requests do not wait on it (`render.api.OWN_LOCK`).
WAIT = 5.0
_PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")


class NoteRefused(Exception):
    """A new note loom will not make, or a command it will not keep, with the code the write API answers."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def commands_path() -> Path:
    """`notes.toml` beside the person's own config (`scan.quilt.user_config_path`)."""
    from loom.scan.quilt import user_config_path

    return user_config_path().parent / "notes.toml"


def _key(root: Path) -> str:
    return str(Path(root).resolve())


def _read() -> dict[str, dict[str, object]]:
    path = commands_path()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise NoteRefused("settings-refused", f"{path} cannot be read ({exc}); fix or remove it") from exc
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def command_for(root: Path) -> str:
    """The person's new-note command for the quilt at `root`, '' when none is set."""
    value = _read().get(_key(root), {}).get("command", "")
    return value.strip() if isinstance(value, str) else ""


def check_command(command: str) -> list[str]:
    """`command` split as a shell splits it, or NoteRefused (`bad-command`) when it cannot be."""
    if any(ord(c) < 32 or ord(c) == 127 for c in command):
        raise NoteRefused("bad-command", "the command is one line, with no control characters")
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise NoteRefused("bad-command", f"the command cannot be split into arguments: {exc}") from exc
    if not argv:
        raise NoteRefused("bad-command", "the command is empty")
    return argv


#: How long the confirmation stays up before it counts as Cancel, in seconds.
CONFIRM_WAIT = 120

#: The dialog that confirms a new command, given the command and the quilt as data (`on run argv`), never spliced into the script: Cancel is the default button and the answer to Escape, closing it or letting it time out.
_DIALOG = (
    "on run argv",
    'set msg to "Set the command loom runs when you choose New note?" & return & return & "Quilt: " & item 2 of argv & return & return & "Command: " & item 1 of argv & return & return & "Choose Cancel unless you have just set this in loom\'s Settings."',
    f'set answer to display dialog msg with title "loom: New note" buttons {{"Cancel", "Set"}} default button "Cancel" cancel button "Cancel" with icon caution giving up after {CONFIRM_WAIT}',
    'if gave up of answer then return "no"',
    "return button returned of answer",
    "end run",
)


def ask_in_dialog(command: str, quilt: Path) -> bool:
    """Whether the person chose Set in a native dialog showing the exact command and the quilt; Cancel, Escape, closing it or `CONFIRM_WAIT` passing is no.

    Raises NoteRefused (`no-dialog`) where loom has no dialog to show (no `osascript`): the command is then set in `notes.toml` by hand.
    """
    import shutil

    if shutil.which("osascript") is None:
        raise NoteRefused(
            "no-dialog",
            f"loom cannot ask you outside the browser on this system; set the command in {commands_path()} yourself",
        )
    argv = ["osascript", *(part for line in _DIALOG for part in ("-e", line)), command, str(Path(quilt).resolve())]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=CONFIRM_WAIT + 30, check=False)
    except subprocess.TimeoutExpired:
        return False
    except OSError as exc:
        raise NoteRefused("no-dialog", f"loom could not show its dialog: {exc}") from exc
    return done.returncode == 0 and done.stdout.strip() == "Set"


#: What a new or changed command must pass before it is kept: the person's Set in a dialog the browser cannot answer (`ask_in_dialog`). Replaced by the tests, which never raise a real dialog.
confirm = ask_in_dialog


def set_command(root: Path, command: str, *, actor: str | None) -> None:
    """Keep `command` as the person's new-note command for the quilt at `root`; '' removes it.

    Refused (`author-only`) to an agent (`identity.agents_act`): a command run at the person's click is set by the person alone. A command that is new or changed is kept only once the person chooses Set in loom's dialog (`confirm`), outside the browser, where an agent holding the server's write token cannot answer; NoteRefused (`not-confirmed`) otherwise. Removing it, or saving it unchanged, asks nothing. The file is written whole, by loom, closed to others.
    """
    from loom.identity import agents_act

    if agents_act(actor):
        raise NoteRefused(
            "author-only", "An agent never sets the command loom runs at your click; only you do, in Settings › Notes"
        )
    command = command.strip()
    if command:
        check_command(command)
    table = _read()
    key = _key(root)
    if command and command != command_for(root) and not confirm(command, root):
        raise NoteRefused(
            "not-confirmed", "The command was not set: it is set only when you choose Set in the dialog loom opens"
        )
    if command:
        table[key] = {**table.get(key, {}), "command": command}
    else:
        table.pop(key, None)
    lines = [
        "# Each quilt's new-note command, by where the quilt lies: loom runs it with no shell at your click on New note.",
        "# Written by loom from Settings › Notes; an agent never sets it.",
        "",
    ]
    for quilt, keys in sorted(table.items()):
        lines.append(f"[{json.dumps(quilt, ensure_ascii=False)}]")
        lines += [f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in keys.items() if isinstance(v, str)]
        lines.append("")
    path = commands_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".notes-", suffix=".toml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write("\n".join(lines))
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


@dataclass(frozen=True)
class Request:
    """What a new note is given: the link, the quoted words, a name for the place, the notes directory and the quilt, the last two absolute."""

    link: str
    quote: str
    title: str
    dir: str
    quilt: str

    def as_dict(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in REQUEST_KEYS}


def request(root: Path, link: str, quote: str = "", title: str = "") -> Request:
    """The request for a new note on `link`, checked: a `quilt:` link with no space or control character, words and name of bounded length."""
    from loom.scan.quilt import load_quilt

    if not link.startswith("quilt:") or re.search(r"[\s\x00-\x1f\x7f]", link):
        raise NoteRefused("bad-field", "link must be a quilt: link with no space in it")
    if len(quote) > MAX_QUOTE or len(title) > MAX_TITLE:
        raise NoteRefused("bad-field", "the words or the name are too long for a note")
    if "\x00" in quote or "\x00" in title:
        raise NoteRefused("bad-field", "the words hold a NUL character")
    quilt = load_quilt(root)
    return Request(
        link=link,
        quote=quote,
        title=title.strip(),
        dir=str((root / quilt.config.notes_dir).resolve()),
        quilt=str(Path(root).resolve()),
    )


def argv_for(command: str, req: Request, request_file: str) -> list[str]:
    """The command's arguments with each placeholder replaced inside its own argument; nothing is split after replacing, so no value becomes another argument."""
    values = {**req.as_dict(), "request": request_file}
    return [_PLACEHOLDER.sub(lambda m: values[m.group(1)], arg) for arg in check_command(command)]


def write_request(req: Request) -> Path:
    """The request file: exactly `REQUEST_KEYS`, as JSON, in the temporary folder, readable by this user alone. Left for the editor to read; the system clears its temporary folder."""
    fd, name = tempfile.mkstemp(prefix="loom-note-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(req.as_dict(), out, ensure_ascii=False)
    return Path(name)


@dataclass(frozen=True)
class Outcome:
    """How a new note went: `ran` the person's command (with what it said when it failed), or `wrote` a Markdown note, at `path`, and opened it."""

    how: str
    said: str = ""
    path: str = ""


def run(root: Path, req: Request, *, actor: str | None) -> Outcome:
    """Make a new note: run the person's command for this quilt, or with none set write a Markdown note in the notes directory and open it with the system's default app.

    Refused (`author-only`) to an agent. The command runs with no shell, in the quilt, its output kept in temporary files; loom waits `WAIT` seconds for it to finish, and one still running then is left to run.
    """
    from loom.identity import agents_act

    if agents_act(actor):
        raise NoteRefused("author-only", "An agent writes its notes as files; New note runs your command at your click")
    command = command_for(root)
    if not command:
        return _stub(root, req)
    argv = argv_for(command, req, str(write_request(req)) if "{request}" in command else "")
    with tempfile.TemporaryFile() as out:
        try:
            proc = subprocess.Popen(
                argv, cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True
            )
        except FileNotFoundError as exc:
            raise NoteRefused("command-failed", f"{argv[0]} is not a program on this computer's PATH") from exc
        except OSError as exc:
            raise NoteRefused("command-failed", f"{argv[0]} could not be started: {exc}") from exc
        try:
            code = proc.wait(timeout=WAIT)
        except subprocess.TimeoutExpired:
            return Outcome("ran", "still running")
        out.seek(0)
        said = out.read(4000).decode("utf-8", errors="replace").strip()
    if code != 0:
        raise NoteRefused("command-failed", f"{argv[0]} stopped with status {code}" + (f": {said}" if said else ""))
    return Outcome("ran", said)


def stub_text(req: Request) -> str:
    """The Markdown note written when no command is set: the name, the quoted words, and the link."""
    head = req.title or "A note"
    quoted = "".join(f"> {line}\n" for line in req.quote.splitlines() if line.strip()) if req.quote.strip() else ""
    return f"# {head}\n\n{quoted}{chr(10) if quoted else ''}[{head}]({req.link})\n\n"


def _slug(title: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return words[:60].rstrip("-") or "note"


def _stub(root: Path, req: Request) -> Outcome:
    """Write `stub_text` as a new Markdown file in the notes directory, named by the day and the place, and open it."""
    from loom.files import launch
    from loom.scan.quilt import load_quilt
    from loom.writes import WriteRefused, put

    quilt = load_quilt(root)
    folder = quilt.config.notes_dir
    stem = f"{date.today().isoformat()}-{_slug(req.title)}"
    for n in range(1, 1000):
        rel = f"{folder}/{stem}{'' if n == 1 else f'-{n}'}.md"
        if not (root / rel).exists():
            break
    try:
        put(root, quilt.history_dir, rel, stub_text(req).encode("utf-8"), kind="new-note", new=True)
    except WriteRefused as exc:
        raise NoteRefused(exc.code, exc.message) from exc
    path = root / rel
    import sys

    if sys.platform == "darwin":
        launch(["open", str(path)])
    elif sys.platform.startswith("linux"):
        launch(["xdg-open", str(path)])
    return Outcome("wrote", path=rel)
