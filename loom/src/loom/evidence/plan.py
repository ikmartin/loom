"""What asking an agent to formalize results comes to (`docs/specs/evidence.md` §7, `formal-plan`): what is to be stated, proved and assumed, what is formalized already, what stops the request, and what stands before the targets read formalized.

The plan walks what each result uses by statement and by proof from the targets, as a caller's `uses` gives it, and reads each result as a caller's `item` gives it, so the drafts and the library are walked alike. One thing stops a request, a target or a result to state or prove with no label, which the person adds by hand; nothing unread or unchecked stops it.

What stands before is the gate's own (`status.needs`), asked of the Lean the request will make: each target stated and proved, each library result to assume, and each result of the person's assumed for now, an axiom; each library result to state, and each result reached that has its Lean already, used. Each thing the gate asks is named once, and says whether the person can do it `now` or only `after` the agent's work, so the list and the gate cannot differ.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from loom.evidence.log import Evidence, Record
from loom.evidence.status import Status, Waiting

#: The kinds of result that are stated in Lean, never proved: a definition, a notation, a convention, a construction.
STATED = frozenset({"definition", "notation", "convention", "construction"})
#: Why something stands before the targets read formalized, in the order the panel lists them: a library result not read, or not compared with its paper on its text now; a citation in what the targets' statements use that names no result a node answers for; a Lean statement to attest; one attested and changed since.
WHY = ("not-read", "not-checked", "cite", "attest", "attested-changed")
#: When the person can do it: now, or only once the agent has stated it (and, for a library result, once its work's macros can be shown).
WHEN = ("now", "after")


@dataclass(frozen=True)
class Item:
    """What the plan reads of a result: whether it is the person's (a draft's) or the library's, whether it has a lasting name, whether it is stated rather than proved, and how it stands."""

    key: str
    mine: bool
    named: bool
    stated: bool
    status: Status


@dataclass(frozen=True)
class Need:
    """One thing that stands before the targets read formalized: a result's key, or a citation's `KEY LOCATOR` for `cite`; why (`WHY`); and when the person can do it (`WHEN`)."""

    key: str
    why: str
    when: str


@dataclass
class Plan:
    """A plan, each list in the order the walk reached it: `prove` with whether each was chosen assumed for now, `assume` with how each reads its paper (`not-read`, `not-checked` or None), `lean` the results reached that have their own Lean already, which the agent uses as it is, and `before` what stands before the targets read formalized."""

    targets: list[str]
    state: list[str] = field(default_factory=list)
    prove: list[tuple[str, bool]] = field(default_factory=list)
    assume: list[tuple[str, str | None]] = field(default_factory=list)
    formalized: list[str] = field(default_factory=list)
    lean: list[str] = field(default_factory=list)
    stops: list[str] = field(default_factory=list)
    before: list[Need] = field(default_factory=list)


def _paper(found: Status) -> str | None:
    """How a library result reads its paper, as a row to assume says it: not read (a stub), not compared on its text now, or nothing."""
    if found.reading == "stub":
        return "not-read"
    if found.reading != "matches":
        return "not-checked"
    return None


def plan(
    targets: list[str],
    assume: list[str],
    item: Callable[[str], Item],
    uses: Callable[[str], tuple[list[str], list[str]]],
    before: Callable[[str, Plan], list[Need]] | None = None,
) -> Plan:
    """The plan for asking an agent to formalize `targets`.

    Parameters
    ----------
    targets : list of str
        The person's results to formalize, by key.
    assume : list of str
        The person's results chosen to be assumed for now rather than proved, a target among them or one reached.
    item : callable
        A result's `Item`, by key.
    uses : callable
        What a result's statement uses and what its proofs use, each a list of keys.
    before : callable, optional
        What stands before one target reads formalized, given the plan walked so far (`needed`, over `status.needs`); without it `before` is empty.

    Returns
    -------
    Plan
        By the rules: a target is proved unless assumed for now; from a result to prove, all it uses by statement and by proof is reached, from one assumed or stated only what its statement uses; a result formalized, or one of the person's whose Lean waits for their word or changed since they gave it, has its Lean already and is not followed; a stated result not formalized is to state, another of the person's to prove, another of the library's to assume; a target, or a result to state or prove, with no label stops the request.
    """
    out = Plan(list(targets))
    chosen = set(assume)
    todo: deque[str] = deque()

    def follow(key: str, it: Item) -> None:
        statement, proofs = uses(key)
        todo.extend(statement)
        if it.mine and not it.stated and key not in chosen:
            todo.extend(proofs)

    for key in targets:
        it = item(key)
        if not it.named:
            out.stops.append(key)
        follow(key, it)
    seen = set(targets)
    while todo:
        key = todo.popleft()
        if key in seen:
            continue
        seen.add(key)
        it = item(key)
        lean = it.status.lean
        if lean == "formalized":
            out.formalized.append(key)
            out.lean.append(key)
            continue
        if it.mine and lean in ("unattested", "changed"):
            out.lean.append(key)
            continue
        if it.stated:
            out.state.append(key)
        elif it.mine:
            out.prove.append((key, key in chosen))
        else:
            out.assume.append((key, _paper(it.status)))
        if it.mine and not it.named:
            out.stops.append(key)
        follow(key, it)
    if before is not None:
        found: list[Need] = []
        for key in targets:
            found += [n for n in before(key, out) if n not in found]
        order = {(w, t): i for i, (w, t) in enumerate((w, t) for t in WHEN for w in WHY)}
        out.before = sorted(found, key=lambda n: order[n.why, n.when])
    return out


