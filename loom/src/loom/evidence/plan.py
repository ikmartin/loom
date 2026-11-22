"""What asking an agent to formalize results comes to (`docs/specs/evidence.md` §7, `formal-plan`): what is to be stated, proved and assumed, what is formalized already, what stops the request, and what will keep the targets from reading formalized.

The plan walks what each result uses by statement and by proof from the targets, as a caller's `uses` gives it, and reads each result as a caller's `item` gives it, so the drafts and the library are walked alike. One thing stops a request, a target or a result to state or prove with no label, which the person adds by hand; nothing unread or unchecked stops it, it only stands before the result reads formalized.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from loom.evidence.status import Status

#: The kinds of result that are stated in Lean, never proved: a definition, a notation, a convention, a construction.
STATED = frozenset({"definition", "notation", "convention", "construction"})
#: Why a result stands before the targets read formalized, in the order the panel lists them.
WHY = ("not-read", "not-checked", "attest", "attested-changed")


@dataclass(frozen=True)
class Item:
    """What the plan reads of a result: whether it is the person's (a draft's) or the library's, whether it has a lasting name, whether it is stated rather than proved, and how it stands."""

    key: str
    mine: bool
    named: bool
    stated: bool
    status: Status


@dataclass
class Plan:
    """A plan, each list in the order the walk reached it: `prove` with whether each was chosen assumed for now, `assume` with why each stands before (or None), `before` by `WHY`."""

    targets: list[str]
    state: list[str] = field(default_factory=list)
    prove: list[tuple[str, bool]] = field(default_factory=list)
    assume: list[tuple[str, str | None]] = field(default_factory=list)
    formalized: list[str] = field(default_factory=list)
    stops: list[str] = field(default_factory=list)
    before: dict[str, list[str]] = field(default_factory=lambda: {w: [] for w in WHY})


def _paper(found: Status) -> str | None:
    """Why a library result stands before by its reading of its paper: not read (a stub), not compared on its text now, or nothing."""
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

    Returns
    -------
    Plan
        By the rules: a target is proved unless assumed for now; from a result to prove, all it uses by statement and by proof is reached, from one assumed or stated only what its statement uses; a result formalized is listed and not followed, and so is one of the person's that Lean accepted and waits to be attested (`attest`) or that changed since it was attested (`attested-changed`); a stated result not formalized is to state, another of the person's to prove, another of the library's to assume, a library result also before when not read or not compared, or when its own Lean statement waits for the person's word; a target, or a result to state or prove, with no label stops the request.
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
            continue
        if it.mine and lean in ("unattested", "changed"):
            out.before["attest" if lean == "unattested" else "attested-changed"].append(key)
            continue
        if it.stated:
            out.state.append(key)
        elif it.mine:
            out.prove.append((key, key in chosen))
        if it.mine and not it.named:
            out.stops.append(key)
        if not it.mine:
            why = _paper(it.status)
            if not it.stated:
                out.assume.append((key, why))
            if why:
                out.before[why].append(key)
            if lean in ("unattested", "changed"):
                out.before["attest" if lean == "unattested" else "attested-changed"].append(key)
        follow(key, it)
    return out
