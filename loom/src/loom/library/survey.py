"""What a TeX source holds, read once for each source and kept by the source's hash and the work's stored PDF's (`docs/specs/library-views.md` §3.2, "The survey"): its sections, its results with their proofs, every label it defines, and its bibliography's files.

Made in two steps, when something asks for it and never by a build or the list of works. `read` parses the source with the scanner's own parsers and reads each heading's and result's number from its counters as `library.counters` emulates them (`emulated`), which a work's outline shows. `complete` compiles a copy of the source with a mark inside each heading, result and proof, with no command started for it (`tex.runner.FOREIGN`). Nothing that compile says is kept on its own word, since a source nobody at loom wrote can read any file the person can into what it prints: its numbers and pages are hints to look with (`confirm`). Where the work holds a PDF, the stored document governs: a printed number is the one it heads the statement's words with, and a page where it shows them; with no PDF, a number is kept only where it is loom's own reading and the compile agrees, and no page. What nothing confirms is left out, and named. Only regular files inside the source's folder are read, never through a link out of it, and the stored source is never changed.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loom import locks
from loom.library.counters import Numbering, plain
from loom.paths import LIBRARY_SURVEYS, SURVEY_LOCK, SURVEY_RUN
from loom.reshape.importer import closure_of
from loom.scan.directives import parse_directives
from loom.scan.envtree import FileEnvs, labels_in, scan_environments
from loom.scan.expand import expand_master
from loom.scan.model import Env, SourceFile, Taxon
from loom.scan.preamble import build_closure, document_start
from loom.scan.sections import SectionUnit, find_sections
from loom.scan.source import read_source
from loom.scan.tokenize import read_args
from loom.tex.aux import AuxNumber, parse_aux
from loom.tex.runner import compile_tex, normalise_engine, stage_sources

#: The survey's own format; a kept survey of another is read again.
VERSION = 3
#: The longest one pass of a source's compile may run, in seconds.
TIMEOUT = 300
#: How long a compile waits for another quilt's survey compile to end before it is refused.
QUEUE = 4 * TIMEOUT
#: A printed number as a counter renders one: arabic numerals with at most a letter after, roman numerals, or a single letter, joined by dots or hyphens, perhaps in parentheses, sixteen characters at most; anything else TeX wrote in its place is no number.
_PART = r"(?:\d{1,6}[a-z]?|[ivxlcdm]{1,8}|[IVXLCDM]{1,8}|[A-Za-z])"
SHAPED = re.compile(rf"(?=.{{1,16}}$)\(?{_PART}(?:[.\-]{_PART})*\)?")
#: The labels the compile's marks write, never one a source's own: `s`, `i` or `p` and the place of the heading, result or proof.
MARK = "loom-survey-"
#: What a marked copy's preamble gains: the mark, a `\label` that also writes the PDF's own count of the page it falls on.
MARKER = r"""\makeatletter
\providecommand\loomSurveySheet[2]{}
\newcommand\loomSurveyMark[1]{\label{#1}\protected@write\@auxout{}{\string\loomSurveySheet{#1}{\ifdefined\ReadonlyShipoutCounter\the\numexpr\ReadonlyShipoutCounter+1\relax\else 0\fi}}}
\makeatother
"""
_SHEET = re.compile(r"\\loomSurveySheet\{([^{}]*)\}\{(\d+)\}")
#: A number that is another label's, as a restated result prints its first statement's (`\renewcommand{\thethm}{\ref{thm:main}}`).
_REFERS = re.compile(r"\\ref\s*\*?\s*\{([^{}]*)\}")
#: The files of a source the scanner reads.
TEXT = (".tex", ".sty", ".cls", ".ltx", ".def", ".clo")
#: The taxa loom writes where a source's name for a result is one of them (`docs/specs/nodes.md` §5); any other is `other`.
TAXA = (
    "theorem",
    "proposition",
    "lemma",
    "corollary",
    "definition",
    "example",
    "remark",
    "conjecture",
    "convention",
    "construction",
)
#: An environment's short name read as the taxon it abbreviates, for a result whose printed name is none of `TAXA`.
SHORT = {
    "thm": "theorem",
    "lem": "lemma",
    "prop": "proposition",
    "cor": "corollary",
    "defn": "definition",
    "def": "definition",
    "dfn": "definition",
    "rem": "remark",
    "rmk": "remark",
    "ex": "example",
    "exa": "example",
    "exmp": "example",
    "conj": "conjecture",
    "conv": "convention",
    "constr": "construction",
}
#: The environments whose `\label` is an equation's.
DISPLAYS = frozenset(
    {
        "equation",
        "align",
        "gather",
        "multline",
        "flalign",
        "alignat",
        "eqnarray",
        "xalignat",
        "xxalignat",
        "subequations",
    }
)
#: The counters of the levels of `enumerate`.
ITEMS = ("enumi", "enumii", "enumiii", "enumiv")
#: `\setcounter` and `\addtocounter` with a literal integer; a value the source computes or reads moves nothing loom reads.
_SETCOUNTER = re.compile(r"\\(set|addto)counter\s*\{\s*([A-Za-z@]+)\s*\}\s*\{\s*(-?\d{1,6})\s*\}")
#: `\numberwithin[\style]{c}{p}` (amsmath), and the kernel's `\counterwithin` and `\counterwithout`, starred or not.
_WITHIN = re.compile(
    r"\\(numberwithin|counterwithin|counterwithout)\s*(\*?)\s*(?:\[\s*\\(arabic|roman|Roman|alph|Alph)\s*\]\s*)?"
    r"\{\s*([A-Za-z@]+)\s*\}\s*\{\s*([A-Za-z@]+)\s*\}"
)
#: How a counter prints, redefined: `\renewcommand{\thethm}{...}`, `\renewcommand*\thethm{...}`, `\def\thethm{...}`.
_THE = re.compile(
    r"\\(?:(?:re|provide)?newcommand\s*\*?\s*(?:\{\s*\\the([A-Za-z@]+)\s*\}|\\the([A-Za-z@]+))|def\s*\\the([A-Za-z@]+))(?![A-Za-z@])"
)
#: What opens and closes a TeX group, an escaped brace first so it counts as neither.
_GROUPING = re.compile(
    r"\\[{}]|\\(begingroup|bgroup)(?![A-Za-z@])|\\(endgroup|egroup)(?![A-Za-z@])"
    r"|\\begin\s*\{[^{}]*\}|\\end\s*\{[^{}]*\}|([{}])"
)
_CLASS = re.compile(r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{\s*([A-Za-z0-9@-]+)\s*\}")
#: The classes that number sections within chapters.
CHAPTERED = frozenset({"book", "report", "memoir", "amsbook", "scrbook", "scrreprt"})
#: The classes whose `secnumdepth` is 2, subsubsections unnumbered; every other is taken as 3, as article's and amsart's.
SHALLOW = frozenset({"book", "report", "memoir", "scrbook", "scrreprt"})
_APPENDIX = re.compile(r"\\appendix(?![A-Za-z@])")
_BIBLIOGRAPHY = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}")


@dataclass
class Section:
    """A heading of the source: `section` its id in the survey (`s1`, `s2`, … in source order), `command` the sectioning command, `emulated` loom's own reading of its number, `order` its place among the source's headings and results, and `number` and `page` only as confirmed (`confirm`, `place`)."""

    section: str
    command: str
    emulated: str | None
    title: str
    level: int
    label: str | None = None
    file: str = ""
    heading_end: int = 0
    opening: str | None = None
    number: str | None = None
    page: int | None = None
    order: int = 0


@dataclass
class Proof:
    """A proof the source attaches to a result: where it stands in its file, and its page in the work's stored PDF once found there."""

    file: str
    start: int
    end: int
    body_start: int
    body_end: int
    opening: str | None = None
    page: int | None = None


@dataclass
class Item:
    """A result of the source, digested or not (`library-views.md` §3.2's `item`).

    `item` is its own label, else `i` and its place among the source's results. `name` is the word the source prints for it ("Lemma") and `taxon` the node's (`nodes.md` §5). `emulated` is loom's own reading of its number, from the source's counters; `number` is the number it prints, only once confirmed, and `page` its page in the work's stored PDF, only once found there (`confirm`, `place`). `order` is its place among the source's headings and results. Offsets are in `file`, the source's own text.
    """

    item: str
    env: str
    taxon: str
    name: str
    numbered: bool
    emulated: str | None
    title: str | None
    label: str | None
    labels: list[str]
    section: str | None
    file: str
    start: int
    end: int
    body_start: int
    body_end: int
    opening: str | None = None
    number: str | None = None
    page: int | None = None
    proofs: list[Proof] = field(default_factory=list)
    order: int = 0


@dataclass
class Label:
    """Every `\\label` of the source: whose text holds it (`owner`, an item; `proof`, which of its proofs), whether it is that item's own, `kind`, the counter it numbers as (`section`, `equation`, `enumi`, `figure`, a result's own, or `other`), and its number and page only as confirmed (`confirm`)."""

    kind: str
    owner: str | None = None
    proof: int | None = None
    result: bool = False
    number: str | None = None
    page: int | None = None


@dataclass
class Survey:
    """What one source holds, confirmed against the work's stored PDF `pdf` where there is one.

    `state` is `reading` until its compile, then `ready`, or `failed` with `why` (`no-main`, `unreadable`, `no-document`, `incomplete`, and the compile's own). `unseen` names each heading, result and proof whose mark the compile never reached, by its id in the survey (`s3`, `lem:x`, `lem:x:proof0`); `unconfirmed` each heading and result that prints a number nothing confirmed, so it is left without one. `compiled` says whether a compile of the source, the person's own act, judged it; the unasked path never compiles (`confirmed`).
    """

    tex: str
    main: str
    pdf: str | None = None
    version: int = VERSION
    state: str = "reading"
    why: str | None = None
    engine: str = "pdflatex"
    sections: list[Section] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    labels: dict[str, Label] = field(default_factory=dict)
    bibliography: list[str] = field(default_factory=list)
    bbl: str | None = None
    unseen: list[str] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)
    compiled: bool = False

    def to_json(self) -> dict[str, Any]:
        """The survey as its kept file holds it."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Survey:
        """A survey from its kept file's JSON."""
        out = cls(**{k: v for k, v in data.items() if k not in ("sections", "items", "labels")})
        out.sections = [Section(**s) for s in data.get("sections", [])]
        out.items = [Item(**{**i, "proofs": [Proof(**p) for p in i.get("proofs", [])]}) for i in data.get("items", [])]
        out.labels = {k: Label(**v) for k, v in data.get("labels", {}).items()}
        return out

    def item(self, item: str) -> Item | None:
        """The item of that id, or None."""
        return next((i for i in self.items if i.item == item), None)


def taxon_of(taxon: Taxon) -> str:
    """The node's taxon for a result the source declares as `taxon`: the taxon its printed name ends in, else the one its environment's name abbreviates, else `other`."""
    words = taxon.name.lower().split()
    if words and words[-1] in TAXA:
        return words[-1]
    return SHORT.get(taxon.env.lower().rstrip("*"), taxon.env.lower() if taxon.env.lower() in TAXA else "other")


def read(src: Path, main: str, tex: str) -> Survey:
    """Read a source's survey from its files, numbers emulated.

    Parameters
    ----------
    src : Path
        The source's folder, unpacked.
    main : str
        Its main file, relative to `src`.
    tex : str
        The source's hash, `sha256:` and 64 hexadecimal digits.

    Returns
    -------
    Survey
        `reading`, or `failed` with why: `not-regular` when the folder holds anything but folders and regular files with no other name (a link, a hard link, a FIFO, a device), judged before anything is read; `no-main`, `unreadable` or `no-document` when the main file is missing, unreadable or begins no document.
    """
    out = Survey(tex=tex, main=main)
    if not _plain_folder(src):
        out.state, out.why = "failed", "not-regular"
        return out
    if ".." in Path(main).parts or not _regular(src, main):
        out.state, out.why = "failed", "no-main"
        return out
    try:
        found, _outside = closure_of(src, src / main)
        files = {
            rel: read_source(src, rel) for rel, p in found.items() if p.suffix.lower() in TEXT and _regular(src, rel)
        }
        if main not in files:
            files[main] = read_source(src, main)
    except (OSError, UnicodeError):
        out.state, out.why = "failed", "unreadable"
        return out
    master = files[main]
    doc = document_start(master)
    if doc is None:
        out.state, out.why = "failed", "no-document"
        return out
    closure = build_closure(master, src, files, parse_directives(master), foreign=True, only_files=True)
    out.engine = normalise_engine(closure.engine)
    exp = expand_master(master, src, files)
    units = find_sections(exp, files)
    taxa = closure.taxa
    envs: dict[str, FileEnvs] = {}
    for rel in [main, *(f for f in exp.reached if f != main)]:
        if rel in files:
            envs[rel] = scan_environments(files[rel], set(taxa), doc if rel == main else 0)
    # a local style's settings stand before the document's own, as it is loaded in the preamble
    styles = [f.src.clean[f.start : f.end] for f in closure.fragments if f.file not in exp.reached]
    _walk(out, exp.text, units, envs, files, taxa, exp, styles)
    _label_all(out, units, envs, files, doc)
    _bibliography(out, src, main, files, exp.reached)
    return out


def _plain_folder(src: Path) -> bool:
    """Whether `src` and everything under it is a folder or a regular file with no other name, judged by `lstat` alone before anything is read: a link, a hard link, a FIFO, a device or a socket refuses the whole source, and none is followed or opened."""
    import stat

    try:
        if not stat.S_ISDIR(src.lstat().st_mode):
            return False
        for folder, folders, files in os.walk(src, followlinks=False):
            for name in (*folders, *files):
                st = (Path(folder) / name).lstat()
                if not (stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1)):
                    return False
    except OSError:
        return False
    return True


