"""Digest: a work's results written as nodes from its TeX source's survey, by loom's own hand (`docs/specs/nodes.md` §4, §6; `docs/design/library.md`, "Digesting and checking").

An item is written once the survey confirms what it prints: its number, and the number of each heading or display outside every node its text points at. Its text is the source's as it stands with its pointers rewritten: a result of the same work becomes that node's id, a stub where it has none; a `\\label` in it an anchor of the node; a heading or a display outside every node the number the work prints for it; a citation the reference's id, or the node of the one result its note locates, a stub where none is read. A work cited is the reference the library holds stating its identifier or the same entry, else one made from the source's own bibliography (`how` `cited`). A node another hand wrote, or a person compared, is kept as it is; loom writes again only its own extraction. Each text written is recorded `digested`, how `extracted` (`evidence.acts.digested`), and each stub of the work its source does not print `sought`. What cannot be written waits, and says why.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.library import body as bodies
from loom.library import ids
from loom.library.node import Node
from loom.library.survey import Item, Label, Survey
from loom.scan.labels import base36_encode
from loom.scan.tokenize import match_group, read_mandatory, read_optional, skip_space

if TYPE_CHECKING:
    from loom.evidence.log import Evidence
    from loom.evidence.subjects import Who
    from loom.library.intake import Library
    from loom.scan.scan import ScanResult

_LABEL = re.compile(r"\\label(?![A-Za-z@])")
#: Commands whose one label loom may write as the number the work prints for it, and how it prints it.
_PRINTED = {"ref": "{}", "eqref": "({})"}
#: Headings' kinds, as the survey names a heading's label.
_HEADINGS = frozenset({"part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph"})


class DigestRefused(ValueError):
    """A digest loom will not run: `code` is `no-such-ref`, `no-source` (the work holds no TeX source), `reading` (its survey is not ready), `no-document` (a work named holds neither document) or `no-reviewer` (an ask with no name to record)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Digested:
    """What one digest of a work wrote, or would write.

    `made` the nodes written new (statements with their proofs, stubs and references), `filled` the stubs given their text under their ids, `rewritten` loom's own earlier extraction written again where the source now reads otherwise, `kept` the nodes another hand wrote or a person compared, left as they are, `numbered` those of them whose waiting display numbers the person's compile filled in, nothing else changed (`evidence.acts.numbered`), `waiting` each item not written with why, and `sought` the work's stubs its source does not print.
    """

    ref: str
    made: list[str] = field(default_factory=list)
    filled: list[str] = field(default_factory=list)
    rewritten: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    numbered: list[str] = field(default_factory=list)
    waiting: dict[str, str] = field(default_factory=dict)
    sought: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        """As an answer carries it."""
        return {
            "ref": self.ref,
            "made": self.made,
            "filled": self.filled,
            "rewritten": self.rewritten,
            "kept": self.kept,
            "numbered": self.numbered,
            "waiting": self.waiting,
            "sought": self.sought,
        }


class _Wait(Exception):
    """An item that cannot be written yet, and why."""


@dataclass
class _Body:
    """A body rewritten: its text, what it points at as uses and as mentions, the numbers of the anchors it defines, and those whose number waits for the person's compile."""

    text: str
    uses: set[str] = field(default_factory=set)
    mentions: set[str] = field(default_factory=set)
    anchors: dict[str, str] = field(default_factory=dict)
    awaiting: set[str] = field(default_factory=set)


@dataclass
class _Cited:
    """A work the source cites: its entry as the source's bibliography has it, and the reference that holds it (`ref`), or None until one is made."""

    key: str
    entry: str
    fields: dict[str, str]
    ref: str | None = None


def digest(
    result: ScanResult,
    ref: str,
    items: Iterable[str],
    s: Survey,
    *,
    closure: bool = False,
    write: bool = True,
    numbers: bool = False,
) -> Digested:
    """Write a work's items as nodes from its source's survey, as loom's own act.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, which stems are drawn against.
    ref : str
        The work's reference, which holds the TeX source `s` surveys.
    items : iterable of str
        The survey's items to digest (`Item.item`); one not in the survey waits.
    s : Survey
        The source's survey, `ready`, confirmed against the work's stored PDF or by a compile.
    closure : bool, default False
        Digest too each result of the work a statement written points at, by its own text and so on, as scope `used` does: what a draft rests on is a cited result's statement and what it needs to say what it means, never its proof's.
    write : bool, default True
        Write the nodes and records, under the id lock and the library's lock; False says what would be written, and takes no lock.
    numbers : bool, default False
        The person's digest after their compile (`s.compiled`): fill the compile's display numbers into the anchors waiting in a node kept as another hand's or a person's, nothing else of it (`evidence.acts.numbered`). The unasked path never passes it.

    Returns
    -------
    Digested
        What was written, kept and left waiting.

    Raises
    ------
    DigestRefused
        `no-such-ref`, `no-source` or `reading`; nothing is written.

    See Also
    --------
    used : the items a draft cites, scope `used`.
    undigested : the items no node holds, scope `all`.
    """
    from loom.library.gather import writing
    from loom.library.store import read

    root = result.quilt.root
    work = read(root, ref)
    if work is None or work.taxon != "reference":
        raise DigestRefused("no-such-ref", f"the library has no work {ref}")
    if not work.tex or work.tex != s.tex:
        raise DigestRefused("no-source", f"{ref} holds no TeX source to digest")
    if s.state != "ready":
        raise DigestRefused("reading", f"the survey of {ref}'s source is {s.state}")
    with writing(root) if write else nullcontext():
        return _Run(result, work, s, write, closure, numbers and s.compiled).run(list(dict.fromkeys(items)))


#: What a digest takes of a work (`library-digest`'s `scope`).
SCOPES = ("used", "marked", "chosen", "all")
#: Each scope as the asks log words it (`evidence.asks.SCOPES`).
_ASKED = {"used": "uses", "marked": "marked", "chosen": "chosen", "all": "all"}


@dataclass
class Asked:
    """What the person's digest did: `made` the nodes written now, `tasks` the asks made of an agent for works held only as a PDF, `job` the job compiling a source first where one was started, and `waiting` each work's results that wait, with why."""

    made: int = 0
    tasks: list[str] = field(default_factory=list)
    job: str | None = None
    waiting: dict[str, dict[str, str]] = field(default_factory=dict)


