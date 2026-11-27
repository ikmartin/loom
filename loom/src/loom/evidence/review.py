"""Review's lists: each kind a rule over the evidence, the asks, the scan and the manifest, saying what puts a row in and what takes it out (`docs/specs/evidence.md` §6).

Computed when they are read, never stored; a read under the same scan and the same files as the last answers from what it computed (`memo.kept`, over `files_read`). A row is what one decision is about; it carries the ids it is addressed by and the fields its words are drawn from, never words of loom's own. `cited` and `check` are the library's, and are empty: a row of either names its work, whose reference the node store does not give yet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.evidence.asks import Standing, open_asks
from loom.evidence.log import Evidence, Record
from loom.evidence.status import Status, brief, gate, status
from loom.evidence.web import DraftWeb, Here, Joined, LibraryWeb, Web
from loom.formal.reading import latest, read_names, stale

if TYPE_CHECKING:
    from loom.library.index import NodeIndex
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

    `row` is its id, made from what it is about so it stays the same while that waits; `docs` the drafts it concerns; `waits` `agent` when an agent is stopped until the person acts, else `person`; `rests` whether a draft rests on it; `since` when what put it in was written; `took`, for an ask to an agent, each session that took it with the agent's name, by which `working` marks it and never sent; `body`, for `attest`, what its body is drawn from.
    """

    row: str
    kind: str
    docs: tuple[str, ...]
    waits: str = "person"
    rests: bool = False
    since: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    took: tuple[tuple[str, str], ...] = ()
    #: What its body is drawn from where the list computed it, sent by `review-row` alone.
    body: dict[str, Any] | None = field(default=None, repr=False)

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


def _questions(asks: list[Standing], every: Mapping[str, Any]) -> list[Row]:
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
                    "under": _under(every.get(str(a.get("under") or ""))),
                },
            )
        )
    return out


def _under(task: Any) -> dict[str, Any] | None:
    """The task an agent's question was asked under, as a row names it so the viewer can say what the agent was doing: its id, its `what` and its place; None where it names none."""
    if task is None:
        return None
    return {"task": task.id, "what": task.what, "on": dict(task.on), "ref": task.get("ref")}


def _how(found: Status | None) -> dict[str, Any]:
    """A result's `reading` and `lean` as a row carries them (`status.brief`); `none` for one no record names."""
    found = found or Status(None)
    return {"reading": found.reading, "lean": brief(found)}


def _at(evidence: Evidence, record: str | None) -> str | None:
    """When a record was written, by its id; None for none."""
    found = evidence.by_id(record) if record else None
    return found.at if found is not None else None


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


def _accepted_changed(manifest: dict[str, Any], result: ScanResult, standing: dict[str, Status]) -> list[Row]:
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
                fields={"key": key, "name": _name(manifest, key, doc), "doc": doc, **_how(standing.get(key))},
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


def _results(evidence: Evidence, drafts: DraftWeb, web: Web, lean_now: Callable[[Record], bool]) -> list[_Result]:
    """Each draft's result some Lean record or attestation speaks of, one for each distinct text of a label; a result nothing formal names has status `none` and no row, so it is not computed."""
    named = {
        r.on.name
        for r in evidence.records
        if r.on is not None and r.on.kind == "label" and r.kind in ("lean", "attested")
    }
    out: list[_Result] = []
    for label in sorted(named):
        by_text: dict[str, list[Any]] = {}
        for node in drafts.bearing.get(label, []):
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


def _library_results(evidence: Evidence, web: Web, lean_now: Callable[[Record], bool]) -> list[tuple[str, Status]]:
    """Each library node some Lean record or attestation speaks of, with its status; a node nothing formal names has no row, so it is not computed."""
    named = sorted(
        {
            r.on.name
            for r in evidence.records
            if r.on is not None and r.on.kind == "node" and r.kind in ("lean", "attested")
        }
    )
    out = []
    for node in named:
        found = status(evidence, web, Here("node", node), lean_now=lean_now)
        if found.subject is not None:
            out.append((node, found))
    return out