def _regular(src: Path, rel: str) -> bool:
    """Whether `rel` is a regular file inside the folder `src` once every link on its way is followed: the only files a survey reads.

    A link out of the folder, to a file or a folder, is not the source's; nor is a master that is one.
    """
    try:
        target = (src / rel).resolve()
        return target.is_file() and target.is_relative_to(src.resolve())
    except (OSError, RuntimeError):
        return False


def _walk(
    out: Survey,
    text: str,
    units: list[SectionUnit],
    envs: dict[str, FileEnvs],
    files: dict[str, SourceFile],
    taxa: dict[str, Taxon],
    exp: Any,
    styles: list[str],
) -> None:
    """The sections and results in the order they stand, each numbered by the emulated counters.

    Events at one place sort headings before results, as TeX steps them; a local style's settings (`styles`) come first; a result outside every reached file is not the document's.
    """
    events: list[tuple[int, int, str, Any]] = [
        (-1, 0, kind, what) for style in styles for _at, kind, what in _settings(style)
    ]
    events += [(u.exp_start, 0, "heading", u) for u in units]
    events += [(m.start(), 0, "appendix", None) for m in _APPENDIX.finditer(text)]
    events += [(at, 0, kind, what) for at, kind, what in _settings(text)]
    for rel, fe in envs.items():
        for env in fe.theorem_envs:
            at = exp.exp_offset(rel, env.start)
            if at is not None and env.name in taxa:
                events.append((at, 1, "result", (rel, env)))
    events.sort(key=lambda e: (e[0], e[1]))
    cls = m.group(1) if (m := _CLASS.search(text)) is not None else ""
    chapters = cls in CHAPTERED or any(u.name == "chapter" for u in units)
    numbering = Numbering(taxa, chapters=chapters, depth=2 if cls in SHALLOW else 3)
    places: list[tuple[int, int, str]] = []
    statements: dict[tuple[str, int], Item] = {}
    taken: set[str] = set()
    for at, _order, kind, payload in events:
        if kind == "appendix":
            numbering.mark_appendix()
        elif kind == "set":
            name, value, add = payload
            numbering.set_counter(name, value, add=add)
        elif kind == "within":
            counter, parent, style, reset, renumber = payload
            numbering.within(counter, parent, style=style, reset=reset, renumber=renumber)
        elif kind == "the":
            numbering.define(*payload)
        elif kind == "close":
            numbering.close(payload)
        elif kind == "heading":
            u: SectionUnit = payload
            sid = f"s{len(out.sections) + 1}"
            out.sections.append(
                Section(
                    section=sid,
                    command=u.name,
                    emulated=numbering.heading(u.name, u.starred),
                    title=u.title,
                    level=u.level,
                    label=u.labels[0] if u.labels else None,
                    file=u.file,
                    heading_end=u.heading_end,
                    opening=_opening(u.title, least=6),
                    order=len(out.sections) + len(out.items),
                )
            )
            if (read_as := out.sections[-1].emulated) is not None:
                numbering.labels.update(dict.fromkeys(u.labels, read_as))
            places.append((u.exp_start, u.exp_end, sid))
        else:
            rel, env = payload
            taxon = taxa[env.name]
            labels = [lab for lab, _ in labels_in(files[rel].clean, env.own_ranges())]
            own = labels[0] if labels else None
            place = f"i{len(out.items) + 1}"
            name = own if own is not None and own not in taken and not re.fullmatch(r"i\d+", own) else place
            taken.add(name)
            within = [p for p in places if p[0] <= at < p[1]]
            item = Item(
                item=name,
                env=env.name,
                taxon=taxon_of(taxon),
                name=taxon.name,
                numbered=taxon.numbered,
                emulated=numbering.theorem(taxon),
                title=env.optarg.strip() if env.optarg and env.optarg.strip() else None,
                label=own,
                labels=labels,
                section=within[-1][2] if within else None,
                file=rel,
                start=env.start,
                end=env.end,
                body_start=env.body_start,
                body_end=env.body_end,
                opening=_opening(files[rel].clean[env.body_start : env.body_end]),
                order=len(out.sections) + len(out.items),
            )
            if item.emulated is not None:
                numbering.labels.update(dict.fromkeys(labels, item.emulated))
            out.items.append(item)
            statements[(rel, env.start)] = item
    for rel, fe in envs.items():
        for proof_start in sorted(fe.attachments):
            att = fe.attachments[proof_start]
            owner = statements.get((rel, att.statement.start)) if att.statement is not None else None
            if owner is not None:
                p = att.proof
                opening = _opening(files[rel].clean[p.body_start : p.body_end])
                owner.proofs.append(Proof(rel, p.start, p.end, p.body_start, p.body_end, opening))


