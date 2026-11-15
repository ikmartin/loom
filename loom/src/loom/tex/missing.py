"""What a document needs from TeX Live that loom's TeX lacks, found before a compile and after one, and fetched.

Before: the preamble names its class, packages, TikZ and PGF libraries and bibliography style, and one `kpsewhich` says which are absent (`preflight`). After: a failed run's log and its program's output name a missing file in one of a handful of forms (`from_log`). Either way a file is mapped to its package by an index of the repository's package database, read locally, so finding the package needs no network. Nothing here installs into the person's own TeX (`private.can_fetch`).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from loom.tex import private

#: Packages that cure a failure which names no file.
BITMAP_FONTS = ("metafont", "mfware")
SCALABLE_FONTS = ("cm-super",)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^! LaTeX Error: File `([^']+)' not found", re.M), "{}"),
    (re.compile(r"^! I can't find file `([^']+)'", re.M), "{}"),
    (re.compile(r"Package `?([\w-]+)'? not installed", re.M), "{}.sty"),
    (re.compile(r"I did not find the tikz library '([\w.-]+)'", re.M), "tikzlibrary{}.code.tex"),
    (re.compile(r"I did not find the pgf library '([\w.-]+)'", re.M), "pgflibrary{}.code.tex"),
    (re.compile(r"Font \S+=([\w-]+) at [^\n]*not loadable: Metric \(TFM\) file not found", re.M), "{}.tfm"),
    (re.compile(r"Running mktextfm ([\w-]+)", re.M), "{}.tfm"),
    (re.compile(r"PostScript header file ([\w.-]+) not found", re.M), "{}"),
    (re.compile(r"I couldn't open style file ([\w.-]+)", re.M), "{}"),
)
_BITMAP = re.compile(r"^!\s*pdfTeX error: [^\n]*Font \S+ at \d+ not found", re.M)
_SCALABLE = re.compile(r"auto expansion is only possible with scalable fonts", re.M)
_BIBER = re.compile(r"\bbiber\b[^\n]*(?:not found|No such file)|Could not find biber", re.M)


@dataclass
class Needs:
    """What a document lacks: TeX Live packages to install, and file names no package holds."""

    packages: set[str] = field(default_factory=set)
    unknown: set[str] = field(default_factory=set)

    def __bool__(self) -> bool:
        return bool(self.packages)


# ---- the index ---------------------------------------------------------------------------


def _database(root: Path | None = None) -> Path | None:
    """The repository's package database tlmgr keeps beside loom's TeX: the newest cached copy, which lists every package and not only the installed."""
    tlpkg = (root or private.tex_dir()) / "tlpkg"
    cached = sorted(tlpkg.glob("texlive.tlpdb.main.*"), key=lambda p: p.stat().st_mtime) if tlpkg.is_dir() else []
    return cached[-1] if cached else None


def parse_database(text: str) -> dict[str, str]:
    """Each file name in a TeX Live package database mapped to its package; a platform package's binaries map to the package it belongs to."""
    out: dict[str, str] = {}
    name = ""
    in_files = False
    for line in text.splitlines():
        if line.startswith("name "):
            name = line[5:].strip()
            head, _, arch = name.rpartition(".")
            if head and ("-" in arch or arch in ("windows", "win32")):
                name = head
            in_files = False
        elif line.startswith(("runfiles", "binfiles")):
            in_files = True
        elif line.startswith(" ") and in_files and name:
            base = line.strip().split(" ", 1)[0].rsplit("/", 1)[-1]
            if base not in out or (out[base].endswith("-dev") and not name.endswith("-dev")):
                out[base] = name
        elif not line.startswith(" "):
            in_files = False
    return out


_INDEX: tuple[Path, float, dict[str, str]] | None = None
#: The form of the kept index; a change to `parse_database` changes it.
_INDEX_FORM = 2


def index(root: Path | None = None) -> dict[str, str]:
    """File name to package, from the cached package database, kept as JSON beside it; empty when there is no database (loom's TeX not installed, or never online)."""
    global _INDEX
    db = _database(root)
    if db is None:
        return {}
    mtime = db.stat().st_mtime
    if _INDEX is not None and _INDEX[0] == db and _INDEX[1] == mtime:
        return _INDEX[2]
    kept = db.with_name("loom-files.json")
    data: dict[str, str] | None = None
    try:
        stored = json.loads(kept.read_text(encoding="utf-8"))
        if stored.get("mtime") == mtime and stored.get("db") == db.name and stored.get("v") == _INDEX_FORM:
            data = stored["files"]
    except (OSError, ValueError, KeyError, AttributeError):
        data = None
    if data is None:
        data = parse_database(db.read_text(encoding="utf-8", errors="replace"))
        try:
            kept.write_text(
                json.dumps({"v": _INDEX_FORM, "db": db.name, "mtime": mtime, "files": data}), encoding="utf-8"
            )
        except OSError:
            pass
    _INDEX = (db, mtime, data)
    return data


# ---- before a compile --------------------------------------------------------------------


