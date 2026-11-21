"""A result's status, computed from the evidence and the texts now, and never stored (`docs/specs/evidence.md` §5).

Nothing reads `formalized` without a person's attestation that still holds, nothing reads `matches` without a person's comparison of this very text, and a Lean record is believed only while every Lean file it read is unchanged.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from loom.evidence.log import Evidence, Record
from loom.evidence.subjects import Subject
from loom.evidence.web import Here, Web

#: What `lean` can be, from nothing done to formalized.
LEAN = ("none", "rerun", "failed", "unattested", "changed", "formalized")
#: Declaration kinds that define rather than state a claim.
_DEFINES = frozenset({"def", "structure", "inductive", "abbrev", "instance", "opaque"})


@dataclass(frozen=True)
class Cause:
    """Why an attestation no longer holds: what changed, the hash it named, and the hash now (None when it no longer resolves)."""

    key: tuple[str, str]
    then: str | None
    now: str | None


@dataclass(frozen=True)
class Status:
    """How a result stands now (`docs/specs/evidence.md` §5).

    Parameters
    ----------
    subject : Subject or None
        The text now; None when it is gone or has no lasting name.
    reading : str or None
        A node of the library: `stub`, `unchecked` or `matches`; None for a draft's result.
    compared_before : bool
        Unchecked, but a person compared an earlier text of it.
    how : str or None
        How this very text was made, from its latest `digested`.
    sought : bool
        A stub loom looked for in its work's TeX source and did not find.
    proposal : str or None
        The id of an open correction to this text.
    lean : str
        One of `LEAN`.
    role : str or None
        With a current Lean record: `proved`, `unproved` (a `sorry`), `assumed` or `defined`.
    relative_to : tuple of Subject
        The assumed results its proof rests on.
    causes : tuple of Cause
        Why the person's attestation no longer holds, for `changed`.
    unattested_notation : tuple of str
        Commands it is typeset with that no person has attested in this definition.
    accepted : str or None
        A draft's result the person accepted: `fresh` or `changed`; None where they never did.
    """

    subject: Subject | None
    reading: str | None = None
    compared_before: bool = False
    how: str | None = None
    sought: bool = False
    proposal: str | None = None
    lean: str = "none"
    role: str | None = None
    relative_to: tuple[Subject, ...] = ()
    causes: tuple[Cause, ...] = ()
    unattested_notation: tuple[str, ...] = ()
    accepted: str | None = None
    lean_record: str | None = field(default=None, compare=False)
    attestation: str | None = field(default=None, compare=False)


def files_unchanged(root: Path) -> Callable[[Record], bool]:
    """Whether a `lean` record's Lean files all still have the hashes it recorded, each file hashed at most once a call of the returned function's life.

    The Lean piece replaces this with a declaration-level check; until then a change anywhere in a file loom read makes the record not current, which can only send loom to run again, never let a stale record stand.
    """
    seen: dict[str, str | None] = {}

    def now(path: str) -> str | None:
        if path not in seen:
            try:
                seen[path] = "sha256:" + hashlib.sha256((root / path).read_bytes()).hexdigest()
            except OSError:
                seen[path] = None
        return seen[path]

    def check(record: Record) -> bool:
        return all(now(path) == digest for path, digest in dict(record.get("files", {})).items())

    return check


def statements_of(record: Record) -> dict[str, str]:
    """The stating declarations of a `lean` record, by name, with their statements' hashes."""
    return {d["name"]: d["statement"] for d in record.get("declarations", []) if d.get("role") == "states"}


def causes_of(attestation: Record, web: Web, here: Here) -> list[Cause]:
    """What changed since an attestation on a result was made: the result's own text, and each member of its closure as `here` reads it."""
    out: list[Cause] = []
    subject = web.subject(here)
    if attestation.on is not None and (subject is None or subject.hash != attestation.on.hash):
        out.append(Cause(attestation.on.key, attestation.on.hash, subject.hash if subject else None))
    for raw in attestation.get("closure", []):
        member = Subject.from_dict(raw, ("node", "label"))
        now = web.resolve(member.key, here)
        if now != member.hash:
            out.append(Cause(member.key, member.hash, now))
    return out


