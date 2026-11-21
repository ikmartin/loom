"""`.loom/records/asks/log.jsonl`: what a person asked of an agent and an agent of a person, and the few things said of it after.

A stack an agent may take from, not a harness: nothing is assigned, ranked or scheduled, and no agent is woken. The log records the asking (`asked`) and what was said afterwards (`took`, `done`, `answered`, `withdrawn`); whether an ask is still open is computed from what exists now, never recorded (`docs/specs/evidence.md` §4). Appended under the log's lock and never rewritten. A line that is not one of these events, or an event naming no ask the log holds, is skipped and reported as `loom:foreign-asks`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from loom.clock import stamp
from loom.evidence.log import AT, Evidence, Read, Record, append_line, grown, stopped
from loom.evidence.status import statements_of
from loom.evidence.subjects import HASH, NODE, REFERENCE, Subject, Who, label_problem
from loom.evidence.web import Here, Web
from loom.locks import locked
from loom.paths import ASK_LOG
from loom.records.ids import ASK, EDIT, SESSION, draw

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
    """Every ask in the order asked, and the problems of the lines skipped.

    `pending` holds an event read before the ask it names, as a merge can order them, until that ask is read; one never found is a problem.
    """

    asks: dict[str, Ask] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    _bad: list[tuple[int, str]] = field(default_factory=list, repr=False)
    _pending: list[tuple[int, dict[str, Any]]] = field(default_factory=list, repr=False)

    def copy(self) -> Asks:
        """A copy a replay extends while a reader holds the first; an ask an event changes is copied before it changes."""
        return Asks(dict(self.asks), list(self.problems), list(self._bad), list(self._pending))

    def _own(self, ask_id: str) -> Ask:
        """The ask to change, copied so a reader of an earlier replay keeps what it read."""
        found = self.asks[ask_id]
        mine = Ask(
            **{**found.__dict__, "took": list(found.took), "done": list(found.done), "answers": list(found.answers)}
        )
        self.asks[ask_id] = mine
        return mine


def log_path(root: Path) -> Path:
    """The log's file in `root`."""
    return root / ASK_LOG


_MEMO: dict[str, tuple[Read, Asks]] = {}


def replay(root: Path) -> Asks:
    """Every ask of the quilt as it stands, and one problem for each line skipped.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Asks
        In the order asked. A replay reads on from where the last one stopped while the file is that one grown, and reads it whole otherwise (`log.grown`); what it returns is a copy a later replay does not change, and a caller must not change it either.
    """
    path = log_path(root)
    if not path.is_file():
        return Asks()
    held = _MEMO.get(str(path))
    found = grown(path, held[0] if held else None)
    if found is None or held is None:
        with path.open("rb") as fh:
            data = fh.read()
        end = data.rfind(b"\n") + 1
        chunk, start, rest, value, lines = data[:end], 0, data[end:], Asks(), 0
    else:
        chunk, start, rest = found
        if not chunk and not rest.strip():
            return held[1]
        value, lines = held[1].copy(), held[0].lines
    _read(chunk.decode("utf-8"), value, lines)
    read = stopped(path, start, chunk, lines)
    _MEMO[str(path)] = (read, value)
    if rest.strip():
        # a last line with no line feed: read when it is a whole line of JSON, as a hand-written one is, and read again once ended
        try:
            text = rest.decode("utf-8")
            json.loads(text)
        except (ValueError, UnicodeDecodeError):
            return value
        value = _read(text, value.copy(), read.lines)
    return value


