"""Settling a write the door left, as it stands: the person's word on one act recovery could neither finish nor undo (`writes.left`), from the control on `loom:write-left` or `loom doctor --settle`.

Loom reads the files as they are and writes none of the person's. For each suggested edit the act wrote or undid it records what the files show: the edit's words at its place, kept; the words they replaced there, open again; neither, closed, as no longer applying. The act's history lines land where they still can, as recovery's finish lands them; where they cannot, the version the act began and never recorded is removed, its texts kept in the history's store, so no stray step stops the next version. The settling is one act through the door (`writes.act`, kind `settle`): it leaves each of the left act's files as it stands (`Act.confirm`) and names the act it settles (`Act.settles`), which ends with its `done`.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

#: Why an open edit is closed by settling: what its card says.
NO_LONGER = "settled as it stands: neither its words nor the ones they replace stand where it was written, so it no longer applies"
#: Why a kept edit is opened again by settling.
OPENED = "settled as it stands: the words it replaced stand where it was written"


class SettleRefused(Exception):
    """A settling loom will not make, in the person's words; `code` and `status` are the write API's."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class Decision:
    """One suggested edit the left act wrote or undid: what settling makes of it, `kept`, `open`, `closed` or `as-is`, why in words, and the event it records (`record`), None where the edit is so already."""

    id: str
    words: str
    outcome: str
    why: str
    record: str | None = None


@dataclass
class Plan:
    """What settling one left act as it stands does, as the files and records stand now.

    `files`, the person's, stay as they are; `edits` say what becomes of each suggested edit; `history` is `recorded` (its version is in the history already), `lands` (its history lines are written now, `lines` being where and which) or `removed` (the version it began was never recorded and is taken away: `steps` are its files, `linked` any reached through a link, which stay), or '' when it began none. An untrusted line (`trusted` False) is only ended.
    """

    act: str
    kind: str
    trusted: bool = True
    files: list[str] = field(default_factory=list)
    edits: list[Decision] = field(default_factory=list)
    history: str = ""
    steps: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    lines: tuple[int, list[str]] | None = None

    def said(self) -> list[str]:
        """The preview in the person's words: every file and every decision, with no id, digest or command."""
        if not self.trusted:
            return [
                f"Loom cannot trust what its journal says of {self.kind}, so settling it writes nothing and decides nothing of your suggested edits; it only stops the notice."
            ]
        out = [f"Settling {self.kind} as it stands writes none of your files."]
        out += [f"{rel} stays as it is." for rel in self.files]
        for d in self.edits:
            if d.outcome == "kept":
                out.append(f"{d.words}: kept, since {d.why}.")
            elif d.outcome == "open":
                out.append(f"{d.words}: open again, since {d.why}.")
            elif d.outcome == "closed":
                out.append(f"{d.words}: closed, since {d.why}.")
            else:
                out.append(f"{d.words}: stays as it is, since {d.why}.")
        if self.history == "lands":
            out.append("The version it kept just before writing is recorded in your history.")
        elif self.history == "removed":
            out.append("The version it began just before writing was never recorded, so this version is not kept.")
            if self.linked:
                out.append(
                    f"Of that version, {', '.join(self.linked)} is reached through a link, so loom leaves it where it is."
                )
        return out

    def to_dict(self) -> dict[str, Any]:
        """The write API's answer (`write-settle-preview`, `write-settle`): the act as data, the rest as the preview says it."""
        return {
            "act": self.act,
            "kind": self.kind,
            "said": self.said(),
            "files": list(self.files),
            "edits": [{"id": d.id, "words": d.words, "outcome": d.outcome, "why": d.why} for d in self.edits],
            "history": self.history,
        }


