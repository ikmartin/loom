"""What a rendering's cache key is made of beyond its own text: loom's version and rendering code, and the numbering read from the compiled documents.

Shared by the fragment cache (`build._input_hash`), the review previews (`review_compare._render`) and the comparison cache (`compare._cached`), so a converter change or a renumbering reaches all three alike.
"""

from __future__ import annotations

import hashlib
import re
from functools import cache
from pathlib import Path

from loom.tex.aux import AuxNumber
from loom.version import __version__

#: The code a rendering's output depends on: three packages, and the reading of a quote that places its mark; editing anything else in a checkout re-renders nothing.
RENDERING = ("render", "scan", "tex", "records/selectors.py")


@cache
def code_hash() -> str:
    """A fingerprint of loom's rendering code, or '' for a released version, which its version string already identifies.

    In a checkout the version stays `0.1.0.dev0` across every edit, so a changed converter would otherwise hit the cache and republish the HTML it was meant to replace. Only `RENDERING`'s modules count, so editing the command line or the reference layer re-renders nothing. Read once per process, since a served quilt rebuilds on every keystroke.
    """
    if "dev" not in __version__:
        return ""
    package = Path(__file__).resolve().parent.parent
    h = hashlib.sha256()
    for sub in RENDERING:
        target = package / sub
        for path in sorted(target.rglob("*.py")) if target.is_dir() else [target]:
            h.update(path.relative_to(package).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()[:16]


def aux_bytes(numbers: dict[str, dict[str, AuxNumber]], cite_labels: dict[str, dict[str, str]]) -> bytes:
    """Every master's number table and citation labels as one byte stream, serialised once per build rather than once per node.

    Pages are left out: what loom renders itself never prints one (TeX's text that does is keyed by `aux_digest`), and a page break that moves would otherwise re-render every block.
    """
    parts: list[str] = []
    for m in sorted(numbers):
        for lab, num in sorted(numbers[m].items()):
            parts.append(f"{m}|{lab}|{num.number}")
    for m in sorted(cite_labels):
        for ck, lab in sorted(cite_labels[m].items()):
            parts.append(f"{m}|cite|{ck}|{lab}")
    return "".join(parts).encode()


#: A command that prints where something fell on the page: every command whose name holds `pageref` (`\pageref`, `\autopageref`, `\cpageref`, `\zpageref`, `\vpageref`, `\pagerefrange`, ...), varioref's `\vref` family, `\fullref` and the page count.
PAGEREF = re.compile(r"\\(?:[A-Za-z@]*pageref[A-Za-z@]*|[vV]ref(?:range)?|fullref|PreviousTotalPages)(?![A-Za-z@])")
#: The page group of a `\newlabel{x}{{number}{page}...}` line, hyperref's and cleveref's alike.
_NEWLABEL_PAGE = re.compile(r"^(\\newlabel\{[^\n]*?\}\{\{(?:[^{}\n]|\{[^{}\n]*\})*\})\{[^{}\n]*\}", re.M)
#: Lines of an aux that record only where things fell: contents lines, the last page, biblatex's page tracking.
_PAGE_ONLY = re.compile(r"^(?:\\@writefile|\\gdef\s*\\@abspage@last|\\abx@aux@page)[^\n]*\n?", re.M)
#: zref's page properties, which sit in a `\zref@newlabel` line beside the number a `\zref` prints.
_ZREF_PAGE = re.compile(r"\\(?:abs)?page\{[^{}\n]*\}")
#: What a preamble reads from the document's directory.
_READS = re.compile(r"\\(input|include|usepackage|RequirePackage|documentclass)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


@cache
def _aux_digests(path: str, mtime: int, size: int) -> tuple[str, str]:
    raw = Path(path).read_bytes()
    text = _PAGE_ONLY.sub("", raw.decode("utf-8", errors="replace"))
    text = _NEWLABEL_PAGE.sub(r"\1{}", text)
    text = re.sub(r"^\\zref@newlabel[^\n]*", lambda m: _ZREF_PAGE.sub("", m[0]), text, flags=re.M)
    return hashlib.sha256(raw).hexdigest(), hashlib.sha256(text.encode()).hexdigest()


def aux_digest(aux: Path | None, text: str, pages: bool = False) -> str:
    """What a TeX-made text's cache key takes from its document's aux, '' with none.

    The whole file's digest when `text` prints a page (`PAGEREF`) or `pages` says its preamble may (`preamble_prints_pages`); else the digest with the pages left out, so a page break that moves remakes nothing.
    """
    if aux is None or not aux.is_file():
        return ""
    st = aux.stat()
    whole, narrow = _aux_digests(str(aux), st.st_mtime_ns, st.st_size)
    return whole if pages or PAGEREF.search(text) else narrow


def preamble_prints_pages(root: Path, base: str, preamble: str) -> bool:
    """Whether a preamble, or a local file it reads (`\\input`, a style or class in the document's directory), names a `PAGEREF` command: a macro of its own may print a page wherever it is used."""
    from loom.scan.preamble import _local

    todo, seen = [preamble], set[str]()
    while todo:
        text = todo.pop()
        if PAGEREF.search(text):
            return True
        for m in _READS.finditer(text):
            exts = (".tex",) if m[1] in ("input", "include") else (".cls",) if m[1] == "documentclass" else (".sty",)
            for name in m[2].split(","):
                rel = _local(root, name, exts, base)
                if rel is not None and rel not in seen and len(seen) < 64:
                    seen.add(rel)
                    todo.append((root / rel).read_text(encoding="utf-8", errors="replace"))
    return False
