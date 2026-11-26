"""The Library's reads of a work and its results (`docs/specs/library-views.md` §3.2, §3.4, §6.2): a work's outline, what each scope of a digest would take, a node or a survey's item beside its page, and loom's best guess where a result stands in a work's PDF.

Each is computed from the files, the survey and the records as they are now and carries the library's generation (`library.generation`). None writes anything but a work's survey, made the first time a work with a TeX source is opened or its whole is counted, by the unasked path, which compiles nothing (`survey.confirmed`). How a result stands is the evidence lane's (`evidence.status`), passed on and never computed here.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.library import ids
from loom.library.generation import generation
from loom.library.store import read

if TYPE_CHECKING:
    from loom.evidence.status import Status
    from loom.library.node import Node
    from loom.library.survey import Survey
    from loom.scan.scan import ScanResult

#: The longest piece of a refused name a message repeats.
_SAID = 80


class ReadRefused(Exception):
    """A read loom will not answer: its code, its sentence, and the HTTP status the write API gives it."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Standing:
    """How each library node stands now, for one read: the evidence log replayed once, each node's status computed once (`evidence.status.status`)."""

    def __init__(self, root: Path) -> None:
        from loom.evidence.log import replay
        from loom.evidence.status import files_unchanged
        from loom.evidence.web import LibraryWeb

        self.evidence = replay(root)
        self.web = LibraryWeb(root)
        self.lean_now = files_unchanged(root)
        self._seen: dict[str, Status] = {}

    def __call__(self, node: str) -> Status:
        from loom.evidence.status import status
        from loom.evidence.web import Here

        if node not in self._seen:
            self._seen[node] = status(self.evidence, self.web, Here("node", node), lean_now=self.lean_now)
        return self._seen[node]

    def paper(self, node: str | None) -> str | None:
        """The node's reading of its paper: `stub`, `unchecked` or `matches`; None for no node."""
        return self(node).reading if node else None

    def lean(self, node: str | None) -> dict[str, Any] | None:
        """How the node stands in Lean, as a row carries it (`evidence.status.brief`); None for no node."""
        from loom.evidence.status import brief

        found = self(node) if node else None
        return brief(found) if found is not None and found.subject is not None else None


def name_of(node: Node | Any) -> str:
    """A result as the person reads it: its taxon's word and the number its source prints, the word alone where it prints none (`Lemma 3.2`)."""
    word = str(node.taxon).replace("-", " ").capitalize()
    return f"{word} {node.number}" if node.number else word


def work_words(root: Path, ref: str) -> dict[str, Any]:
    """A work as a read names it: `ref`, `short`, `title`, `authors` and `year` from its entry; refused `no-such-ref` (404) for no work of that id."""
    from loom.library.works import described

    work = read(root, ref) if ids.kind_of(ref) == ids.REFERENCE else None
    said = described(work.body) if work is not None else None
    if work is None or said is None:
        raise ReadRefused("no-such-ref", f"the library has no work {ref[:_SAID]}", 404)
    return {"ref": ref, **said}


def surveyed(root: Path, work: Node, *, make: bool = True) -> Survey | None:
    """The survey of a work's TeX source, confirmed against its stored PDF: the one kept, or with `make` one made now by the unasked path, which compiles nothing; None for a work holding no source, or none kept and `make` false."""
    from loom.library import documents, survey

    if not work.tex:
        return None
    held = survey.kept(root, work.tex, work.pdf)
    if held is not None or not make:
        return held
    src = documents.source_dir(root, work.tex)
    main = documents.main_file(src)
    if main is None:
        return survey.Survey(tex=work.tex, main="", pdf=work.pdf, state="failed", why="no-main")
    pdf = documents.path_of(root, work.pdf, "pdf") if work.pdf else None
    return survey.confirmed(root, work.tex, src, main.relative_to(src).as_posix(), pdf=work.pdf, pdf_path=pdf)


def _pages(root: Path, pdf: str | None) -> int | None:
    from loom.library import documents
    from loom.refs.pages import page_count

    return page_count(documents.path_of(root, pdf, "pdf")) if pdf else None