def preview(root: Path, history: Path, act_id: str) -> Plan:
    """What settling the left act `act_id` as it stands would do, as the files stand now; writes nothing.

    Parameters
    ----------
    root : Path
        The quilt.
    history : Path
        Its history directory.
    act_id : str
        The act, as `writes.left_acts` names it.

    Returns
    -------
    Plan
        Its `said` is the preview a person reads.

    Raises
    ------
    SettleRefused
        `no-such-act` (404) for an act the journal does not hold begun; `not-left` for one recovery will finish or put back itself.
    """
    from loom import writes as door

    j = door.read_journal(root)
    begun = j.begun.get(act_id)
    if begun is None:
        raise SettleRefused("no-such-act", "That write is not waiting to be settled; nothing to do.", 404)
    verdict = door._judge(root, history, begun[1], j.crossing(act_id), j.again.get(act_id, ()))
    if verdict.how != "left":
        raise SettleRefused(
            "not-left", "Loom settles that write itself the next time it writes; there is nothing to decide."
        )

    def read(rel: str) -> bytes | None:
        try:
            return door._read(root, rel)
        except (door.WriteRefused, OSError):
            return None

    return _plan(root, history, act_id, begun[1], read)


def settle(root: Path, history: Path, act_id: str, who: str) -> Plan:
    """Settle the left act `act_id` as it stands, the person's act, through the door: re-planned under its lock, as `preview` plans it.

    Parameters
    ----------
    root : Path
        The quilt.
    history : Path
        Its history directory.
    act_id : str
        The act, as `writes.left_acts` names it.
    who : str
        The person, as the journal and the edit log record them.

    Returns
    -------
    Plan
        What was done.

    Raises
    ------
    SettleRefused
        `author-only` (403) for an agent's act (`identity.agents_act`); `no-such-act` (404) for an act no longer waiting, recovery having settled it as the door opened.
    WriteRefused
        `changed` when a file of it changed between the read under the lock and the commit; nothing is written.
    """
    from loom import writes as door
    from loom.identity import agents_act

    if agents_act(who):
        raise SettleRefused(
            "author-only", "Settling a write is the author's; an agent says what it found in an annotation.", 403
        )
    with door.act(root, history, "settle", who) as w:
        begun = w.journal.begun.get(act_id)
        if begun is None:
            raise SettleRefused("no-such-act", "That write is not waiting to be settled; nothing to do.", 404)
        plan = _plan(root, history, act_id, begun[1], w.read)
        _stage(w, root, history, begun[1], plan, who)
    return plan


def _plan(root: Path, history: Path, act_id: str, entry: dict[str, Any], read: Callable[[str], bytes | None]) -> Plan:
    """The plan for `entry`, the left act's `begin` line, with the files read through `read`."""
    from loom import writes as door

    plan = Plan(act_id, door.KINDS.get(str(entry.get("kind")), "a write"))
    if door.untrusted(root, history, entry):
        plan.trusted = False
        return plan
    from loom.paths import LOOM

    written = door._written(entry)
    base = _rel(root, history)
    mine = {rel: ab for rel, ab in written.items() if base is not None and (rel + "/").startswith(base + "/")}
    # the person's files: loom's own, the history among them, are said by what becomes of the version
    plan.files = sorted(rel for rel in written if rel not in mine and not (rel + "/").startswith(f"{LOOM}/"))
    _history(root, history, entry, mine, base, plan)
    plan.edits = _decisions(root, history, entry, read)
    return plan


def _rel(root: Path, history: Path) -> str | None:
    """`history` relative to the quilt, or None where it lies outside it."""
    rel = os.path.relpath(os.path.realpath(history), os.path.realpath(root))
    return None if rel.startswith("..") or rel == "." else PurePosixPath(rel).as_posix()


