"""An agent's commands on the library's web (`docs/design/library.md`, "What an agent can do to the web"), each an MCP tool: to read a node with its neighbours, a search, what a node uses and what uses it, what a draft rests on, the stubs and a work; to write, fill a stub, propose a node at a place, and propose a correction; and to have loom digest a work from its TeX source.

An agent writes no node file by hand: each write here is an act of the evidence lane (`evidence.acts`: `give` for a filled stub or a proposed node, `propose` for a correction), which writes through the library's checks and records how the text was made and by whom. What an agent transcribes from a PDF's pages or reads from a source is checked to stand there; a correction of a text a person compared waits as a proposal, and the compared text stands. Comparing a node with its paper is the person's, and no command here records it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import click

from loom.cli._quilt import open_quilt, quilt_option
from loom.cli.report import Group, Item, Report, counted
from loom.cli.tasks_cmd import AS_OPTION, JSON_OPTION, _agent
from loom.errors import ContentError

#: How an agent says what it read a text from: a work's PDF, by its pages, or its TeX source.
FROM = ("pdf", "tex")


def _scanned(quilt_path: str | None) -> Any:
    from loom.library.citations import resolve
    from loom.scan.scan import scan

    result = scan(open_quilt(quilt_path))
    resolve(result)
    return result


def _read(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """A library read, its refusal said as a command says one."""
    from loom.library.reads import ReadRefused

    try:
        return fn(*args, **kwargs)
    except ReadRefused as exc:
        raise ContentError(exc.message) from None


def _row_line(row: dict[str, Any]) -> str:
    work = row.get("source") or {}
    where = f" of {work.get('short') or work.get('ref')}" if isinstance(work, dict) and work.get("ref") else ""
    return f"{row['result']}  {row['name']}{where}  [{row.get('paper') or 'no text'}]"


@click.command(name="node")
@click.argument("node")
@JSON_OPTION
@quilt_option
def node_command(node: str, as_json: bool, quilt_path: str | None) -> None:
    """A statement or a proof of the library with its neighbours: its header, its text, what it uses and mentions, its proofs, and what rests on it. NODE is its id."""
    from loom.library.reads import node as read_node

    said = _read(read_node, _scanned(quilt_path), node)
    groups = [
        Group("text", [Item(line) for line in said["body"].splitlines()] or [Item("(a stub: not read yet)")]),
        Group("uses", [Item(_row_line(r)) for r in said["uses"]]),
        Group("mentions", [Item(_row_line(r)) for r in said["mentions"]]),
        Group(
            "proofs",
            [
                Item(f"{p['node']}  pages {p['pages'] or '?'}{'  (a pointer)' if p['pointer'] else ''}")
                for p in said["proofs"]
            ],
        ),  # fmt: skip
    ]
    made = said["digested"]
    head = f"{said['node']}: {said['name']} of {said['work']['short']}, page {said['pages'] or '?'}, {said['paper'] or 'no text'}"
    if made:
        head += f"; {made['how']} by {made['by']}"
    Report(head, groups=[g for g in groups if g.items], data=said).emit(as_json)


@click.command(name="search")
@click.argument("words", nargs=-1)
@click.option("--work", default=None, metavar="REF", help="Only this work's statements: its id or its entry's key.")
@click.option("--taxon", default=None, help="Only statements of this taxon (lemma, theorem, ...).")
@click.option("--tag", default=None, help="Only statements with this tag.")
@click.option("--proofs", is_flag=True, help="Look in proofs' words too.")
@JSON_OPTION
@quilt_option
def search_command(
    words: tuple[str, ...],
    work: str | None,
    taxon: str | None,
    tag: str | None,
    proofs: bool,
    as_json: bool,
    quilt_path: str | None,
) -> None:
    """Search the library's statements, stubs among them, by their words, name, title and work."""
    from loom.library.index import NodeIndex
    from loom.library.reads import name_of

    root = open_quilt(quilt_path).root
    with NodeIndex.open(root) as index:
        hits = index.search(" ".join(words), work=work, taxon=taxon, tag=tag, proofs=proofs)
    rows = [
        {
            "node": h.row.id,
            "name": name_of(h.row),
            "title": h.row.title,
            "work": h.row.source,
            "stub": h.row.empty,
            "where": h.where,
            "proof": h.in_proof,
            "snippet": f"{h.snippet.before}{h.snippet.match}{h.snippet.after}" if h.snippet else None,
        }
        for h in hits
    ]
    items = [Item(f"{r['node']}  {r['name']}{'  (stub)' if r['stub'] else ''}" + (f"  …{r['snippet']}…" if r["snippet"] else "")) for r in rows]  # fmt: skip
    Report(f"{counted(len(rows), 'statement')} found", groups=[Group("found", items)] if items else [], data={"hits": rows}).emit(as_json)  # fmt: skip