def _settings(text: str) -> list[tuple[int, str, Any]]:
    """The counter settings `text` writes literally, each at its offset: `set`, `within` and `the` events for `Numbering`."""
    out: list[tuple[int, str, Any]] = [
        (m.start(), "set", (m.group(2), int(m.group(3)), m.group(1) == "addto")) for m in _SETCOUNTER.finditer(text)
    ]
    for m in _WITHIN.finditer(text):
        command, starred, style, counter, parent = m.groups()
        out.append(
            (m.start(), "within", (counter, parent, style or "arabic", command != "counterwithout", not starred))
        )
    for m in _THE.finditer(text):
        (body,), _spans, after = read_args(text, m.end(), "m")
        if body is not None:
            counter = m.group(1) or m.group(2) or m.group(3)
            out.append((m.start(), "the", (counter, body)))
            # a definition holds until its group closes: `{\\renewcommand{\\thethm}{\\ref{x}} ...}` restates one result
            if (end := _group_end(text, after)) is not None:
                out.append((end, "close", counter))
    return sorted(out, key=lambda e: e[0])


def _group_end(text: str, at: int) -> int | None:
    """Where the group holding offset `at` closes: a brace, an environment's `\\end`, `\\endgroup`; None where it does not close in `text`."""
    depth = 0
    for m in _GROUPING.finditer(text, at):
        token = m.group(0)
        if token.startswith("\\") and len(token) == 2:
            continue
        if m.group(1) or token.startswith("\\begin") or m.group(3) == "{":
            depth += 1
        else:
            depth -= 1
            if depth < 0:
                return m.start()
    return None


