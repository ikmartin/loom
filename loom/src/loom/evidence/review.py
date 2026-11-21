"""Review's lists: each kind a rule over the evidence, the asks, the scan and the manifest, saying what puts a row in and what takes it out (`docs/specs/evidence.md` §6).

Computed when they are read, never stored; a read under the same scan and the same files as the last answers from what it computed (`memo.kept`, over `files_read`). A row is what one decision is about; it carries the ids it is addressed by and the fields its words are drawn from, never words of loom's own. `cited` and `check` are a library's, and are empty until the node store gives a web of nodes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.evidence.asks import Standing, open_asks
from loom.evidence.log import Evidence, Record
from loom.evidence.status import Status, gate, status
from loom.evidence.web import DraftWeb, Here, Web

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: Each kind, by its key, in its rank by who waits: an agent stopped until the person acts first, then what a draft rests on, then the rest (the integrator's ruling). The column draws them alphabetically by the viewer's words; this order is the list's under Everything.
KINDS: tuple[str, ...] = (
    "questions",
    "fetch",
    "cited",
    "check",
    "attest",
    "accepted-changed",
    "attested-changed",
    "edits",
)
#: What waits for an agent, apart from the kinds.
AGENTS = "agents"
#: The keys every row has; no kind's field is named for one.
ROW_KEYS = frozenset({"row", "kind", "docs"})


@dataclass
class Row:
    """One row of a list.

    `row` is its id, made from what it is about so it stays the same while that waits; `docs` the drafts it concerns; `waits` `agent` when an agent is stopped until the person acts, else `person`; `rests` whether a draft rests on it; `since` when what put it in was written; `took`, for an ask to an agent, each session that took it with the agent's name, by which `working` marks it and never sent.
    """

    row: str
    kind: str
    docs: tuple[str, ...]
    waits: str = "person"
    rests: bool = False
    since: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    took: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """As `review-list` sends it; a field named for one of `ROW_KEYS` is refused (ValueError) rather than let it overwrite the row's own."""
        clash = ROW_KEYS & self.fields.keys()
        if clash:
            raise ValueError(f"{self.row}: a field may not be named {sorted(clash)[0]}, which is the row's own")
        return {"row": self.row, "kind": self.kind, "docs": list(self.docs), **self.fields}


@dataclass
class Gathered:
    """Every row of every kind, and of what waits for an agent, gathered once for a read."""

    rows: dict[str, list[Row]] = field(default_factory=dict)

    def of(self, kind: str, doc: str | None = None) -> list[Row]:
        """A kind's rows in their order, narrowed to those that concern `doc` when given."""
        found = self.rows.get(kind, [])
        return [r for r in found if doc is None or doc in r.docs]


def _ordered(rows: list[Row]) -> list[Row]:
    """Who waits: rows an agent is stopped on first, then those a draft rests on, then the rest; ties oldest first."""
    return sorted(rows, key=lambda r: (r.waits != "agent", not r.rests, r.since, r.row))


def _name(manifest: dict[str, Any], key: str, doc: str | None) -> str:
    """A result as the person reads it: its taxon's word and its number in `doc`, as the manifest publishes them (`numbers[doc].number`); in another document that numbers it when `doc` does not; the word alone when unnumbered."""
    node = manifest.get("nodes", {}).get(key, {})
    taxon = str(node.get("taxon") or "")
    numbers = node.get("numbers") or {}
    given = numbers.get(doc) if doc else None
    given = given or next(iter(numbers.values()), None)
    number = given.get("number") if isinstance(given, dict) else given
    return f"{taxon} {number}".strip() if number else taxon


def _questions(asks: list[Standing]) -> list[Row]:
    out = []
    for s in asks:
        a = s.ask
        if a.to != "person" or a.what != "question":
            continue
        out.append(
            Row(
                f"questions:{a.id}",
                "questions",
                a.origin,
                waits="agent",
                since=a.at,
                fields={
                    "question": a.id,
                    "by": a.by.name,
                    "on": dict(a.on),
                    "text": a.get("text"),
                    "choices": list(a.get("choices", [])),
                    "quote": a.get("quote"),
                },
            )
        )
    return out