@click.command(name="uses")
@click.argument("node")
@JSON_OPTION
@quilt_option
def uses_command(node: str, as_json: bool, quilt_path: str | None) -> None:
    """What a node's text uses and mentions, and which nodes use and mention it. NODE is its id."""
    from loom.library.index import NodeIndex

    root = open_quilt(quilt_path).root
    with NodeIndex.open(root) as index:
        if index.row(node) is None:
            raise ContentError(f"the library has no node {node}")
        said = {
            kind: [r.id for r in getattr(index, kind)(node)] for kind in ("uses", "mentions", "used_by", "mentioned_by")
        }
    words = {"uses": "it uses", "mentions": "it mentions", "used_by": "used by", "mentioned_by": "mentioned by"}
    groups = [Group(words[k], [Item(i) for i in v]) for k, v in said.items() if v]
    Report(f"{node}: uses {len(said['uses'])}, used by {len(said['used_by'])}", groups=groups, data=said).emit(as_json)


@click.command(name="rests-on")
@click.argument("what")
@JSON_OPTION
@quilt_option
def rests_on_command(what: str, as_json: bool, quilt_path: str | None) -> None:
    """The library's results a draft rests on, through its citations and what those use in turn: WHAT is a draft's result (its id or label) or a document's path. Each says how it stands; a stub is one nobody has read."""
    from loom.library.index import NodeIndex
    from loom.library.reads import Standing, name_of

    result = _scanned(quilt_path)
    root = result.quilt.root
    if what in result.masters:
        files = set(result.expansions[what].reached) if what in result.expansions else {what}
        cites = [c for c in result.edges.cites if c.file in files]
    else:
        key = result.assembly.labels.get(what, what)
        if key not in result.nodes:
            raise ContentError(f"{what} is no result or document of this quilt")
        inside = {key, *result.nodes[key].proofs}
        cites = [c for c in result.edges.cites if c.src in inside]
    standing = Standing(root)
    seen: dict[str, dict[str, Any]] = {}
    with NodeIndex.open(root) as index:
        todo = [c.target for c in cites if c.target]
        while todo:
            node = todo.pop(0)
            if node in seen:
                continue
            row = index.row(node)
            if row is None:
                continue
            seen[node] = {"node": node, "name": name_of(row) if row.kind != "reference" else node, "kind": row.kind, "paper": standing.paper(node) if row.kind != "reference" else None}  # fmt: skip
            todo += [r.id for r in index.uses(node)]
            todo += [p.id for p in index.proofs(node)] if row.kind == "statement" else []
    rows = list(seen.values())
    items = [Item(f"{r['node']}  {r['name']}  [{r['paper'] or r['kind']}]") for r in rows]
    Report(f"{what} rests on {counted(len(rows), 'node')}", groups=[Group("rests on", items)] if items else [], data={"rests_on": rows}).emit(as_json)  # fmt: skip


@click.command(name="stubs")
@click.option("--work", default=None, metavar="REF", help="Only this work's stubs.")
@JSON_OPTION
@quilt_option
def stubs_command(work: str | None, as_json: bool, quilt_path: str | None) -> None:
    """The library's stubs: results known to stand in a work whose text nobody has read yet, which `loom library fill` gives their text."""
    from loom.library.index import NodeIndex
    from loom.library.reads import name_of

    root = open_quilt(quilt_path).root
    with NodeIndex.open(root) as index:
        rows = [{"node": r.id, "name": name_of(r), "work": r.source, "pages": r.pages} for r in index.stubs(work)]
    items = [
        Item(f"{r['node']}  {r['name']} of {r['work']}" + (f", page {r['pages']}" if r["pages"] else "")) for r in rows
    ]
    Report(f"{counted(len(rows), 'stub')}", groups=[Group("stubs", items)] if items else [], data={"stubs": rows}).emit(as_json)  # fmt: skip