def digest_works(
    result: ScanResult, refs: list[str] | None, scope: str, chosen: list[str] | None, *, by: Who | None, online: bool
) -> Asked:
    """`library-digest`: the person digests works by a scope, each as what it holds allows.

    From a TeX source loom writes the nodes now, from its survey (`digest`); where the work holds no PDF to confirm its numbers by and no compile has judged it, the compile is started first as a job, the person's own act (`survey.complete`), and the nodes are written when it is done. A work held only as a PDF gets one ask of an agent, which waits in Review.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, its citations resolved.
    refs : list of str or None
        The works; None for every work holding a document, those the drafts cite for `used`.
    scope : str
        One of `SCOPES`: what the drafts cite (with what their statements use in the same work), the person's marks, the results `chosen` names, or all.
    chosen : list of str or None
        For `chosen`: survey items, and nodes for stubs the survey does not hold, which stay as they are.
    by : Who or None
        The person, by the name an ask records; None where the quilt names none, which only an ask needs.
    online : bool
        Whether a compile may fetch what the source's text names and loom's TeX lacks.

    Returns
    -------
    Asked

    Raises
    ------
    DigestRefused
        `no-such-ref`; `no-document` for a work named that holds neither document; `no-reviewer` where an agent must be asked and the person has no name to ask by.
    """
    from loom.evidence.asks import ask
    from loom.library.jobs import jobs_of
    from loom.library.reads import surveyed
    from loom.library.store import read

    root = result.quilt.root
    out = Asked()
    if refs is None:
        cited = {c.ref for c in result.edges.cites if c.ref}
        held = [n.id for n in (read(root, r) for r in _references(root)) if n is not None and (n.tex or n.pdf)]
        refs = [r for r in held if scope != "used" or r in cited]
        named = False
    else:
        named = True
    for ref in refs:
        work = read(root, ref) if ids.kind_of(ref) == ids.REFERENCE else None
        if work is None:
            raise DigestRefused("no-such-ref", f"the library has no work {ref[:80]}")
        if not work.tex and not work.pdf:
            if named:
                raise DigestRefused("no-document", f"{ref} holds neither a PDF nor a TeX source to digest from")
            continue
        if work.tex:
            s = surveyed(root, work)
            if s is None or s.state != "ready":
                out.waiting[ref] = {"": f"its source's survey is {s.state if s else 'missing'}: {s.why if s else ''}"}
                continue
            if s.why == "no-pdf" and not s.compiled:
                out.job = jobs_of(root).submit(partial(_compiled, root, ref, scope, chosen, online))
                continue
            done = digest(result, ref, scoped(result, ref, s, scope, chosen), s, closure=scope == "used", numbers=True)
            out.made += len(done.made) + len(done.filled) + len(done.rewritten)
            if done.waiting:
                out.waiting[ref] = done.waiting
            continue
        fields = _for_reader(result, ref, scope, chosen)
        if fields is not None:
            if by is None:
                raise DigestRefused("no-reviewer", "an ask records who asks: choose your reviewer name in Settings")
            out.tasks.append(ask(root, by, "digest", "agent", {"ref": ref}, ref=ref, scope=_ASKED[scope], **fields).id)
    return out


def _references(root: Path) -> list[str]:
    from loom.library.store import node_ids

    return [i for i in node_ids(root) if ids.kind_of(i) == ids.REFERENCE]


def scoped(result: ScanResult, ref: str, s: Survey, scope: str, chosen: list[str] | None) -> list[str]:
    """The survey's items a scope takes of a work: what the drafts cite (`used`), every item no node holds with its text (`all`), the items `chosen` names and those of the stubs it names, or the items the person's marks to digest are on (`marked`): a mark naming a stub, that stub's item; one naming none, the item on its page whose opening words it holds. After the person's compile every scope takes too each item whose node or proof has an anchor `awaiting` its number, so the compile's numbers reach it."""
    items = _scoped(result, ref, s, scope, chosen)
    if s.compiled:
        items += _awaiting(result.quilt.root, ref, s)
    return list(dict.fromkeys(items))


def _awaiting(root: Path, ref: str, s: Survey) -> list[str]:
    """The items of a work whose statement or a proof of it holds an anchor waiting for the person's compile."""
    nodes = of_work(root, ref)
    waiting = {n.id if n.kind == ids.STATEMENT else (n.parent or "") for n in nodes if n.awaiting}
    held = matched(s, [n for n in nodes if n.kind == ids.STATEMENT])
    return [item for item, n in held.items() if n.id in waiting]


def _scoped(result: ScanResult, ref: str, s: Survey, scope: str, chosen: list[str] | None) -> list[str]:
    """`scoped` before the items waiting for the compile's numbers."""
    from loom.refs.search import _loose

    root = result.quilt.root
    if scope == "used":
        return used(result, ref, s)
    if scope == "all":
        return undigested(root, ref, s)
    held = matched(s, [n for n in of_work(root, ref) if n.kind == ids.STATEMENT])
    of_node = {n.id: item for item, n in held.items()}
    if scope == "chosen":
        return [c for c in chosen or [] if s.item(c) is not None] + [of_node[c] for c in chosen or [] if c in of_node]
    from loom.library.reads import _to_digest

    out: list[str] = []
    for ra in _to_digest(result, ref):
        a = ra.annotation
        if a.node:
            out += [of_node[a.node]] if a.node in of_node else []
            continue
        page = ra.page or a.page or (a.anchor.page if a.anchor is not None else None)
        words = _loose(a.selector.exact).lower() if a.selector is not None else ""
        out += [i.item for i in s.items if i.page == page and i.opening and i.opening.lower()[:24] in words]
    return list(dict.fromkeys(out))


def _for_reader(result: ScanResult, ref: str, scope: str, chosen: list[str] | None) -> dict[str, Any] | None:
    """What an ask of an agent to digest a work held only as a PDF names: the stubs the drafts cite (`used`), the marks (`marked`), the nodes `chosen` names, or nothing for `all`; None where the scope takes nothing."""
    from loom.library.reads import marks

    root = result.quilt.root
    if scope == "all":
        return {}
    if scope == "marked":
        named = [m["mark"] for m in marks(result, ref)]
        return {"marks": named} if named else None
    if scope == "chosen":
        nodes = [c for c in chosen or [] if c in {n.id for n in of_work(root, ref)}]
        return {"nodes": nodes} if nodes else None
    stubs = sorted({n for c in result.edges.cites if c.ref == ref for n in c.nodes if n})
    stubs = [n for n in stubs if (got := _read(root, n)) is not None and got.empty]
    return {"nodes": stubs} if stubs else None


def _read(root: Path, node: str) -> Node | None:
    from loom.library.store import read

    return read(root, node)