def _fetch(asks: list[Standing]) -> list[Row]:
    """An agent's open request for a paper; the work's words (`short`, `title`) come with the node store."""
    return [
        Row(
            f"fetch:{s.ask.id}",
            "fetch",
            s.ask.origin,
            waits="agent",
            since=s.ask.at,
            fields={
                "task": s.ask.id,
                "ref": s.ask.get("ref"),
                "link": s.ask.get("link"),
                "want": s.ask.get("want"),
                "by": s.ask.by.name,
                "words": s.ask.words,
            },
        )
        for s in asks
        if s.ask.to == "person" and s.ask.what == "paper"
    ]


def _agents(asks: list[Standing]) -> list[Row]:
    """What a person asked of an agent and no agent has produced; oldest first, as `_ordered` leaves them.

    `working` is left null for `working` to mark by the servers alive now; the ask's own fields go first, so none of them overwrites a field the row names.
    """
    out = []
    for s in asks:
        a = s.ask
        if a.to != "agent":
            continue
        took = tuple((str(t.get("session")), str((t.get("by") or {}).get("name") or "")) for t in a.took)
        skip = {"event", "id", "at", "by", "to", "from", "on", "what", *ROW_KEYS}
        own = {k: v for k, v in a.fields.items() if k not in skip}
        out.append(
            Row(
                f"agents:{a.id}",
                AGENTS,
                a.origin,
                since=a.at,
                fields={**own, "task": a.id, "what": a.what, "on": dict(a.on), "working": None, "asked_at": a.at},
                took=took,
            )
        )
    return out


def working(gathered: Gathered, sessions: frozenset[str]) -> Gathered:
    """Each ask to an agent marked by the agent servers alive now.

    Parameters
    ----------
    gathered : Gathered
        The rows, as `gather` computed them now or for an earlier read; never changed.
    sessions : frozenset of str
        The loom sessions of the agent servers alive now (`asks.live_sessions`).

    Returns
    -------
    Gathered
        The same rows, each of `agents` with `working` `{by}`, the agent whose live session took it last, or null where no live session took it. Whether a server is alive changes with no file changing, so a kept read is marked again each time.
    """
    marked = []
    for row in gathered.rows.get(AGENTS, []):
        live = [by for session, by in row.took if session in sessions]
        marked.append(replace(row, fields={**row.fields, "working": {"by": live[-1]} if live else None}))
    return Gathered({**gathered.rows, AGENTS: marked})


def _accepted_changed(manifest: dict[str, Any], result: ScanResult) -> list[Row]:
    """Today's ledger read through its own resolver, as the build publishes it (`manifest["unresolved"]`): a result whose acceptance went stale (`earlier-change`). A result never accepted is not listed, nor one taken in from a copy or a pull, which Proposed edits and the incoming pull show."""
    out = []
    keys = manifest.get("keys", {})
    for u in manifest.get("unresolved", []):
        if u.get("cause") != "earlier-change":
            continue
        key = u["key"]
        node = result.nodes.get(key)
        docs = tuple(node.reached_by) if node is not None else ()
        acceptance = keys.get(key, {}).get("acceptance") or {}
        doc = docs[0] if docs else None
        out.append(
            Row(
                f"accepted-changed:{key}",
                "accepted-changed",
                docs,
                since=str(acceptance.get("date") or ""),
                fields={"key": key, "name": _name(manifest, key, doc), "doc": doc},
            )
        )
    return out


@dataclass(frozen=True)
class _Result:
    """A draft's result as Review lists it: one text by its label, every block bearing it with that text, and how it stands."""

    key: str
    label: str
    docs: tuple[str, ...]
    status: Status


def _results(evidence: Evidence, web: DraftWeb, lean_now: Callable[[Record], bool]) -> list[_Result]:
    """Each draft's result some Lean record or attestation speaks of, one for each distinct text of a label; a result nothing formal names has status `none` and no row, so it is not computed."""
    named = {
        r.on.name
        for r in evidence.records
        if r.on is not None and r.on.kind == "label" and r.kind in ("lean", "attested")
    }
    out: list[_Result] = []
    for label in sorted(named):
        by_text: dict[str, list[Any]] = {}
        for node in web.bearing.get(label, []):
            here = Here("block", node.key)
            subject = web.subject(here)
            if subject is not None and subject.name == label:
                by_text.setdefault(subject.hash, []).append(node)
        for nodes in by_text.values():
            first = nodes[0]
            docs = tuple(sorted({d for n in nodes for d in n.reached_by}))
            out.append(
                _Result(first.key, label, docs, status(evidence, web, Here("block", first.key), lean_now=lean_now))
            )
    return out