def work(result: ScanResult, ref: str) -> dict[str, Any]:
    """`library-work`: a work's details, what loom holds of it, and its outline, the results of its source digested or not.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    ref : str
        The work's reference.

    Returns
    -------
    dict
        `gen`, the work's words, `holds` `{pdf, pages, tex}`, `entry`, `link`, `outline` `{from, state, why, sections, items}`, an item `waits: "compile"` where it is written only after the person's compile, `marks` and `unplaced` (`library-views.md` §3.2). A number in the outline the survey has not confirmed is loom's own reading of the source's counters, said by `confirmed` false.

    Raises
    ------
    ReadRefused
        `no-such-ref` (404).

    See Also
    --------
    node : one result beside its page.
    """
    from loom.library.digest import matched, of_work

    root = result.quilt.root
    said = work_words(root, ref)
    held = read(root, ref)
    assert held is not None
    standing = Standing(root)
    statements = [n for n in of_work(root, ref) if n.kind == ids.STATEMENT]
    outline: dict[str, Any] = {
        "from": None,
        "state": "ready",
        "why": None,
        "sections": [],
        "items": [],
    }
    s = surveyed(root, held)
    placed = set(_marked_nodes(result, ref))
    if s is not None:
        outline = _outline(s, statements, standing)
        placed |= {n.id for n in matched(s, statements).values()}
    elif held.pdf:
        outline["from"] = "pdf"
        outline["items"] = [_row(None, n, standing) for n in statements if n.pages]
    return {
        "gen": generation(result),
        **said,
        "holds": {"pdf": held.pdf, "pages": _pages(root, held.pdf), "tex": held.tex is not None},
        "entry": held.body,
        "outline": outline,
        "marks": marks(result, ref),
        "unplaced": [
            {"node": n.id, "name": name_of(n), "paper": standing.paper(n.id)}
            for n in statements
            if n.empty and not n.pages and n.id not in placed
        ],
    }


def _outline(s: Survey, statements: list[Node], standing: Standing) -> dict[str, Any]:
    """A source's outline: its sections and every result, digested or not, then the work's stubs the source does not print."""
    from loom.library.digest import matched

    held = matched(s, statements)
    sections = [
        {
            "section": x.section,
            "number": x.number or x.emulated,
            "confirmed": x.number is not None,
            "title": x.title,
            "page": x.page,
            "level": x.level,
        }
        for x in s.sections
    ]
    items = []
    for i in s.items:
        node = held.get(i.item)
        number = i.number or i.emulated
        items.append(
            {
                "item": i.item,
                "node": node.id if node is not None else None,
                "name": f"{i.name} {number}" if number else i.name,
                "confirmed": i.number is not None or not i.numbered,
                "found": i.found,
                "title": i.title,
                "taxon": i.taxon,
                "section": i.section,
                "page": i.page,
                "paper": standing.paper(node.id) if node is not None else None,
                "lean": standing.lean(node.id) if node is not None else None,
                # it points at an equation outside every result, whose number only the person's compile gives
                "waits": "compile" if i.outside and not s.compiled and (node is None or node.empty) else None,
            }
        )
    holding = {n.id for n in held.values()}
    items += [_row(None, n, standing) for n in statements if n.empty and n.id not in holding]
    return {"from": "tex", "state": s.state, "why": s.why, "sections": sections, "items": items}


def _row(item: str | None, n: Node, standing: Standing) -> dict[str, Any]:
    return {
        "item": item,
        "node": n.id,
        "name": name_of(n),
        "confirmed": True,
        "found": n.found,
        "title": n.title,
        "taxon": n.taxon,
        "section": None,
        "page": int(n.pages.split("-")[0]) if n.pages and n.pages.split("-")[0].isdigit() else None,
        "paper": standing.paper(n.id),
        "lean": standing.lean(n.id),
    }


def _to_digest(result: ScanResult, ref: str) -> list[Any]:
    """The person's marks to digest on a work, annotations whose purpose is `to-digest`, that stand somewhere."""
    from loom.records.store import Records

    return [
        ra
        for ra in Records(result.quilt.root).resolved(result)
        if ra.work == ref and ra.annotation.purpose == "to-digest" and not ra.detached
    ]