def _compiled(root: Path, ref: str, scope: str, chosen: list[str] | None, online: bool) -> None:
    """The job a digest starts for a work whose numbers nothing confirms: its source compiled, the person's own act, and then the scope digested from that survey, on a scan made under the id lock."""
    from loom.library import documents, survey
    from loom.library.citations import resolve
    from loom.library.gather import writing
    from loom.library.store import read
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    work = read(root, ref)
    if work is None or not work.tex:
        return
    src = documents.source_dir(root, work.tex)
    main = documents.main_file(src)
    if main is None:
        return
    pdf = documents.path_of(root, work.pdf, "pdf") if work.pdf else None
    s = survey.complete(root, work.tex, src, main.relative_to(src).as_posix(), work.pdf, pdf, online=online)
    if s.state != "ready":
        return
    with writing(root):
        result = scan(load_quilt(root))
        resolve(result)
        digest(result, ref, scoped(result, ref, s, scope, chosen), s, closure=scope == "used", numbers=True)


def used(result: ScanResult, ref: str, s: Survey) -> list[str]:
    """The items of a work's survey the drafts cite by number (scope `used`), in the survey's order: each whose kind and confirmed number a citation of the work locates.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, its citations resolved (`citations.resolve`).
    ref : str
        The work's reference.
    s : Survey
        Its source's survey.

    Returns
    -------
    list of str
        Item ids.
    """
    wanted = {(t, n) for c in result.edges.cites if c.ref == ref for t, n in c.results}
    out: list[str] = []
    for taxon, number in wanted:
        hit = next((i for i in s.items if i.number == number and i.taxon == taxon), None)
        if hit is not None:
            out.append(hit.item)
    order = {i.item: k for k, i in enumerate(s.items)}
    return sorted(set(out), key=lambda i: order[i])


def undigested(root: Path, ref: str, s: Survey) -> list[str]:
    """The items of a work's survey no node of the work holds with its text (scope `all`), in the survey's order.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The work's reference.
    s : Survey
        Its source's survey.

    Returns
    -------
    list of str
        Item ids.
    """
    held = matched(s, [n for n in of_work(root, ref) if n.kind == ids.STATEMENT])
    return [i.item for i in s.items if i.item not in held or held[i.item].empty]


def of_work(root: Path, ref: str) -> list[Node]:
    """The statements and proofs whose `source` is `ref`, read from the store's files, by id."""
    from loom.library.node import NodeUnreadable, read_node
    from loom.library.store import folder

    nodes = folder(root)
    out: list[Node] = []
    if not nodes.is_dir():
        return out
    for path in sorted(nodes.glob("*.node")):
        if ids.kind_of(path.stem) not in (ids.STATEMENT, ids.PROOF):
            continue
        try:
            node = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
        if node.source == ref:
            out.append(node)
    return out


def matched(s: Survey, statements: list[Node]) -> dict[str, Node]:
    """Each item of the survey a statement of its work holds (`library-views.md` Open 8): by the source's label; else by its kind and printed number both, a stub as a node with text; each node once, never by guess, and never across kinds.

    Parameters
    ----------
    s : Survey
        The source's survey.
    statements : list of Node
        The work's statements.

    Returns
    -------
    dict of str to Node
        By item id.
    """
    by_label = {n.label: n for n in statements if n.label}
    out: dict[str, Node] = {}
    taken: set[str] = set()
    for item in s.items:
        node = by_label.get(item.label) if item.label else None
        if node is None and item.number is not None:
            node = next(
                (
                    n
                    for n in statements
                    if n.number == item.number
                    and n.taxon == item.taxon
                    and n.id not in taken
                    and n.label in (None, item.label)
                ),
                None,
            )
        if node is not None and node.id not in taken:
            out[item.item] = node
            taken.add(node.id)
    return out


