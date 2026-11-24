"""What asking an agent to formalize results comes to (`docs/specs/evidence.md` §7, `formal-plan`): what is to be stated, proved and assumed, what is formalized already, what stops the request, and what stands before the targets read formalized.

The plan walks what each result uses by statement and by proof from the targets, as a caller's `uses` gives it, and reads each result as a caller's `item` gives it, so the drafts and the library are walked alike. One thing stops a request, a target or a result to state or prove with no label, which the person adds by hand; nothing unread or unchecked stops it.

What stands before is the gate's own (`status.needs`), asked of the Lean the request will make: each target stated and proved, each library result to assume, and each result of the person's assumed for now, an axiom; each library result to state, and each result reached that has its Lean already, used. Each thing the gate asks is named once, with what is wrong and whether the person can do it `now`, only `after` the agent's work, or nothing anyone does settles it yet (`waiting`), so the list and the gate cannot differ.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loom.evidence.log import Evidence, Record
from loom.evidence.status import Status, Waiting, own_needs
from loom.evidence.web import Web

if TYPE_CHECKING:
    from loom.evidence.acts import Unattestable

#: What the plan reads of a result a Lean statement is asked of (`needed`'s `own`): its key as a row names it, its status, whether its current Lean is on its text now, standing and elaborated, and why `formal-attest` would refuse the person's word on it now (`acts.attest_refusal`, None where it would take it), asked only where it is offered.
Own = tuple[str, Status, bool, "Callable[[], Unattestable | None]"]

#: The kinds of result that are stated in Lean, never proved: a definition, a notation, a convention, a construction.
STATED = frozenset({"definition", "notation", "convention", "construction"})
#: Why something stands before the targets read formalized, in the order the panel lists them: a library result not read, or not compared with its paper on its text now; one whose work holds no document to read or compare it with; a label two texts answer to near the targets; a label or a library result nothing answers to; a library result that names no work; a citation that names no result a node answers for; a Lean statement to attest; one attested and changed since; a Lean that comes round, through what it rests on, to a result already asked of.
WHY = (
    "not-read",
    "not-checked",
    "no-document",
    "ambiguous",
    "missing",
    "no-source",
    "cite",
    "attest",
    "attested-changed",
    "cycle",
)
#: When it can be done: by the person now; only once the agent has done its work (and, for a library result, once its work's macros can be shown); or by nobody yet, as a citation waits until loom resolves citations to results.
WHEN = ("now", "after", "waiting")
#: What a `Need`'s key names: a result, by its key; a citation (`KEY LOCATOR`); a label no one text answers to; a library node by an id the library holds no result by.
OF = ("result", "cite", "label", "node")


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
    """One thing that stands before the targets read formalized: its key, what the key names (`OF`), why (`WHY`) and when it can be done (`WHEN`)."""

    key: str
    why: str
    when: str
    of: str = "result"


@dataclass
class Plan:
    """A plan, each list in the order the walk reached it: `prove` with whether each was chosen assumed for now, `assume` with how each reads its paper (`not-read`, `not-checked` or None), `lean` the results reached that have their own Lean already, which the agent uses as it is, `before` what stands before the targets read formalized, and `asking` the targets each of those stands before."""

    targets: list[str]
    state: list[str] = field(default_factory=list)
    prove: list[tuple[str, bool]] = field(default_factory=list)
    assume: list[tuple[str, str | None]] = field(default_factory=list)
    formalized: list[str] = field(default_factory=list)
    lean: list[str] = field(default_factory=list)
    stops: list[str] = field(default_factory=list)
    before: list[Need] = field(default_factory=list)
    asking: dict[Need, list[str]] = field(default_factory=dict)


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
        for key in targets:
            for need in before(key, out):
                asking = out.asking.setdefault(need, [])
                if key not in asking:
                    asking.append(key)
        order = {(w, t): i for i, (w, t) in enumerate((w, t) for t in WHEN for w in WHY)}
        out.before = sorted(out.asking, key=lambda n: order[n.why, n.when])
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


def asked_of(
    evidence: Evidence,
    web: Web,
    standing: Status,
    lean_now: Callable[[Record], bool],
    planned: Callable[[], list[Waiting]],
) -> list[Waiting]:
    """What the gate asks before a target reads formalized: of its own Lean record, where one stands on its text now and proves it (`status.own_needs`); else of the Lean the request will make (`planned`, `status.needs` of `asked`).

    Once the agent has written the target's Lean, what it rests on is that record's, which the plan as walked now may no longer reach.
    """
    if standing.asked and standing.lean != "failed":
        return own_needs(evidence, web, standing, lean_now)
    return planned()


def needed(
    leaves: list[Waiting],
    own: Callable[[tuple[str, str]], Own | None],
    texts: Callable[[tuple[str, str]], set[str]],
    paper: Callable[[str], str | None],
) -> list[Need]:
    """Each thing the gate asks (`status.needs`) as the person reads it, with when it can be done: every leaf an entry, and a leaf of a reason this does not say refused (`ValueError`).

    `now`, what loom takes now: a node not read or not compared, or, where its work holds no document to read or compare it with (`paper`, `acts.unreadable`), that document to add (`no-document`); a label that two texts answer to near the targets (`ambiguous`, by `texts`), or a label or node nothing answers to (`missing`); a Lean statement Lean accepted on its result's text now that waits for the person's word (`attest`, `attested-changed` where they gave it before something it uses changed), offered only where `formal-attest` would take it, else what stands in its way. `after`: a Lean statement with no Lean on its text now that elaborated, which the agent writes or loom runs again, or whose notation cannot be shown yet; one attested and still asked of, whose Lean comes round to a result already asked of (`cycle`). `waiting`: a citation, until loom resolves citations to results; a node that names no work, until it is given one (`no-source`). `own` gives what the plan reads of a result (`Own`); None where no row can say of it.
    """
    out: list[Need] = []
    for w in leaves:
        kind, name = w.key
        if kind == "cite":
            found = [Need(name, "cite", "waiting", "cite")]
        elif w.why in ("stub", "unchecked"):
            found = [_reading(name, "not-read" if w.why == "stub" else "not-checked", paper)]
        elif w.why == "unknown":
            found = [_unknown(w.key, texts)]
        elif w.why == "unattested":
            found = _to_attest(name, kind, own(w.key), texts, paper)
        else:
            raise ValueError(f"the panel has no entry for the gate's {w.why!r}")
        out += [n for n in found if n not in out]
    return out


def _reading(node: str, why: str, paper: Callable[[str], str | None]) -> Need:
    """A node to read or compare against its paper: `why` now, or, where nothing can be read against, why not: its work's document to add now, or no work named, which waits."""
    cannot = paper(node)
    if cannot == "no-source":
        return Need(node, "no-source", "waiting")
    return Need(node, cannot or why, "now")


