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
        One per link: `from` the file, `line` 1-based, `at` the id of the heading above it in a Markdown file ('' for none, and in any other kind), `href` as written, and what it names, `kind`, `key`, `place` and `quote` (`links.Target`). A file's links to itself are left out.
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
        if kinds[rel] == "notebook":
            text = _cells(text)
        elif kinds[rel] == "html":
            # an attribute's `&amp;` is the `&` between a link's place and its words
            text = html.unescape(text)
        heads = _headings(root, rel, text) if kinds[rel] == "markdown" else []
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


def _cells(raw: str) -> str:
    """A notebook's cells' sources, one after another, so a link in its JSON is read as its cell wrote it; '' for a notebook that does not parse."""
    import json

    try:
        cells = json.loads(raw).get("cells", [])
    except (ValueError, AttributeError):
        return ""
    out: list[str] = []
    for cell in cells if isinstance(cells, list) else []:
        src = cell.get("source", "") if isinstance(cell, dict) else ""
        out.append("".join(src) if isinstance(src, list) else str(src))
    return "\n".join(out)


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
