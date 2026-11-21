"""A result's status, computed from the evidence and the texts now, and never stored (`docs/specs/evidence.md` §5).

Nothing reads `formalized` without a person's attestation that still holds and every library result under it read and compared with its paper, nothing reads `matches` without a person's comparison of this very text, and a Lean record is believed only while every Lean file it read is unchanged. The gate is computed here from whatever records exist, not trusted to the act that wrote them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

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
    """What keeps a result from reading formalized, and why: a node `stub` (not read) or `unchecked` (not compared with its paper on its text now); a node or a result of the person's assumed in Lean, `unattested` (its own Lean statement not attested); or a node, a result or a citation (`("cite", "KEY LOCATOR")`, or `"KEY"` with none) `unknown`, which nothing can say of yet."""

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
    relative_to : tuple of (str, str)
        What its proof is verified relative to: each result its Lean rests on as an axiom, `("node", id)` or `("label", label)` (`relative_to`).
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
    relative_to: tuple[tuple[str, str], ...] = ()
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


#: Lean's own axioms, which a proof may rest on and still read proved. A `sorry` is `sorryAx`, never among them.
STANDARD_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})


def _stating(record: Record, subject: Subject) -> list[dict]:  # type: ignore[type-arg]
    return [
        d
        for d in record.get("declarations", [])
        if d.get("role") == "states" and d.get("names") == {subject.kind: subject.name}
    ]


def states(record: Record, subject: Subject) -> bool:
    """Whether a `lean` record has a declaration stating `subject`: a record that states nothing of a result is not about it."""
    return bool(_stating(record, subject))


def assumes(record: Record, subject: Subject) -> tuple[list[tuple[str, str]], bool]:
    """What Lean reports the result rests on as axioms, by name, and whether every axiom it reports is accounted for.

    An axiom a declaration stating `subject` reports beyond Lean's three is accounted for only as a declaration of the record that is an axiom stating a library node, or one of the person's own results other than this one; anything else (a `sorry`, a supporting axiom, an axiom stating nothing, a result of the person's stated as its own axiom) is not. Read from the axioms Lean reports, never from the record's `assumed`.
    """
    by_name = {d.get("name"): d for d in record.get("declarations", [])}
    out: list[tuple[str, str]] = []
    whole = True
    for d in _stating(record, subject):
        for axiom in d.get("axioms", []):
            if axiom in STANDARD_AXIOMS:
                continue
            found = by_name.get(axiom) or {}
            names = found.get("names")
            if found.get("kind") != "axiom" or found.get("role") != "states" or not isinstance(names, dict):
                whole = False
                continue
            [(kind, name)] = names.items()
            if (kind, name) == subject.key:
                # the library is assumed, so a node is its own axiom; a result of the person's is proved
                whole = whole and kind == "node"
            elif kind in ("node", "label"):
                out.append((kind, name))
            else:
                whole = False
    return list(dict.fromkeys(out)), whole


def relative_to(record: Record, subject: Subject) -> tuple[tuple[str, str], ...]:
    """What the result's proof in this record is verified relative to: each result Lean reports it rests on as an axiom (`assumes`), and each node the record lists as `assumed`, which only adds a wait."""
    listed = [("node", str(a.get("node"))) for a in record.get("assumed", []) if isinstance(a, dict) and "node" in a]
    return tuple(k for k in dict.fromkeys([*assumes(record, subject)[0], *listed]) if k != subject.key)


def proves(record: Record, subject: Subject) -> bool:
    """Whether Lean accepted `subject` whole in this record (`docs/specs/evidence.md` §5.2): `ok`, the kernel's replay passed, a declaration stating it, none with a `sorry`, a result of the person's not stated as an axiom, and every axiom accounted for (`assumes`)."""
    if not record.get("ok") or (record.get("replay") or {}).get("exit") != 0:
        return False
    mine = _stating(record, subject)
    if not mine or any(d.get("sorry") for d in mine):
        return False
    if subject.kind != "node" and any(d.get("kind") == "axiom" for d in mine):
        return False
    return assumes(record, subject)[1]


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
    assumed: Iterable[tuple[str, str]],
    lean_now: Callable[[Record], bool],
    seen: frozenset[str] = frozenset(),
    cites: Iterable[str] = (),
    near: Here | None = None,
) -> tuple[Waiting, ...]:
    """What keeps a result from reading formalized (`docs/specs/evidence.md` §5.2).

    `uses` are nodes that must be read and compared with their paper on their text now: those its closure holds, as it reads now and as attested, and a node asked of itself. `assumed` are what its Lean rests on as axioms (`relative_to`), a library node or a result of the person's, each held to one standard (`_assumption`). `cites` are citations no node answers for yet. What nothing can say of waits, so nothing resting on the library reads formalized before the library can answer for it.
    """
    out: list[Waiting] = [Waiting(("cite", c), "unknown") for c in dict.fromkeys(cites)]
    for node in uses:
        key = ("node", node)
        if any(w.key == key for w in out):
            continue
        why = _read_and_compared(evidence, web, node)
        if why:
            out.append(Waiting(key, why))
    for key in assumed:
        if any(w.key == key for w in out):
            continue
        why = _assumption(evidence, web, key, near, lean_now, seen)
        if why:
            out.append(Waiting(key, why))
    return tuple(out)