def _history(
    root: Path, history: Path, entry: dict[str, Any], mine: dict[str, Any], base: str | None, plan: Plan
) -> None:
    """Into `plan`, what becomes of the version the act began, if it began one: its ledger lines landed where they still can and every file of the version holds what the act wrote, as recovery's finish lands them, else the step folders it made that no line names, removed."""
    from loom import writes as door
    from loom.history.ledger import LEDGER, load_history

    if base is None or not mine:
        return  # it began no version: what else it would have recorded is not written, as none of its records are
    ledger = door._log_name(root, history / LEDGER)
    guard = door._guards(entry.get("records") or []).get(ledger)
    if guard is not None:
        at, lines = guard
        have = door._landed(root, ledger, at, lines)
        if have == len(lines):
            plan.history = "recorded"
            return
        if have is not None and all(door._holds(root, rel, ab[1]) for rel, ab in mine.items()):
            plan.history, plan.lines = "lands", (at + have, lines[have:])
            return
    named = {d.name for d in load_history(history).unrecorded_dirs()}
    made = {PurePosixPath(rel).relative_to(base).parts[0] for rel in mine} & named
    if not made:
        return
    plan.history = "removed"
    for name in sorted(made):
        for folder, _dirs, files in os.walk(root / base / name):
            for f in sorted(files):
                rel = (Path(folder) / f).relative_to(root).as_posix()
                (plan.steps if door._place(root, rel) == PurePosixPath(rel).parts else plan.linked).append(rel)


def _decisions(root: Path, history: Path, entry: dict[str, Any], read: Callable[[str], bytes | None]) -> list[Decision]:
    """What becomes of each suggested edit the act wrote (`edits`) or undid (`undid`), judged by its own splice at its place in the file now."""
    from loom.records.edits import generation, replay

    current = {e.id: e for e in replay(root)[0]}
    named = [(str(g), False) for g in entry.get("edits") or []] + [(str(g), True) for g in entry.get("undid") or []]
    out: list[Decision] = []
    for gen, undo in named:
        eid, _, n = gen.rpartition(":")
        e = current.get(eid)
        if e is None or not n.isdigit():
            continue
        now = generation(e)
        if now != int(n) and not (undo and now == int(n) + 1):
            out.append(Decision(e.id, _words(e), "as-is", "it has been opened again since"))
            continue
        out.append(_reconcile(e, _side(history, entry, gen, e, read, undo)))
    return out


def _side(
    history: Path, entry: dict[str, Any], gen: str, e: Any, read: Callable[[str], bytes | None], undo: bool
) -> str | None:
    """`kept`, `open` or `closed` by the edit's own splices at their places now; None where loom cannot tell: a text missing from the store, a splice that does not carry the edit's own words, or a file that is not text."""
    from loom import writes as door

    splices = door.splices_of(history, entry, edit=gen)
    if not splices:
        return None
    sides = set()
    for w in splices:
        if not _own(e, w, undo):
            return None
        data = read(w.rel)
        try:
            text = data.decode("utf-8") if data is not None else None
        except UnicodeDecodeError:
            return None
        if text is None:
            sides.add("neither")
            continue
        try:
            after = door.place_in(w, text, side="after") is not None
            before = not after and door.place_in(w, text, side="before") is not None
        except door.TooChanged:
            after = before = False
        sides.add("after" if after else "before" if before else "neither")
    if sides == {"after"}:
        return "open" if undo else "kept"
    if sides == {"before"}:
        return "kept" if undo else "open"
    return "closed"


def _own(e: Any, w: Any, undo: bool) -> bool:
    """Whether the splice `w` carries the edit's own words, as the edit log holds them: a line naming an edit with other words decides nothing of it."""

    def norm(t: str) -> str:
        return " ".join(t.split())

    new, old = (w.old, w.new) if undo else (w.new, w.old)
    if norm(e.with_text):
        return norm(e.with_text) in norm(new)
    quote = e.selector.exact if e.selector else ""
    return bool(norm(quote)) and norm(quote) in norm(old)


