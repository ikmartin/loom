"""The links a quilt's own files make (`docs/design/model.md`, "Notes"): every `quilt:` and `cited:` link written in a shown Markdown file, notebook, HTML page or plain-text file, org among them, resolved to what it names, so the viewer lists beside each document, work and PDF the files that link to it.

The index is computed at each build and nobody edits it. A link that names nothing the viewer shows is left out here; `loom lint` names it where Markdown is concerned.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

#: The kinds of shown file whose text is read for links: what a person writes notes in.
READ = frozenset({"markdown", "notebook", "html", "text"})
#: A file longer than this is not read for links, as the viewer draws no longer text.
LIMIT = 1 << 20


def backlinks(result: Any, root: Path, kinds: dict[str, str]) -> list[dict[str, Any]]:
    """Every link the shown files make, resolved, in file and line order.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned.
    root : Path
        The quilt root.
    kinds : dict of str to str
        Each shown file's kind by its path (`files.kind_of`).

    Returns
    -------
    list of dict
        One per link: `from` the file, `line` 1-based, `at` the id of the heading above it in a Markdown file or a notebook ('' for none, and in any other kind), `href` as written, and what it names, `kind`, `key`, `place` and `quote` (`links.Target`). A file's links to itself are left out.
    """
    from loom.links import LinkError, raw_links, resolve

    found: list[tuple[str, int, str, str]] = []
    for rel in sorted(kinds):
        if kinds[rel] not in READ:
            continue
        path = root / rel
        try:
            if path.stat().st_size > LIMIT:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        heads: list[tuple[int, str]] = []
        if kinds[rel] == "notebook":
            cells = _cell_list(text)
            text = "\n".join(src for _, src in cells)
            heads = _notebook_headings(root, rel, cells)
        elif kinds[rel] == "html":
            # an attribute's `&amp;` is the `&` between a link's place and its words
            text = html.unescape(text)
        elif kinds[rel] == "markdown":
            heads = _headings(root, rel, text)
        found.extend((rel, line, href, _above(heads, line)) for line, href in raw_links(text))
    if not found:
        return []
    from loom.records.annotations import load_records

    records, _ = load_records(root)
    seen: dict[str, Any] = {}
    out: list[dict[str, Any]] = []
    for rel, line, href, at in found:
        if href not in seen:
            try:
                seen[href] = resolve(result, root, href, records)
            except LinkError:
                seen[href] = None
        target = seen[href]
        if target is None or (target.kind == "file" and target.key == rel):
            continue
        out.append(
            {
                "from": rel,
                "line": line,
                "at": at,
                "href": href,
                "kind": target.kind,
                "key": target.key,
                "place": target.place,
                "quote": target.quote,
            }
        )
    return out


def _cell_list(raw: str) -> list[tuple[str, str]]:
    """A notebook's cells as (type, source), in order, so a link in its JSON is read as its cell wrote it; none for a notebook that does not parse."""
    import json

    try:
        cells = json.loads(raw).get("cells", [])
    except (ValueError, AttributeError):
        return []
    out: list[tuple[str, str]] = []
    for cell in cells if isinstance(cells, list) else []:
        src = cell.get("source", "") if isinstance(cell, dict) else ""
        kind = cell.get("cell_type", "") if isinstance(cell, dict) else ""
        out.append((str(kind), "".join(src) if isinstance(src, list) else str(src)))
    return out