class _Run:
    """One digest of one work: what it reads once, the ids it gives, and what it writes."""

    def __init__(
        self, result: ScanResult, work: Node, s: Survey, write: bool, closure: bool = False, numbers: bool = False
    ) -> None:
        from loom.evidence.log import replay
        from loom.library import documents
        from loom.library.intake import Library

        self.result, self.work, self.s, self.write, self.closure = result, work, s, write, closure
        self.numbers = (
            numbers and s.compiled
        )  # the person's digest after their compile, which alone fills a kept node's numbers
        self.kept_items: list[Item] = []
        self.reached: list[str] = []  # items a statement written points at, by its own text
        self.root, self.ref = result.quilt.root, work.id
        assert work.tex is not None
        self.src = documents.source_dir(self.root, work.tex)
        self.texts: dict[str, tuple[str, str]] = {}
        self.nodes = {n.id: n for n in of_work(self.root, self.ref)}
        statements = [n for n in self.nodes.values() if n.kind == ids.STATEMENT]
        self.held = matched(s, statements)
        self.proofs: dict[str, list[str]] = {}
        for n in sorted(self.nodes.values(), key=lambda n: n.id):
            if n.kind == ids.PROOF and n.parent:
                self.proofs.setdefault(n.parent, []).append(n.id)
        self.evidence: Evidence = replay(self.root)
        self.library: Library = Library.read(self.root)
        self.by_item = {i.item: i for i in s.items}
        self.out = Digested(self.ref)
        self.ids: dict[str, str] = {}  # item -> its statement's id
        self.proof_ids: dict[str, list[str]] = {}  # item -> its proofs' ids, in order
        # id -> a stub this run makes: of this work's items, or of another work's results
        self.stubs: dict[str, Node] = {}
        self.cited: dict[str, _Cited] = {}
        self.located: dict[tuple[str, str, str], str] = {}  # (key, taxon, number) -> the stub of another work's result
        self._minted = 0
        self._minter: Any = None
        self._bib: dict[str, tuple[str, dict[str, str]]] | None = None
        self._wrappers: dict[str, bodies.Wrapper] | None = None
        self._entries: dict[str, tuple[str, ...]] | None = None
        self._reading: str | None = None  # `statement` or `proof`, while a body of that kind is rewritten

    # ---- ids -----------------------------------------------------------------------------------------

    def _stem(self) -> str:
        from loom.library.references import Minter

        if not self.write:
            self._minted += 1
            return f"?{self._minted}"
        if self._minter is None:
            self._minter = Minter.of(self.result)
        return str(self._minter.stem())

    def statement_of(self, item: Item) -> str:
        """The id of the statement holding `item`: its node's, or one given now, with a stub made for it where nothing else will write it."""
        if item.item in self.ids:
            return self.ids[item.item]
        held = self.held.get(item.item)
        sid = held.id if held is not None else self._stem()
        self.ids[item.item] = sid
        if held is None:
            self.stubs[sid] = self._stub(sid, item)
        return sid

    def _stub(self, sid: str, item: Item) -> Node:
        title = (
            item.title if item.title and not bodies.pointers(item.title) and not bodies.unknown(item.title) else None
        )
        return Node(
            id=sid,
            taxon=item.taxon,
            number=item.number,
            title=title,
            source=self.ref,
            label=item.label,
            pages=str(item.page) if item.page else None,
            found=item.found if item.number or item.page else None,
        )

    def proof_of(self, item: Item, k: int) -> str | None:
        """The id of `item`'s proof `k`, where it has one: its node's, or one given now for an item this run writes."""
        if item.item in self.proof_ids:
            got = self.proof_ids[item.item]
            return got[k] if k < len(got) else None
        held = self.held.get(item.item)
        have = self.proofs.get(held.id, []) if held is not None else []
        return have[k] if k < len(have) else None

    def _give_proofs(self, item: Item, sid: str) -> list[str]:
        """Ids for an item's proofs: its statement's proofs with text in order, then new ones, the first past every number seen of an existing statement's (`store.next_proof`), of a new stem from `00`; a pointer is never reused."""
        from loom.library.store import next_proof

        # a pointer, an empty proof, is never loom's to write: it keeps its id, and the source's proof takes a new one
        have = [p for p in self.proofs.get(sid, []) if not self.nodes[p].empty]
        out = have[: len(item.proofs)]
        while len(out) < len(item.proofs):
            if not self.write:
                out.append(f"{sid}-proof?{len(out)}")
            elif sid in self.nodes and len(out) == len(have):
                out.append(next_proof(self.root, sid))
            else:
                out.append(ids.mint_proof(sid, out))
        self.proof_ids[item.item] = out
        return out

    # ---- reading the source -----------------------------------------------------------------------------

    def _text(self, rel: str) -> tuple[str, str]:
        """A file of the source, as written and with its comments blanked."""
        from loom.scan.source import read_source

        if rel not in self.texts:
            got = read_source(self.src, rel)
            self.texts[rel] = (got.text, got.clean)
        return self.texts[rel]

    def _bibliography(self) -> dict[str, tuple[str, dict[str, str]]]:
        """The source's own bibliography by key: each `.bib` entry its files name, its abbreviations written out, then each `\\bibitem` of its `.bbl` or its text as `@misc`."""
        if self._bib is not None:
            return self._bib
        from loom.library.entries import entries_in, expand_strings, strings_of
        from loom.library.gather import bibitem_entry, bibitems
        from loom.scan.bib import parse_bib

        out: dict[str, tuple[str, dict[str, str]]] = {}

        def offer(key: str, text: str) -> None:
            parsed = parse_bib(text)
            if key not in out and key in parsed:
                out[key] = (text, dict(parsed[key].fields))

        for rel in self.s.bibliography:
            raw = (self.src / rel).read_text(encoding="utf-8", errors="replace")
            strings = strings_of(raw)
            for key, entry, _at in entries_in(raw):
                offer(key, expand_strings(entry.strip(), strings) + "\n")
        texts = [self._text(self.s.main)[0]]
        if self.s.bbl:
            texts.append((self.src / self.s.bbl).read_text(encoding="utf-8", errors="replace"))
        for text in texts:
            for key, (item, _at) in bibitems(text).items():
                offer(key, bibitem_entry(key, item))
        self._bib = out
        return out

    def _wrapping(self) -> dict[str, bodies.Wrapper]:
        """The work's own commands that wrap a pointer, from its macros node."""
        from loom.library.store import read

        if self._wrappers is None:
            macros = read(self.root, ids.macros_of(self.ref))
            self._wrappers = bodies.wrappers(macros.body) if macros is not None else {}
        return self._wrappers

    # ---- what a pointer becomes ------------------------------------------------------------------------

    def target(self, name: str, command: str) -> tuple[str, str]:
        """What `\\command{name}` points at: `("id", id)` for a node or an anchor, or `("text", printed)` for a number the work prints outside every node; raises `_Wait`."""
        # a line break inside the argument is a space, as TeX reads it
        name = " ".join(name.split())
        label = self.s.labels.get(name)
        if label is None:
            raise _Wait(f"\\{command}{{{name}}}: the source defines no such label")
        if name in self.s.twice:
            raise _Wait(f"\\{command}{{{name}}}: the source defines this label more than once")
        owner = self.by_item.get(label.owner) if label.owner else None
        if owner is not None and (self._reading or "") != "proof":
            self.reached.append(owner.item)
        if owner is not None and label.result:
            return "id", self.statement_of(owner)
        if owner is not None:
            return "id", self.anchor(name)
        if label.kind in _HEADINGS:
            sec = next((x for x in self.s.sections if x.label == name), None)
            number = sec.number if sec is not None else None
            if number is None:
                raise _Wait(f"\\{command}{{{name}}}: the {label.kind}'s number is not confirmed in the work's PDF")
            return "text", number
        if label.kind == "equation":
            if label.number is None and not self.s.compiled:
                raise _Wait(
                    f"\\{command}{{{name}}}: an equation outside every result, which loom numbers only from a compile of the source"
                )
            if label.number is None:
                raise _Wait(f"\\{command}{{{name}}}: {self._unnumbered(label)}")
            return "text", label.number
        raise _Wait(f"\\{command}{{{name}}}: loom does not read the number of a {label.kind} outside every result")

    def _unnumbered(self, label: Label) -> str:
        """Why a display's number is not kept after a compile, as the person reads it."""
        read_as = f" ({label.emulated} as loom reads it)" if label.emulated else ""
        return f"the display's number{read_as} is not confirmed in the work's PDF"

    def anchor(self, name: str) -> str:
        """The anchor a label inside a result or its proof is: its owner's id, `eq` or `it`, and its place among its owner's labels of that kind."""
        label = self.s.labels[name]
        item = self.by_item[label.owner or ""]
        if label.proof is None:
            owner = self.statement_of(item)
            start, end, rel = item.body_start, item.body_end, item.file
        else:
            proof = item.proofs[label.proof]
            got = self.proof_of(item, label.proof)
            if got is None:
                raise _Wait(f"{name} stands in a proof of {item.item}, which no node holds")
            owner, start, end, rel = got, proof.body_start, proof.body_end, proof.file
        kind = "eq" if label.kind == "equation" else "it"
        own = self._owned(rel, start, end, item if label.proof is None else None)
        same = [lab for lab in own if (self.s.labels[lab].kind == "equation") == (kind == "eq")]
        if name not in same:
            raise _Wait(f"{name} stands in {item.item} and is no anchor of it")
        return f"{owner}-{kind}{base36_encode(same.index(name), 2)}"

    def _owned(self, rel: str, start: int, end: int, statement: Item | None) -> list[str]:
        """The labels a body defines as anchors, in order: every label in it but its statement's own."""
        from loom.scan.envtree import labels_in

        clean = self._text(rel)[1]
        found = [lab for lab, _ in labels_in(clean, [(start, end)]) if lab in self.s.labels]
        return [
            lab
            for lab in found
            if not (statement is not None and self.s.labels[lab].result and self.s.labels[lab].owner == statement.item)
        ]

    def work_of(self, key: str) -> _Cited:
        """The work the source cites as `key`, with the reference that holds it where the library has one."""
        if key in self.cited:
            return self.cited[key]
        got = self._bibliography().get(key)
        if got is None:
            raise _Wait(f"\\cite{{{key}}}: the source's bibliography holds no such entry")
        entry, fields = got
        cited = _Cited(key, entry, fields, self._held_work(fields))
        self.cited[key] = cited
        return cited

    def _held_work(self, fields: dict[str, str]) -> str | None:
        """The reference holding the work an entry names: the one stating its identifier as that version, else the one whose entry has its title and year, or for an entry with neither its note; None for none or more than one."""
        from loom.library.entries import identifiers

        found = self.library.same_version(identifiers(fields))
        if len(found) == 1:
            return found[0]
        if found:
            return None
        mine = _same_entry(fields)
        if not mine:
            return None
        if self._entries is None:
            self._entries = {r: _same_entry(_fields(n)) for r, n in self.library.refs.items()}
        alike = [r for r, theirs in self._entries.items() if theirs == mine]
        return alike[0] if len(alike) == 1 else None

    def stub_of(self, cited: _Cited, taxon: str, number: str) -> str:
        """The node of another work's result a citation locates: the one its work holds by printed number, else a stub made now."""
        from loom.library.citations import node_of, numbered

        key = (cited.key, taxon, number)
        if key in self.located:
            return self.located[key]
        held = node_of(numbered(self.root, {cited.ref}), cited.ref, taxon, number) if cited.ref else None
        if held is None:
            held = self._stem()
            # a work made in this run is named when it is made (`_make_works`)
            self.stubs[held] = Node(id=held, taxon=taxon, number=number, source=cited.ref or f"?{cited.key}")
        self.located[key] = held
        return held

    # ---- a body rewritten ------------------------------------------------------------------------------

    def rewrite(self, rel: str, start: int, end: int, of: Item, statement: Item | None, exempt: set[str]) -> _Body:
        """The body at `start`..`end` of `rel`, `of`'s statement or one of its proofs, with its pointers rewritten (§4); raises `_Wait`.

        `statement` is `of` where this is its own text, whose own labels go to its header; `exempt` the ids a pointer at which is listed nowhere (§4: the node itself, a proof's statement, their anchors). A body holding another result, its label that result's, waits: a node holds one result.
        """
        from loom.library.survey import taxon_named
        from loom.scan.postnote import located

        raw = self._text(rel)[0][start:end]
        scan = bodies.unread(raw)
        bad = bodies.unknown(raw)
        if bad:
            raise _Wait(f"\\{bad[0].command}: loom cannot read what it points at")
        wraps = bodies.wrapped(raw, self._wrapping())
        if wraps:
            raise _Wait(f"\\{wraps[0].via}: the work's own command wrapping a pointer")
        edits: list[tuple[int, int, str]] = []
        out = _Body("")
        for at, end_, arg_at, arg_end, name in _labels(scan):
            name = " ".join(name.split())
            label = self.s.labels.get(name)
            if label is None:
                raise _Wait(f"\\label{{{name}}}: not read by the survey")
            if statement is not None and label.result and label.owner == statement.item:
                edits.append((at, end_, ""))
                continue
            if name in self.s.twice:
                raise _Wait(f"\\label{{{name}}}: the source defines this label more than once")
            if label.owner != of.item:
                raise _Wait(f"it holds {label.owner or name}, a result of its own, which one node cannot")
            anchor = self.anchor(name)
            edits.append((arg_at, arg_end, anchor))
            if label.kind == "equation":
                if label.number is None and not self.s.compiled:
                    # loom keeps no display's number without the person's compile: written, its number waiting
                    out.awaiting.add(anchor)
                elif label.number is None:
                    raise _Wait(f"\\label{{{name}}}: {self._unnumbered(label)}")
                else:
                    out.anchors[anchor] = label.number
        for cmd in _commands(scan):
            points: list[str] = []
            if cmd.name in bodies.CITES:
                keys = [k.strip() for _s, _e, g in cmd.groups for k in g.split(",") if k.strip()]
                works = [self.work_of(k) for k in keys]
                post = cmd.opts[-1][2] if cmd.opts else ""
                results = (
                    [(taxon_named(t), n) for t, n in located(post)]
                    if post and len(keys) == 1 and cmd.name not in bodies.MULTICITES
                    else []
                )
                stubs = [self.stub_of(works[0], t, n) for t, n in results]
                if len(stubs) == 1:
                    edits.append((cmd.start, cmd.end, f"\\ref{{{stubs[0]}}}"))
                    points = stubs
                else:
                    for s_, e_, group in cmd.groups:
                        listed = [k.strip() for k in group.split(",")]
                        edits.append((s_, e_, ",".join(_work_id(self.work_of(k)) if k else k for k in listed)))
                    points = [_work_id(w) for w in works] + stubs
            else:
                spans = [t for s_, _e, g in cmd.groups for t in _split(g, s_, cmd.name)]
                got = [(s_, e_, self.target(n, cmd.name)) for s_, e_, n in spans if n]
                texts = [g for _s, _e, g in got if g[0] == "text"]
                if texts:
                    if cmd.name == bodies.HYPERREF and len(got) == 1:
                        edits.append((cmd.start, cmd.end, cmd.tail))
                        continue
                    if len(got) != 1 or cmd.name not in _PRINTED:
                        raise _Wait(
                            f"\\{cmd.name}: loom writes only \\ref and \\eqref of a number outside every result as text"
                        )
                    edits.append((cmd.start, cmd.end, _PRINTED[cmd.name].format(texts[0][1])))
                    continue
                for s_, e_, (_k, target) in got:
                    edits.append((s_, e_, target))
                    points.append(target)
            # loom marks no mention: every pointer it finds is a use, and only an agent's proposal or the person moves one
            for target in points:
                node = ids.anchor_owner(target) or target
                if target in exempt or node in exempt:
                    continue
                out.uses.add(node)
        text = raw
        for s_, e_, new in sorted(edits, reverse=True):
            text = text[:s_] + new + text[e_:]
        out.mentions -= out.uses
        out.text = text.strip() + "\n" if text.strip() else ""
        return out

    # ---- one run ---------------------------------------------------------------------------------------

    def run(self, wanted: list[str]) -> Digested:
        todo: list[Item] = []
        for name in wanted:
            item = self.by_item.get(name)
            if item is None:
                self.out.waiting[name] = "the source's survey holds no such result"
            elif (why := self._why_not(item)) is not None:
                self.out.waiting[name] = why
            else:
                todo.append(item)
        for item in todo:
            # every item's ids before any body is read, so a pointer at a proof's anchor finds its proof
            self._give_proofs(item, self.statement_of(item))
        planned: list[tuple[Item, Node, list[Node]]] = []
        queued = {i.item for i in todo} | set(self.out.waiting)
        while todo:
            item = todo.pop(0)
            try:
                planned.append(self._nodes(item))
            except _Wait as wait:
                self.out.waiting[item.item] = str(wait)
            for name in self.reached if self.closure else []:
                if name in queued:
                    continue
                queued.add(name)
                more = self.by_item[name]
                # one that cannot be written yet stays the stub the pointer names
                if self._why_not(more) is None:
                    self._give_proofs(more, self.statement_of(more))
                    todo.append(more)
            self.reached.clear()
        planned = self._into_proofs(planned)
        planned = self._make_works(planned)
        needed = {st.id for _i, st, _ps in planned}
        needed |= {
            ids.anchor_owner(t) or t for _i, st, ps in planned for n in (st, *ps) for t in (*n.uses, *n.mentions)
        }
        self._write_stubs([self.stubs[i] for i in sorted(needed) if i in self.stubs and i not in self.nodes])
        self._write_items(planned)
        if self.numbers and self.write:
            self._number_kept()
        self._sought()
        return self.out

    def _why_not(self, item: Item) -> str | None:
        """Why an item is not written now: unseen by the compile, a number not confirmed, a title that cites, or its node another hand's."""
        if item.item in self.s.unseen:
            return "the compile never reached it"
        if item.numbered and item.number is None:
            read_as = f" ({item.emulated} as loom reads it)" if item.emulated else ""
            return f"its number{read_as} is not confirmed in the work's PDF"
        if item.title and (bodies.pointers(item.title) or bodies.unknown(item.title)):
            return "its title points at something, which a header cannot"
        held = self.held.get(item.item)
        if held is not None and not self._ours(held):
            self.out.kept.append(held.id)
            self.kept_items.append(item)
            return "its node's text is another hand's, or a person compared it"
        return None

    def _number_kept(self) -> None:
        """Fill the compile's display numbers into the anchors waiting in each kept item's statement and proofs, nothing else of them (`acts.numbered`); a node whose anchors were given from another text of the source stays waiting, since an anchor is its label's place among its owner's."""
        from loom.evidence.acts import ActRefused, numbered
        from loom.library.node import node_bytes, node_hash

        for item in self.kept_items:
            sid = self.statement_of(item)
            self._give_proofs(item, sid)
            confirmed: dict[str, str] = {}
            for name, label in self.s.labels.items():
                if label.owner != item.item or label.kind != "equation" or label.number is None or name in self.s.twice:
                    continue
                try:
                    confirmed[self.anchor(name)] = label.number
                except _Wait:
                    continue
            for nid in (sid, *self.proofs.get(sid, [])):
                n = self.nodes.get(nid)
                if n is None or not n.awaiting or not self._anchored_here(n):
                    continue
                fill = {a: confirmed[a] for a in n.awaiting if a in confirmed}
                if not fill:
                    continue
                new = replace(
                    n,
                    anchors=tuple(sorted({**dict(n.anchors), **fill}.items())),
                    awaiting=tuple(a for a in n.awaiting if a not in fill),
                )
                try:
                    numbered(self.root, nid, node_hash(node_bytes(n)), new, {"ref": self.ref, "tex": self.work.tex})
                except ActRefused as exc:
                    self.out.waiting[item.item] = f"its display numbers could not be filled in: {exc}"[:300]
                    continue
                self.nodes[nid] = new
                self.out.numbered.append(nid)

    def _anchored_here(self, node: Node) -> bool:
        """Whether loom gave the node's anchors from this very source: its latest extraction, at any text, read the work's TeX source as it is held now."""
        made = [r for r in self.evidence.about("node", node.id, of="digested") if r.by.kind == "loom" and r.get("how") == "extracted"]  # fmt: skip
        return bool(made) and (made[-1].get("from") or {}).get("tex") == self.work.tex

    def _ours(self, node: Node) -> bool:
        """Whether loom may write a node again: a stub, or loom's own extraction no person compared, its proofs with text alike; a pointer proof is left as it stands (`_give_proofs`)."""
        from loom.library.node import node_bytes, node_hash

        for n in (node, *(self.nodes[p] for p in self.proofs.get(node.id, []))):
            if n.empty:
                continue
            digest = node_hash(node_bytes(n))
            # how its words were made, through a fill of its numbers (`Evidence.made`)
            made = self.evidence.made("node", n.id, digest)
            if made is None or made.by.kind != "loom" or made.get("how") != "extracted":
                return False
            if self.evidence.compared("node", n.id, digest):
                return False
        return True

    def _nodes(self, item: Item) -> tuple[Item, Node, list[Node]]:
        """An item's statement and proofs as they would be written; raises `_Wait`."""
        sid = self.statement_of(item)
        pids = self._give_proofs(item, sid)
        self._reading = "statement"
        stmt_body = self.rewrite(item.file, item.body_start, item.body_end, item, item, {sid})
        self._reading = "proof"
        statement = replace(
            self._stub(sid, item),
            body=stmt_body.text,
            anchors=tuple(sorted(stmt_body.anchors.items())),
            awaiting=tuple(sorted(stmt_body.awaiting)),
            uses=tuple(sorted(stmt_body.uses)),
            mentions=tuple(sorted(stmt_body.mentions)),
        )
        proofs: list[Node] = []
        for proof, pid in zip(item.proofs, pids, strict=True):
            got = self.rewrite(proof.file, proof.body_start, proof.body_end, item, None, {pid, sid})
            proofs.append(
                Node(
                    id=pid,
                    taxon="proof",
                    body=got.text,
                    source=self.ref,
                    pages=str(proof.page) if proof.page else None,
                    anchors=tuple(sorted(got.anchors.items())),
                    awaiting=tuple(sorted(got.awaiting)),
                    uses=tuple(sorted(got.uses)),
                    mentions=tuple(sorted(got.mentions)),
                )
            )
        return item, statement, proofs

    def _into_proofs(self, planned: list[tuple[Item, Node, list[Node]]]) -> list[tuple[Item, Node, list[Node]]]:
        """The planned items less each that points at an anchor in a proof no node holds and none planned writes, until none does: a proof has no stub."""
        while True:
            proofs = {p.id for _i, _st, ps in planned for p in ps} | {
                i for i in self.nodes if ids.kind_of(i) == ids.PROOF
            }
            out: list[tuple[Item, Node, list[Node]]] = []
            for item, statement, ps in planned:
                owners = {ids.anchor_owner(t) or t for n in (statement, *ps) for t in (*n.uses, *n.mentions)}
                gone = sorted(o for o in owners if ids.kind_of(o) == ids.PROOF and o not in proofs)
                if gone:
                    self.out.waiting[item.item] = f"it points into {gone[0]}, a proof not written: its result waits"
                else:
                    out.append((item, statement, ps))
            if len(out) == len(planned):
                return out
            planned = out

    def _make_works(self, planned: list[tuple[Item, Node, list[Node]]]) -> list[tuple[Item, Node, list[Node]]]:
        """Make a reference for each work the planned items cite that the library holds none of (`how` `cited`, from the citing work), and name it where they wait for it (`?KEY-ref`); an item citing a work whose entry is refused waits."""
        from loom.library.references import Minter, make
        from loom.library.store import NodeRefused

        def cites(nodes: Iterable[Node], key: str) -> bool:
            mark = f"?{key}-ref"
            return any(mark in n.body or mark in n.uses or mark in n.mentions for n in nodes)

        def located(nodes: Iterable[Node], key: str) -> bool:
            wanted = {t for n in nodes for t in (*n.uses, *n.mentions)}
            return any(self.stubs[i].source == f"?{key}" for i in wanted if i in self.stubs)

        refused: set[str] = set()
        names: dict[str, str] = {}
        for cited in self.cited.values():
            if cited.ref is not None:
                continue
            group = [n for _i, st, ps in planned for n in (st, *ps)]
            if not (cites(group, cited.key) or located(group, cited.key)) or not self.write:
                continue
            if self._minter is None:
                self._minter = Minter.of(self.result)
            try:
                node = make(
                    self.root,
                    _keyed(cited, self.library),
                    self._minter,
                    by="loom",
                    kind="loom",
                    how="cited",
                    source=self.ref,
                )
            except NodeRefused:
                refused.add(cited.key)
                continue
            cited.ref = names[cited.key] = node.id
            self.out.made.append(node.id)
        for sid, stub in list(self.stubs.items()):
            if stub.source and stub.source[1:] in names and stub.source.startswith("?"):
                self.stubs[sid] = replace(stub, source=names[stub.source[1:]])
        out: list[tuple[Item, Node, list[Node]]] = []
        for item, statement, proofs in planned:
            group = [statement, *proofs]
            gone = next((k for k in sorted(refused) if cites(group, k) or located(group, k)), None)
            if gone is not None:
                self.out.waiting[item.item] = f"\\cite{{{gone}}}: its entry in the source's bibliography is refused"
                continue
            out.append((item, *_named((statement, proofs), names)))
        return out

    def _write_stubs(self, stubs: list[Node]) -> None:
        from loom.library.store import write_nodes

        if not stubs:
            return
        if self.write:
            write_nodes(self.root, stubs, new=True)
        self.out.made += [n.id for n in stubs]
        for n in stubs:
            self.nodes[n.id] = n

    def _write_items(self, planned: list[tuple[Item, Node, list[Node]]]) -> None:
        """Write the planned items' statements and proofs that differ from their files as one act, checked together, so one item may point at an anchor in another's proof; where the checks refuse, the items they name wait and the rest are written again; then record each text written."""
        from loom.evidence.acts import digested
        from loom.evidence.subjects import Who
        from loom.library.node import node_bytes
        from loom.library.store import NodeRefused, write_nodes

        pending: list[tuple[Item, Node, list[Node], dict[str, Node | None], list[Node]]] = []
        for item, statement, proofs in planned:
            before = {n.id: self.nodes.get(n.id) for n in (statement, *proofs)}
            changed = [
                n for n in (statement, *proofs) if (old := before[n.id]) is None or node_bytes(old) != node_bytes(n)
            ]
            if changed:
                pending.append((item, statement, proofs, before, changed))
        hashes: list[str] = []
        while pending and self.write:
            try:
                hashes = write_nodes(self.root, [n for *_rest, changed in pending for n in changed])
                break
            except NodeRefused as exc:
                said: dict[str, str] = {}
                for d in exc.diagnostics:
                    for name in [*d.keys, *(Path(loc.file).stem for loc in d.locations)]:
                        said.setdefault(name, f"{d.code}: {d.message}")
                kept = [p for p in pending if not any(n.id in said for n in p[4])]
                for p in pending:
                    why = next((said[n.id] for n in p[4] if n.id in said), None)
                    if why is not None or len(kept) == len(pending):
                        self.out.waiting[p[0].item] = f"the library's checks refuse it: {why or 'refused'}"[:300]
                pending = kept if len(kept) < len(pending) else []
        source = {"ref": self.ref, "tex": self.work.tex}
        written = iter(hashes)
        for item, statement, proofs, before, changed in pending:
            for n in changed:
                digest_ = next(written, "")
                if self.write and n.body.strip():
                    # under the library's lock, which this run holds, so the text recorded is the text written
                    digested(self.root, n.id, digest_, Who("loom"), "extracted", source)
                self.nodes[n.id] = n
            was = self.held.get(item.item)
            if was is not None and was.empty:
                self.out.filled.append(statement.id)
            elif was is not None:
                self.out.rewritten.append(statement.id)
            elif statement.id not in self.out.made:
                self.out.made.append(statement.id)
            self.out.made += [p.id for p in proofs if before[p.id] is None]

    def _sought(self) -> None:
        """Record `sought` on each stub of the work its source does not print, where the work's PDF or a compile governs its numbers, once for each text of the stub and each source."""
        from loom.evidence.log import write
        from loom.evidence.subjects import Subject, Who
        from loom.library.node import node_bytes, node_hash

        if self.s.why == "no-pdf" or not (self.s.pdf or self.s.compiled):
            return
        if any(i.numbered and i.number is None and i.emulated is None for i in self.s.items):
            # a result whose number loom reads no way may be any stub's
            return
        printed = {(i.taxon, i.number) for i in self.s.items if i.number} | {
            (i.taxon, i.emulated) for i in self.s.items if i.emulated and i.item in self.s.unconfirmed
        }
        holding = {n.id for n in self.held.values()}
        for node in sorted(self.nodes.values(), key=lambda n: n.id):
            if (
                node.kind != ids.STATEMENT
                or node.source != self.ref
                or not node.empty
                or not node.number
                or node.id in holding
                or (node.taxon, node.number) in printed
            ):
                continue
            digest_ = node_hash(node_bytes(node))
            looked = [
                r
                for r in self.evidence.about("node", node.id, of="sought")
                if r.on is not None and r.on.hash == digest_ and (r.get("from") or {}).get("tex") == self.work.tex
            ]
            self.out.sought.append(node.id)
            if self.write and not looked:
                write(
                    self.root,
                    "sought",
                    Who("loom"),
                    on=Subject("node", node.id, digest_),
                    found=False,
                    **{"from": {"ref": self.ref, "tex": self.work.tex}},
                )