def _reconcile(e: Any, side: str | None) -> Decision:
    """The decision on `e` for what the files show (`side`), and the event that records it where its record says otherwise."""
    words = _words(e)
    if side is None:
        return Decision(e.id, words, "as-is", "loom cannot tell from the files what became of it")
    if side == "kept":
        if e.status == "discarded":
            return Decision(e.id, words, "as-is", "it was closed already")
        return Decision(
            e.id, words, "kept", "its words stand where it was written", "kept" if e.status == "open" else None
        )
    if side == "open":
        if e.status == "discarded":
            return Decision(e.id, words, "as-is", "it was closed already")
        return Decision(
            e.id,
            words,
            "open",
            "the words it replaced stand where it was written",
            "reopened" if e.status == "kept" else None,
        )
    if e.status == "open":
        return Decision(
            e.id, words, "closed", "neither its words nor the ones they replace stand where it was written", "discarded"
        )
    return Decision(e.id, words, "as-is", "it was kept or closed already, and its words have changed since")


def _words(e: Any) -> str:
    """A suggested edit as a person reads it: whose, and what it writes."""

    def short(t: str) -> str:
        t = " ".join(t.split())
        return t if len(t) <= 60 else t[:59] + "…"

    who = e.author_id or "someone"
    quote = e.selector.exact if e.selector else ""
    if e.with_text and quote and e.placement == "replace":
        return f"{who}'s suggestion “{short(e.with_text)}” for “{short(quote)}”"
    if e.with_text:
        return f"{who}'s suggestion to add “{short(e.with_text)}”"
    return f"{who}'s suggestion to remove “{short(quote)}”"


def _stage(w: Any, root: Path, history: Path, entry: dict[str, Any], plan: Plan, who: str) -> None:
    """Stage `plan` in the settling act `w`: the act it settles named, its files left as they stand, the edit lines, the history's lines landed or its unrecorded version removed."""
    from loom import writes as door
    from loom.history.ledger import LEDGER

    w.settles = plan.act
    if not plan.trusted:
        return
    for rel in door._written(entry):
        if rel in plan.steps:
            continue
        try:
            w.confirm(rel, w.read(rel))
        except door.WriteRefused:
            continue  # a folder or a device where the act wrote a file: nothing of it to leave as it is
    writer = ("person", who)
    records = [d for d in plan.edits if d.record]
    if records:
        _record(w, root, records, writer)
    if plan.lines is not None:
        at, lines = plan.lines
        for line in lines:
            w.log(history / LEDGER, line, at=at)
    for rel in plan.steps:
        w.remove_own(rel)
    if plan.steps:
        steps = list(plan.steps)
        w.then(lambda: door._prune_at(root, history, steps))


def _record(w: Any, root: Path, decisions: list[Decision], writer: tuple[str, str]) -> None:
    """The edit log's line for each decision that records one, and the annotation line a Keep or its undo would write with it."""
    from loom.clock import stamp
    from loom.paths import EDIT_LOG
    from loom.records.edits import answered_event, home, kept_event, reopened_event, replay, unanswered_event
    from loom.records.log import log_path as annotation_log

    current = {e.id: e for e in replay(root)[0]}
    result = None
    for d in decisions:
        e = current[d.id]
        if d.record == "kept":
            if result is None:
                from loom.scan.quilt import load_quilt
                from loom.scan.scan import scan

                result = scan(load_quilt(root))
            from loom.scan.owntext import key_hash

            node = home(result, e)
            w.log(root / EDIT_LOG, kept_event(e, writer, key_hash(result, node.key) if node is not None else ""))
            line = answered_event(root, e, writer)
        elif d.record == "reopened":
            w.log(root / EDIT_LOG, reopened_event(e, writer, why=OPENED))
            line = unanswered_event(root, e, writer)
        else:
            w.log(
                root / EDIT_LOG,
                {
                    "event": "discarded",
                    "id": e.id,
                    "when": stamp(),
                    "author": writer[1],
                    "kind": writer[0],
                    "why": NO_LONGER,
                },
            )
            line = None
        if line is not None:
            w.log(annotation_log(root), line)