def _check(
    root: Path, evidence: Evidence, web: Web, library: LibraryWeb, lean_now: Callable[[Record], bool]
) -> list[Row]:
    """Results to check (library-views.md §4.3, `check`): a row a work, its statements with a text not compared with their paper on their text now; and a row for each open correction an agent proposed, with the word diff of the two bodies.

    No draft rests on a library result until citations resolve to results, so `rests` names no document yet and the rows are in the order of their works.
    """
    from loom.evidence.subjects import is_node
    from loom.library.index import opened
    from loom.library.store import node_ids, read

    by_work: dict[str, list[dict[str, Any]]] = {}
    proposals: list[tuple[str, Any, str]] = []
    for node in node_ids(root):
        if not is_node(node, "statement"):
            continue
        found = status(evidence, web, Here("node", node), lean_now=lean_now)
        held = library.file(node)
        if found.subject is None or held is None:
            continue
        ref = held[1].source or ""
        if found.reading == "unchecked":
            by_work.setdefault(ref, []).append(
                {
                    "node": node,
                    "name": node_name(held[1]),
                    "number": held[1].number,
                    "title": held[1].title,
                    "rests": {"docs": []},
                    "how": found.how,
                }  # fmt: skip
            )
        if found.proposal is not None:
            proposals.append((node, held[1], found.proposal))
    corrections: list[Row] = []
    if proposals:
        # one index and one library for every correction's take check: one per row stats every node file and lists the folder each time
        with opened(root) as index:
            corrections = [_correction(root, evidence, library, n, held, p, index) for n, held, p in proposals]
    out = []
    for ref, nodes in sorted(by_work.items()):
        work = read(root, ref) if ref else None
        out.append(Row(f"check:{ref or 'none'}", "check", (), fields={"ref": ref or None, "short": library.short(ref), "pdf": work.pdf if work is not None else None, "nodes": nodes}))  # fmt: skip
    return out + corrections


def _cited(
    root: Path, drafts: DraftWeb, manifest: dict[str, Any], evidence: Evidence, library: LibraryWeb
) -> list[Row]:
    """Cited results loom can't read (library-views.md §4.3, `cited`): each citation, in a block of the person's documents, of a library work that names no result of it, while no `mention` of it holds; its body the citing block and which of its citations it is. A stub a draft rests on is listed once citations resolve to results."""
    from loom.evidence.acts import bare_citation
    from loom.evidence.asks import mention_holds
    from loom.evidence.web import citations_in
    from loom.library.index import NodeIndex
    from loom.library.store import folder
    from loom.scan.source import blank_comments

    result = drafts.result
    if not folder(root).is_dir():
        return []
    out: list[Row] = []
    with NodeIndex.open(root) as index:
        for node in sorted(drafts.blocks, key=lambda n: n.key):
            docs = [d for d in node.reached_by if result.document_role(d) == "person"]
            if not docs:
                continue
            seen: set[str] = set()
            for citekey, locator in citations_in(blank_comments(drafts.text(node))):
                found = index.reference(citekey) if not locator else None
                # a mention is on the block its text went to, so one on a place key stays with its block when another is put in above it
                if found is None or found.id in seen or mention_holds(evidence, node.key, found.id, drafts.placed):
                    continue
                seen.add(found.id)
                where = _name(manifest, node.key, docs[0])
                cite = {"doc": docs[0], "key": node.key, "where": where, "fragment": manifest.get("nodes", {}).get(node.key, {}).get("fragment"), "nth": bare_citation(result, node.key, citekey)}  # fmt: skip
                fields = {"citation": f"{found.id}@{node.key}", "doc": docs[0], "key": node.key, "where": where, "ref": found.id, "short": library.short(found.id), "citekey": citekey}  # fmt: skip
                out.append(
                    Row(f"cited:{found.id}@{node.key}", "cited", tuple(docs), fields=fields, body={"cite": cite})
                )
    return out


def _correction(
    root: Path, evidence: Evidence, library: LibraryWeb, node: str, held: Any, proposal: str, index: NodeIndex
) -> Row:
    """An open correction as a `check` row: whose it is, why taking it would be refused now (`refusal`, by take's own check, `acts.take_refusal`; null where it would be taken, the take offered only then), and as its body when the person compared the text it would replace and the word diff of the two bodies (`runs`, `=` kept, `-` the person's words, `+` the agent's)."""
    from loom.evidence.acts import take_refusal
    from loom.library.node import NodeUnreadable, read_node
    from loom.pending import cut

    found = evidence.by_id(proposal)
    assert found is not None and found.on is not None
    try:
        new = read_node(str(found.get("bytes")).encode("utf-8"), f"{node}.node").body
    except NodeUnreadable:
        new = ""
    old = held.body
    runs: list[list[str]] = []
    at = 0
    for o0, o1, n0, n1 in cut(old, new):
        runs += [["=", old[at:o0]]] if o0 > at else []
        runs += [["-", old[o0:o1]]] if o1 > o0 else []
        runs += [["+", new[n0:n1]]] if n1 > n0 else []
        at = o1
    runs += [["=", old[at:]]] if at < len(old) else []
    compared = [r.at for r in evidence.compared("node", node, found.on.hash)]
    refused = take_refusal(root, proposal, index, library)
    fields = {"correction": proposal, "node": node, "name": node_name(held), "ref": held.source, "short": library.short(held.source), "by": found.by.name, "refusal": str(refused) if refused else None}  # fmt: skip
    return Row(f"check:{proposal}", "check", (), since=found.at, fields=fields, body={"compared_at": compared[-1] if compared else None, "runs": runs})  # fmt: skip


