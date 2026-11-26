"""A node drawn by TeX with its work's macros (`library-views.md` §3.4): the person's own act, given once for a work, never an agent's.

The person's word to compile a work's source, given with the viewer's sentence (`library-compile`, or `library-digest` compiling first), covers that compile and the drawing of the work's nodes afterwards, in this quilt on this machine. It is kept in loom's machine folder (`machine.words_file`), keyed by where the quilt lies and naming the source it was given for, never in the quilt's files, so opening a co-author's quilt, or a copy of one, draws nothing. A drawing is a `standalone` document of the node's text under its heading, after its work's macros node and what its pointers print as the store holds them when it is drawn (`printed`), compiled as a foreign source (`compile_tex`: shell escape off, a time limit, nothing fetched), one at a time with the survey's compiles, in a folder emptied before and removed after; its PDF becomes SVG as a figure's does (`render.assets.pdf_to_svg`). It is kept by both hashes under `.loom/cache/library/drawn/`, and so is a failure of TeX's, so neither is made twice.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

from loom import locks, machine
from loom.library import ids
from loom.library.node import Node, node_bytes, node_hash
from loom.paths import DRAWN_RUN, LIBRARY_DRAWN, SURVEY_LOCK

#: A drawing's name: the node's hash and its work's macros node's, `none` for a work with none.
NAME = re.compile(r"([0-9a-f]{64})-([0-9a-f]{64}|none)\.svg")
#: How wide a drawn node is set at most, as a page's text is.
WIDTH = "16cm"
#: Seconds TeX is given to draw one node.
TIMEOUT = 60
#: The engines a drawing is compiled with: the work's own where its survey names one of these.
ENGINES = ("pdflatex", "xelatex", "lualatex")


def given(root: Path, ref: str, tex: str) -> bool:
    """Whether the person gave their word to compile the source `tex` of the work `ref`, in the quilt at `root` on this machine.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The work.
    tex : str
        The hash of its source.

    Returns
    -------
    bool
    """
    return _words(root).get(ref) == tex


def give(root: Path, ref: str, tex: str) -> None:
    """Keep the person's word to compile the source `tex` of the work `ref`: in loom's machine folder, readable by this user alone.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The work.
    tex : str
        The hash of the source the word is given for; a source put in its place asks again.
    """
    p = machine.words_file(root)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with locks.locked(p.with_suffix(".lock")):
        works = _words(root)
        if works.get(ref) == tex:
            return
        works[ref] = tex
        tmp = p.with_name(f".{p.name}.{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"root": str(Path(root).resolve()), "compile": works}, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, p)


def _words(root: Path) -> dict[str, str]:
    """The works whose sources the person gave their word to compile here, by their sources' hashes; empty where none is kept or the file names another quilt."""
    try:
        data = json.loads(machine.words_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("root") != str(Path(root).resolve()):
        return {}
    works = data.get("compile")
    return {k: v for k, v in works.items() if isinstance(v, str)} if isinstance(works, dict) else {}


def drawn(root: Path, name: str) -> Path | None:
    """The node a drawing's name names, drawn by TeX with its work's macros, made the first time it is asked for.

    Parameters
    ----------
    root : Path
        The quilt.
    name : str
        `<node-hex>-<macros-hex>.svg`: the node's hash and its work's macros node's, `none` for a work with none (`library-node`'s `hash` and `macros.hash`).

    Returns
    -------
    Path or None
        The SVG under `.loom/cache/library/drawn/`. None where no node of the store has that hash, it has no text, its work's macros node is not the one named, the person has not given their word for the work's source here, or TeX could not draw it.
    """
    from loom.library.index import IndexUnavailable, NodeIndex
    from loom.library.store import read

    m = NAME.fullmatch(name)
    if m is None:
        return None
    try:
        with NodeIndex.open(root) as index:
            node_id = index.hashed(f"sha256:{m.group(1)}")
    except IndexUnavailable:
        return None
    node = read(root, node_id) if node_id else None
    if node is None or node.empty or node.kind not in (ids.STATEMENT, ids.PROOF):
        return None
    ref = node.source
    work = read(root, ref) if ref and ids.kind_of(ref) == ids.REFERENCE else None
    if work is None or not work.tex or not given(root, work.id, work.tex):
        return None
    macros = read(root, ids.macros_of(work.id))
    if (node_hash(node_bytes(macros)).removeprefix("sha256:") if macros is not None else "none") != m.group(2):
        return None
    out = root / LIBRARY_DRAWN / name
    if out.is_file():
        return out
    if out.with_suffix(".failed").is_file():
        return None
    heading = "Proof" if node.kind == ids.PROOF else _name(node)
    text = document(node, heading, macros.body if macros else "", printed(root, node, work.id))
    return out if _draw(root, text, _engine(root, work), out) else None


def printed(root: Path, node: Node, ref: str) -> dict[str, str]:
    """What each pointer of the node's body prints, read from the store when it is drawn: an id or anchor its number (`r@…`), a cited work its short name (`b@…`), another work's result its work and name together; one with nothing to print is left to TeX's `??`.

    Parameters
    ----------
    root : Path
        The quilt.
    node : Node
        A statement or a proof.
    ref : str
        Its work.

    Returns
    -------
    dict of str to str
        By LaTeX's name for it, `r@<id>` or `b@<ref>`, the text, TeX's specials escaped where it is not TeX already.
    """
    from loom.library.body import pointers
    from loom.library.store import read

    own = dict(node.anchors)
    out: dict[str, str] = {}
    for p in pointers(node.body):
        name = f"b@{p.target}" if p.cites else f"r@{p.target}"
        if name in out or p.command == "label":
            continue
        if p.cites:
            short = _short(root, p.target)
            if short:
                out[name] = _escaped(short)
            continue
        owner = ids.anchor_owner(p.target)
        if owner is not None:
            held = own if owner == node.id else dict(getattr(read(root, owner), "anchors", ()) or ())
            if p.target in held:
                out[name] = held[p.target]
            continue
        target = read(root, p.target)
        if target is None or not target.number:
            continue
        work = target.source if target.kind == ids.STATEMENT else None
        if work is None or work == ref:
            out[name] = target.number
        elif short := _short(root, work):
            out[name] = f"[{_escaped(short)}, {_name(target)}]"
    return out


def _short(root: Path, ref: str) -> str:
    """A work's short name, `Smith 2024`, or '' for no work of that id."""
    from loom.library.store import read
    from loom.library.works import described

    work = read(root, ref) if ids.kind_of(ref) == ids.REFERENCE else None
    said = described(work.body) if work is not None else None
    return str(said["short"]) if said and said.get("short") else ""


def _escaped(text: str) -> str:
    """Plain words as TeX prints them."""
    return re.sub(r"([&%#_{}$])", r"\\\1", text).replace("~", "\\~{}").replace("^", "\\^{}")


def document(node: Node, heading: str, macros: str, labels: dict[str, str] | None = None) -> str:
    """The `standalone` document a node is drawn from: its work's macros node, then its heading and text in a box as wide as a page's text at most.

    Parameters
    ----------
    node : Node
        A statement or a proof.
    heading : str
        What it is headed by: `Lemma 3.2`, or `Proof`.
    macros : str
        Its work's macros node's text, '' for none.
    labels : dict of str to str, optional
        What its pointers print (`printed`). Each display the body labels with an anchor `anchors` numbers is tagged with that number, as its source prints it, and one `awaiting` its number with none, never TeX's own count; unless the body tags its own.

    Returns
    -------
    str
    """
    title = f" ({node.title})" if node.title and node.kind == ids.STATEMENT else ""
    head = f"\\textit{{{heading}.}}" if node.kind == ids.PROOF else f"\\textbf{{{heading}}}{title}."
    defined = [
        f"\\@namedef{{{name}}}{{{{{text}}}{{}}}}" if name.startswith("r@") else f"\\@namedef{{{name}}}{{{text}}}"
        for name, text in (labels or {}).items()
    ]
    if (node.anchors or node.awaiting) and "\\tag" not in node.body:
        defined += [f"\\@namedef{{loom@tag@{anchor}}}{{\\tag{{{number}}}}}" for anchor, number in node.anchors]
        defined += [f"\\@namedef{{loom@tag@{anchor}}}{{\\tag*{{}}}}" for anchor in node.awaiting]
        defined += [
            "\\let\\loom@label\\label@in@display",
            "\\def\\label@in@display#1{\\loom@label{#1}\\@ifundefined{loom@tag@#1}{}"
            "{\\iftag@\\else\\csname loom@tag@#1\\endcsname\\fi}}",
        ]
    told = "\\makeatletter\n" + "\n".join(defined) + "\n\\makeatother\n" if defined else ""
    return (
        "\\documentclass[border=1pt]{standalone}\n"
        "\\usepackage{varwidth}\n"
        "\\usepackage{amsmath,amssymb,amsthm}\n"
        f"{macros.strip()}\n"
        f"{told}"
        "\\begin{document}\n"
        f"\\begin{{varwidth}}{{{WIDTH}}}\n"
        f"{head}\\enspace {node.body.strip()}\n"
        "\\end{varwidth}\n"
        "\\end{document}\n"
    )


def _name(node: Node) -> str:
    from loom.library.reads import name_of

    return name_of(node)


def _engine(root: Path, work: Node) -> str:
    """The engine the work's source is compiled with, as its survey read it; pdflatex where none is kept."""
    from loom.library.survey import kept

    s = kept(root, work.tex, work.pdf) if work.tex else None
    return s.engine if s is not None and s.engine in ENGINES else "pdflatex"


def _draw(root: Path, text: str, engine: str, out: Path) -> bool:
    """Compile `text` and keep its page as the SVG `out`, one compile at a time in the quilt; a failure of TeX's is kept as `.failed`, one of the machine's (no TeX, no converter, out of time) is not."""
    from loom.library.survey import QUEUE
    from loom.render.assets import pdf_to_svg
    from loom.tex.runner import compile_tex

    with locks.locked(root / SURVEY_LOCK, wait=QUEUE), _scratch(root / DRAWN_RUN) as tmp:
        if out.is_file():
            return True
        (tmp / "node.tex").write_text(text, encoding="utf-8")
        res = compile_tex(tmp, "node.tex", tmp / "out", engine, timeout=TIMEOUT, foreign=True, online=False)
        if res.ok and res.pdf is not None and res.pdf.is_file():
            made, _ = pdf_to_svg(res.pdf, tmp / "node.svg")
            if made:
                out.parent.mkdir(parents=True, exist_ok=True)
                os.replace(tmp / "node.svg", out)
                return True
            return False
        if res.returncode not in (124, 127) and not res.stopped:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.with_suffix(".failed").write_text(res.first_error[:500] + "\n", encoding="utf-8")
        return False


@contextlib.contextmanager
def _scratch(at: Path) -> Iterator[Path]:
    """The folder one drawing compiles in: emptied first and removed after."""
    shutil.rmtree(at, ignore_errors=True)
    at.mkdir(parents=True)
    try:
        yield at
    finally:
        shutil.rmtree(at, ignore_errors=True)