def _innermost(roots: list[Env], at: int) -> list[Env]:
    """The environments holding offset `at`, outermost first."""
    out: list[Env] = []
    level = roots
    while True:
        here = next((e for e in level if e.start <= at < e.end), None)
        if here is None:
            return out
        out.append(here)
        level = here.children


def _kind(chain: list[Env]) -> str:
    """The counter a `\\label` inside these environments numbers as."""
    for env in reversed(chain):
        name = env.name.rstrip("*")
        if name in DISPLAYS:
            return "equation"
        if name == "enumerate":
            depth = sum(1 for e in chain if e.name == "enumerate")
            return ITEMS[min(depth, len(ITEMS)) - 1]
        if name in ("figure", "table"):
            return name
    return "other"


def _label_all(
    out: Survey, units: list[SectionUnit], envs: dict[str, FileEnvs], files: dict[str, SourceFile], doc: int
) -> None:
    """Every `\\label` of the reached files, by whose text holds it and what it numbers.

    A label inside a result or one of its proofs is that result's: its own when it stands in the result's own text and is first there, else an anchor. A heading's label is its section's; anything else is classed by the environments around it.
    """
    headings = {(u.file, lab): u.name for u in units for lab in u.labels}
    by_file: dict[str, list[Item]] = {}
    for item in out.items:
        by_file.setdefault(item.file, []).append(item)
    for rel, fe in envs.items():
        clean = files[rel].clean
        lo = doc if rel == out.main else 0
        for lab, at in labels_in(clean, [(lo, len(clean))]):
            if lab in out.labels:
                continue
            chain = _innermost(fe.roots, at)
            owner = next((i for i in by_file.get(rel, []) if i.start <= at < i.end), None)
            proof = None
            if owner is None:
                for item in by_file.get(rel, []):
                    proof = next(
                        (k for k, p in enumerate(item.proofs) if p.file == rel and p.start <= at < p.end), None
                    )
                    if proof is not None:
                        owner = item
                        break
            if owner is not None and proof is None and lab in owner.labels:
                out.labels[lab] = Label(kind=owner.env, owner=owner.item, result=True)
            elif owner is not None:
                out.labels[lab] = Label(kind=_kind(chain), owner=owner.item, proof=proof)
            elif (rel, lab) in headings:
                out.labels[lab] = Label(kind=headings[(rel, lab)])
            else:
                out.labels[lab] = Label(kind=_kind(chain))


def _bibliography(out: Survey, src: Path, main: str, files: dict[str, SourceFile], reached: dict[str, int]) -> None:
    """The `.bib` files the source names and holds, and its `.bbl` where it ships one."""
    base = Path(main).parent
    for rel in [main, *(f for f in reached if f != main)]:
        if rel not in files:
            continue
        for m in _BIBLIOGRAPHY.finditer(files[rel].clean):
            for name in m.group(1).split(","):
                name = name.strip()
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    continue
                path = (base / (name if name.endswith(".bib") else f"{name}.bib")).as_posix()
                if _regular(src, path) and path not in out.bibliography:
                    out.bibliography.append(path)
    bbl = Path(main).with_suffix(".bbl").as_posix()
    out.bbl = bbl if _regular(src, bbl) else None


def path_of(root: Path, tex: str, pdf: str | None = None) -> Path:
    """Where the survey of the source `tex`, confirmed against the stored PDF `pdf` or none, is kept."""
    name = tex.removeprefix("sha256:") + ("-" + pdf.removeprefix("sha256:") if pdf else "")
    return root / LIBRARY_SURVEYS / f"{name}.json"


def kept(root: Path, tex: str, pdf: str | None = None) -> Survey | None:
    """The survey kept for the source `tex` and the stored PDF `pdf`, or None when there is none of this version."""
    try:
        data = json.loads(path_of(root, tex, pdf).read_text(encoding="utf-8"))
        return Survey.from_json(data) if data.get("version") == VERSION else None
    except (OSError, ValueError, TypeError):
        return None