def asked(
    found: Plan, target: str, library: Callable[[str], bool], key_of: Callable[[str], tuple[str, str] | None]
) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]]]:
    """What the gate is asked of the Lean the request will make for `target`, as `status.needs` takes it: the library nodes to be read and compared, what that Lean assumes, and what it uses and does not state.

    Each library result to assume, and each result of the person's chosen assumed for now, is an axiom of that Lean; each library result to state, and each result reached that has its Lean already, is used by it; every library result reached is read and compared. A result with no lasting name (`key_of` None) is in `stops`, and is asked of nothing.
    """
    nodes = [k for k in [*found.state, *(k for k, _ in found.assume), *found.lean] if library(k)]
    assumed = [key_of(k) for k, _ in found.assume] + [key_of(k) for k, chosen in found.prove if chosen]
    rests = [key_of(k) for k in found.state if library(k)] + [key_of(k) for k in found.lean]
    return nodes, [k for k in assumed if k is not None], [k for k in rests if k is not None]


def needed(leaves: list[Waiting], own: Callable[[tuple[str, str]], tuple[str, Status, bool] | None]) -> list[Need]:
    """Each thing the gate asks (`status.needs`) as the person reads it, with when they can do it.

    A node not read or not compared, and a citation that names no result a node answers for, are the person's to do now. A Lean statement the gate asks to be attested is to attest now where Lean has accepted it on the result's text now and it waits for the person's word (`attested-changed` where they gave it before something it uses changed); after, where it has no Lean on its text now that elaborated, which the agent writes or loom runs again, or where its notation cannot be shown yet. A Lean that is attested and still asked of is waiting only on what it in turn needs, each of which is a leaf of its own. `own` gives, for a result's key, the result as a row names it, its status, and whether its current Lean is on its text now, standing and elaborated; None where nothing can say of it, which is left out.
    """
    out: list[Need] = []

    def add(need: Need) -> None:
        if need not in out:
            out.append(need)

    for w in leaves:
        kind, name = w.key
        if kind == "cite":
            add(Need(name, "cite", "now"))
            continue
        if w.why in ("stub", "unchecked"):
            add(Need(name, "not-read" if w.why == "stub" else "not-checked", "now"))
            continue
        found = own(w.key) if w.why == "unattested" else None
        if found is None:
            continue
        key, standing, elaborated = found
        if standing.lean_record is None or not elaborated or standing.lean == "rerun":
            add(Need(key, "attest", "after"))
        elif standing.lean == "changed":
            add(Need(key, "attested-changed", "now"))
        elif standing.attestation is not None and not standing.causes and standing.unattested_notation is None:
            add(Need(key, "attest", "after"))
        elif standing.attestation is None or standing.unattested_notation:
            add(Need(key, "attest", "now"))
    return out


def target_need(key: str, standing: Status, elaborated: bool) -> Need | None:
    """What a target's own Lean still needs: attested after the agent states it, where it has no Lean that elaborated; attested now where Lean accepted it and it waits; None where it is formalized, or attested and waiting only on what the rest of the list names."""
    if standing.lean == "formalized":
        return None
    if standing.lean_record is None or not elaborated or standing.lean in ("rerun", "failed"):
        return Need(key, "attest", "after")
    if standing.lean == "changed":
        return Need(key, "attested-changed", "now")
    if standing.attestation is None or standing.unattested_notation:
        return Need(key, "attest", "now" if standing.unattested_notation is not None else "after")
    return None


def elaborated(evidence: Evidence, standing: Status, lean_now: Callable[[Record], bool]) -> bool:
    """Whether a result's current Lean record is on its text now, still stands, and elaborated: accepted, and the kernel's replay passed."""
    record = evidence.by_id(standing.lean_record) if standing.lean_record else None
    return (
        record is not None
        and standing.subject is not None
        and record.on is not None
        and record.on.hash == standing.subject.hash
        and lean_now(record)
        and bool(record.get("ok"))
        and (record.get("replay") or {}).get("exit") == 0
    )
