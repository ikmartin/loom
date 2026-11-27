"""An agent's reading of a result's Lean in ordinary mathematics: a `reading` record of the evidence log (`docs/specs/evidence.md` §3.8), written by `loom formal read` alone.

Each part names one of the declarations the person reads in loom's `lean` record (`read_names`) and carries no Lean of its own; nothing checks the reading against the Lean, so it never counts toward a result's status, and it is stale once a newer `lean` record states the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.evidence.log import Evidence, EvidenceRefused, Record, log_path, replay
from loom.evidence.log import write as write_record
from loom.evidence.subjects import Who
from loom.locks import locked


@dataclass
class Refused(Exception):
    """A reading not written, and why: `no-lean` (no `lean` record states the result), `changed` (the record read is no longer the latest), `no-such-declaration` (a part names a declaration the person does not read in that record), `refused` (the log refused the record)."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _states(record: Record, kind: str, name: str) -> bool:
    return any(d.get("role") == "states" and d.get("names") == {kind: name} for d in record.get("declarations", []))


def leans(evidence: Evidence, name: str) -> tuple[str, list[Record]]:
    """The `lean` records stating the result `name`, oldest first, and the kind it is named by: a draft's label first, since a draft's id has a node's shape, else a node's id."""
    for kind in ("label", "node"):
        found = [r for r in evidence.about(kind, name, of="lean") if _states(r, kind, name)]
        if found:
            return kind, found
    return "label", []


def read_names(record: Record) -> list[str]:
    """The declarations of a `lean` record the person reads before attesting: those stating its result, then each the statements name (`means`) and what those name in turn, breadth first.

    The order `review`'s attest row draws them in; a declaration that only serves the proof is not among them.
    """
    rows = {d["name"]: d for d in record.get("declarations", [])}
    on = record.on
    states = [n for n, d in rows.items() if on is not None and d.get("role") == "states" and d.get("names") == {on.kind: on.name}]  # fmt: skip
    out, todo = list(states), [m for n in states for m in rows[n].get("means", [])]
    while todo:
        name = todo.pop(0)
        if name in out or name not in rows:
            continue
        out.append(name)
        todo.extend(rows[name].get("means", []))
    return out


def latest(evidence: Evidence, kind: str, name: str) -> Record | None:
    """The latest reading of the result `kind`, `name`, at any text, or None."""
    found = evidence.about(kind, name, of="reading")
    return found[-1] if found else None


def stale(evidence: Evidence, reading: Record) -> bool:
    """Whether a reading is of an earlier Lean: a `lean` record stating its result is newer than the one it read, or that one is gone."""
    on = reading.on
    if on is None:
        return True
    found = [r for r in evidence.about(on.kind, on.name, of="lean") if _states(r, on.kind, on.name)]
    return not found or found[-1].id != reading.get("lean")


def write(
    root: Path,
    name: str,
    by: Who,
    parts: list[dict[str, str]],
    difference: str | None,
    *,
    record: str | None = None,
) -> Record:
    """Record an agent's reading of the latest `lean` record stating a result.

    Parameters
    ----------
    root : Path
        The quilt.
    name : str
        The result: a draft's label, or a statement node's id.
    by : Who
        The agent reading; the log refuses any other hand.
    parts : list of dict
        Each `{part, draft, declaration, reading}`: the part's name ('' for the whole statement), what the statement says there as LaTeX, a declaration of `read_names`, and its reading as LaTeX.
    difference : str or None
        The agent's note of where the Lean and the statement differ; None where it found none.
    record : str, optional
        The `lean` record read; default the latest. Refused `changed` when it is not the latest.

    Returns
    -------
    Record
        As written, on the text that record checked.

    Raises
    ------
    Refused
        With its code; nothing was written.
    """
    with locked(log_path(root)):
        evidence = replay(root)
        _kind, found = leans(evidence, name)
        if not found:
            raise Refused("no-lean", f"no record of loom's check states {name}; ask loom to check the Lean first")
        target = found[-1]
        if record is not None and record != target.id:
            raise Refused("changed", f"{record} is not the latest record of {name}'s Lean, {target.id}; read that one")
        names = set(read_names(target))
        unknown = [p.get("declaration", "") for p in parts if p.get("declaration") not in names]
        if unknown:
            raise Refused(
                "no-such-declaration",
                f"{', '.join(unknown)}: not a declaration the person reads in {target.id}, which are {', '.join(read_names(target))}",
            )
        try:
            return write_record(root, "reading", by, on=target.on, lean=target.id, parts=parts, difference=difference)
        except EvidenceRefused as exc:
            raise Refused("refused", str(exc)) from None


def to_read(evidence: Evidence, name: str) -> dict[str, Any] | None:
    """What a reading of `name` reads: the latest `lean` record stating it, and each declaration of `read_names` with its kind and Lean's print of it; None where no record states it."""
    _kind, found = leans(evidence, name)
    if not found:
        return None
    target = found[-1]
    rows = {d["name"]: d for d in target.get("declarations", [])}
    return {
        "record": target.id,
        "on": target.on.to_dict() if target.on else None,
        "declarations": [
            {"name": n, "kind": rows[n]["kind"], "shown": rows[n].get("shown")} for n in read_names(target)
        ],
    }