def _marked_nodes(result: ScanResult, ref: str) -> list[str]:
    return [ra.annotation.node for ra in _to_digest(result, ref) if ra.annotation.node]


def marks(result: ScanResult, ref: str) -> list[dict[str, Any]]:
    """The work's marks to digest that nothing has been read from yet: a mark naming no node, or naming one still a stub; each `{mark, page, words}`."""
    root = result.quilt.root
    out = []
    for ra in _to_digest(result, ref):
        a = ra.annotation
        named = read(root, a.node) if a.node else None
        if named is not None and not named.empty:
            continue
        page = ra.page or a.page or (a.anchor.page if a.anchor is not None else None)
        out.append({"mark": a.id, "page": page, "words": a.selector.exact if a.selector is not None else ""})
    return out


def _cited(result: ScanResult, ref: str) -> set[tuple[str, str]]:
    """The results of a work the drafts cite by number that no node holds with its text: (taxon, number)."""
    out = set()
    for c in result.edges.cites:
        if c.ref != ref:
            continue
        for (taxon, number), node in zip(c.results, c.nodes, strict=True):
            held = read(result.quilt.root, node) if node else None
            if held is None or held.empty:
                out.add((taxon, number))
    return out


def scopes(result: ScanResult, ref: str | None) -> dict[str, Any]:
    """`library-digest-scopes`: what each scope of a digest would take, as a `digest…` menu counts it.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, its citations resolved.
    ref : str or None
        The work; None for the list's menu, every work.

    Returns
    -------
    dict
        For a work `{gen, tex, pdf, used, marked, all}`: `used` the results the drafts cite by number not yet read, `marked` the marks to digest nothing has been read from, `all` the source's results no node holds with its text (its survey made where there is none), a work held only as a PDF its page count, and null for a work holding neither. For every work `{gen, used}`.

    Raises
    ------
    ReadRefused
        `no-such-ref` (404).
    """
    from loom.library.digest import undigested

    root = result.quilt.root
    gen = generation(result)
    if ref is None:
        works = {c.ref for c in result.edges.cites if c.ref}
        return {"gen": gen, "used": sum(len(_cited(result, w)) for w in sorted(works))}
    work_words(root, ref)
    held = read(root, ref)
    assert held is not None
    s = surveyed(root, held)
    every: int | None
    if s is not None and s.state == "ready":
        every = len(undigested(root, ref, s))
    elif s is None and held.pdf:
        every = _pages(root, held.pdf)
    else:
        every = None
    return {
        "gen": gen,
        "tex": held.tex is not None,
        "pdf": held.pdf is not None,
        "used": len(_cited(result, ref)),
        "marked": len(marks(result, ref)),
        "all": every,
    }


