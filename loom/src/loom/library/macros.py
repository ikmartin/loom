"""A work's macros node, made from its TeX source's preamble (`docs/specs/nodes.md` §8): what typesetting the work's bodies needs, and nothing else.

The preamble is read from the source's main file up to `\\begin{document}`. Every item `body.ARGUMENTS` allows is taken whole, as the source wrote it and in its order; a local `.sty` or `.tex` file the preamble loads (`\\usepackage`, `\\RequirePackage`, `\\input`, `\\include`) is read in its place, a package's file between `\\makeatletter` and `\\makeatother` since `@` is a letter there; a package the source does not hold stays a `\\usepackage` line. Everything else, the class, the title, `\\newtheorem`, settings TeX alone reads, is left out. A definition nothing uses costs nothing (`docs/design/library.md`, "Nodes"), so all of them are taken, not only those the digested bodies use.
"""

from __future__ import annotations

import re
from pathlib import Path

from loom.library import documents
from loom.library.body import ARGUMENTS, blank_comments, macros_items
from loom.library.node import Node
from loom.scan.tokenize import match_group, read_optional, skip_space

#: How deep loaded files are followed, so a file that loads itself ends.
DEPTH = 8
_BEGIN_DOCUMENT = re.compile(r"\\begin\s*\{document\}")
_LOADERS = ("usepackage", "RequirePackage", "input", "include")


def preamble_items(source: Path) -> list[str]:
    """The items a source's preamble holds that a macros node may, each as the source wrote it, with its local files read in their places.

    Parameters
    ----------
    source : Path
        The source's folder, unpacked.

    Returns
    -------
    list of str
        In order; empty when the source declares no class or its preamble defines nothing a macros node holds.
    """
    main = documents.main_file(source)
    if main is None:
        return []
    text = main.read_text(encoding="utf-8", errors="replace")
    end = _BEGIN_DOCUMENT.search(blank_comments(text))
    return _items(text[: end.start()] if end else text, source, main.parent, set(), 0)


def _items(text: str, source: Path, here: Path, seen: set[Path], depth: int) -> list[str]:
    out: list[str] = []
    clean = blank_comments(text)
    for item in macros_items(text):
        if item.command not in _LOADERS:
            if item.command in ARGUMENTS:
                out.append(text[item.start : item.end].strip())
            continue
        names, options = _loaded(clean, item.start, item.end)
        kept: list[str] = []
        inlined: list[str] = []
        for name in names:
            found = _local(source, here, name, package=item.command in ("usepackage", "RequirePackage"))
            if found in seen:
                continue
            if found is None or depth >= DEPTH:
                if item.command in ("usepackage", "RequirePackage"):
                    kept.append(name)
                continue
            seen.add(found)
            inner = _items(found.read_text(encoding="utf-8", errors="replace"), source, found.parent, seen, depth + 1)
            if found.suffix == ".sty" and inner:
                inner = ["\\makeatletter", *inner, "\\makeatother"]
            inlined.extend(inner)
        # the packages it loads before the definitions a local file of it makes, which may need them
        if kept:
            out.append(f"\\{item.command}{options}{{{','.join(kept)}}}")
        out.extend(inlined)
    return out


def _loaded(clean: str, start: int, end: int) -> tuple[list[str], str]:
    """The names a loading command at `clean[start:end]` loads, and its options as written (`[utf8]`, or '')."""
    m = re.match(r"\\[A-Za-z]+\*?", clean[start:end])
    pos = start + (m.end() if m else 0)
    options = ""
    opt, _s, _e, after = read_optional(clean, pos)
    if opt is not None:
        options = f"[{opt}]"
        pos = after
    p = skip_space(clean, pos)
    if p < len(clean) and clean[p] == "{":
        close = match_group(clean, p)
        group = clean[p + 1 : close - 1] if close > 0 else ""
    else:
        group = clean[p:end].strip()
    return [n.strip() for n in group.split(",") if n.strip()], options


def _local(source: Path, here: Path, name: str, *, package: bool) -> Path | None:
    """The file of the source `name` loads, inside the source: `name.sty` for a package, `name` or `name.tex` otherwise; None when the source does not hold it."""
    tries = [f"{name}.sty"] if package else [name, f"{name}.tex"]
    for base in (here, source):
        for t in tries:
            candidate = (base / t).resolve()
            if candidate.is_file() and candidate.is_relative_to(source.resolve()):
                return candidate
    return None


def macros_node(ref: str, items: list[str]) -> Node | None:
    """The macros node of the reference `ref` holding `items`, one a line; None when there are none.

    Parameters
    ----------
    ref : str
        The reference's id, `stem-ref`.
    items : list of str
        What `preamble_items` gave.

    Returns
    -------
    Node or None
        `stem-macros`, to be written with `store.write_node`.
    """
    if not items:
        return None
    return Node(id=ref.removesuffix("-ref") + "-macros", taxon="macros", body="\n".join(items) + "\n")