def _notebook_headings(root: Path, rel: str, cells: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """A notebook's headings by line of its cells joined as `backlinks` reads them, each with the id its page gives it: its Markdown cells' alone, numbered across cells as the page numbers them, so a `#` comment in code is none."""
    from loom.files import headings_of, slug

    drawn = headings_of(root, rel, "notebook")
    seen: dict[str, int] = {}
    out: list[tuple[int, str]] = []
    first = 1
    for kind, src in cells:
        lines = src.split("\n")
        if kind == "markdown":
            fenced = False
            for n, line in enumerate(lines, start=first):
                if _FENCE.match(line):
                    fenced = not fenced
                elif not fenced and (m := _HEADING.match(line)):
                    sid = slug(m.group(1), seen)
                    if sid in drawn:
                        out.append((n, sid))
        first += len(lines)
    return out


#: An ATX heading's line, and a code fence's.
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
_FENCE = re.compile(r"^ {0,3}(```|~~~)")


def _headings(root: Path, rel: str, text: str) -> list[tuple[int, str]]:
    """The Markdown file's headings by line, each with the id its page gives it (`files.slug`), those the page does not draw with that id left out; code fences skipped."""
    from loom.files import headings_of, slug

    drawn = headings_of(root, rel, "markdown")
    seen: dict[str, int] = {}
    out: list[tuple[int, str]] = []
    fenced = False
    for n, line in enumerate(text.split("\n"), start=1):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and (m := _HEADING.match(line)):
            sid = slug(m.group(1), seen)
            if sid in drawn:
                out.append((n, sid))
    return out


def _above(heads: list[tuple[int, str]], line: int) -> str:
    """The id of the last heading at or above `line`; '' for none."""
    return next((sid for n, sid in reversed(heads) if n <= line), "")


#: Whether quoted words stand on a project PDF's page, by the file's path, stamp and size, the page and the words: a build asks again for every link, and a PDF's word boxes are slow to draw.
_ON_PAGE: dict[tuple[str, int, int, int, str], bool | None] = {}


def words_found(result: Any, root: Path, link: dict[str, Any]) -> bool | None:
    """Whether a backlink's quoted words still stand in what it names, found as the viewer finds them to light them; None where it quotes nothing or loom cannot tell.

    A result's words are looked for in its own text, a document's beyond any result in its own source with its inputs expanded, a project PDF's or a work's on the page the link names (`records.marks.lines_of`, `refs.search.find_in_page`); a PDF with no page named, or a work whose pages cannot be read, is not judged.
    """
    from loom.records.selectors import find_quote

    words = " ".join(str(link.get("quote") or "").split())
    if not words:
        return None
    kind, key, place = link["kind"], link["key"], link.get("place") or ""
    if kind in ("node", "document"):
        named = key if kind == "node" else (result.named(place) if place else None)
        if named and named in result.nodes:
            from loom.scan.owntext import own_text

            return bool(find_quote(own_text(result, result.nodes[named]), words))
        if kind == "document":
            # the document's own source, its inputs expanded in place; another document's words are not its
            expanded = result.expansions.get(key)
            text = expanded.text if expanded is not None else (result.files[key].text if key in result.files else None)
            return None if text is None else bool(find_quote(text, words))
        return None
    page = int(m.group(1)) if (m := re.fullmatch(r"page=(\d+)", place)) else 0
    if not page:
        return None
    if kind == "file" and key.lower().endswith(".pdf"):
        return _on_page(root / key, page, words)
    if kind == "work":
        from loom.library.store import read
        from loom.records.marks import reference_pdf
        from loom.refs.pages import mapped, read_page
        from loom.refs.search import find_in_page

        node = read(root, key)
        home = mapped(root, node.pdf) if node is not None and node.pdf and reference_pdf(root, key) else None
        text = read_page(home, page) if home is not None else None
        return None if text is None else bool(find_in_page(text, words))
    return None


def _on_page(pdf: Path, page: int, words: str) -> bool | None:
    from loom.refs.pages import MapRefused, token_boxes
    from loom.refs.search import locate_span

    try:
        st = pdf.stat()
    except OSError:
        return None
    stamp = (str(pdf), st.st_mtime_ns, st.st_size, page, words)
    if stamp not in _ON_PAGE:
        if len(_ON_PAGE) > 4096:
            _ON_PAGE.clear()
        try:
            _ON_PAGE[stamp] = locate_span(token_boxes(pdf, page, None), words, page) is not None
        except MapRefused:
            _ON_PAGE[stamp] = None
    return _ON_PAGE[stamp]