@click.command(name="work")
@click.argument("ref")
@JSON_OPTION
@quilt_option
def work_command(ref: str, as_json: bool, quilt_path: str | None) -> None:
    """A work: what loom holds of it and its outline, every result of its source digested or not. REF is its id."""
    from loom.library.reads import work

    said = _read(work, _scanned(quilt_path), ref)
    o = said["outline"]
    items = [Item(f"{i['item'] or '-'}  {i['name']}  {i['node'] or '(not digested)'}  [{i['paper'] or ''}]") for i in o["items"]]  # fmt: skip
    head = f"{said['short']}: {'PDF' if said['holds']['pdf'] else 'no PDF'}, {'TeX source' if said['holds']['tex'] else 'no source'}"
    Report(head, groups=[Group("outline", items)] if items else [], data=said).emit(as_json)


#: The most pages one statement's text is read from: a range wider than this would let any words pass.
SPAN = 3


def _span(pages: str | None) -> tuple[int, int] | None:
    """A page or a range `12-13` as its first and last page; None where it is neither."""
    first, _, last = (pages or "").partition("-")
    if not first.isdecimal() or (last and not last.isdecimal()):
        return None
    return int(first), int(last or first)


def _check_read(
    root: Path, work: Any, body: str, read_from: str, pages: str | None, held_pages: str | None = None
) -> dict[str, Any]:
    """The document a text was read from, `{ref, pdf | tex, pages?}`, once its words stand there: on the PDF's pages `pages`, or in the TeX source; refused otherwise.

    Pages are checked only from a PDF, so `--pages` is refused with the source; the range is at most `SPAN` pages and, for a stub whose pages are known (`held_pages`), must meet them.
    """
    from loom.library import documents
    from loom.library.places import _words
    from loom.refs.search import fold

    words = re.findall(r"[^\W\d_]{3,}", fold(" ".join(_words(body))))
    if not words:
        raise ContentError("the text has no words outside its mathematics for loom to find where it was read, so loom cannot check it stands there")  # fmt: skip
    if read_from == "pdf":
        from loom.refs.pages import mapped, read_page

        home = mapped(root, work.pdf) if work.pdf else None
        if home is None:
            raise ContentError(f"{work.id} holds no PDF loom can read on this computer")
        span = _span(pages)
        if span is None or not 1 <= span[0] <= span[1]:
            raise ContentError("--pages is a page, or the first and last joined by a hyphen, as the PDF numbers them")
        first, last = span
        if last - first >= SPAN:
            raise ContentError(f"--pages names at most {SPAN} pages, where the text stands")
        known = _span(held_pages)
        if known is not None and (last < known[0] or first > known[1]):
            raise ContentError(f"the result stands on page {held_pages} of its work; read it there")
        text = " ".join(read_page(home, p) or "" for p in range(first, last + 1))
        where: dict[str, Any] = {"ref": work.id, "pdf": work.pdf, "pages": pages}
    else:
        if pages:
            raise ContentError("--pages is checked on the PDF's pages, so it is given only with --from pdf")
        if not work.tex:
            raise ContentError(f"{work.id} holds no TeX source")
        src = documents.source_dir(root, work.tex)
        text = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(src.rglob("*.tex")) if p.is_file() and not p.is_symlink())  # fmt: skip
        where = {"ref": work.id, "tex": work.tex}
    held = set(re.findall(r"[^\W\d_]{3,}", fold(text)))
    lacks = list(dict.fromkeys(w for w in words if w not in held))
    if lacks:
        raise ContentError(
            f"the text's words are not all on {'its pages' if read_from == 'pdf' else 'its source'}: {', '.join(lacks[:8])}"
        )
    return where


