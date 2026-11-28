"""A person's look at the LaTeX files agents may edit: each file's text as they last saw it, and which files changed since.

A look is `.loom/records/looked/<reviewer>.json`, `{who, when, files: {path: hash}, deny}`, each file's text stored exactly in the history's `texts/` (`write_raw`). It watches the LaTeX documents agents may edit (`watching`): each open `.tex` file, one the viewer shows that reads as UTF-8 and is at most 1 MB, that no `[agents] deny` entry or protection keeps from agents (`agents.denied_by`); Markdown, notes, bibliographies, plain text and every other file are never watched, so a change to one is never listed and never waits to be kept. A place agents are denied is the person's own, so a change there is never listed and not tracked; loom cannot tell who saved a file, and where agents may edit, a change to a LaTeX file is listed whoever made it. `deny` is the list the look was last brought to: a file opened to agents since goes in as it stands, and one closed to them keeps what the look held, so a change waiting there is listed again if it is opened (`read_look`). It is personal, by the reviewer name Review resolves, and taken when the person acts or when `loom serve` starts and finds none; every act the person makes through loom puts what it wrote into it (`writes._follow_look`, and Keep, the undo, Discard and a tick themselves), so it records what the person did, never a save (P13). What changed since it is cut into changes by words, and kept or discarded one by one, in `pending.py`.
"""

from __future__ import annotations

import dataclasses
import difflib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom import own
from loom.clock import stamp
from loom.paths import LOOKED

if TYPE_CHECKING:
    from loom.scan.quilt import Quilt, QuiltConfig

#: What a look holds of a file that was not there at the look and whose place has since been closed to agents (`_align`): an agent's new file waiting there, listed again as new once the place is opened, never taken in unseen. Read as no entry (`held`).
ABSENT = ""

#: The ledger's line for a change discarded, a plain line beside the steps; a keep writes `history.acts.KEEP`, and taking a look writes nothing.
UNDO = "undo"
#: Lines of context around a change, as `unified_diff` prints them.
CONTEXT = 3


@dataclass
class Look:
    """One person's look: who, when, each watched file's text by its hash, whose look it was carried over from (`read_look`), '' for one taken under this name, the `[agents] deny` list it was last brought to, None for a look that does not say, and `closed`, the hash of the text each file in a place closed to agents held as it closed, by which a file renamed there meanwhile is found (`_align`)."""

    who: str
    when: str
    files: dict[str, str] = field(default_factory=dict)
    carried: str = ""
    deny: list[str] | None = None
    closed: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"who": self.who, "when": self.when, "files": dict(sorted(self.files.items()))}
        if self.carried:
            out["carried"] = self.carried
        if self.deny is not None:
            out["deny"] = list(self.deny)
        if self.closed:
            out["closed"] = dict(sorted(self.closed.items()))
        return out


@dataclass(frozen=True)
class Change:
    """One open file changed since the look: `changed`, `new` (not there at the look) or `gone` (there at the look, not now)."""

    path: str
    kind: str
    before: str | None  # the look's hash
    after: str | None  # the hash now
    diff: str  # unified, `a/PATH` to `b/PATH`


def look_path(root: Path, who: str) -> Path:
    from loom.since import slug

    return root / LOOKED / f"{slug(who)}.json"