def notation_of(evidence: Evidence, web: Web, here: Here) -> tuple[list[Cause], list[str]]:
    """Each command the result is typeset with: the ones a person attested in an earlier definition only (changed), and the ones never attested."""
    changed: list[Cause] = []
    never: list[str] = []
    for name, digest in sorted(web.notation(here).items()):
        said = [r for r in evidence.about("macro", name, of="attested") if r.on is not None]
        if any(r.on.hash == digest for r in said if r.on):
            continue
        if said and said[-1].on is not None:
            changed.append(Cause(("macro", name), said[-1].on.hash, digest))
        else:
            never.append(name)
    return changed, never


def _role(record: Record, subject: Subject) -> str | None:
    for d in record.get("declarations", []):
        if d.get("role") == "states" and d.get("names") == {subject.kind: subject.name}:
            if d["kind"] == "axiom":
                return "assumed"
            if d["kind"] in _DEFINES:
                return "defined"
            return "unproved" if d["sorry"] else "proved"
    return None


def status(evidence: Evidence, web: Web, here: Here, *, lean_now: Callable[[Record], bool]) -> Status:
    """How the result at `here` stands now.

    Parameters
    ----------
    evidence : Evidence
        The replayed evidence log.
    web : Web
        The texts now.
    here : Here
        A node by its id, or a draft's block by its key.
    lean_now : callable
        Whether a `lean` record's Lean is unchanged since loom ran it (`files_unchanged`).

    Returns
    -------
    Status
        `subject` None, and nothing else said, for a thing gone or with no lasting name.
    """
    subject = web.subject(here)
    if subject is None:
        return Status(None)
    kind, name = subject.key
    reading: str | None = None
    compared_before = False
    how: str | None = None
    sought = False
    proposal: str | None = None
    stub = web.stub(here)
    if stub is not None:
        compared = evidence.about(kind, name, of="compared")
        if stub:
            reading = "stub"
        elif any(r.on is not None and r.on.hash == subject.hash for r in compared):
            reading = "matches"
        else:
            reading, compared_before = "unchecked", bool(compared)
        made = [r for r in evidence.about(kind, name, of="digested") if r.on is not None and r.on.hash == subject.hash]
        how = made[-1].get("how") if made else None
        sought = stub and any(
            r.on is not None and r.on.hash == subject.hash for r in evidence.about(kind, name, of="sought")
        )
        open_ = [
            r
            for r in evidence.about(kind, name, of="proposed")
            if r.on is not None and r.on.hash == subject.hash and evidence.declined(r.id) is None
        ]
        proposal = open_[-1].id if open_ else None
    base = Status(subject, reading, compared_before, how, sought, proposal, accepted=web.acceptance(here))
    leans = evidence.about(kind, name, of="lean")
    if not leans:
        return base
    standing = [r for r in leans if lean_now(r)]
    if not standing:
        return _with(base, "rerun")
    latest = standing[-1]
    current = latest if latest.on is not None and latest.on.hash == subject.hash else None
    role = _role(current, subject) if current else None
    relative = tuple(Subject.from_dict(a, ("node",)) for a in current.get("assumed", [])) if current else ()
    said = [r for r in evidence.about(kind, name, of="attested") if r.by.kind == "person"]
    attestation = said[-1] if said else None
    if attestation is not None and dict(attestation.get("statements", {})) == statements_of(latest):
        changed, never = notation_of(evidence, web, here)
        causes = causes_of(attestation, web, here) + changed
        if causes:
            return _with(base, "changed", role, relative, causes, never, latest, attestation)
        if current is None:
            return _with(base, "rerun", None, (), (), never, latest, attestation)
        if not current.get("ok"):
            return _with(base, "failed", role, relative, (), never, current, attestation)
        if never:
            return _with(base, "unattested", role, relative, (), never, current, attestation)
        return _with(base, "formalized", role, relative, (), (), current, attestation)
    if current is None:
        return _with(base, "rerun", lean_record=latest)
    if not current.get("ok"):
        return _with(base, "failed", role, relative, lean_record=current)
    _changed, never = notation_of(evidence, web, here)
    return _with(base, "unattested", role, relative, (), never, current)


def _with(
    base: Status,
    lean: str,
    role: str | None = None,
    relative: tuple[Subject, ...] = (),
    causes: list[Cause] | tuple[Cause, ...] = (),
    never: list[str] | tuple[str, ...] = (),
    lean_record: Record | None = None,
    attestation: Record | None = None,
) -> Status:
    return Status(
        base.subject,
        base.reading,
        base.compared_before,
        base.how,
        base.sought,
        base.proposal,
        lean,
        role,
        relative,
        tuple(causes),
        tuple(never),
        base.accepted,
        lean_record.id if lean_record else None,
        attestation.id if attestation else None,
    )