# ---- helpers -----------------------------------------------------------------------------------------------


@dataclass
class _Cmd:
    """A pointer command in a body: its name, its span, its optional arguments and its groups of names, each `(start, end, text)`, and for `\\hyperref` the text it shows."""

    name: str
    start: int
    end: int
    opts: list[tuple[int, int, str]]
    groups: list[tuple[int, int, str]]
    tail: str = ""


_POINTER = re.compile(
    r"\\("
    + "|".join(sorted(bodies.REFS | bodies.CITES | {bodies.HYPERREF}, key=len, reverse=True))
    + r")\*?(?![A-Za-z@])"
)


def _commands(scan: str) -> Iterator[_Cmd]:
    """Each referencing command and citation of a body with comments and verbatim text blanked, with the spans of its arguments."""
    for m in _POINTER.finditer(scan):
        name, pos = m.group(1), m.end()
        opts: list[tuple[int, int, str]] = []
        groups: list[tuple[int, int, str]] = []
        tail = ""
        if name == bodies.HYPERREF:
            arg, s_, e_, pos = read_optional(scan, pos)
            if arg is not None:
                groups.append((s_, e_, arg))
            shown, _s, _e, nxt = read_mandatory(scan, pos)
            if shown is not None:
                tail, pos = shown, nxt
        elif name in bodies.CITES:
            if name in bodies.MULTICITES:
                for _ in range(2):
                    p = skip_space(scan, pos)
                    end = match_group(scan, p, "(", ")") if p < len(scan) and scan[p] == "(" else -1
                    if end < 0:
                        break
                    pos = end
            while True:
                for _ in range(2):
                    opt, s_, e_, nxt = read_optional(scan, pos)
                    if opt is None:
                        break
                    opts.append((s_, e_, opt))
                    pos = nxt
                p = skip_space(scan, pos)
                end = match_group(scan, p) if p < len(scan) and scan[p] == "{" else -1
                if end < 0:
                    break
                groups.append((p + 1, end - 1, scan[p + 1 : end - 1]))
                pos = end
                if name not in bodies.MULTICITES:
                    break
        else:
            for _ in range(2 if name in bodies.RANGES else 1):
                arg, s_, e_, nxt = read_mandatory(scan, pos)
                if arg is None:
                    break
                groups.append((s_, e_, arg))
                pos = nxt
        yield _Cmd(name, m.start(), pos, opts, groups, tail)