def keep(root: Path, survey: Survey) -> None:
    """Write a survey to its file whole: a reader sees the last one or this one, never part of it."""
    path = path_of(root, survey.tex, survey.pdf)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(survey.to_json(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def survey(root: Path, tex: str, src: Path, main: str, pdf: str | None = None) -> Survey:
    """A source's survey: the one kept for it, else read now and kept.

    Parameters
    ----------
    root : Path
        The quilt.
    tex : str
        The source's hash.
    src : Path
        The source's folder, unpacked.
    main : str
        Its main file, relative to `src`.
    pdf : str, optional
        The hash of the work's stored PDF, which its numbers and pages are confirmed against.

    Returns
    -------
    Survey
        As kept, or `reading` when read now (see `read`).
    """
    found = kept(root, tex, pdf)
    if found is not None:
        return found
    out = read(src, main, tex)
    out.pdf = pdf
    keep(root, out)
    return out


def shaped(value: str | None) -> str | None:
    """`value` when it is shaped as a counter renders a number (`SHAPED`), else None: a word of the person's read in by a source is not."""
    if value is None:
        return None
    value = value.strip()
    return value if SHAPED.fullmatch(value) else None


def marked(src: Path, s: Survey, dest: Path) -> Path:
    """A copy of the source in `dest` with a mark after each heading and at the start of each result and proof, and the mark's definition before `\\begin{document}`; the copy's root.

    Marks are named by place, `s3`, `i12`, `p12-0`, so a source's own labels are untouched. Each file is written in the encoding it was read in; `src` is never written.
    """
    root = stage_sources(src, dest, regular_only=True)
    at: dict[str, list[tuple[int, str]]] = {}
    for k, sec in enumerate(s.sections):
        if sec.file:
            at.setdefault(sec.file, []).append((sec.heading_end, f"\\loomSurveyMark{{{MARK}s{k}}}"))
    for k, item in enumerate(s.items):
        at.setdefault(item.file, []).append((item.body_start, f"\\loomSurveyMark{{{MARK}i{k}}}"))
        for j, proof in enumerate(item.proofs):
            at.setdefault(proof.file, []).append((proof.body_start, f"\\loomSurveyMark{{{MARK}p{k}-{j}}}"))
    master = read_source(src, s.main)
    doc = document_start(master)
    if doc is not None:
        at.setdefault(s.main, []).append((doc, MARKER))
    for rel, inserts in at.items():
        sf = master if rel == s.main else read_source(src, rel)
        text = sf.text
        for offset, what in sorted(inserts, reverse=True):
            text = text[:offset] + what + text[offset:]
        (root / rel).write_bytes(text.encode(sf.encoding, errors="replace"))
    return root


def _hint(number: str, found: dict[str, AuxNumber]) -> str | None:
    """What the compile says a mark or label printed, shaped as a number, or the number of the label it is a `\\ref` of, followed once; a hint to look with, never kept on its own word."""
    if (m := _REFERS.fullmatch(number.strip())) is not None:
        got = found.get(re.sub(r"\s+", " ", m.group(1)).strip())
        return shaped(plain(got.number)) if got is not None else None
    return shaped(plain(number))


def _opening(text: str, *, least: int = 12) -> str | None:
    """The words a statement, a proof or a heading opens with, before its first formula or environment, as `refs.search` compares page text; None when there are fewer than `least` letters to find it by."""
    from loom.refs.search import _loose

    text = re.sub(r"\\label\s*\{[^{}]*\}", " ", text)
    head = re.split(r"\$|\\\[|\\\(|\\begin\s*\{", text, maxsplit=1)[0]
    head = re.sub(r"\\[A-Za-z@]+\*?|[{}~]", " ", head)
    words = _loose(" ".join(head.split()[:10]))
    return words if len(words) >= least else None


#: A number at the start of a heading's or result's own line in the stored PDF's text: `SHAPED`'s parts joined by dots or hyphens, never stopped short of a longer one.
_LINE_NUMBER = rf"\(?{_PART}(?:[.\-]{_PART})*\)?(?![.\-]?\w)"
#: How a heading's line opens: its number, after a word naming its kind where the class prints one.
_HEADING = re.compile(rf"(?:(?:appendix|chapter|section)\s+)?(?P<n>{_LINE_NUMBER})\.?(?:\s+(?P<rest>\S.*))?", re.I)
#: What follows a title on a contents page's entry, compared with spaces dropped: the page number, perhaps after dot leaders.
_CONTENTS = re.compile(r"\.*\d{1,4}")
#: The words a heading's line may open with before its number.
_HEADING_WORDS = ("appendix", "chapter", "section")


class Pages:
    """A stored PDF's text, a page at a time and a line at a time, as `pdftotext` writes it: where a heading's or result's printed number is read, only at the start of its own line (`place`), and where a proof's opening words give its page, compared as `refs.search` compares quotations.

    `lines` holds every line in order with its page, each normalised on its own; `contents` the lines of a contents page, where no heading is read; `texts` the pages with spaces and hyphens dropped.
    """

    def __init__(self, texts: list[str]) -> None:
        from loom.refs.search import _loose, normalize

        self.texts = [_loose(t) for t in texts]
        self.lines = [(k + 1, normalize(line).strip()) for k, t in enumerate(texts) for line in t.split("\n")]
        self._by_word: dict[str, list[int]] = {}
        self._numbered: list[int] = []
        number = re.compile(_LINE_NUMBER)
        for k, (_page, line) in enumerate(self.lines):
            word = line.split(" ", 1)[0] if line else ""
            self._by_word.setdefault(word.lower(), []).append(k)
            if number.fullmatch(word.rstrip(".")):
                self._numbered.append(k)
        self.contents = self._contents()

    def _contents(self) -> range:
        """The lines of a contents page: from its "Contents" line to where its first entry stands again, as the heading it lists; empty where there is none."""
        from loom.refs.search import _loose

        # an entry and its heading compared without dots, spaces or the entry's page number
        lines = [re.sub(r"\d{1,4}$", "", _loose(line).replace(".", "").lower()) for _p, line in self.lines]
        start = next((k for k, line in enumerate(lines) if line in ("contents", "tableofcontents")), None)
        if start is None:
            return range(0)
        first = next((k for k in range(start + 1, len(lines)) if lines[k]), None)
        again = next((k for k in range(first + 1, len(lines)) if lines[k] == lines[first]), None) if first else None
        return range(start, again) if again is not None else range(0)

    @classmethod
    def of(cls, pdf: Path | None) -> Pages | None:
        """The text of every page of `pdf`, read by poppler's `pdftotext` at once; None without a PDF or poppler, or a PDF it cannot read."""
        import shutil
        import subprocess

        exe = shutil.which("pdftotext")
        if pdf is None or exe is None or not pdf.is_file():
            return None
        try:
            done = subprocess.run([exe, "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if done.returncode != 0:
            return None
        return cls(done.stdout.decode("utf-8", errors="replace").split("\f"))

    def after(self, at: int, word: str | None) -> list[int]:
        """The lines from `at` on that open with `word`, or with a number where `word` is None."""
        import bisect

        pool = self._numbered if word is None else self._by_word.get(word, [])
        return pool[bisect.bisect_left(pool, at) :]

    def following(self, k: int) -> str:
        """The next line after `k` that holds anything, within three."""
        return next((line for _p, line in self.lines[k + 1 : k + 4] if line), "")

    def opens(self, k: int) -> bool:
        """Whether line `k` opens a block: the first of its page, or after an empty line."""
        return k == 0 or not self.lines[k - 1][1] or self.lines[k - 1][0] != self.lines[k][0]

    def find(self, words: str, near: int | None) -> list[tuple[int, int]]:
        """Each place `words` stand, as (page from 1, offset in its compared text), those on the page `near` and its neighbours first, then the rest by page."""
        out = [(k + 1, m.start()) for k, t in enumerate(self.texts) for m in re.finditer(re.escape(words), t)]
        return sorted(out, key=lambda at: (abs(at[0] - near) if near else 0, at[0], at[1]))

    def shows(self, page: int, text: str) -> bool:
        """Whether `page` shows `text`, compared as quotations are."""
        from loom.refs.search import _loose

        return 0 < page <= len(self.texts) and _loose(text) in self.texts[page - 1]


def place(s: Survey, pages: Pages, hints: dict[str, str] | None = None) -> dict[str, tuple[str, int]]:
    """Each numbered heading's and result's printed number and page, read in the work's stored PDF.

    The marks are looked for in the source's order, each only after the line where the last was found. A number is read only at the start of the mark's own line: a result's line opening with its printed name and a number (`Lemma 2.2.`, `Lemma 2.2 (Title).`) or the number and then the name (`2.2 Lemma.`); a heading's opening with its number and title (`12 Title`, `A. Proofs`), or the number alone on a line that opens a block, with no full stop, and the title next (`Chapter 3`, and article's headings as `pdftotext` writes them). The number is taken where it is loom's reading of the mark or the compile's `hints` of it, or where the mark's own words witness the line: a result's opening words in the rest of its line and the four after, a heading's title beginning its line or the next. So a token that ends the line before a mark is never read as its number.

    Parameters
    ----------
    s : Survey
        The source's survey.
    pages : Pages
        The work's stored PDF.
    hints : dict of str to str, optional
        What a compile of the source, the person's own act, says each mark prints, by its id.

    Returns
    -------
    dict of str to (str, int)
        Each mark found, by its id: the number the PDF prints there and its page.
    """
    hints = hints or {}
    at = 0
    out: dict[str, tuple[str, int]] = {}
    marks: list[Section | Item] = [*s.sections, *s.items]
    for mark in sorted(marks, key=lambda m: m.order):
        if isinstance(mark, Section):
            got = _heading(pages, at, mark, hints.get(mark.section)) if mark.emulated is not None else None
            key = mark.section
        else:
            got = _result(pages, at, mark, hints.get(mark.item)) if mark.numbered else None
            key = mark.item
        if got is not None:
            number, page, at = got
            out[key] = (number, page)
    return out


def _result(pages: Pages, at: int, item: Item, hint: str | None) -> tuple[str, int, int] | None:
    """The first line after `at` that is `item`'s heading: its number, its page, and the line after it."""
    import heapq

    from loom.refs.search import normalize

    words = normalize(item.name).split()
    if not words:
        return None
    name = r"\s*".join(re.escape(w) for w in words)
    forms = (
        re.compile(rf"(?:{name})\s+(?P<n>{_LINE_NUMBER})(?P<rest>\s*(?:[.:(].*)?)", re.I),
        re.compile(rf"(?P<n>{_LINE_NUMBER})\.?\s+(?:{name})(?P<rest>\s*(?:[.:(].*)?)", re.I),
    )
    wanted = {item.emulated, hint} - {None}
    for k in heapq.merge(pages.after(at, words[0].lower()), pages.after(at, None)):
        page, line = pages.lines[k]
        m = forms[0].fullmatch(line) or forms[1].fullmatch(line)
        number = shaped(m.group("n")) if m is not None else None
        if m is not None and number is not None and (number in wanted or _witness(pages, k, item.opening, m["rest"])):
            return number, page, k + 1
    return None


def _heading(pages: Pages, at: int, sec: Section, hint: str | None) -> tuple[str, int, int] | None:
    """The first line after `at` that is `sec`'s heading: its number, its page, and the line after it."""
    import heapq

    from loom.refs.search import _loose

    whole = (_opening(sec.title, least=1) or "").lower()
    title = whole[:24]
    wanted = {sec.emulated, hint} - {None}
    for k in heapq.merge(pages.after(at, None), *(pages.after(at, w) for w in _HEADING_WORDS)):
        if k in pages.contents:
            continue
        page, line = pages.lines[k]
        m = _HEADING.fullmatch(line)
        number = shaped(m.group("n")) if m is not None else None
        if m is None or number is None:
            continue
        if m["rest"] and whole and _CONTENTS.fullmatch(_loose(m["rest"]).lower().removeprefix(whole)):
            # a contents page's entry: its title, then nothing but the page it stands on
            continue
        if m["rest"]:
            words = f"{m['rest']} {pages.following(k)}"
        elif line.endswith(".") or not pages.opens(k):
            # a number alone on a line is a heading only where it opens a block: a paragraph's last word never is
            continue
        else:
            words = pages.following(k)
        if _loose(words).lower().startswith(title) if title else number in wanted:
            return number, page, k + 1
    return None


def _witness(pages: Pages, k: int, opening: str | None, rest: str) -> bool:
    """Whether a result's opening words stand in the rest of line `k` and the four after it."""
    from loom.refs.search import _loose

    if not opening:
        return False
    near = _loose(" ".join([rest, *(line for _p, line in pages.lines[k + 1 : k + 5])])).lower()
    return opening.lower()[:24] in near


def _page_of(opening: str | None, near: int | None, pages: Pages) -> int | None:
    """The page where a proof's opening words stand in the stored PDF: the one page, or the one nearest the compile's `near` among several."""
    found = pages.find(opening, near) if opening is not None else []
    if not found:
        return None
    on = {p for p, _a in found}
    nearest = {p for p in on if near and abs(p - near) == abs(found[0][0] - near)}
    return found[0][0] if len(on) == 1 or len(nearest) == 1 else None


def _placed(out: Survey, pages: Pages, hints: dict[str, str], near: dict[str, int]) -> list[str]:
    """Number and page `out`'s headings and results by the stored PDF (`place`) and its proofs by their words; the numbered marks it leaves without a number, headings first."""
    got = place(out, pages, hints)
    left: list[str] = []
    for sec in out.sections:
        sec.number, sec.page = got.get(sec.section, (None, None))
        if sec.emulated is not None and sec.number is None:
            left.append(sec.section)
    for item in out.items:
        item.number, item.page = got.get(item.item, (None, None))
        for j, proof in enumerate(item.proofs):
            proof.page = _page_of(proof.opening, near.get(f"{item.item}:proof{j}"), pages)
    left += [item.item for item in out.items if item.numbered and item.number is None]
    return left


def _labels(out: Survey, found: dict[str, AuxNumber], pages: Pages | None) -> None:
    """Each label's number and page: its result's or its heading's where it is one's own; a display's or an item's inside a result, the compile's, only where the stored PDF numbers that result as loom reads it and shows the number in parentheses on its page."""
    by_item = {i.item: i for i in out.items}
    by_label = {sec.label: sec for sec in out.sections if sec.label}
    for name, label in out.labels.items():
        owner = by_item.get(label.owner) if label.owner else None
        if label.result and owner is not None:
            label.number, label.page = owner.number, owner.page
        elif name in by_label:
            label.number, label.page = by_label[name].number, by_label[name].page
        elif owner is not None:
            page = owner.page if label.proof is None else owner.proofs[label.proof].page
            got = found.get(name)
            said = _hint(got.number, found) if got is not None else None
            alike = owner.number is not None and owner.number == owner.emulated
            shown = (
                said is not None and page is not None and pages is not None and alike and pages.shows(page, f"({said})")
            )
            label.number, label.page = (said if shown else None), page
        else:
            label.number, label.page = None, None


def confirm(s: Survey, auxes: list[str], pages: Pages | None = None) -> Survey:
    """A copy of `s` judged by `auxes`, the `.aux` files of its marked copy's compile, the person's own act; its numbers and pages kept only as confirmed.

    Nothing a source's compile says is kept on its own word, since a source nobody at loom wrote can read the person's files into what it prints: the compile's numbers and pages are hints to look with. With the work's stored PDF (`pages`), the stored document governs: each heading's and result's number and page are the PDF's own, read at the start of its line (`place`), the compile's hint one way to tell it. Without one, a number is kept where it is loom's own reading of the source's counters and the compile says the same, and no page. Labels are numbered by `_labels`. What nothing confirms is left without, and each heading and result that prints a number nothing confirmed is named in `unconfirmed`. A mark the compile never reached, a result inside `\\iffalse`, is named in `unseen` and fails only itself: the survey is `ready` unless no mark at all was reached (`failed`, `incomplete`).
    """
    found: dict[str, AuxNumber] = {}
    sheets: dict[str, int] = {}
    for text in auxes:
        found.update(parse_aux(text))
        sheets.update({m.group(1): int(m.group(2)) for m in _SHEET.finditer(text)})
    marks: list[tuple[str, str]] = [(f"s{k}", sec.section) for k, sec in enumerate(s.sections)]
    for k, item in enumerate(s.items):
        marks.append((f"i{k}", item.item))
        marks += [(f"p{k}-{j}", f"{item.item}:proof{j}") for j in range(len(item.proofs))]
    out = Survey.from_json(s.to_json())
    out.compiled = True
    out.unseen = [name for mark, name in marks if MARK + mark not in found]
    if len(out.unseen) == len(marks) and marks:
        # not one mark reached: the compile never read the source's body
        out.state, out.why = "failed", "incomplete"
        return out
    hints = {name: _hint(found[MARK + mark].number, found) for mark, name in marks if MARK + mark in found}
    near = {name: sheets[MARK + mark] for mark, name in marks if sheets.get(MARK + mark)}
    if pages is not None:
        out.unconfirmed = _placed(out, pages, {k: v for k, v in hints.items() if v is not None}, near)
    else:
        for sec in out.sections:
            sec.number = sec.emulated if sec.emulated is not None and hints.get(sec.section) == sec.emulated else None
        for item in out.items:
            numbered = item.numbered and item.emulated is not None
            item.number = item.emulated if numbered and hints.get(item.item) == item.emulated else None
        out.unconfirmed = [x.section for x in out.sections if x.emulated is not None and x.number is None] + [
            i.item for i in out.items if i.numbered and i.number is None
        ]
    # a mark the compile never reached stands in no printed document (`\iffalse`): it is named in `unseen`, has no number, and prints none to be confirmed
    hidden = set(out.unseen)
    for sec in out.sections:
        if sec.section in hidden:
            sec.number, sec.page = None, None
    for item in out.items:
        if item.item in hidden:
            item.number, item.page = None, None
    out.unconfirmed = [name for name in out.unconfirmed if name not in hidden]
    _labels(out, found, pages)
    out.state, out.why = "ready", None
    return out


def compile_marks(
    src: Path, s: Survey, pdf: Path | None = None, *, scratch: Path | None = None, online: bool = True
) -> Survey:
    """Compile a marked copy of the source in a scratch folder, removed after, and keep of what it wrote only what is confirmed (`confirm`): the person's own act, never the unasked path.

    Parameters
    ----------
    src : Path
        The source's folder, unpacked.
    s : Survey
        Its survey as `read` made it.
    pdf : Path, optional
        The work's stored PDF, the one `s.pdf` names, which governs its numbers and pages; without one a number is kept only as loom's own reading the compile agrees with, and no page.
    scratch : Path, optional
        The folder the compile runs in, emptied before and removed after; default a temporary one.
    online : bool, default True
        Whether what the source's text names and loom's TeX lacks may be fetched.

    Returns
    -------
    Survey
        As `confirm` judges what TeX wrote, so a source whose figure is missing still reads `ready` when every mark is there; or `failed` when TeX wrote no `.aux`: `no-tex` without latexmk, `timeout` past `TIMEOUT`, `stopped`, else `compile`.
    """
    if s.state == "failed":
        return s
    with _scratch(scratch) as tmp:
        root = marked(src, s, tmp / "src")
        res = compile_tex(
            root, s.main, tmp / "out", s.engine, halt_on_error=False, timeout=TIMEOUT, foreign=True, online=online
        )
        auxes = [p.read_text(encoding="utf-8", errors="replace") for p in sorted((tmp / "out").rglob("*.aux"))]
    if res.aux is None or not auxes:
        out = Survey.from_json(s.to_json())
        out.state, out.compiled = "failed", True
        out.why = {127: "no-tex", 124: "timeout"}.get(res.returncode, "stopped" if res.stopped else "compile")
        return out
    return confirm(s, auxes, Pages.of(pdf))


@contextlib.contextmanager
def _scratch(at: Path | None) -> Iterator[Path]:
    """A folder for one compile: `at`, emptied first and removed after, or a temporary one."""
    if at is None:
        with tempfile.TemporaryDirectory(prefix="loom-survey-") as tmp:
            yield Path(tmp)
        return
    shutil.rmtree(at, ignore_errors=True)
    at.mkdir(parents=True)
    try:
        yield at
    finally:
        shutil.rmtree(at, ignore_errors=True)


def complete(
    root: Path,
    tex: str,
    src: Path,
    main: str,
    pdf: str | None = None,
    pdf_path: Path | None = None,
    *,
    online: bool = True,
) -> Survey:
    """A source's survey once compiled, the person's own act: the kept one when a compile already judged it, else compiled now and kept.

    One compile at a time in a quilt: each holds `SURVEY_LOCK`, decides again under it, and waits up to `QUEUE` seconds for another to end. It runs in `.loom/cache/library/survey/run/`, which it empties first, so what a compile killed part way left goes at the next.

    Parameters
    ----------
    root : Path
        The quilt.
    tex : str
        The source's hash.
    src : Path
        The source's folder, unpacked.
    main : str
        Its main file, relative to `src`.
    pdf : str, optional
        The hash of the work's stored PDF, which the survey is kept by and which governs its numbers.
    pdf_path : Path, optional
        That PDF on the disk.
    online : bool, default True
        Whether what the source's text names and loom's TeX lacks may be fetched.

    Returns
    -------
    Survey
        `ready` or `failed` (see `compile_marks`).

    See Also
    --------
    confirmed : the unasked path, which never compiles.
    """
    with locks.locked(root / SURVEY_LOCK, wait=QUEUE):
        kept_now = kept(root, tex, pdf)
        if kept_now is not None and kept_now.compiled:
            return kept_now
        s = survey(root, tex, src, main, pdf)
        if s.state == "failed":
            return s
        base = Survey.from_json({**s.to_json(), "state": "reading", "why": None, "unconfirmed": []})
        done = compile_marks(src, base, pdf_path if pdf else None, scratch=root / SURVEY_RUN, online=online)
        keep(root, done)
        return done


def confirmed(
    root: Path, tex: str, src: Path, main: str, pdf: str | None = None, pdf_path: Path | None = None
) -> Survey:
    """A source's survey as the unasked path has it: numbered and paged by the work's stored PDF alone, never compiled.

    With a PDF, each heading's and result's number and page are the PDF's own, read at the start of its line in the source's order (`place`), what it leaves named in `unconfirmed`; kept by both hashes. Without one, nothing is confirmed: the outline is loom's own reading, every numbered heading and result is named, and `why` is `no-pdf`. A PDF `pdftotext` cannot read leaves it `failed`, `pdf`.

    Parameters
    ----------
    root : Path
        The quilt.
    tex : str
        The source's hash.
    src : Path
        The source's folder, unpacked.
    main : str
        Its main file, relative to `src`.
    pdf : str, optional
        The hash of the work's stored PDF.
    pdf_path : Path, optional
        That PDF on the disk.

    Returns
    -------
    Survey
        `ready`, or `failed` with why.

    See Also
    --------
    complete : the person's own act, which compiles.
    """
    s = survey(root, tex, src, main, pdf)
    if s.state != "reading":
        return s
    out = Survey.from_json(s.to_json())
    if pdf is None:
        out.unconfirmed = [x.section for x in out.sections if x.emulated is not None] + [
            i.item for i in out.items if i.numbered
        ]
        out.state, out.why = "ready", "no-pdf"
        return out
    pages = Pages.of(pdf_path)
    if pages is None:
        out.state, out.why = "failed", "pdf"
    else:
        out.unconfirmed = _placed(out, pages, {}, {})
        _labels(out, {}, pages)
        out.state, out.why = "ready", None
    keep(root, out)
    return out