_COMMENT = re.compile(r"(?<!\\)%.*$", re.M)
_CLASS = re.compile(r"\\documentclass\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_PACKAGE = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_LIBRARY = re.compile(r"\\use(tikz|pgf)library\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_BST = re.compile(r"\\bibliographystyle\s*\{([^}]+)\}")
_INPUT = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_BIBLATEX_BIBTEX = re.compile(r"\\usepackage\s*\[[^\]]*backend\s*=\s*bibtex")


def wanted(cwd: Path, tex_rel: str, *, limit: int = 40) -> set[str]:
    """The files of TeX Live that `tex_rel`'s preamble names: its class, packages, libraries, bibliography style, and biber for biblatex; local files it reads are followed, up to `limit` of them, and are not themselves wanted."""
    out: set[str] = set()
    seen: set[Path] = set()
    todo = [cwd / tex_rel]
    while todo and len(seen) < limit:
        f = todo.pop()
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        text = _COMMENT.sub("", f.read_text(encoding="utf-8", errors="replace"))
        head = text.split("\\begin{document}", 1)[0]
        names: list[str] = []
        names += [f"{c.strip()}.cls" for m in _CLASS.finditer(head) for c in m.group(1).split(",")]
        names += [f"{p.strip()}.sty" for m in _PACKAGE.finditer(head) for p in m.group(1).split(",") if p.strip()]
        names += [
            f"{kind}library{lib.strip()}.code.tex"
            for m in _LIBRARY.finditer(head)
            for kind, lib in ((m.group(1), x) for x in m.group(2).split(","))
            if lib.strip()
        ]
        names += [f"{b.strip()}.bst" for m in _BST.finditer(text) for b in m.group(1).split(",")]
        if "biblatex.sty" in names and not _BIBLATEX_BIBTEX.search(head):
            names.append("biber")
        for name in names:
            local = cwd / name if name != "biber" else None
            if local is not None and local.is_file():
                todo.append(local)
            else:
                out.add(name)
        for m in _INPUT.finditer(text):
            rel = m.group(1).strip()
            for cand in (cwd / rel, cwd / f"{rel}.tex"):
                if cand.is_file():
                    todo.append(cand)
                    break
    return out


def absent(names: set[str], cwd: Path) -> set[str]:
    """The names in `names` that neither `cwd` nor the TeX in use has, asked of one `kpsewhich`; biber is a program, looked up on the path."""
    import shutil

    files = sorted(n for n in names if n != "biber" and not (cwd / n).is_file())
    out = {n for n in names if n == "biber" and shutil.which("biber") is None}
    if not files:
        return out
    exe = shutil.which("kpsewhich")
    if exe is None:
        return out | set(files)
    try:
        found = subprocess.run([exe, *files], cwd=cwd, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return out
    have = {Path(line.strip()).name for line in found.splitlines() if line.strip()}
    return out | {n for n in files if n not in have}


def packages_for(names: set[str], files: dict[str, str] | None = None) -> Needs:
    """The packages that hold `names`, by the index; a name no package holds is the document's own, or a typo."""
    files = index() if files is None else files
    needs = Needs()
    for n in names:
        pkg = files.get(n) or (files.get(f"{n}.tex") if "." not in n else None)
        if pkg is None and n.startswith("tikzlibrary"):
            pkg = files.get("pgf" + n.removeprefix("tikz"))
        if pkg:
            needs.packages.add(pkg)
        else:
            needs.unknown.add(n)
    return needs


def preflight(cwd: Path, tex_rel: str) -> Needs:
    """What `tex_rel` will lack, before it is compiled: the preamble read, the absent asked of TeX, the packages found in the index.

    Parameters
    ----------
    cwd : Path
        The directory the document compiles from.
    tex_rel : str
        The document, relative to `cwd`.

    Returns
    -------
    Needs
    """
    return packages_for(absent(wanted(cwd, tex_rel), cwd))


# ---- after a compile ---------------------------------------------------------------------


def from_log(*texts: str, files: dict[str, str] | None = None) -> Needs:
    """What a failed run lacked, read from its log and its programs' output.

    Parameters
    ----------
    *texts : str
        The log, latexmk's or make4ht's output, in any order.
    files : dict, optional
        The index; default `index()`.

    Returns
    -------
    Needs
        Packages for every missing file the index knows, and the cure for a missing font, which names no file.
    """
    text = "\n".join(t for t in texts if t)
    names: set[str] = set()
    for pattern, form in _PATTERNS:
        names |= {form.format(m.group(1)) for m in pattern.finditer(text)}
    needs = packages_for(names, files)
    if _BITMAP.search(text):
        needs.packages.update(BITMAP_FONTS)
    if _SCALABLE.search(text):
        needs.packages.update(SCALABLE_FONTS)
    if _BIBER.search(text):
        needs.packages.add("biber")
    return needs


# ---- fetching ---------------------------------------------------------------------------


@dataclass
class Round:
    """What loom fetched for one document over its compile's rounds, and what it still needs."""

    fetched: list[str] = field(default_factory=list)
    needed: list[str] = field(default_factory=list)
    reason: str = ""
    tried: set[str] = field(default_factory=set)

    def fetch(self, needs: Needs) -> bool:
        """Install what `needs` names and was not tried before; whether anything new was installed."""
        new = sorted(needs.packages - self.tried)
        if not new:
            return False
        self.tried.update(new)
        got = private.install_packages(new)
        self.fetched += got.installed
        self.needed = sorted(set(self.needed) - set(got.installed) | set(got.failed))
        if got.failed:
            self.reason = got.reason
        return bool(got.installed)

    @property
    def note(self) -> str:
        """One line for the person: what was fetched, and what is still needed and why."""
        parts = []
        if self.fetched:
            parts.append(f"fetched {', '.join(self.fetched)}")
        if self.needed:
            parts.append(f"needs {', '.join(self.needed)}" + (f" ({self.reason})" if self.reason else ""))
        return "; ".join(parts)


#: Rounds a compile may take fetching what its log names, after the preflight.
ROUNDS = 12