def _unknown(key: tuple[str, str], texts: Callable[[tuple[str, str]], set[str]]) -> Need:
    """A label or node nothing can say of: `ambiguous` for a label two texts answer to, else `missing`."""
    return Need(key[1], "ambiguous" if key[0] == "label" and texts(key) else "missing", "now", key[0])


def _to_attest(
    name: str,
    kind: str,
    found: Own | None,
    texts: Callable[[tuple[str, str]], set[str]],
    paper: Callable[[str], str | None],
) -> list[Need]:
    """What a Lean statement the gate asks to be attested needs, by how its result stands (`needed`).

    Attested, holding and elaborated, and still asked of, it is asked only where its Lean comes round to a result already asked of (`status.assumption_needs`), which attesting cannot settle.
    """
    if found is None:
        return [Need(name, "attest", "after", kind)]
    key, standing, elaborated, refused = found
    if standing.lean_record is None or not elaborated or standing.lean == "rerun":
        return [Need(key, "attest", "after")]
    wanted = _wanted(key, standing, refused, texts, paper)
    return wanted if wanted is not None else [Need(key, "cycle", "after")]


def _wanted(
    key: str,
    standing: Status,
    refused: Callable[[], Unattestable | None],
    texts: Callable[[tuple[str, str]], set[str]],
    paper: Callable[[str], str | None],
) -> list[Need] | None:
    """The person's word a Lean that elaborated waits for: `attested-changed` or `attest` now where `formal-attest` would take it, else what stands in its way; `attest` after where it holds but its notation cannot be shown yet; None where none is wanted."""
    if standing.lean == "changed":
        why = "attested-changed"
    elif standing.attestation is not None and standing.unattested_notation is None:
        return [Need(key, "attest", "after")]
    elif standing.attestation is None or standing.unattested_notation:
        why = "attest"
    else:
        return None
    blocked = refused()
    if blocked is None:
        return [Need(key, why, "now")]
    if blocked.code in ("no-lean", "no-such-result"):
        return [Need(key, "attest", "after")]
    return [
        *(_unknown(member, texts) for member in blocked.gone),
        *(_reading(n, "not-read", paper) for n in blocked.unread),
        *(_reading(n, "not-checked", paper) for n in blocked.unchecked),
        *(Need(c, "cite", "waiting", "cite") for c in blocked.cites),
    ]


def target_need(
    key: str,
    standing: Status,
    elaborated: bool,
    refused: Callable[[], Unattestable | None],
    texts: Callable[[tuple[str, str]], set[str]],
    paper: Callable[[str], str | None],
) -> list[Need]:
    """What a target's own Lean still needs: attested after the agent states it, where it has no Lean that elaborated; the person's word now where `formal-attest` would take it, else what stands in its way (`_wanted`); attested after where its notation cannot be shown yet; nothing where it is formalized, or attested and waiting only on what the rest of the list names."""
    if standing.lean == "formalized":
        return []
    if standing.lean_record is None or not elaborated or standing.lean in ("rerun", "failed"):
        return [Need(key, "attest", "after")]
    return _wanted(key, standing, refused, texts, paper) or []


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