def _read_and_compared(evidence: Evidence, web: Web, node: str) -> str | None:
    """Why a library node is not settled as a statement is used, None when it is: `unknown` where nothing can say of it, `stub` unread, `unchecked` not compared with its paper on its text now."""
    here = Here("node", node)
    subject, stub = web.subject(here), web.stub(here)
    if subject is None or stub is None:
        return "unknown"
    if stub:
        return "stub"
    if not any(r.on is not None and r.on.hash == subject.hash for r in evidence.about("node", node, of="compared")):
        return "unchecked"
    return None


def _assumption(
    evidence: Evidence,
    web: Web,
    key: tuple[str, str],
    near: Here | None,
    lean_now: Callable[[Record], bool],
    seen: frozenset[str],
) -> str | None:
    """Why a statement another's Lean assumes does not count yet, None when it does; one standard for a library node stated as an axiom and a result of the person's assumed for now.

    It counts once its own statement is attested on its text now (its status holds a person's attestation, nothing changed and its notation attested) over Lean that elaborated (`ok`, the replay passed), whether or not that Lean proves it, since its proof is what is assumed; a node is read and compared itself; and every library node its statement uses is read and compared and every citation answered, what only its proof uses not needed. `unknown` where nothing can say of it, a node's `stub` or `unchecked`, else `unattested`; an assumption that comes round to a result already asked of never counts.
    """
    kind, name = key
    if kind == "node":
        there: Here | None = Here("node", name)
        why = _read_and_compared(evidence, web, name)
        if why:
            return why
    else:
        holder = getattr(web, "holder", None)
        there = holder(key, near) if holder is not None and near is not None else None
        if there is None:
            return "unknown"
    assert there is not None
    if name in seen:
        return "unattested"
    own = status(evidence, web, there, lean_now=lean_now, _seen=seen | {name})
    record = evidence.by_id(own.lean_record) if own.lean_record else None
    elaborated = record is not None and bool(record.get("ok")) and (record.get("replay") or {}).get("exit") == 0
    attested = own.attestation is not None and not own.causes and not own.unattested_notation
    if not (attested and elaborated and own.lean in ("failed", "waiting", "formalized")):
        return "unattested"
    cited = getattr(web, "cited", None)
    statement_uses = [k[1] for k in web.closure(there) if k[0] == "node"]
    if gate(evidence, web, statement_uses, [], lean_now, cites=list(cited(there)) if cited is not None else []):
        return "unattested"
    return None


def brief(found: Status) -> dict[str, Any]:
    """How a result stands as a row of a list carries it (`docs/specs/evidence.md` §6, §8): the Lean word with its role and what it waits on, so a row never reads a bare word; the reading of the paper is the row's `reading` beside it."""
    return {
        "lean": found.lean,
        "role": found.role,
        "waiting_on": [{w.key[0]: w.key[1], "why": w.why} for w in found.waiting_on],
    }


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
        found = replace(
            found, role=_role(current, subject), relative_to=relative_to(current, subject), lean_since=current.at
        )
    # every standing record on this text says what Lean rested on, whether or not it states the result: its uses count
    on_this = [
        r
        for r in evidence.about(kind, name, of="lean")
        if lean_now(r) and r.on is not None and r.on.hash == subject.hash
    ]
    now = closure_now(web, here, on_this or [latest])
    # a node is read and compared itself before anything is attested on it
    itself = [name] if kind == "node" else []
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
        uses = itself + [k[1] for k in now if k[0] == "node"] + attested_nodes
        waiting = gate(evidence, web, uses, found.relative_to, lean_now, _seen | {name}, cites, here)
        found = replace(found, waiting_on=waiting)
        if not proves(current, subject):
            return replace(found, lean="failed")
        if never:
            return replace(found, lean="unattested")
        return replace(found, lean="waiting" if waiting else "formalized")
    # an attestation of a text that no block bearing the label still has: this block's earlier text, which moved; one another block still has is that block's, never this one's
    texts = getattr(web, "texts", None)
    now_borne: set[str] = set(texts(subject.key)) if texts is not None else set()
    moved = [a for a in said if a.on is not None and a.on.hash not in now_borne]
    if not on_text and moved:
        # the person attested this block's earlier text, of a Lean that still stands: this text is not what they gave their word for
        earlier = moved[-1]
        if any(statements_of(r) == dict(earlier.get("statements", {})) for r in standing):
            changed, never = notation_of(evidence, web, here)
            causes = causes_of(earlier, web, here, now) + changed
            return replace(
                found, lean="changed", attestation=earlier.id, causes=tuple(causes), unattested_notation=tuple(never)
            )
    if current is None:
        return replace(found, lean="rerun")
    never = notation_of(evidence, web, here)[1]
    uses = itself + [k[1] for k in now if k[0] == "node"]
    waiting = gate(evidence, web, uses, found.relative_to, lean_now, _seen | {name}, cites, here)
    found = replace(found, unattested_notation=tuple(never), waiting_on=waiting)
    if not proves(current, subject):
        return replace(found, lean="failed")
    return replace(found, lean="unattested")