def _load(path: Path) -> Look | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        files = {str(k): str(v) for k, v in data.get("files", {}).items()}
        deny = data.get("deny")
        closed = {str(k): str(v) for k, v in (data.get("closed") or {}).items()}
        return Look(
            str(data["who"]),
            str(data["when"]),
            files,
            str(data.get("carried", "")),
            [str(x) for x in deny] if isinstance(deny, list) else None,
            closed,
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def watching(config: QuiltConfig, root: Path) -> Callable[[str], bool]:
    """Whether the look watches quilt-relative `rel`: a LaTeX source file (`.tex`) in a place agents may edit, by the predicate the door's refusal and the agents' permission files read (`agents.denied_by`), outside a Lake project (`scan.source.lake_project`).

    Only LaTeX is watched, since keeping a change there is a reading of mathematics; a change to Markdown, notes, a bibliography or any other file is never listed. A place agents are denied is the person's own and a Lake project the agents' own, and a change in either is never listed either. Each folder's Lake test is made once per predicate.
    """
    from loom.agents import denied_by
    from loom.scan.source import lake_project

    known: dict[str, bool] = {}
    return lambda rel: is_latex(rel) and denied_by(config, rel) is None and lake_project(root, rel, known) is None


def is_latex(rel: str) -> bool:
    """Whether quilt-relative `rel` is a LaTeX source file, the only kind the look watches (`watching`)."""
    return rel.lower().endswith(".tex")


def unwatched(config: QuiltConfig) -> list[str]:
    """The places the look leaves to the person, as Review and `loom changes` name them: the config, which no agent edits, then each `[agents] deny` entry as written."""
    from loom.agents import CONFIG

    return [CONFIG, *config.agents_deny]


def read_look(root: Path, who: str) -> Look | None:
    """`who`'s last look, brought to the `[agents] deny` list now (`_align`); None before the quilt has any (or when the file does not parse, which is the same thing).

    A name with no look of its own, as after the person sets their name in Settings, is given the newest look the quilt holds, saying whose (`carried`), and kept under the new name: a fresh first look would take in unseen every edit waiting since that one.
    """
    if not who:
        return None
    own = _load(look_path(root, who))
    if own is not None:
        return _align(root, own)
    others = [x for p in sorted((root / LOOKED).glob("*.json")) if (x := _load(p)) is not None]
    if not others:
        return None
    newest = max(others, key=lambda x: x.when)
    carried = Look(who, newest.when, dict(newest.files), newest.who, newest.deny, dict(newest.closed))
    _write(root, carried)
    return _align(root, carried)


def _align(root: Path, look: Look) -> Look:
    """`look` brought to the `[agents] deny` list in force, written where that moved anything.

    A file opened to agents since the look's own list goes in as it stands, so the person's edits there before it was opened are never listed; one closed to them keeps what the look held, so a change waiting there is listed again if it is opened, and one the look did not hold, made since it, is kept as `ABSENT`, so it is listed as new then rather than taken in unseen. Each file of a place that closes also leaves the hash of its text as it closed (`closed`), so a file renamed while the place is closed is found by its text when it opens: its entry moves to the new path, an agent's new file is listed as new there and an agent's waiting change is listed there, never taken in as the file stands. A look that names no list is taken as brought to the one in force. A config loom cannot read leaves the look as it is.
    """
    from loom.records.snapshots import write_raw
    from loom.scan.hashing import sha256
    from loom.scan.quilt import load_quilt

    try:
        quilt = load_quilt(root)
    except Exception:  # noqa: BLE001 -- no config, no list to bring the look to
        return look
    deny = list(quilt.config.agents_deny)
    if look.deny is None or look.deny == deny:
        look.deny = deny
        return look
    was = watching(dataclasses.replace(quilt.config, agents_deny=look.deny), root)
    now = watching(quilt.config, root)
    texts = open_texts(quilt)
    for rel, text in texts.items():
        if was(rel) and not now(rel):
            if rel not in look.files:
                # made since the look while agents could write there: listed as new if the place is opened again
                look.files[rel] = ABSENT
            look.closed[rel] = sha256(text)
    # each file of a closed place gone since it closed, by the text it held then, one list per text since files may share one: a file renamed meanwhile is found by it, one gone file for each
    moved: dict[str, list[str]] = {}
    for rel, h in sorted(look.closed.items()):
        if rel not in texts and rel in look.files:
            moved.setdefault(h, []).append(rel)
    for rel, text in sorted(texts.items()):
        if now(rel) and not was(rel) and rel not in look.files:
            gone = moved.get(sha256(text))
            if gone:
                look.files[rel] = look.files.pop(gone.pop(0))
            else:
                look.files[rel] = write_raw(root, text, quilt.history_dir)
    look.closed = {rel: h for rel, h in look.closed.items() if not now(rel) and rel in look.files}
    look.deny = deny
    _write(root, look)
    return look


def _write(root: Path, look: Look) -> None:
    p = look_path(root, look.who)
    own.mkdir(p.parent, root=root)
    tmp = p.with_name(p.name + ".loom-tmp")
    own.write_text(tmp, json.dumps(look.to_json(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8", root=root)
    own.replace(tmp, p, root=root)


def open_texts(quilt: Quilt) -> dict[str, str]:
    """Every open text file's text by its path: shown, UTF-8, at most 1 MB and none of LaTeX's auxiliary files."""
    from loom.files import TEXT_LIMIT, Shown, is_latex_aux

    out: dict[str, str] = {}
    for rel in Shown.of(quilt).walk():
        if is_latex_aux(rel):
            continue
        p = quilt.root / rel
        try:
            if p.stat().st_size > TEXT_LIMIT:
                continue
            data = p.read_bytes()
            if b"\x00" in data[:8192]:
                continue
            out[rel] = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return out


def held(look: Look, rel: str) -> str | None:
    """The hash `look` holds of `rel`'s text, None where it holds none or holds the file as absent at the look (`ABSENT`)."""
    return look.files.get(rel) or None


def watched_texts(quilt: Quilt) -> dict[str, str]:
    """The open text files the look watches (`watching`), each one's text by its path."""
    watched = watching(quilt.config, quilt.root)
    return {rel: text for rel, text in open_texts(quilt).items() if watched(rel)}


def take(quilt: Quilt, who: str) -> Look:
    """A new look by `who` at every watched file now, each text stored; what an earlier look held of a file agents are denied now is kept as it was, with the text it held as its place closed (`_align`)."""
    from loom.records.snapshots import write_raw

    hist = quilt.history_dir
    files = {rel: write_raw(quilt.root, text, hist) for rel, text in watched_texts(quilt).items()}
    old = _load(look_path(quilt.root, who))
    closed: dict[str, str] = {}
    if old is not None:
        watched = watching(quilt.config, quilt.root)
        files |= {rel: h for rel, h in old.files.items() if is_latex(rel) and not watched(rel)}
        closed = {rel: h for rel, h in old.closed.items() if rel in files and not watched(rel)}
    look = Look(who, stamp(), files, deny=list(quilt.config.agents_deny), closed=closed)
    _write(quilt.root, look)
    return look


def first(quilt: Quilt) -> Look | None:
    """The reviewer's first look, taken when they have none (`read_look` carries another's where the quilt holds one): when the person makes a quilt or brings a paper in, and when `loom serve` starts, so an agent's edit before then is listed. None without a reviewer name."""
    from loom.scan.quilt import reviewer_identity

    who = reviewer_identity(quilt.root)[0]
    if not who:
        return None
    return read_look(quilt.root, who) or take(quilt, who)


def _lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def changes(quilt: Quilt, who: str) -> list[Change]:
    """What changed in the watched files since `who`'s last look, by path; empty before their first."""
    from loom.files import is_latex_aux
    from loom.records.snapshots import read_raw
    from loom.scan.hashing import sha256

    look = read_look(quilt.root, who)
    if look is None:
        return []
    now = watched_texts(quilt)
    watched = watching(quilt.config, quilt.root)
    out: list[Change] = []
    for rel in sorted(set(now) | {f for f in look.files if not is_latex_aux(f) and watched(f)}):
        before_hash = held(look, rel)
        text = now.get(rel)
        after_hash = sha256(text) if text is not None else None
        if before_hash == after_hash:
            continue
        old = (read_raw(quilt.root, before_hash, quilt.history_dir) or "") if before_hash else ""
        kind = "new" if before_hash is None else "gone" if text is None else "changed"
        a, b = _lines(old), _lines(text or "")
        diff = "".join(
            difflib.unified_diff(
                a,
                b,
                fromfile=f"a/{rel}" if before_hash else "/dev/null",
                tofile=f"b/{rel}" if text is not None else "/dev/null",
                n=CONTEXT,
            )
        )
        out.append(Change(rel, kind, before_hash, after_hash, diff))
    return out


def keep_all(quilt: Quilt, who: str) -> Look:
    """A new look by `who` at every watched file, with a `keep` line naming the files that had changed since the last; a first look writes none."""
    from loom.history.acts import KEEP
    from loom.history.ledger import append_entry

    moved = [c.path for c in changes(quilt, who)] if read_look(quilt.root, who) else []
    look = take(quilt, who)
    if moved:
        append_entry(quilt.history_dir, KEEP, {"who": who, "paths": moved}, who)
    return look


def take_line(quilt: Quilt, who: str, path: str, before: str, after: str, line: int) -> None:
    """Take the one line a person just changed in the viewer into their look, so a change they made there is not listed back to them (`loom.tasks`).

    Every other change to the file stays listed. A line the look does not hold as `before` does is part of a change already listed, and stays in it. `line` is a line of `tasks.split_lines`; no ledger line, since the act that called this writes its own.
    """
    from loom.records.snapshots import read_raw, write_raw
    from loom.tasks import split_lines

    if not watching(quilt.config, quilt.root)(path):
        return  # a place agents are denied: nothing there is listed
    look = read_look(quilt.root, who)
    seen = look.files.get(path) if look else None
    old = read_raw(quilt.root, seen, quilt.history_dir) if seen else None
    if look is None or old is None:
        return
    if old == before:
        look.files[path] = write_raw(quilt.root, after, quilt.history_dir)
        _write(quilt.root, look)
        return
    held, now = split_lines(old), split_lines(before)
    for tag, i1, _i2, j1, j2 in difflib.SequenceMatcher(None, held, now).get_opcodes():
        if tag == "equal" and j1 <= line < j2:
            held[i1 + line - j1] = split_lines(after)[line]
            look.files[path] = write_raw(quilt.root, "".join(held), quilt.history_dir)
            _write(quilt.root, look)
            return
