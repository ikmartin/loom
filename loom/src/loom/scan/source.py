"""File discovery and decoding.

Every .tex under the root outside `.loom/`, tool directories and Lake projects is a source file, and so is every agent copy. Decoding tries UTF-8, then Mac Roman, then Latin-1; the fallback is reported by the caller as loom:non-utf8-source. Comments are blanked to spaces so every later stage sees the same offsets as the raw text.
"""

from __future__ import annotations

import os
import re
from collections.abc import Collection
from pathlib import Path

from loom.paths import COPIES, LOOM
from loom.scan.memo import Memo
from loom.scan.model import SourceFile

#: Directories never read, by name at any depth: loom's own, whose agent copies alone are read on purpose, and tools', among them a Lake project's `.lake`, which holds its build and every package it depends on (Mathlib's alone is tens of thousands of files).
SKIP_DIRS = {".git", "node_modules", LOOM, ".svelte-kit", ".claude", ".lake"}
#: The files that make a folder a Lake project's root (`lake_root`); `lean-toolchain` alone makes none.
LAKEFILES = ("lakefile.toml", "lakefile.lean")
IGNORE_RE = re.compile(r"^\s*%\s*!LOOM\s+ignore\s*$", re.M)
_VERB_RE = re.compile(r"\\verb\*?(\S)(.*?)\1")
_VERBATIM_RE = re.compile(r"\\begin\{(verbatim\*?|lstlisting|comment|filecontents\*?)\}.*?\\end\{\1\}", re.S)


def lake_root(folder: Path) -> bool:
    """Whether `folder` is a Lake project's root, one holding a `lakefile.toml` or a `lakefile.lean`.

    The scan prunes such a folder below the quilt's root, the watcher does not walk it, and the look leaves out what lies under it (`lake_project`), all by this one test, so none of them disagrees with another. A Lean project is the agents' own: the skills' linters copy the paper's files into it, which the scan would read as a second copy.

    Parameters
    ----------
    folder : Path
        The folder to test.

    Returns
    -------
    bool
        True when it holds either lakefile.
    """
    return any((folder / name).is_file() for name in LAKEFILES)


def lake_project(root: Path, rel: str, known: dict[str, bool] | None = None) -> str | None:
    """The quilt-relative Lake project root (`lake_root`) that quilt-relative `rel` lies under, the outermost, or None; the quilt's own root is never one.

    Parameters
    ----------
    root : Path
        The quilt.
    rel : str
        A quilt-relative POSIX path.
    known : dict of str to bool, optional
        Each folder's answer, kept across calls by a caller that asks of many paths.

    Returns
    -------
    str or None
        The folder, quilt-relative; None when `rel` lies in no Lake project.
    """
    parts = rel.split("/")[:-1]
    known = {} if known is None else known
    for depth in range(1, len(parts) + 1):
        folder = "/".join(parts[:depth])
        if folder not in known:
            known[folder] = lake_root(root / folder)
        if known[folder]:
            return folder
    return None


def _tex_under(root: Path, top: Path, skip: set[Path], names: Collection[str] = ()) -> list[str]:
    """Quilt-relative paths of the .tex files under `top`, never descending into a directory in `skip`, named in `names` or a Lake project's root (`lake_root`), so a pruned one is never listed."""
    found: list[str] = []
    for here, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d not in names and Path(here) / d not in skip and not lake_root(Path(here) / d)]
        rel = Path(here).relative_to(root)
        found += [(rel / f).as_posix() for f in files if f.endswith(".tex")]
    return found


def discover_files(root: Path, skip_top: tuple[str, ...] = ()) -> list[str]:
    """Quilt-relative posix paths of every .tex file under root, sorted: every one outside `SKIP_DIRS`, a Lake project's root (`lake_root`) and the directories in `skip_top` (the history directory and the sync directory, given relative to root), and every agent copy.

    The tree is walked with those directories pruned, never listed and filtered after. Agent copies are read from `.loom/agents/copies/`, where `loom draft --ai` makes them.
    """
    found = _tex_under(root, root, {root / d.strip("/") for d in skip_top if d.strip("/")}, SKIP_DIRS)
    copies = root / COPIES
    if copies.is_dir():
        found += [p.relative_to(root).as_posix() for p in copies.glob("*.tex") if p.is_file()]
    return sorted(found)


def decode(data: bytes) -> tuple[str, str]:
    """Return (text, encoding). UTF-8 first; Mac Roman then Latin-1 accept every byte, so the first fallback always wins."""
    for enc in ("utf-8", "mac_roman", "latin-1"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1"


def _protected_ranges(text: str) -> list[tuple[int, int]]:
    ranges = [(m.start(), m.end()) for m in _VERBATIM_RE.finditer(text)]
    ranges += [(m.start(), m.end()) for m in _VERB_RE.finditer(text)]
    return sorted(ranges)


def blank_comments(text: str) -> str:
    """Replace every comment (from an unescaped % to end of line) with spaces, leaving verbatim regions untouched.

    A long text's result is remembered while it is in use, as `tokenize`'s is: a served quilt reads every file again on every change.
    """
    return _blank_cached(text) if len(text) >= 4096 else _blank_comments(text)


def _blank_comments(text: str) -> str:
    protected = _protected_ranges(text)
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "%":
            if any(a <= i < b for a, b in protected):
                i += 1
                continue
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


_blank_cached: Memo[str, str] = Memo(_blank_comments)


def line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


#: The marked block that carries loom's three macros in a document's own preamble, in place of `\\usepackage{loom}` (`reshape.linearize.loom_macro_block`).
MACRO_BLOCK_BEGIN = "% !LOOM begin loom-macros"
MACRO_BLOCK_END = "% !LOOM end loom-macros"
MACRO_BLOCK = re.compile(re.escape(MACRO_BLOCK_BEGIN) + r"\n.*?" + re.escape(MACRO_BLOCK_END) + r"\n?", re.S)


def blank_macro_block(text: str, clean: str) -> str:
    """`clean` with loom's macro block blanked as a comment is: its definitions of `\\nest` and `\\uses` are loom's, not the document's inclusions or dependencies."""
    for m in MACRO_BLOCK.finditer(text):
        clean = clean[: m.start()] + re.sub(r"[^\n]", " ", clean[m.start() : m.end()]) + clean[m.end() :]
    return clean


def read_source(root: Path, rel: str, overlay: str | None = None) -> SourceFile:
    """One file as the scanner sees it. `overlay` is the text of an unsaved editor buffer, used in place of what is on disk; it is decoded already, and CRLF is normalised here as for a file."""
    abspath = root / rel
    if overlay is None:
        text, enc = decode(abspath.read_bytes())
    else:
        text, enc = overlay, "utf-8"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    head = "\n".join(text.split("\n", 20)[:20])
    ignored = bool(IGNORE_RE.search(head))
    return SourceFile(
        path=rel,
        abspath=abspath,
        text=text,
        clean=blank_macro_block(text, blank_comments(text)),
        encoding=enc,
        ignored=ignored,
        line_starts=line_starts(text),
    )