def _attested_changed(results: list[_Result], manifest: dict[str, Any]) -> list[Row]:
    """A result whose attestation no longer holds, each keyed by its result (its first block), so one label on two texts is two rows.

    One whose own text or a notation row changed is a row of its own. One changed only through members of its closure rests under the first of its `causes` that is such a row, matched by the member's label and its hash now, so under the text it reads by that label; where none is, it is a row of its own.
    """
    changed = [r for r in results if r.status.lean == "changed"]
    own = {r.key: [c for c in r.status.causes if c.key == ("label", r.label) or c.key[0] == "macro"] for r in changed}
    # a result whose own words changed, by the label and the hash its text has now, as a cause names it
    heads: dict[tuple[str, str | None], str] = {
        (r.label, r.status.subject.hash): r.key for r in changed if own[r.key] and r.status.subject is not None
    }
    rows: dict[str, Row] = {}
    nested: dict[str, list[_Result]] = {}
    for r in changed:
        under = next(
            (heads[(c.key[1], c.now)] for c in r.status.causes if c.key[0] == "label" and (c.key[1], c.now) in heads),
            None,
        )
        if not own[r.key] and under is not None:
            nested.setdefault(under, []).append(r)
            continue
        doc = r.docs[0] if r.docs else None
        rows[r.key] = Row(
            f"attested-changed:{r.key}",
            "attested-changed",
            r.docs,
            rests=True,
            fields={
                "result": r.key,
                "name": _name(manifest, r.key, doc),
                "doc": doc,
                "changed": "statement" if own[r.key] else "used",
                "causes": [{"changed": {c.key[0]: c.key[1]}, "then": c.then, "now": c.now} for c in r.status.causes],
                "attestation": r.status.attestation,
                "resting": [],
            },
        )
    for key, resting in nested.items():
        row = rows[key]
        row.fields["resting"] = [
            {"result": u.key, "name": _name(manifest, u.key, u.docs[0] if u.docs else None)} for u in resting
        ]
        row.docs = tuple(sorted({*row.docs, *(d for u in resting for d in u.docs)}))
    return list(rows.values())


def _attest(
    results: list[_Result], manifest: dict[str, Any], evidence: Evidence, web: Web, lean_now: Callable[[Record], bool]
) -> list[Row]:
    """A result Lean accepted on its text now that waits for the person's word, and that may be attested now: no node of its closure is unread or uncompared, and no citation of one result of a work is left that no node answers for. What it assumes in Lean does not hold it back from being attested, only from reading formalized."""
    out = []
    # a web written before citations were asked of it cites nothing, as `status` reads it
    cited = getattr(web, "cited", None)
    for r in results:
        if r.status.lean != "unattested":
            continue
        here = Here("block", r.key)
        uses = [k[1] for k in web.closure(here) if k[0] == "node"]
        cites = list(cited(here)) if cited is not None else []
        if gate(evidence, web, uses, [], lean_now, cites=cites):
            continue
        doc = r.docs[0] if r.docs else None
        out.append(
            Row(
                f"attest:{r.key}",
                "attest",
                r.docs,
                rests=True,
                since=r.status.lean_since or "",
                fields={
                    "result": r.key,
                    "name": _name(manifest, r.key, doc),
                    "source": {"doc": doc},
                    "what": "statement and proof" if r.status.role in ("proved", "unproved") else "statement only",
                    "paper": None,
                    "lean": r.status.lean_record,
                    "waiting_on": [{w.key[0]: w.key[1], "why": w.why} for w in r.status.waiting_on],
                },
            )
        )
    return out


def _edits(result: ScanResult, reviewer: str | None, manifest: dict[str, Any]) -> list[Row]:
    """Every change waiting on the person, as Review lists it today (`pending.pending`): an agent's suggested edits and the in-place changes since their look."""
    from loom.pending import pending

    out = []
    for p in pending(result, reviewer):
        doc = p.documents[0] if p.documents else None
        out.append(
            Row(
                f"edits:{p.id}",
                "edits",
                tuple(p.documents),
                since=p.created or "",
                fields={
                    "change": p.id,
                    "type": p.kind,
                    "doc": doc,
                    "key": p.key,
                    "where": _name(manifest, p.key, doc) if p.key else None,
                    "by": p.author,
                    "state": p.state,
                    "broke": None,
                },
            )
        )
    return out