def _pointed(
    node_id: str, body: str, mentions: tuple[str, ...], parent: str | None = None
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What a body points at, as `uses` and `mentions`: every node and anchor's owner it names, those named by `--mention` among the mentions."""
    from loom.library import ids
    from loom.library.body import pointers

    exempt = {node_id, parent} - {None}
    named = {ids.anchor_owner(p.target) or p.target for p in pointers(body)} - exempt
    return tuple(sorted(named - set(mentions))), tuple(sorted(set(mentions)))


def _record(root: Path, node: Any, by: Any, read_from: str, where: dict[str, Any], *, new: bool) -> None:
    """Write an agent's node and record how it was made, as one act (`evidence.acts.give`); its refusal said as a command says one."""
    from loom.evidence.acts import ActRefused, give

    try:
        give(root, node, by, "transcribed" if read_from == "pdf" else "read", where, fresh=new)
    except ActRefused as exc:
        said = "; ".join(getattr(d, "message", str(d)) for d in exc.diagnostics[:3])
        raise ContentError(f"{exc}: {said}" if said else str(exc)) from None


@click.command(name="fill")
@click.argument("stub")
@click.option("--body", required=True, help="The result's text, as LaTeX, pointing at other nodes by their ids.")
@click.option(
    "--from",
    "read_from",
    type=click.Choice(FROM),
    default="pdf",
    show_default=True,
    help="Read from the work's PDF, or from its TeX source.",
)
@click.option(
    "--pages",
    default=None,
    help="The page or pages it stands on, as the PDF numbers them (`12`, `12-13`), at most three; needed from a PDF and refused from the source.",
)
@click.option(
    "--mention",
    "mentions",
    multiple=True,
    metavar="NODE",
    help="A node the text mentions without resting on it; every other it names is a use.",
)
@AS_OPTION
@JSON_OPTION
@quilt_option
def fill_command(stub: str, body: str, read_from: str, pages: str | None, mentions: tuple[str, ...], declared: str | None, as_json: bool, quilt_path: str | None) -> None:  # fmt: skip
    """Give a stub its text, transcribed from its work's PDF or read from its TeX source: its words are checked to stand there, and how it was made is recorded as yours."""
    from dataclasses import replace

    from loom.library.store import read

    root = open_quilt(quilt_path).root
    by = _agent(root, declared)
    found = read(root, stub)
    if found is None or found.kind != "statement":
        raise ContentError(f"the library has no statement {stub}")
    if not found.empty:
        raise ContentError(f"{stub} has its text already; propose a correction with `loom library correct`")
    work = read(root, found.source or "")
    if work is None:
        raise ContentError(f"{stub} names no work the library holds")
    where = _check_read(root, work, body, read_from, pages, found.pages)
    uses, mentioned = _pointed(stub, body, mentions)
    node = replace(found, body=body.strip() + "\n", pages=pages or found.pages, uses=uses, mentions=mentioned)
    _record(root, node, by, read_from, where, new=False)
    Report(f"filled {stub}, {'transcribed' if read_from == 'pdf' else 'read'} by {by.name}", data={"node": stub}).emit(
        as_json
    )


@click.command(name="propose")
@click.argument("ref")
@click.option("--taxon", required=True, help="What it is: lemma, theorem, definition, ...")
@click.option("--number", default=None, help="Its number as the work prints it.")
@click.option("--title", default=None, help="The name the work gives it.")
@click.option("--body", required=True, help="The result's text, as LaTeX, pointing at other nodes by their ids.")
@click.option(
    "--from",
    "read_from",
    type=click.Choice(FROM),
    default="pdf",
    show_default=True,
    help="Read from the work's PDF, or from its TeX source.",
)
@click.option(
    "--pages",
    default=None,
    help="The page or pages it stands on, as the PDF numbers them, at most three; needed from a PDF and refused from the source.",
)
@click.option(
    "--mention", "mentions", multiple=True, metavar="NODE", help="A node the text mentions without resting on it."
)
@AS_OPTION
@JSON_OPTION
@quilt_option
def propose_command(ref: str, taxon: str, number: str | None, title: str | None, body: str, read_from: str, pages: str | None, mentions: tuple[str, ...], declared: str | None, as_json: bool, quilt_path: str | None) -> None:  # fmt: skip
    """Propose a node at a place of a work no node holds: a new statement of REF, its words checked to stand there; it reads as not checked until the person compares it."""
    from loom.library.digest import of_work
    from loom.library.node import Node
    from loom.library.references import Minter
    from loom.library.store import read

    result = _scanned(quilt_path)
    root = result.quilt.root
    by = _agent(root, declared)
    work = read(root, ref)
    if work is None or work.kind != "reference":
        raise ContentError(f"the library has no work {ref}")
    held = [
        n for n in of_work(root, ref) if n.kind == "statement" and number and n.number == number and n.taxon == taxon
    ]
    if held:
        raise ContentError(
            f"{ref} holds {held[0].id} at {taxon} {number} already; fill it if it is a stub, or correct it"
        )
    where = _check_read(root, work, body, read_from, pages)
    from loom.library.gather import writing

    with writing(root):
        stem = Minter.of(result).stem()
        uses, mentioned = _pointed(stem, body, mentions)
        node = Node(id=stem, taxon=taxon, number=number, title=title, source=ref, pages=pages, body=body.strip() + "\n", uses=uses, mentions=mentioned)  # fmt: skip
        _record(root, node, by, read_from, where, new=True)
    Report(f"proposed {stem}, {taxon} {number or ''} of {ref}".rstrip(), data={"node": stem}).emit(as_json)


@click.command(name="correct")
@click.argument("node")
@click.option("--body", required=True, help="The node's corrected text, as LaTeX; its header is kept.")
@click.option("--why", required=True, help="What was wrong, for the person who compared it.")
@click.option(
    "--mention", "mentions", multiple=True, metavar="NODE", help="A node the text mentions without resting on it."
)
@AS_OPTION
@JSON_OPTION
@quilt_option
def correct_command(node: str, body: str, why: str, mentions: tuple[str, ...], declared: str | None, as_json: bool, quilt_path: str | None) -> None:  # fmt: skip
    """Propose a correction of a node's text: written at once where no person has compared it, else filed for the person to take or decline, the compared text standing meanwhile."""
    from dataclasses import replace

    from loom.evidence.acts import ActRefused, propose
    from loom.library.node import node_bytes
    from loom.library.store import read

    root = open_quilt(quilt_path).root
    by = _agent(root, declared)
    found = read(root, node)
    if found is None or found.kind not in ("statement", "proof"):
        raise ContentError(f"the library has no statement or proof {node}")
    uses, mentioned = _pointed(node, body, mentions, found.parent)
    new = replace(found, body=body.strip() + "\n", uses=uses, mentions=mentioned)
    try:
        how, _record_ = propose(root, node, node_bytes(new), by, why)
    except ActRefused as exc:
        raise ContentError(str(exc)) from None
    said = (
        "written; nobody had compared it"
        if how == "written"
        else "filed for the person, who compared the text it corrects"
    )
    Report(f"{node}: {said}", data={"node": node, "outcome": how}).emit(as_json)


@click.command(name="digest")
@click.argument("ref")
@click.option(
    "--scope",
    type=click.Choice(("used", "all", "chosen")),
    default="used",
    show_default=True,
    help="What the drafts cite of it, every result, or the items --item names.",
)
@click.option(
    "--item", "items", multiple=True, metavar="ITEM", help="A result of its source's survey, for --scope chosen."
)
@JSON_OPTION
@quilt_option
def digest_command(ref: str, scope: str, items: tuple[str, ...], as_json: bool, quilt_path: str | None) -> None:
    """Have loom write a work's results from its TeX source, numbered by its stored PDF: loom's own extraction, never a compile. A work whose numbers only a compile could confirm waits for the person's act in the viewer."""
    from loom.library.digest import DigestRefused, digest, scoped
    from loom.library.reads import surveyed
    from loom.library.store import read

    result = _scanned(quilt_path)
    root = result.quilt.root
    work = read(root, ref)
    if work is None or work.kind != "reference":
        raise ContentError(f"the library has no work {ref}")
    if not work.tex:
        raise ContentError(
            f"{ref} holds no TeX source; read its results from its PDF with `loom library fill` and `propose`"
        )
    s = surveyed(root, work)
    if s is None or s.state != "ready":
        raise ContentError(f"{ref}'s source could not be surveyed: {s.why if s else 'no main file'}")
    if s.why == "no-pdf" and not s.compiled:
        raise ContentError(f"{ref} holds no PDF to number its results by; only a compile, the person's act in the viewer, could, and an agent's call compiles nothing")  # fmt: skip
    try:
        done = digest(result, ref, scoped(result, ref, s, scope, list(items)), s, closure=scope == "used")
    except DigestRefused as exc:
        raise ContentError(str(exc)) from None
    wrote = len(done.made) + len(done.filled) + len(done.rewritten)
    groups = [Group("waiting", [Item(f"{k}: {v}") for k, v in done.waiting.items()])] if done.waiting else []
    Report(f"{ref}: {counted(wrote, 'node')} written, {len(done.waiting)} waiting", groups=groups, data=done.to_json()).emit(as_json)  # fmt: skip


COMMANDS = [
    node_command,
    search_command,
    uses_command,
    rests_on_command,
    stubs_command,
    work_command,
    fill_command,
    propose_command,
    correct_command,
    digest_command,
]