def _read(text: str, out: Asks | None = None, before: int = 0) -> Asks:
    """Read lines of the log into `out`, numbering them from `before`: each `asked` as it comes, each event onto its ask, or held until its ask is read; problems in the order of their lines."""
    out = out if out is not None else Asks()
    for n, line in enumerate(text.splitlines(), before + 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            out._bad.append((n, f"not JSON ({exc.msg})"))
            continue
        if not isinstance(raw, dict) or raw.get("event") not in EVENTS:
            out._bad.append((n, "not an ask's event"))
            continue
        if raw["event"] != "asked":
            out._pending.append((n, raw))
            continue
        try:
            made = parse_ask(raw)
        except ValueError as exc:
            out._bad.append((n, str(exc)))
            continue
        out.asks.setdefault(made.id, made)
    waiting = []
    for n, raw in out._pending:
        if str(raw.get("task")) not in out.asks:
            waiting.append((n, raw))
            continue
        try:
            apply(out._own(str(raw.get("task"))), raw)
        except ValueError as exc:
            out._bad.append((n, str(exc)))
    out._pending = waiting
    unfound = [(n, f"{raw['event']} names {raw.get('task')!r}, which is no ask in the log") for n, raw in waiting]
    out.problems = [f"{ASK_LOG}:{n}: {said}" for n, said in sorted(out._bad + unfound)]
    return out


def _keys(raw: dict[str, Any], required: set[str], optional: frozenset[str] = frozenset()) -> None:
    have = set(raw) - _COMMON
    missing, extra = required - have, have - required - optional
    if missing:
        raise ValueError(f"lacks {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"has {', '.join(sorted(extra))}, which this {raw.get('what') or raw.get('event')} does not")


#: A character a person is shown that is not text: a control character other than a tab or a line break, which could rewrite what a terminal shows.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _words(value: Any, what: str, *, empty: bool = True, most: int = WORDS) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > most:
        raise ValueError(f"{what} is {'a' if empty else 'a non-empty'} string of at most {most} characters")
    if _CONTROL.search(value):
        raise ValueError(f"{what} holds a control character")
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
        return (
            None
            if isinstance(page, int) and not isinstance(page, bool) and page >= 1
            else "on's page is a number from 1"
        )
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
    if parts.username is not None or parts.password is not None:
        raise ValueError("link holds a name or a password; give the page's address alone")


def _what_fields(raw: dict[str, Any]) -> None:
    """The fields each `what` adds to an `asked` line (`docs/specs/evidence.md` §4.1)."""
    what = raw["what"]
    base = {"id", "what", "to", "on", "from", "words"}
    if what == "read":
        _keys(raw, base | {"nodes"}, frozenset({"marks"}))
        _node_list(raw["nodes"], "nodes")
        if "marks" in raw and (
            not isinstance(raw["marks"], list) or not all(isinstance(m, str) and m for m in raw["marks"])
        ):
            raise ValueError("marks is a list of the marks' ids")
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
        if raw["scope"] == "marked" and not raw.get("marks"):
            raise ValueError("a digest of what was marked names the marks")
        if raw["scope"] == "chosen" and not raw.get("nodes"):
            raise ValueError("a digest of chosen results names them in nodes")
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
        if "session" in raw:
            # the loom session an agent asked in, by which its own ask is told from another conversation's
            if by.kind != "agent" or not isinstance(raw["session"], str) or not re.fullmatch(SESSION, raw["session"]):
                raise ValueError("session is the asking agent's loom session")
        _what_fields({k: v for k, v in raw.items() if k != "session"})
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
                for m in raw["made"]:
                    if not (NODE.fullmatch(m) or re.fullmatch(EDIT, m)):
                        raise ValueError(f"{m!r} is neither a node's id nor a suggested edit's")
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
            _keys(raw, {"task"}, frozenset({"session"}))
            if not may_withdraw(ask, by, raw.get("session")):
                if ask.by == by:
                    raise ValueError(
                        f"{by.name} may not withdraw it here: it was asked in the session {ask.get('session')}"
                    )
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


def may_withdraw(ask: Ask, by: Who, session: str | None = None) -> bool:
    """A person withdraws any ask; an agent only one it made: under the name it asked as, and in the loom session it asked in where the ask names one.

    Both, since neither tells one conversation alone: every conversation of one app declares one name, and every agent in a shell shares the quilt's active session.
    """
    if by.kind == "person":
        return True
    asked_in = ask.get("session")
    return by.kind == "agent" and ask.by == by and (not asked_in or session == asked_in)


def _append(root: Path, line: dict[str, Any]) -> None:
    append_line(log_path(root), json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


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
    # checked before the lock too, since taking it makes the log's file: a refusal writes nothing at all
    trial = f"t-{at[:10]}-0"
    try:
        parse_ask({**line, "id": trial})
    except ValueError as exc:
        raise AskRefused(str(exc).removeprefix(f"{trial}: ")) from None
    with locked(log_path(root)):
        line["id"] = draw(f"t-{at[:10]}-", set(replay(root).asks))
        made = parse_ask(line)
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
    if task not in replay(root).asks:
        # before the lock, which would make the log's file: a refusal writes nothing at all
        raise AskRefused(f"{task} is no ask in this quilt")
    with locked(log_path(root)):
        found = replay(root).asks.get(task)
        if found is None:
            raise AskRefused(f"{task} is no ask in this quilt")
        closed = closed_for(found, event, by, fields, root)
        if closed:
            raise AskRefused(closed)
        try:
            apply(_copy(found), line)
        except ValueError as exc:
            raise AskRefused(str(exc)) from None
        _append(root, line)
        return replay(root).asks[task]


def closed_for(found: Ask, event: str, by: Who, fields: Mapping[str, Any], root: Path) -> str:
    """Why an event may not be said of an ask as it stands, '' when it may: nothing is said of a withdrawn ask, an answered one is not answered again, `done` names what it made, and a task a live session of another works on is not taken."""
    if found.withdrawn is not None:
        return f"{found.id} is withdrawn"
    if event == "answered" and found.answers:
        return f"{found.id} is answered already"
    if event == "done" and not fields.get("made"):
        return "say what you made with --made"
    if event == "took":
        live = live_sessions(root)
        holders = {str(t.get("session")) for t in found.took} & live
        if holders - {str(fields.get("session"))}:
            return f"{found.id} is being worked on by a live session, {sorted(holders)[0]}"
    return ""


def _copy(found: Ask) -> Ask:
    """An ask to try an event on without touching the memoised replay."""
    return Ask(**{**found.__dict__, "took": [], "done": [], "answers": [], "withdrawn": None})


# ---- what is still open ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Standing:
    """An ask as it stands now: whether it is open, why not, and whether a live session has taken it."""

    ask: Ask
    open: bool
    why: str
    working: bool


def standing(
    found: Ask,
    evidence: Evidence,
    web: Web,
    *,
    sessions: frozenset[str] = frozenset(),
    edits: list[Any] | None = None,
    lean_now: Callable[[Record], bool] | None = None,
) -> Standing:
    """Whether an ask is still open, computed from what exists now (`docs/specs/evidence.md` §4.3).

    Parameters
    ----------
    found : Ask
        The ask, replayed.
    evidence : Evidence
        The replayed evidence log.
    web : Web
        The texts now.
    sessions : frozenset of str, default empty
        The loom sessions of the agent servers alive now (`presence.live`); an ask taken in one of them is being worked on.
    edits : list, optional
        The suggested edits (`records.edits.replay`), for a `which-result`.
    lean_now : callable, optional
        Whether a `lean` record's Lean is unchanged (`status.files_unchanged`); default every record stands.

    Returns
    -------
    Standing
        `why` is `withdrawn`, `answered` or `produced` for a closed ask, '' for an open one.
    """
    working = any(str(t.get("session")) in sessions for t in found.took)
    if found.withdrawn is not None:
        return Standing(found, False, "withdrawn", False)
    if found.what in ANSWERED:
        return Standing(found, not found.answers, "answered" if found.answers else "", working and not found.answers)
    done = _produced(found, evidence, web, edits or [], lean_now or (lambda _r: True))
    return Standing(found, not done, "produced" if done else "", working and not done)


def _bodied(web: Web, ids: Iterable[str]) -> bool:
    """Every node named exists with a body; a node the web cannot say of keeps the ask open."""
    ids = list(ids)
    return bool(ids) and all(web.stub(Here("node", i)) is False for i in ids)


def _produced(found: Ask, evidence: Evidence, web: Web, edits: list[Any], lean_now: Callable[[Record], bool]) -> bool:
    """Whether what the ask asked for exists now."""
    what = found.what
    if what == "read":
        return _bodied(web, found.get("nodes", []))
    if what == "digest":
        if found.get("nodes"):
            return _bodied(web, found.get("nodes"))
        made = [m for event in found.done for m in event.get("made", [])]
        return _bodied(web, made)
    if what == "paper":
        return web.holds(str(found.get("ref")), str(found.get("want"))) is True
    if what in ("formalize", "restate"):
        target = Subject.from_dict(found.get("target"), ("node", "label"))
        after = [
            r for r in evidence.about(*target.key, of="lean") if r.at >= found.at and lean_now(r) and _states(r, target)
        ]
        if what == "formalize":
            return any(r.get("ok") for r in after)
        before = [r for r in evidence.about(*target.key, of="attested") if r.by.kind == "person" and r.at <= found.at]
        attested = dict(before[-1].get("statements", {})) if before else None
        return any(attested is None or statements_of(r) != attested for r in after)
    if what == "correct":
        node = str(found.on["node"])
        return any(r.at >= found.at for r in evidence.about("node", node) if r.kind in ("digested", "proposed"))
    if what == "which-result":
        block = found.on["block"]
        cites = found.get("cites")
        if mention_holds(evidence, block["key"], str(cites)):
            return True
        return any(
            getattr(e, "author_kind", "") == "agent" and e.target_key == block["key"] and e.created >= found.at
            for e in edits
        )
    return False


def _states(record: Record, target: Subject) -> bool:
    """Whether a `lean` record has a declaration stating `target`."""
    return any(
        d.get("role") == "states" and d.get("names") == {target.kind: target.name}
        for d in record.get("declarations", [])
    )


def mention_holds(evidence: Evidence, key: str, cites: str) -> bool:
    """Whether the person's last word on a citation of `cites` in the block at `key` is that it is only a mention."""
    said = [r for r in evidence.of_kind("mention") if r.get("cites") == cites and r.get("block", {}).get("key") == key]
    return bool(said) and not said[-1].get("undo")


def live_sessions(root: Path) -> frozenset[str]:
    """The loom sessions of the agent servers alive now."""
    from loom.presence import live

    return frozenset(str(r["session"]) for r in live(root) if r.get("session"))


def open_asks(root: Path, *, closed: bool = False, web: Web | None = None) -> list[Standing]:
    """Every ask of the quilt as it stands now, in the order asked.

    Parameters
    ----------
    root : Path
        The quilt.
    closed : bool, default False
        Include the asks that are closed or withdrawn.
    web : Web, optional
        The texts now; default one that knows no node, which keeps open every ask a node would close.

    Returns
    -------
    list of Standing
    """
    from loom.evidence.log import replay as replay_evidence
    from loom.evidence.status import files_unchanged
    from loom.evidence.web import Blank
    from loom.records.edits import replay as replay_edits

    evidence = replay_evidence(root)
    sessions = live_sessions(root)
    edits = replay_edits(root)[0]
    now = files_unchanged(root)
    out = [
        standing(a, evidence, web or Blank(), sessions=sessions, edits=edits, lean_now=now)
        for a in replay(root).asks.values()
    ]
    return [s for s in out if closed or s.open]


def place_of(quilt: Any, text: str) -> tuple[dict[str, Any], list[str]]:
    """The place a person or an agent names in a command, and the documents that read it.

    A draft's label or a block's key first, since a draft's id has the shape of a node's; then a work's id with `:PAGE`, a node's id, and a document's path.

    Raises
    ------
    ContentError
        When nothing of the quilt is named so.
    """
    from loom.errors import ContentError
    from loom.evidence.web import DraftWeb
    from loom.records.locate import block_hash, context_of
    from loom.scan.scan import scan

    result = scan(quilt)
    web = DraftWeb(result)
    name = text.strip()
    if name in web.bearing:
        readers = sorted({d for n in web.bearing[name] for d in n.reached_by})
        return {"label": name}, readers
    node = result.nodes.get(name)
    if node is not None and node.kind not in ("master", "file"):
        block = {"key": node.key, "hash": block_hash(result, node.key), "context": context_of(result, node)}
        return {"block": block}, sorted(node.reached_by)
    ref, _, page = name.partition(":")
    if REFERENCE.fullmatch(ref) and (not page or page.isdigit()):
        return ({"ref": ref, "page": int(page)} if page else {"ref": ref}), []
    if NODE.fullmatch(name):
        return {"node": name}, []
    if name in result.masters:
        return {"document": name}, [name]
    raise ContentError(
        f"nothing of this quilt is named {name}: give a result's label or key, a node's id, a work's id, or a document's path"
    )


def answered_unseen(root: Path, found: Ask) -> bool:
    """Whether an agent's question has an answer the agent that asked has not seen since: given after its last look (`loom since`'s marker for its name), or with no look yet."""
    from loom.since import read_marker

    if found.to != "person" or found.what != "question" or not found.answers or found.by.kind != "agent":
        return False
    marker = read_marker(root, found.by.name)
    when = str(found.answers[-1].get("at", ""))
    return marker is None or marker.new(when, f"answered:{found.id}:{when}")