def node(result: ScanResult, node_id: str, *, brief: bool = False) -> dict[str, Any]:
    """`library-node`: a statement or a proof beside its page, with what it points at and what it rests on.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    node_id : str
        A statement's or a proof's id.
    brief : bool, default False
        Leave out `uses`, `mentions`, `proofs` and `used_by`, for a citation's card.

    Returns
    -------
    dict
        `gen`, `node`, `hash`, `name`, `title`, `taxon`, `work` `{ref, short, pdf}`, `pages`, `digested` `{how, by, at}` or null, `paper`, `lean`, `body`, `macros` `{node, hash, body}` or null, `compiled`, whether the person compiled its work's source here (null for a work holding none), `points`, and unless `brief` `uses`, `mentions`, `proofs` and `used_by` (`library-views.md` §3.4).

    Raises
    ------
    ReadRefused
        `no-such-node` (404) for no statement or proof of that id.

    See Also
    --------
    item : a result of a survey no node holds.
    """
    from loom.library.index import NodeIndex
    from loom.library.node import node_bytes, node_hash

    root = result.quilt.root
    found = read(root, node_id) if ids.kind_of(node_id) in (ids.STATEMENT, ids.PROOF) else None
    if found is None:
        raise ReadRefused("no-such-node", f"the library has no statement or proof {node_id[:_SAID]}", 404)
    standing = Standing(root)
    digest = node_hash(node_bytes(found))
    work = _work_of(root, found.source)
    macros = read(root, ids.macros_of(found.source)) if found.source else None
    out: dict[str, Any] = {
        "gen": generation(result),
        "node": found.id,
        "hash": digest,
        "name": name_of(found) if found.kind == ids.STATEMENT else "Proof",
        "title": found.title,
        "taxon": found.taxon,
        "work": work,
        "pages": found.pages,
        # how its number and page were found in its work, so the check can say a place found by position
        "found": found.found,
        "digested": _digested(standing, found.id, digest),
        "paper": standing.paper(found.id),
        "lean": standing.lean(found.id),
        "body": found.body,
        "macros": {"node": macros.id, "hash": node_hash(node_bytes(macros)), "body": macros.body}
        if macros is not None
        else None,
        "compiled": _compiled_here(root, found.source),
    }
    with NodeIndex.open(root) as index:
        out["points"] = _points(root, found, index, standing)
        if brief:
            return out
        named = {found.source} | {r.source for r in (*index.uses(found.id), *index.mentions(found.id)) if r.source}
        shorts = {ref: _work_of(root, ref)["short"] for ref in named if ref}
        out["uses"] = [_list_row(r, found.source, shorts, standing) for r in index.uses(found.id)]
        out["mentions"] = [_list_row(r, found.source, shorts, standing) for r in index.mentions(found.id)]
        out["proofs"] = [
            {
                "node": p.id,
                "source": None if p.source == found.source else _work_of(root, p.source),
                "pages": p.pages,
                "pointer": p.empty,
            }
            for p in (index.proofs(found.id) if found.kind == ids.STATEMENT else [])
        ]
        by = {r.id for r in index.used_by(found.id)}
    docs = sorted({c.file for c in result.edges.cites if c.target == found.id or found.id in c.nodes})
    out["used_by"] = {"docs": docs, "nodes": len(by)}
    return out


def _compiled_here(root: Path, ref: str | None) -> bool | None:
    """Whether the person compiled the work `ref`'s source here, so TeX draws its nodes (`drawn.given`); None for a work holding no source.

    `library-node`'s `compiled`: the viewer asks for a drawing only where it is true, and asks the person once for the work where it is false.
    """
    from loom.library.drawn import given

    work = read(root, ref) if ref and ids.kind_of(ref) == ids.REFERENCE else None
    if work is None or not work.tex:
        return None
    return given(root, work.id, work.tex)


def _work_of(root: Path, ref: str | None) -> dict[str, Any]:
    """A node's work as a read names it, `{ref, short, pdf}`."""
    held = read(root, ref) if ref else None
    if held is None or ref is None:
        return {"ref": ref, "short": None, "pdf": None}
    return {"ref": ref, "short": work_words(root, ref)["short"], "pdf": held.pdf}


def _digested(standing: Standing, node: str, digest: str) -> dict[str, Any] | None:
    """The latest `digested` record saying how this text's words were made (`Evidence.made`, through a fill of its numbers): how, by whom (`loom`, or the name), and when."""
    last = standing.evidence.made("node", node, digest)
    if last is None:
        return None
    return {"how": last.get("how"), "by": last.by.name or last.by.kind, "at": last.at}


def _points(root: Path, found: Node, index: Any, standing: Standing) -> dict[str, dict[str, Any]]:
    """What is drawn in place of each id and anchor the body points at: a node's name, number and mark, and for a result of another work that work's short name (`work`); an anchor's number, or `awaiting` where only the person's compile numbers it."""
    from loom.library.body import pointers

    out: dict[str, dict[str, Any]] = {}
    for p in pointers(found.body):
        target = p.target
        if target in out:
            continue
        owner = ids.anchor_owner(target)
        if owner is not None:
            out[target] = {"number": index.anchor_number(target)}
            held = found if owner == found.id else read(root, owner)
            if held is not None and target in held.awaiting:
                # numbered only by the person's compile, drawn so
                out[target]["awaiting"] = True
            continue
        row = index.row(target)
        if row is None:
            continue
        if row.kind == ids.REFERENCE:
            out[target] = {"name": _work_of(root, target)["short"], "number": None, "paper": None}
            continue
        out[target] = {"name": name_of(row), "number": row.number, "paper": standing.paper(target)}
        if row.source and row.source != found.source:
            # a result of another work, drawn as a citation with the result as its locator
            out[target]["work"] = _work_of(root, row.source)["short"]
    return out


