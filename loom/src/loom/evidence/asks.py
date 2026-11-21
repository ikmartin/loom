"""`.loom/records/asks/log.jsonl`: what a person asked of an agent and an agent of a person, and the few things said of it after.

A stack an agent may take from, not a harness: nothing is assigned, ranked or scheduled, and no agent is woken. The log records the asking (`asked`) and what was said afterwards (`took`, `done`, `answered`, `withdrawn`); whether an ask is still open is computed from what exists now, never recorded (`docs/specs/evidence.md` §4). Appended under the log's lock and never rewritten. A line that is not one of these events, or an event naming no ask the log holds, is skipped and reported as `loom:foreign-asks`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from loom.clock import stamp
from loom.evidence.log import AT
from loom.evidence.subjects import HASH, NODE, REFERENCE, Subject, Who, label_problem
from loom.locks import locked
from loom.paths import ASK_LOG
from loom.records.ids import ASK, SESSION, draw

#: An ask's id: `t-`, the day it was asked, and a random token.
ID = re.compile(ASK)
EVENTS = ("asked", "took", "done", "answered", "withdrawn")
#: What can be asked, of whom, and by which hand: `what` -> (`to`, the hand that asks). A person asks an agent; an agent asks a person a question or for a paper.
WHATS: dict[str, tuple[str, str]] = {
    "read": ("agent", "person"),
    "digest": ("agent", "person"),
    "ask": ("agent", "person"),
    "correct": ("agent", "person"),
    "restate": ("agent", "person"),
    "which-result": ("agent", "person"),
    "formalize": ("agent", "person"),
    "question": ("person", "agent"),
    "paper": ("person", "agent"),
}
#: What is answered by an `answered` event rather than closed by what it produces: a question either way.
ANSWERED = frozenset({"ask", "question"})
#: How much of a work a `digest` takes in.
SCOPES = ("uses", "marked", "chosen", "all")
#: The most choices a question offers, and the longest a choice is.
CHOICES, CHOICE_LENGTH = 6, 200
#: The longest question, answer or words a person adds.
WORDS = 4000
_COMMON = {"event", "at", "by"}


class AskRefused(ValueError):
    """An ask or an event a writer built that is not of its shape, or that its hand may not make: nothing was written."""


@dataclass
class Ask:
    """One ask as it stands in the log: the asking, and every event said of it since, oldest first."""

    id: str
    what: str
    to: str
    by: Who
    at: str
    on: Mapping[str, Any]
    origin: tuple[str, ...]
    words: str
    fields: Mapping[str, Any]
    took: list[Mapping[str, Any]] = field(default_factory=list)
    done: list[Mapping[str, Any]] = field(default_factory=list)
    answers: list[Mapping[str, Any]] = field(default_factory=list)
    withdrawn: Mapping[str, Any] | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """A field of the `asked` line, or `default`."""
        return self.fields.get(key, default)


@dataclass
class Asks:
    """Every ask in the order asked, and the problems of the lines skipped."""

    asks: dict[str, Ask] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def log_path(root: Path) -> Path:
    """The log's file in `root`."""
    return root / ASK_LOG


_MEMO: dict[str, tuple[tuple[int, int, int], Asks]] = {}


def replay(root: Path) -> Asks:
    """Every ask of the quilt as it stands, and one problem for each line skipped.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Asks
        In the order asked; read again only when the file's size, time or inode moved since the last replay. A caller must not change what it is given.
    """
    path = log_path(root)
    try:
        st = path.stat()
    except FileNotFoundError:
        return Asks()
    key = (st.st_size, st.st_mtime_ns, st.st_ino)
    held = _MEMO.get(str(path))
    if held is not None and held[0] == key:
        return held[1]
    found = _read(path.read_text(encoding="utf-8"))
    _MEMO[str(path)] = (key, found)
    return found