def _split(group: str, at: int, command: str) -> Iterator[tuple[int, int, str]]:
    """A command's group of names, each with its span: a list split at its commas for cleveref's lists, else the one name."""
    if command not in bodies.LISTS:
        lead = len(group) - len(group.lstrip())
        yield at + lead, at + len(group.rstrip()), group.strip()
        return
    pos = 0
    for part in group.split(","):
        lead = len(part) - len(part.lstrip())
        yield at + pos + lead, at + pos + len(part.rstrip()), part.strip()
        pos += len(part) + 1


def _labels(scan: str) -> Iterator[tuple[int, int, int, int, str]]:
    """Each `\\label` of a body: the command's span, its argument's span past cleveref's `[type]`, and the label."""
    for m in _LABEL.finditer(scan):
        _o, _s, _e, pos = read_optional(scan, m.end())
        arg, s_, e_, end = read_mandatory(scan, pos)
        if arg is not None:
            lead = len(arg) - len(arg.lstrip())
            yield m.start(), end, s_ + lead, s_ + len(arg.rstrip()), arg.strip()


def _work_id(cited: _Cited) -> str:
    return cited.ref or f"?{cited.key}-ref"


def _named(nodes: tuple[Node, list[Node]], names: dict[str, str]) -> tuple[Node, list[Node]]:
    """Nodes with each placeholder of a work made in this run (`?KEY-ref`) named by its reference's id."""

    def name(n: Node) -> Node:
        def sub(text: str) -> str:
            for key, ref in names.items():
                text = text.replace(f"?{key}-ref", ref)
            return text

        return replace(
            n,
            body=sub(n.body),
            uses=tuple(sorted(sub(u) for u in n.uses)),
            mentions=tuple(sorted(sub(m) for m in n.mentions)),
        )

    statement, proofs = nodes
    return name(statement), [name(p) for p in proofs]


def _fields(node: Node) -> dict[str, str]:
    from loom.library.entries import read_entry

    entry = read_entry(node.body)
    return dict(entry.fields) if entry is not None else {}


def _same_entry(fields: dict[str, str]) -> tuple[str, ...]:
    """What two entries are compared by when neither states an identifier: the title's words and the year, or for an entry with no title its note's words; empty for neither."""
    from loom.library.entries import decode, year

    def words(text: str) -> str:
        return " ".join(re.findall(r"\w+", decode(text).casefold()))

    if fields.get("title"):
        return ("title", words(fields["title"]), year(fields))
    if fields.get("note"):
        return ("note", words(fields["note"]))
    return ()


def _keyed(cited: _Cited, library: Library) -> str:
    """The cited work's entry with a key no reference holds, ignoring case: its own, else its own with `-2`, `-3`, ..."""
    key, n = cited.key, 2
    while key.casefold() in library.by_key:
        key, n = f"{cited.key}-{n}", n + 1
    library.by_key[key.casefold()] = ""
    if key == cited.key:
        return cited.entry
    return re.sub(r"^(\s*@\w+\s*[{(]\s*)" + re.escape(cited.key), lambda m: m.group(1) + key, cited.entry, count=1)