def _list_row(r: Any, home: str | None, shorts: dict[str, Any], standing: Standing) -> dict[str, Any]:
    """A node as a list sends it (`ROW`), `source` null for one of the same work."""
    if r.kind == ids.REFERENCE:
        return {"result": r.id, "name": shorts.get(r.id) or r.id, "title": None, "taxon": "reference", "source": None, "paper": None, "reading": None, "lean": None}  # fmt: skip
    return {
        "result": r.id,
        "name": name_of(r),
        "title": r.title,
        "taxon": r.taxon,
        "source": None if r.source == home else {"ref": r.source, "short": shorts.get(r.source)},
        "paper": standing.paper(r.id),
        "reading": standing.paper(r.id),
        "lean": standing.lean(r.id),
    }


def item(result: ScanResult, ref: str, name: str) -> dict[str, Any]:
    """`library-node` for a result of a work's survey: its name, title, taxon, pages and work, and nothing read.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    ref : str
        The work.
    name : str
        The survey's item (`Item.item`).

    Returns
    -------
    dict
        `{gen, item, name, title, taxon, pages, work, digested: null, paper: null}`.

    Raises
    ------
    ReadRefused
        `no-such-ref` (404); `no-such-result` (404) for no such item of the work's survey.
    """
    root = result.quilt.root
    said = work_words(root, ref)
    held = read(root, ref)
    s = surveyed(root, held) if held is not None else None
    found = s.item(name) if s is not None else None
    if found is None:
        raise ReadRefused("no-such-result", f"{said['short']}'s source holds no result {name[:_SAID]}", 404)
    number = found.number or found.emulated
    return {
        "gen": generation(result),
        "item": found.item,
        "name": f"{found.name} {number}" if number else found.name,
        "title": found.title,
        "taxon": found.taxon,
        "pages": str(found.page) if found.page else None,
        "found": found.found,
        "work": _work_of(root, ref),
        "digested": None,
        "paper": None,
    }


def find(result: ScanResult, ref: str, q: str, *, limit: int = 20) -> dict[str, Any]:
    """`library-find`: loom's best guess where words stand in a work's stored PDF, a page to open at and never a mark.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    ref : str
        The work.
    q : str
        The words, a result's name ("Theorem 2.3") as a citation's locator gives it.
    limit : int, default 20
        The most pages answered.

    Returns
    -------
    dict
        `{gen, pdf, hits: [{page, rects}], pages}`: each page whose text holds the words, compared as a quotation is (`refs.search`), in page order, with the rectangles of their first place there, and the PDF's page count.

    Raises
    ------
    ReadRefused
        `no-such-ref` (404); `no-document` (409) for a work holding no PDF loom can read.
    """
    from loom.library import documents
    from loom.refs.anchoring import anchor_on_page
    from loom.refs.pages import mapped, read_map, read_page
    from loom.refs.search import find_in_page

    root = result.quilt.root
    said = work_words(root, ref)
    held = read(root, ref)
    home = mapped(root, held.pdf) if held is not None and held.pdf else None
    pdf = documents.path_of(root, held.pdf, "pdf") if held is not None and held.pdf else None
    if home is None or pdf is None or held is None:
        raise ReadRefused("no-document", f"{said['short']} holds no PDF loom can read")
    shown = read_map(home)
    count = shown.pages if shown is not None else len(list((home / "pages").glob("*.txt")))
    hits: list[dict[str, Any]] = []
    for page in range(1, count + 1):
        if len(hits) >= limit:
            break
        if q.strip() and find_in_page(read_page(home, page) or "", q):
            try:
                rects = anchor_on_page(home, pdf, page, q, [], None).anchor.quads or []
            except Exception:  # noqa: BLE001 -- the page holds the words; where on it is a nicety
                rects = []
            hits.append({"page": page, "rects": rects})
    return {"gen": generation(result), "pdf": held.pdf, "hits": hits, "pages": count}