def gather(
    root: Path, result: ScanResult, manifest: dict[str, Any], *, reviewer: str | None = None, web: Web | None = None
) -> Gathered:
    """Every row of every list, from one scan and one manifest.

    Parameters
    ----------
    root : Path
        The quilt.
    result : ScanResult
        The scan the manifest was published from.
    manifest : dict
        The published manifest: names, numbers, acceptance.
    reviewer : str, optional
        Whose look and acceptances; default the manifest's reviewer.
    web : Web, optional
        The texts now; default the drafts' alone, under which `cited` and `check` are empty.

    Returns
    -------
    Gathered
        Each ask to an agent marked by the servers alive now (`working`).

    See Also
    --------
    files_read : What it reads beside the scan, for a caller that keeps it (`memo.kept`).
    """
    from loom.evidence import asks as asks_log
    from loom.evidence.log import replay
    from loom.evidence.status import files_unchanged

    reviewer = reviewer or manifest.get("reviewer", {}).get("name") or None
    drafts = DraftWeb(result, reviewer=reviewer)
    web = web or drafts
    evidence = replay(root)
    lean_now = files_unchanged(root)
    asks = open_asks(root, web=web)
    results = _results(evidence, drafts, lean_now)
    gathered = Gathered()
    gathered.rows = {
        "questions": _questions(asks),
        "fetch": _fetch(asks),
        "cited": [],
        "check": [],
        "attest": _attest(results, manifest, evidence, web, lean_now),
        "accepted-changed": _accepted_changed(manifest, result),
        "attested-changed": _attested_changed(results, manifest),
        "edits": _edits(result, reviewer, manifest),
        AGENTS: _agents(asks),
    }
    gathered.rows = {k: _ordered(v) for k, v in gathered.rows.items()}
    return working(gathered, asks_log.live_sessions(root))


def files_read(root: Path) -> list[Path]:
    """Every file `gather` reads beside the scan, for a read kept while none changes (`memo.kept`).

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    list of Path
        `memo.read_files` (the logs, the manifest, the Lean files records name); every person's look, since whose is read from the manifest, and the folder they are in; the door's journal and its index, by which a suggested edit reads `taken`; the acceptance ledger; and the person's configuration, which names the reviewer before a build does. Which agent servers are alive is not a file's, and `working` marks it on every read.
    """
    from loom.evidence.memo import read_files
    from loom.paths import JOURNAL, JOURNAL_INDEX, LEDGER, LOOKED
    from loom.scan.quilt import user_config_path

    looks = root / LOOKED
    try:
        each = sorted(looks.iterdir())
    except OSError:
        each = []
    return [*read_files(root), looks, *each, root / JOURNAL, root / JOURNAL_INDEX, root / LEDGER, user_config_path()]


def counts(gathered: Gathered, documents: list[str]) -> dict[str, Any]:
    """`review-counts`: each kind's rows, what waits for an agent, everything, and for each draft what waits for the person that concerns it."""
    kinds = {k: len(gathered.of(k)) for k in KINDS}
    return {
        "everything": sum(kinds.values()),
        "kinds": kinds,
        "agents": len(gathered.of(AGENTS)),
        "drafts": [{"doc": d, "n": sum(len(gathered.of(k, d)) for k in KINDS)} for d in documents],
    }


def listed(gathered: Gathered, kind: str, doc: str | None = None) -> list[dict[str, Any]]:
    """`review-list`'s groups: one kind, what waits for an agent, or everything in rank order with what waits for an agent last; empty groups left out."""
    kinds = [*KINDS, AGENTS] if kind == "all" else [kind]
    return [{"kind": k, "rows": [r.to_dict() for r in gathered.of(k, doc)]} for k in kinds if gathered.of(k, doc)]


def find(gathered: Gathered, row: str) -> Row | None:
    """The row with this id, wherever it is."""
    return next((r for rows in gathered.rows.values() for r in rows if r.row == row), None)


def body_of(row: Row, manifest: dict[str, Any]) -> dict[str, Any]:
    """What an open row's body is drawn from, beyond its fields: an accepted result's change as the build published it, a proposed edit's change and its patch; the rest draw from their fields until formalization and the library give their bodies more."""
    if row.kind == "accepted-changed":
        entry = manifest.get("keys", {}).get(row.fields["key"], {})
        return {"acceptance": entry.get("acceptance"), "review_fragment": entry.get("review_fragment")}
    if row.kind == "edits":
        change = next((c for c in manifest.get("changes", []) if c.get("id") == row.fields["change"]), None)
        return {"change": change}
    return {}