def _attested_changed(results: list[_Result], manifest: dict[str, Any], evidence: Evidence) -> list[Row]:
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
                "attested_at": _at(evidence, r.status.attestation),
                "reading": r.status.reading,
                "lean": brief(r.status),
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


def _may_attest(evidence: Evidence, web: Web, here: Here, lean_now: Callable[[Record], bool]) -> bool:
    """Whether nothing under the result keeps it from being attested now: no node of its closure is unread or uncompared, and no citation of one result of a work is left that no node answers for."""
    # a web written before citations were asked of it cites nothing, as `status` reads it
    cited = getattr(web, "cited", None)
    uses = [k[1] for k in web.closure(here) if k[0] == "node"]
    cites = list(cited(here)) if cited is not None else []
    return not gate(evidence, web, uses, [], lean_now, cites=cites)


def node_name(found: Any) -> str:
    """A library node as the person reads it: its taxon's word and the number its source prints, the word alone where it prints none."""
    return f"{found.taxon} {found.number}".strip() if found.number else str(found.taxon)


def _attest(
    results: list[_Result],
    nodes: list[tuple[str, Status]],
    manifest: dict[str, Any],
    evidence: Evidence,
    web: Web,
    library: LibraryWeb,
    lean_now: Callable[[Record], bool],
) -> list[Row]:
    """A result Lean accepted on its text now that waits for the person's word and may be attested now (`_may_attest`): a draft's, and a library node's once it matches its paper, since nothing is attested on a node nobody checked. What it assumes in Lean does not hold it back from being attested, only from reading formalized."""
    out = []
    for r in results:
        here = Here("block", r.key)
        if r.status.lean != "unattested" or not _may_attest(evidence, web, here, lean_now):
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
                    "record": r.status.lean_record,
                    "reading": r.status.reading,
                    "lean": brief(r.status),
                },
                body=_attest_body(evidence, web, library, here, r.status, manifest, doc),
            )
        )
    for node, found in nodes:
        here = Here("node", node)
        if found.lean != "unattested" or found.reading != "matches" or not _may_attest(evidence, web, here, lean_now):
            continue
        held = library.file(node)
        out.append(
            Row(
                f"attest:{node}",
                "attest",
                (),
                since=found.lean_since or "",
                fields={
                    "result": node,
                    "name": node_name(held[1]) if held else node,
                    "source": {
                        "ref": held[1].source if held else None,
                        "short": library.short(held[1].source) if held else None,
                    },  # fmt: skip
                    "what": "statement only",
                    "paper": found.reading,
                    "record": found.lean_record,
                    "reading": found.reading,
                    "lean": brief(found),
                },
                body=_attest_body(evidence, web, library, here, found, manifest, None),
            )
        )
    return out


def _attest_body(
    evidence: Evidence,
    web: Web,
    library: LibraryWeb,
    here: Here,
    found: Status,
    manifest: dict[str, Any],
    doc: str | None,
) -> dict[str, Any]:
    """What a row to attest opens on (`docs/specs/evidence.md` §7, `review-row`): the Lean record to attest, the statement, the Lean that states it and each definition of the project that Lean's statement names, mapped to the result it stands for, all as loom's check read them; its notation, what it uses that the person attested and when, the declarations that only serve its proof, and the latest agent's reading of the Lean, null where none."""
    record = next((r for r in evidence.of_kind("lean") if r.id == found.lean_record), None)
    if here.kind == "block":
        statement: dict[str, Any] = {"fragment": manifest.get("nodes", {}).get(here.name, {}).get("fragment")}
    else:
        held = library.file(here.name)
        statement = {"body": held[1].body if held else None, "macros": library.macros(held[1].source) if held else None}
    rows = web.notation(here)
    notation = (
        None
        if rows is None
        else [
            {
                "part": name,
                "from": "macros" if here.kind == "node" else "preamble",
                "attested": any(
                    r.on is not None and r.on.hash == digest for r in evidence.about("macro", name, of="attested")
                ),  # fmt: skip
            }
            for name, digest in sorted(rows.items())
        ]
    )
    uses: list[dict[str, Any]] = []
    for (kind, name), digest in sorted(web.closure(here).items()):
        said = [r for r in evidence.about(kind, name, of="attested") if r.by.kind == "person" and r.on is not None and r.on.hash == digest]  # fmt: skip
        if not said:
            continue
        there = web.holder((kind, name), here) if kind == "label" else Here("node", name)
        key = there.name if there is not None else name
        uses.append({"result": key, "name": _name(manifest, key, doc) if kind == "label" else name, "at": said[-1].at})
    decls = {d["name"]: d for d in (record.get("declarations", []) if record else [])}
    on = record.on if record else None
    states = [n for n, d in decls.items() if on is not None and d.get("role") == "states" and d.get("names") == {on.kind: on.name}]  # fmt: skip
    read = read_names(record) if record else []
    supporting = [n for n, d in decls.items() if d.get("role") == "supports"]
    return {
        "observation": found.lean_record,
        "statement": statement,
        "lean": [{"name": n, "kind": decls[n]["kind"], "shown": decls[n].get("shown")} for n in states],
        "definitions": _definitions(
            evidence, web, library, here, decls, [n for n in read if n not in states], manifest, doc
        ),
        "notation": notation,
        "uses_attested": uses,
        "supporting": supporting,
        "account": _account(evidence, found),
    }


