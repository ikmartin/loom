"""A result's status, computed from the evidence and the texts now, and never stored (`docs/specs/evidence.md` §5).

Nothing reads `formalized` without a person's attestation that still holds and every library result under it read and compared with its paper, nothing reads `matches` without a person's comparison of this very text, and a Lean record is believed only while every Lean file it read is unchanged. The gate is computed here from whatever records exist, not trusted to the act that wrote them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

from loom.evidence.log import Evidence, Record
from loom.evidence.subjects import Subject
from loom.evidence.web import Here, Web

#: What `lean` can be, from nothing done to formalized.
LEAN = ("none", "rerun", "failed", "unattested", "changed", "waiting", "formalized")
#: Declaration kinds that define rather than state a claim.
_DEFINES = frozenset({"def", "structure", "inductive", "abbrev", "instance", "opaque"})


@dataclass(frozen=True)
class Cause:
    """Why an attestation no longer holds: what changed, the hash it named, and the hash now (None when it no longer resolves)."""

    key: tuple[str, str]
    then: str | None
    now: str | None


@dataclass(frozen=True)
class Waiting:
    """A library result a result rests on that keeps it from reading formalized, and why: `stub` (not read), `unchecked` (not compared with its paper on its text now), `unattested` (assumed in Lean, its own Lean statement not attested), or `unknown` (nothing can say of it, as before the node store)."""

    key: tuple[str, str]
    why: str


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
    waiting_on : tuple of Waiting
        With a current Lean record: each library result its statement uses or its Lean assumes that is not yet read, compared, or (assumed) attested; `formalized` only when there is none.
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
    waiting_on: tuple[Waiting, ...] = ()
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


def gate(
    evidence: Evidence,
    web: Web,
    uses: Iterable[str],
    assumed: Iterable[str],
    lean_now: Callable[[Record], bool],
    seen: frozenset[str] = frozenset(),
) -> tuple[Waiting, ...]:
    """The library results that keep a result from reading formalized (`docs/specs/evidence.md` §5.2).

    `uses` are the nodes its statement's closure holds: each must be read and compared with its paper on its text now. `assumed` are the nodes its Lean states as axioms: each must be that, and its own Lean statement attested (its status `formalized`). A node nothing can say of waits, so a result resting on the library never reads formalized before the library can answer for it.
    """
    out: list[Waiting] = []
    for node, must_attest in [(n, False) for n in uses] + [(n, True) for n in assumed]:
        if any(w.key == ("node", node) for w in out):
            continue
        here = Here("node", node)
        subject, stub = web.subject(here), web.stub(here)
        if subject is None or stub is None:
            out.append(Waiting(("node", node), "unknown"))
        elif stub:
            out.append(Waiting(("node", node), "stub"))
        elif not any(
            r.on is not None and r.on.hash == subject.hash for r in evidence.about("node", node, of="compared")
        ):
            out.append(Waiting(("node", node), "unchecked"))
        elif must_attest and node not in seen:
            if status(evidence, web, here, lean_now=lean_now, _seen=seen | {node}).lean != "formalized":
                out.append(Waiting(("node", node), "unattested"))
    return tuple(out)


def status(
    evidence: Evidence, web: Web, here: Here, *, lean_now: Callable[[Record], bool], _seen: frozenset[str] = frozenset()
) -> Status:
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
        return replace(base, lean="rerun")
    latest = standing[-1]
    current = latest if latest.on is not None and latest.on.hash == subject.hash else None
    if current is None:
        found = replace(base, lean="rerun", lean_record=latest.id)
    else:
        assumed = tuple(Subject.from_dict(a, ("node",)) for a in current.get("assumed", []))
        found = replace(base, role=_role(current, subject), relative_to=assumed, lean_record=current.id)
    said = [r for r in evidence.about(kind, name, of="attested") if r.by.kind == "person"]
    attestation = said[-1] if said else None
    if attestation is not None and dict(attestation.get("statements", {})) == statements_of(latest):
        found = replace(found, attestation=attestation.id)
        changed, never = notation_of(evidence, web, here)
        causes = causes_of(attestation, web, here) + changed
        if causes:
            return replace(found, lean="changed", causes=tuple(causes), unattested_notation=tuple(never))
        if current is None:
            return replace(found, unattested_notation=tuple(never))
        uses = [m["node"] for m in attestation.get("closure", []) if "node" in m]
    else:
        if current is None:
            return found
        never = notation_of(evidence, web, here)[1]
        uses = [k[1] for k in web.closure(here) if k[0] == "node"]
        attestation = None
    waiting = gate(evidence, web, uses, [a.name for a in found.relative_to], lean_now, _seen | {name})
    found = replace(found, unattested_notation=tuple(never), waiting_on=waiting)
    if not current.get("ok"):
        return replace(found, lean="failed")
    if attestation is None or never:
        return replace(found, lean="unattested")
    return replace(found, lean="waiting" if waiting else "formalized")
