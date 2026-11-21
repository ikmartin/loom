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
    #: When loom wrote the current Lean record: since when the result has waited for the person's word.
    lean_since: str | None = field(default=None, compare=False)
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


#: The axioms a proof may rest on and still read proved: Lean's own three. A `sorry` is `sorryAx`; any other axiom must be one the record itself states, a result it assumes.
STANDARD_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})


def states(record: Record, subject: Subject) -> bool:
    """Whether a `lean` record has a declaration stating `subject`: a record that states nothing of a result is not about it."""
    return any(
        d.get("role") == "states" and d.get("names") == {subject.kind: subject.name}
        for d in record.get("declarations", [])
    )


def proves(record: Record, subject: Subject) -> bool:
    """Whether Lean accepted `subject` whole in this record: `ok`, the kernel's replay passed, and every declaration stating it free of `sorry` and of any axiom beyond Lean's own three and the results the record itself states as axioms."""
    if not record.get("ok") or (record.get("replay") or {}).get("exit") != 0:
        return False
    decls = record.get("declarations", [])
    stated = {d["name"] for d in decls if d.get("kind") == "axiom"}
    for d in decls:
        if d.get("role") != "states" or d.get("names") != {subject.kind: subject.name}:
            continue
        if d.get("sorry") or set(d.get("axioms", [])) - STANDARD_AXIOMS - stated:
            return False
    return True


def closure_now(web: Web, here: Here, leans: list[Record]) -> dict[tuple[str, str], str | None]:
    """What the statement at `here` uses as it reads now, and what each Lean record of it says its declarations rest on, each with its hash now (None where nothing answers)."""
    out: dict[tuple[str, str], str | None] = dict(web.closure(here))
    for lean in leans:
        for raw in lean.get("uses", []):
            member = Subject.from_dict(raw, ("node", "label"))
            out.setdefault(member.key, web.resolve(member.key, here))
    return out


def causes_of(
    attestation: Record, web: Web, here: Here, now: dict[tuple[str, str], str | None] | None = None
) -> list[Cause]:
    """Why an attestation no longer holds: the result's own text changed, a member of the closure as it reads now is not attested at its hash now (`then` null for one it never named), or a member it named no longer has its hash."""
    out: list[Cause] = []
    subject = web.subject(here)
    if attestation.on is not None and (subject is None or subject.hash != attestation.on.hash):
        out.append(Cause(attestation.on.key, attestation.on.hash, subject.hash if subject else None))
    members = (Subject.from_dict(raw, ("node", "label")) for raw in attestation.get("closure", []))
    attested = {m.key: m.hash for m in members}
    reads: dict[tuple[str, str], str | None] = now if now is not None else dict(web.closure(here))
    for key, digest in reads.items():
        # a member it never named is a cause even where nothing answers for it now
        if key not in attested or attested[key] != digest:
            out.append(Cause(key, attested.get(key), digest))
    # what it named must still be what `here` reads under that name, alone: a label two texts answer to near it holds nothing
    for key, then in attested.items():
        answer = web.resolve(key, here)
        if answer != then and all(c.key != key for c in out):
            out.append(Cause(key, then, answer))
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
    cites: Iterable[str] = (),
) -> tuple[Waiting, ...]:
    """The library results that keep a result from reading formalized (`docs/specs/evidence.md` §5.2).

    `uses` are the nodes its statement's closure holds, as it reads now and as it was attested: each must be read and compared with its paper on its text now. `assumed` are the nodes its Lean states as axioms: each must be that, and its own Lean statement attested (its own status `formalized`). `cites` are the draft's citations of one result of a work that no node answers for yet. A node nothing can say of waits, so a result resting on the library never reads formalized before the library can answer for it.
    """
    out: list[Waiting] = [Waiting(("cite", c), "unknown") for c in dict.fromkeys(cites)]
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
    # a record that states nothing of this result is not about it; one on another text speaks for that text
    leans = [r for r in evidence.about(kind, name, of="lean") if states(r, subject)]
    if not leans:
        return base
    standing = [r for r in leans if lean_now(r)]
    if not standing:
        return replace(base, lean="rerun")
    mine = [r for r in standing if r.on is not None and r.on.hash == subject.hash]
    current = mine[-1] if mine else None
    latest = current or standing[-1]
    found = replace(base, lean_record=latest.id)
    if current is not None:
        assumed = tuple(Subject.from_dict(a, ("node",)) for a in current.get("assumed", []))
        found = replace(found, role=_role(current, subject), relative_to=assumed, lean_since=current.at)
    # every standing record on this text says what Lean rested on, whether or not it states the result: its uses count
    on_this = [
        r
        for r in evidence.about(kind, name, of="lean")
        if lean_now(r) and r.on is not None and r.on.hash == subject.hash
    ]
    now = closure_now(web, here, on_this or [latest])
    # a web written before citations were asked of it (a test's) cites nothing
    cited = getattr(web, "cited", None)
    cites: list[str] = list(cited(here)) if cited is not None else []
    said = [r for r in evidence.about(kind, name, of="attested") if r.by.kind == "person" and r.on is not None]
    on_text = [a for a in said if a.on is not None and a.on.hash == subject.hash]
    fitting = [a for a in on_text if dict(a.get("statements", {})) == statements_of(latest)]
    if fitting:
        attestation = fitting[-1]
        changed, never = notation_of(evidence, web, here)
        causes = causes_of(attestation, web, here, now) + changed
        found = replace(found, attestation=attestation.id, unattested_notation=tuple(never))
        if causes:
            return replace(found, lean="changed", causes=tuple(causes))
        if current is None:
            return replace(found, lean="rerun")
        attested_nodes = [m["node"] for m in attestation.get("closure", []) if "node" in m]
        uses = [k[1] for k in now if k[0] == "node"] + attested_nodes
        waiting = gate(evidence, web, uses, [a.name for a in found.relative_to], lean_now, _seen | {name}, cites)
        found = replace(found, waiting_on=waiting)
        if not proves(current, subject):
            return replace(found, lean="failed")
        if never:
            return replace(found, lean="unattested")
        return replace(found, lean="waiting" if waiting else "formalized")
    if not on_text and said:
        # the person attested another text of this label, of a Lean that still stands: this text is not what they gave their word for
        earlier = said[-1]
        if any(statements_of(r) == dict(earlier.get("statements", {})) for r in standing):
            changed, never = notation_of(evidence, web, here)
            causes = causes_of(earlier, web, here, now) + changed
            return replace(
                found, lean="changed", attestation=earlier.id, causes=tuple(causes), unattested_notation=tuple(never)
            )
    if current is None:
        return replace(found, lean="rerun")
    never = notation_of(evidence, web, here)[1]
    uses = [k[1] for k in now if k[0] == "node"]
    waiting = gate(evidence, web, uses, [a.name for a in found.relative_to], lean_now, _seen | {name}, cites)
    found = replace(found, unattested_notation=tuple(never), waiting_on=waiting)
    if not proves(current, subject):
        return replace(found, lean="failed")
    return replace(found, lean="unattested")