def _account(evidence: Evidence, found: Status) -> dict[str, Any] | None:
    """The latest agent's reading of the result's Lean (`formal.reading`), as the person reads it beside loom's Lean: who read it and when, the record it read, whether a newer one states the result since, and its parts and difference; None where no agent read it."""
    if found.subject is None:
        return None
    said = latest(evidence, *found.subject.key)
    if said is None:
        return None
    return {
        "by": said.by.name,
        "at": said.at,
        "observation": said.get("lean"),
        "stale": stale(evidence, said),
        "parts": [dict(p) for p in said.get("parts", [])],
        "difference": said.get("difference"),
    }


def _definitions(
    evidence: Evidence,
    web: Web,
    library: LibraryWeb,
    here: Here,
    rows: dict[str, dict[str, Any]],
    named: list[str],
    manifest: dict[str, Any],
    doc: str | None,
) -> list[dict[str, Any]]:
    """Each declaration `named`, those the stating declarations' statements name and what those name in turn (`formal.reading.read_names`), as the Lean record has them, each beside the result its marker says it stands for, or none.

    One that stands for a result carries that result's statement and when the person attested its own Lean on its text now; one that stands for none is the Lean's alone, and the person's word on this result covers it, since its statement hash takes it in (`formal/check._statement_hashes`).
    """
    out: list[dict[str, Any]] = []
    closure = web.closure(here)
    for name in named:
        d = rows[name]
        stands: dict[str, Any] | None = None
        names = d.get("names")
        if isinstance(names, dict) and names:
            kind, target = next(iter(names.items()))
            digest = closure.get((kind, target))
            said = [r for r in evidence.about(kind, target, of="attested") if r.by.kind == "person" and digest is not None and r.on is not None and r.on.hash == digest]  # fmt: skip
            if kind == "label":
                there = web.holder((kind, target), here)
                key = there.name if there is not None else None
                stands = {
                    "result": key,
                    "name": _name(manifest, key, doc) if key else target,
                    "statement": {"fragment": manifest.get("nodes", {}).get(key, {}).get("fragment")} if key else None,
                }
            else:
                held = library.file(target)
                stands = {
                    "result": target,
                    "name": node_name(held[1]) if held else target,
                    "statement": {"body": held[1].body, "macros": library.macros(held[1].source)} if held else None,
                }
            stands["attested"] = said[-1].at if said else None
        out.append({"name": name, "kind": d["kind"], "shown": d.get("shown"), "stands_for": stands})
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
        The texts now; default the drafts' and the library's (`Joined`).

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
    library = LibraryWeb(root)
    web = web or Joined(drafts, library)
    evidence = replay(root)
    lean_now = files_unchanged(root)
    asks = open_asks(root, web=web)
    results = _results(evidence, drafts, web, lean_now)
    gathered = Gathered()
    gathered.rows = {
        "questions": _questions(asks, asks_log.replay(root).asks),
        "fetch": _fetch(asks),
        "cited": _cited(root, drafts, manifest, evidence, library),
        "check": _check(root, evidence, web, library, lean_now),
        "attest": _attest(
            results, _library_results(evidence, web, lean_now), manifest, evidence, web, library, lean_now
        ),
        "accepted-changed": _accepted_changed(manifest, result, {r.key: r.status for r in results}),
        "attested-changed": _attested_changed(results, manifest, evidence),
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
    """What an open row's body is drawn from, beyond its fields: an accepted result's change as the build published it, a proposed edit's change and its patch, when an attestation that no longer holds was made; the rest draw from their fields until formalization and the library give their bodies more."""
    if row.kind == "accepted-changed":
        entry = manifest.get("keys", {}).get(row.fields["key"], {})
        return {"acceptance": entry.get("acceptance"), "review_fragment": entry.get("review_fragment")}
    if row.kind == "edits":
        change = next((c for c in manifest.get("changes", []) if c.get("id") == row.fields["change"]), None)
        return {"change": change}
    if row.body is not None:
        return row.body
    if row.kind == "attested-changed":
        # "What you attested, on …": the rest of what was attested comes with formalization
        return {"at": row.fields["attested_at"]}
    return {}
