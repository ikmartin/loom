"""A work's macros node, made from its TeX source's preamble (`docs/specs/nodes.md` §8): what typesetting the work's bodies needs, and nothing else.

The preamble is read from the source's main file up to `\\begin{document}`, and no further than `PREAMBLE_CAP`, a line at a time, since a source may be hundreds of megabytes. Every item `body.ARGUMENTS` allows is taken whole, as the source wrote it and in its order; a local `.sty` or `.tex` file the preamble loads (`\\usepackage`, `\\RequirePackage`, `\\input`, `\\include`) is read in its place, a package's file between `\\makeatletter` and `\\makeatother` since `@` is a letter there; a package the source does not hold, or holds in a file larger than `LOADED_CAP`, stays a `\\usepackage` line. A conditional (`body.is_conditional`) is kept whole, its branches made as the preamble is, when they hold only what a macros node may, and is otherwise left out with a comment in the node saying so, since a definition in it may be one a body needs. Everything else, the class and the packages it loads, the title, `\\newtheorem`, settings TeX alone reads, is left out. A definition nothing uses costs nothing (`docs/design/library.md`, "Nodes"), so all of them are taken, not only those the digested bodies use.
"""

from __future__ import annotations

import re
from pathlib import Path

from loom.library import documents
from loom.library.body import ARGUMENTS, Item, blank_comments, conditional, is_conditional, macros_items
from loom.library.node import Node
from loom.scan.tokenize import match_group, read_optional, skip_space

#: How deep loaded files are followed, so a file that loads itself ends.
DEPTH = 8
_BEGIN_DOCUMENT = re.compile(r"\\begin\s*\{document\}")
_LOADERS = ("usepackage", "RequirePackage", "input", "include")
#: The most of a main file read for its preamble, which is kilobytes in a source that may be hundreds of megabytes.
PREAMBLE_CAP = 4 * 1024 * 1024
#: The largest local file a preamble loads that is read in its place; a larger one is no file of definitions, and is kept as a package load or left out.
LOADED_CAP = 1024 * 1024
#: The longest piece of a line read at once, so a file with no line breaks is still read in pieces.
_PIECE = 64 * 1024


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
    return _items(_preamble(main), source, main.parent, set(), 0)


def _preamble(main: Path) -> str:
    """The main file up to its `\\begin{document}` outside a comment, read a line at a time and no further than `PREAMBLE_CAP`."""
    read: list[str] = []
    size = 0
    with main.open(encoding="utf-8", errors="replace") as fh:
        while size < PREAMBLE_CAP:
            line = fh.readline(_PIECE)
            if not line:
                break
            if end := _BEGIN_DOCUMENT.search(blank_comments(line)):
                read.append(line[: end.start()])
                break
            read.append(line)
            size += len(line)
    return "".join(read)


def _read_local(path: Path) -> str | None:
    """A local file a preamble loads, whole; None when it is larger than `LOADED_CAP` or cannot be read."""
    try:
        if path.stat().st_size > LOADED_CAP:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _items(
    text: str, source: Path, here: Path, seen: set[Path], depth: int, flags: frozenset[str] = frozenset()
) -> list[str]:
    out: list[str] = []
    clean = blank_comments(text)
    # a conditional `\\newif\\ifdraft` defines `\\drafttrue` and `\\draftfalse`, which a preamble sets
    flags = flags | {f"{n}{v}" for n in re.findall(r"\\newif\s*\\if([A-Za-z@]+)", clean) for v in ("true", "false")}
    for item in macros_items(text):
        if item.command == "AtBeginDocument":
            # what it holds is taken as the preamble's own items are, and the rest left out
            group = text[item.start : item.end]
            inner = (
                _items(group[group.find("{") + 1 : group.rfind("}")], source, here, seen, depth, flags)
                if "{" in group
                else []
            )
            if inner:
                out.append("\\AtBeginDocument{" + "\n".join(inner) + "}")
            continue
        if is_conditional(item.command):
            out.append(_conditional(text, item, source, here, seen, depth, flags))
            continue
        if item.command not in _LOADERS:
            if item.command in ARGUMENTS or item.command in flags:
                out.append(text[item.start : item.end].strip())
            continue
        names, options = _loaded(clean, item.start, item.end)
        kept: list[str] = []
        inlined: list[str] = []
        for name in names:
            found = _local(source, here, name, package=item.command in ("usepackage", "RequirePackage"))
            if found in seen:
                continue
            local = _read_local(found) if found is not None and depth < DEPTH else None
            if found is None or local is None:
                if item.command in ("usepackage", "RequirePackage"):
                    kept.append(name)
                continue
            seen.add(found)
            inner = _items(local, source, found.parent, seen, depth + 1, flags)
            if found.suffix == ".sty" and inner:
                inner = ["\\makeatletter", *inner, "\\makeatother"]
            inlined.extend(inner)
        # the packages it loads before the definitions a local file of it makes, which may need them
        if kept:
            out.append(f"\\{item.command}{options}{{{','.join(kept)}}}")
        out.extend(inlined)
    return out


def _conditional(
    text: str, item: Item, source: Path, here: Path, seen: set[Path], depth: int, flags: frozenset[str]
) -> str:
    """A conditional of the preamble kept whole, each branch made as the preamble is, its local files read in their places; or, when its condition is none loom reads or a branch holds what a macros node may not, a comment in the node saying it was left out and why."""
    cond = conditional(text, item)
    if cond is None:
        shown = " ".join(text[item.start : item.end].split())
        return f"% left out: {shown[:60]}{' …' if len(shown) > 60 else ''}, a conditional whose condition loom does not read"
    shown = " ".join(f"{cond.head} … {cond.tail}".split())
    for branch in cond.branches:
        if refused := _refused(branch, flags):
            return f"% left out: {shown}, a conditional holding {refused}, which a macros node may not"
    return cond.text([_branch(b, source, here, seen, depth, flags) for b in cond.branches])


def _branch(text: str, source: Path, here: Path, seen: set[Path], depth: int, flags: frozenset[str]) -> str:
    return "\n".join(_items(text, source, here, seen, depth, flags))


def _refused(text: str, flags: frozenset[str]) -> str:
    """The first thing `text` holds that a macros node may not, as the node's comment names it (`\\newtheorem`, `text`); '' when there is none. The loaders are allowed, since the maker reads them."""
    for item in macros_items(text):
        if item.command == "AtBeginDocument":
            group = text[item.start : item.end]
            if "{" in group and (inner := _refused(group[group.find("{") + 1 : group.rfind("}")], flags)):
                return inner
            continue
        if is_conditional(item.command):
            cond = conditional(text, item)
            if cond is None:
                return f"\\{item.command} with a condition loom does not read"
            for branch in cond.branches:
                if inner := _refused(branch, flags):
                    return inner
            continue
        if item.command in ARGUMENTS or item.command in flags or item.command in _LOADERS:
            continue
        return "text" if item.command == "text" else f"\\{item.command}"
    return ""


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
    """The macros node of the reference `ref` holding `items`, one a line; None when they hold nothing but the comments saying what was left out.

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
    body = "\n".join(items) + "\n"
    if not macros_items(body):
        return None  # nothing but what was left out, said in comments
    return Node(id=ref.removesuffix("-ref") + "-macros", taxon="macros", body=body)