def _read(text: str) -> Asks:
    """Two passes: every `asked` first, then the events, so a line a merge put above its ask still finds it; problems in the order of their lines."""
    out = Asks()
    later: list[tuple[int, dict[str, Any]]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            out.problems.append(f"{ASK_LOG}:{n}: not JSON ({exc.msg})")
            continue
        if not isinstance(raw, dict) or raw.get("event") not in EVENTS:
            out.problems.append(f"{ASK_LOG}:{n}: not an ask's event")
            continue
        if raw["event"] != "asked":
            later.append((n, raw))
            continue
        try:
            made = parse_ask(raw)
        except ValueError as exc:
            out.problems.append(f"{ASK_LOG}:{n}: {exc}")
            continue
        out.asks.setdefault(made.id, made)
    for n, raw in later:
        found = out.asks.get(str(raw.get("task")))
        try:
            if found is None:
                raise ValueError(f"{raw['event']} names {raw.get('task')!r}, which is no ask in the log")
            apply(found, raw)
        except ValueError as exc:
            out.problems.append(f"{ASK_LOG}:{n}: {exc}")
    out.problems.sort(key=lambda p: int(p.split(":", 2)[1]))
    return out


def _keys(raw: dict[str, Any], required: set[str], optional: frozenset[str] = frozenset()) -> None:
    have = set(raw) - _COMMON
    missing, extra = required - have, have - required - optional
    if missing:
        raise ValueError(f"lacks {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"has {', '.join(sorted(extra))}, which this {raw.get('what') or raw.get('event')} does not")


def _words(value: Any, what: str, *, empty: bool = True, most: int = WORDS) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > most:
        raise ValueError(f"{what} is {'a' if empty else 'a non-empty'} string of at most {most} characters")
    return value


def _at(raw: dict[str, Any]) -> str:
    at = raw.get("at")
    if not isinstance(at, str) or not AT.fullmatch(at):
        raise ValueError(f"{at!r} is not a time")
    return at


def place_problem(on: Any) -> str | None:
    """Why `on` is not a place an ask can be tied to; None when it is.

    One of `{node}`, `{label}`, `{block: {key, hash, context}}`, `{ref, page?}` or `{document}`.
    """
    if not isinstance(on, dict) or not on:
        return "on is an object naming a place"
    if set(on) == {"node"}:
        return None if isinstance(on["node"], str) and NODE.fullmatch(on["node"]) else "on's node is not a node's id"
    if set(on) == {"label"}:
        return label_problem(on["label"])
    if set(on) == {"block"}:
        b = on["block"]
        if not (
            isinstance(b, dict) and set(b) == {"key", "hash", "context"} and isinstance(b["key"], str) and b["key"]
        ):
            return "on's block has key, hash and context"
        if not isinstance(b["hash"], str) or not HASH.fullmatch(b["hash"]) or not isinstance(b["context"], dict):
            return "on's block has key, hash and context"
        return None
    if set(on) in ({"ref"}, {"ref", "page"}):
        if not isinstance(on["ref"], str) or not REFERENCE.fullmatch(on["ref"]):
            return "on's ref is not a reference's id"
        page = on.get("page", 1)
        return None if isinstance(page, int) and not isinstance(page, bool) and page >= 1 else "on's page is a number"
    if set(on) == {"document"}:
        return None if isinstance(on["document"], str) and on["document"] else "on's document is a path"
    return "on names a node, a label, a block, a work or a document"


def _node_list(value: Any, what: str) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and NODE.fullmatch(v) for v in value):
        raise ValueError(f"{what} is a non-empty list of node ids")


def _subject_list(value: Any, what: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{what} is a list")
    for v in value:
        Subject.from_dict(v, ("node", "label"))


def _link(value: Any) -> None:
    """A link a person is given to open: http or https, with a host, and nothing a browser would run."""
    if not isinstance(value, str) or len(value) > 2000 or any(c.isspace() for c in value):
        raise ValueError("link is one http or https address")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("link is one http or https address")


def _what_fields(raw: dict[str, Any]) -> None:
    """The fields each `what` adds to an `asked` line (`docs/specs/evidence.md` §4.1)."""
    what = raw["what"]
    base = {"id", "what", "to", "on", "from", "words"}
    if what == "read":
        _keys(raw, base | {"nodes"})
        _node_list(raw["nodes"], "nodes")
    elif what == "digest":
        _keys(raw, base | {"ref", "scope"}, frozenset({"nodes", "marks"}))
        if not isinstance(raw["ref"], str) or not REFERENCE.fullmatch(raw["ref"]):
            raise ValueError("ref is not a reference's id")
        if raw["scope"] not in SCOPES:
            raise ValueError(f"scope is one of {', '.join(SCOPES)}")
        if "nodes" in raw:
            _node_list(raw["nodes"], "nodes")
        if "marks" in raw and (
            not isinstance(raw["marks"], list) or not all(isinstance(m, str) and m for m in raw["marks"])
        ):
            raise ValueError("marks is a list of the marks' ids")
    elif what == "formalize":
        _keys(raw, base | {"target", "state", "prove", "assume"})
        Subject.from_dict(raw["target"], ("node", "label"))
        for k in ("state", "prove", "assume"):
            _subject_list(raw[k], k)
    elif what == "restate":
        _keys(raw, base | {"target", "differs"})
        Subject.from_dict(raw["target"], ("node", "label"))
        _words(raw["differs"], "differs")
    elif what == "which-result":
        _keys(raw, base | {"cites"})
        if set(raw["on"]) != {"block"}:
            raise ValueError("a which-result is on the citing block")
        if not isinstance(raw["cites"], str) or not REFERENCE.fullmatch(raw["cites"]):
            raise ValueError("cites is not a reference's id")
    elif what == "correct":
        _keys(raw, base | {"text"})
        if set(raw["on"]) != {"node"}:
            raise ValueError("a correct is on the node to correct")
        _words(raw["text"], "text")
    elif what == "ask":
        _keys(raw, base | {"text"}, frozenset({"quote"}))
        _words(raw["text"], "text", empty=False)
        if "quote" in raw:
            _words(raw["quote"], "quote", empty=False)
    elif what == "question":
        _keys(raw, base | {"text"}, frozenset({"choices", "quote"}))
        _words(raw["text"], "text", empty=False)
        if "quote" in raw:
            _words(raw["quote"], "quote", empty=False)
        choices = raw.get("choices", [])
        if not isinstance(choices, list) or len(choices) > CHOICES:
            raise ValueError(f"choices is a list of at most {CHOICES}")
        for c in choices:
            _words(c, "a choice", empty=False, most=CHOICE_LENGTH)
        if len(set(choices)) != len(choices):
            raise ValueError("two choices are the same")
    elif what == "paper":
        _keys(raw, base | {"ref", "link", "want"})
        if not isinstance(raw["ref"], str) or not REFERENCE.fullmatch(raw["ref"]):
            raise ValueError("ref is not a reference's id")
        _link(raw["link"])
        if raw["want"] not in ("pdf", "tex"):
            raise ValueError("want is pdf or tex")


def parse_ask(raw: dict[str, Any]) -> Ask:
    """Read one `asked` line, checked whole.

    Parameters
    ----------
    raw : dict
        The line, parsed, with `event` `asked`.

    Returns
    -------
    Ask
        With no events yet.

    Raises
    ------
    ValueError
        Naming the first thing wrong with it.
    """
    aid = raw.get("id")
    if not isinstance(aid, str) or not ID.fullmatch(aid):
        raise ValueError(f"{aid!r} is not an ask's id")
    try:
        at = _at(raw)
        by = Who.from_dict(raw.get("by"))
        what, to = raw.get("what"), raw.get("to")
        if what not in WHATS:
            raise ValueError(f"{what!r} is not something to ask")
        if (to, by.kind) != WHATS[what]:
            raise ValueError(f"a {what} is not asked of {to!r} by {by.kind}")
        problem = place_problem(raw.get("on"))
        if problem:
            raise ValueError(problem)
        origin = raw.get("from")
        if not isinstance(origin, list) or not all(isinstance(d, str) and d for d in origin):
            raise ValueError("from is a list of the drafts it was asked for")
        _words(raw.get("words"), "words")
        _what_fields(raw)
    except ValueError as exc:
        raise ValueError(f"{aid}: {exc}") from None
    return Ask(aid, str(what), str(to), by, at, raw["on"], tuple(origin), raw["words"], raw)


def apply(ask: Ask, raw: dict[str, Any]) -> None:
    """Add one event to its ask, after checking it is of its shape and that its hand may say it.

    Raises
    ------
    ValueError
        Naming what is wrong; the ask is unchanged.
    """
    event = raw["event"]
    try:
        _at(raw)
        by = Who.from_dict(raw.get("by"))
        if event in ("took", "done"):
            if ask.to != "agent" or by.kind != "agent":
                raise ValueError(f"only an agent says it {event} a task asked of an agent")
            if event == "took":
                _keys(raw, {"task", "session"})
                if not isinstance(raw["session"], str) or not re.fullmatch(SESSION, raw["session"]):
                    raise ValueError("session is not a session's id")
            else:
                _keys(raw, {"task", "made"})
                if not isinstance(raw["made"], list) or not all(isinstance(m, str) and m for m in raw["made"]):
                    raise ValueError("made is a list of what it produced")
        elif event == "answered":
            _keys(raw, {"task", "words"}, frozenset({"choice"}))
            if by.kind != ask.to:
                raise ValueError(f"only {'an agent' if ask.to == 'agent' else 'the person'} answers it, not {by.kind}")
            if ask.what not in ANSWERED:
                raise ValueError("only a question is answered")
            choice = raw.get("choice")
            choices = ask.get("choices", [])
            if choice is not None and (
                not isinstance(choice, int) or isinstance(choice, bool) or not 0 <= choice < len(choices)
            ):
                raise ValueError("choice is the number of one of the question's choices")
            _words(raw["words"], "words")
            if choice is None and not raw["words"].strip():
                raise ValueError("an answer is a choice, words, or both")
        else:  # withdrawn
            _keys(raw, {"task"})
            if not may_withdraw(ask, by):
                raise ValueError(f"{by.name or by.kind} may not withdraw an ask another agent made")
    except ValueError as exc:
        raise ValueError(f"{ask.id}: {exc}") from None
    if event == "took":
        ask.took.append(raw)
    elif event == "done":
        ask.done.append(raw)
    elif event == "answered":
        ask.answers.append(raw)
    elif ask.withdrawn is None:
        ask.withdrawn = raw


def may_withdraw(ask: Ask, by: Who) -> bool:
    """A person withdraws any ask; an agent only one it made."""
    return by.kind == "person" or (by.kind == "agent" and ask.by == by)


def _append(root: Path, line: dict[str, Any]) -> None:
    with log_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def ask(root: Path, by: Who, what: str, to: str, on: Mapping[str, Any], **fields: Any) -> Ask:
    """Record an ask, its id drawn under the log's lock.

    Parameters
    ----------
    root : Path
        The quilt.
    by : Who
        Who asks: a person asks an agent, an agent asks a person (`WHATS`).
    what : str
        One of `WHATS`.
    to : str
        `agent` or `person`.
    on : mapping
        The place it is tied to (`place_problem`).
    **fields
        `from` (as `origin`), `words`, and the fields of `what` (`docs/specs/evidence.md` §4.1).

    Returns
    -------
    Ask

    Raises
    ------
    AskRefused
        When it is not of its shape; nothing was written.
    """
    at = stamp()
    origin = list(fields.pop("origin", []))
    line: dict[str, Any] = {
        "event": "asked",
        "at": at,
        "by": by.to_dict(),
        "what": what,
        "to": to,
        "on": dict(on),
        "from": origin,
        "words": fields.pop("words", ""),
        **fields,
    }
    with locked(log_path(root)):
        line["id"] = draw(f"t-{at[:10]}-", set(replay(root).asks))
        try:
            made = parse_ask(line)
        except ValueError as exc:
            raise AskRefused(str(exc)) from None
        _append(root, line)
    return made


def say(root: Path, by: Who, event: str, task: str, **fields: Any) -> Ask:
    """Record an event on an ask: `took`, `done`, `answered` or `withdrawn`.

    Parameters
    ----------
    root : Path
        The quilt.
    by : Who
        Who says it.
    event : str
        One of `EVENTS` but `asked`.
    task : str
        The ask's id.
    **fields
        The event's own: `session` for `took`, `made` for `done`, `words` and `choice` for `answered`.

    Returns
    -------
    Ask
        As it stands after the event.

    Raises
    ------
    AskRefused
        `no-such-ask`, or the event is not of its shape or not its hand's to say; nothing was written.
    """
    line: dict[str, Any] = {"event": event, "at": stamp(), "by": by.to_dict(), "task": task, **fields}
    with locked(log_path(root)):
        found = replay(root).asks.get(task)
        if found is None:
            raise AskRefused(f"{task} is no ask in this quilt")
        try:
            apply(_copy(found), line)
        except ValueError as exc:
            raise AskRefused(str(exc)) from None
        _append(root, line)
        return replay(root).asks[task]


def _copy(found: Ask) -> Ask:
    """An ask to try an event on without touching the memoised replay."""
    return Ask(**{**found.__dict__, "took": [], "done": [], "answers": [], "withdrawn": None})
