"""What a TeX source holds, read once for each source and kept by the source's hash and the work's stored PDF's (`docs/specs/library-views.md` §3.2, "The survey"): its sections, its results with their proofs, every label it defines, and its bibliography's files.

Made in two steps, when something asks for it and never by a build or the list of works. `read` parses the source with the scanner's own parsers and reads each heading's and result's number from its counters as `library.counters` emulates them (`emulated`), which a work's outline shows. `complete` compiles a copy of the source with a mark inside each heading, result and proof, with no command started for it (`tex.runner.FOREIGN`). Nothing that compile says is kept on its own word, since a source nobody at loom wrote can read any file the person can into what it prints: its numbers and pages are hints to look with (`confirm`). Where the work holds a PDF, the stored document governs: a printed number is the one it heads the statement's words with, and a page where it shows them; with no PDF, a number is kept only where it is loom's own reading and the compile agrees, and no page. What nothing confirms is left out, and named. Only regular files inside the source's folder are read, never through a link out of it, and the stored source is never changed.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loom import locks
from loom.library.counters import Numbering, plain
from loom.paths import LIBRARY_SURVEYS, SURVEY_LOCK
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
VERSION = 2
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
    """A heading of the source: `section` its id in the survey (`s1`, `s2`, … in source order), `command` the sectioning command, `emulated` loom's own reading of its number, and `number` and `page` only as confirmed (`confirm`)."""

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

    `item` is its own label, else `i` and its place among the source's results. `name` is the word the source prints for it ("Lemma") and `taxon` the node's (`nodes.md` §5). `emulated` is loom's own reading of its number, from the source's counters; `number` is the number it prints, only once confirmed, and `page` its page in the work's stored PDF, only once found there (`confirm`). Offsets are in `file`, the source's own text.
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

    `state` is `reading` until its compile, then `ready`, or `failed` with `why` (`no-main`, `unreadable`, `no-document`, `incomplete`, and the compile's own). `unseen` names each heading, result and proof whose mark the compile never reached, by its id in the survey (`s3`, `lem:x`, `lem:x:proof0`); `unconfirmed` each heading and result that prints a number nothing confirmed, so it is left without one.
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
                )
            )
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
            )
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


#: A number as a counter prints it, in the stored PDF's text: `SHAPED`'s parts, joined by dots or hyphens.
_PRINTED = rf"\(?{_PART}(?:[.\-]{_PART})*\)?"
#: What may stand between a printed number and a statement's words: a title in parentheses, then a full stop or a colon.
_TITLE = r"(?:\s*\([^()]{0,120}\))?\s*[.:]?\s*$"


class Pages:
    """A stored PDF's text, a page at a time, compared as `refs.search` compares quotations: what a compile's word is checked against, since the compile cannot have written it.

    `texts` are the pages as quotations are compared, spaces and hyphens dropped; `flat` the same pages with their spaces, where a printed number is read, so `12` is never taken for the `2` it ends in; `at` maps each offset of the one into the other.
    """

    def __init__(self, texts: list[str]) -> None:
        from array import array

        from loom.refs.search import _LOOSE, normalize

        self.flat = [normalize(t) for t in texts]
        self.texts: list[str] = []
        self.at: list[array[int]] = []
        for flat in self.flat:
            keep = array("I", (k for k, c in enumerate(flat) if c not in _LOOSE))
            self.texts.append("".join(flat[k] for k in keep))
            self.at.append(keep)

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

    def find(self, words: str, near: int | None) -> list[tuple[int, int]]:
        """Each place `words` stand, as (page from 1, offset in its compared text), those on the page `near` and its neighbours first, then the rest by page."""
        out = [(k + 1, m.start()) for k, t in enumerate(self.texts) for m in re.finditer(re.escape(words), t)]
        return sorted(out, key=lambda at: (abs(at[0] - near) if near else 0, at[0], at[1]))

    def heading(self, page: int, at: int, name: str) -> str | None:
        """The number the PDF heads the words at `at` on `page` with, under `name` ("Lemma 11.2.", "Lemma 11.2 (Title).", "11.2 Lemma.", or a heading's "12 Title"); None where it prints none loom can read.

        A number that continues a longer one, a digit, a letter or a dot before it, is refused. Only a number shaped as a counter prints one is read (`shaped`).
        """
        from loom.refs.search import normalize

        flat, offsets = self.flat[page - 1], self.at[page - 1]
        end = offsets[at] if at < len(offsets) else len(flat)
        before = flat[max(0, end - 200) : end]
        word = r"\s*".join(re.escape(w) for w in normalize(name).split())
        forms = [rf"(?<![\w.\-])(?P<n>{_PRINTED})\.?{_TITLE}"]
        if word:
            forms = [
                rf"(?<!\w){word}\s*(?P<n>{_PRINTED}){_TITLE}",
                rf"(?<![\w.\-])(?P<n>{_PRINTED})\.?\s*{word}{_TITLE}",
            ]
        for form in forms:
            if (m := re.search(form, before, re.IGNORECASE if word else 0)) is not None:
                number = m.group("n")
                # a heading's lone lower-case letter or roman numeral is a word of the text before it more often than a number
                if not word and re.fullmatch(r"[a-z]+", number):
                    continue
                return shaped(number)
        return None

    def shows(self, page: int, text: str) -> bool:
        """Whether `page` shows `text`, compared as quotations are."""
        from loom.refs.search import _loose

        return 0 < page <= len(self.texts) and _loose(text) in self.texts[page - 1]


def _confirmed(
    emulated: str | None,
    hint: str | None,
    name: str,
    opening: str | None,
    near: int | None,
    pages: Pages | None,
    *,
    numbered: bool = True,
) -> tuple[str | None, int | None]:
    """A printed number and a page for one heading, result or proof, each only where something the compile could not have written confirms it.

    With a stored PDF, the stored document governs: the number is the one it heads the opening words with where it shows them, and none where it heads them with none loom can read or does not show them; loom's own reading never stands alone. Where the words stand at several places, a title that is another's prefix or a contents page, the place headed by loom's reading is the statement's; failing that, the number every place agrees on, and none where they disagree. Without one, the number is loom's own reading (`emulated`) where the compile's `hint` is that very reading. The page is where the PDF shows the opening words, the page nearest the compile's `near` among several; nothing of the compile's is kept for itself.
    """
    if pages is None:
        return (emulated if numbered and emulated is not None and hint == emulated else None), None
    found = pages.find(opening, near) if opening is not None else []
    printed = [
        (page, n) for page, at in (found if numbered else []) if (n := pages.heading(page, at, name)) is not None
    ]
    # words stand at several places when a title is another's prefix or a contents page repeats it
    for page, n in printed:
        if n == emulated:
            return n, page
    if printed and len({n for _p, n in printed}) == 1:
        return printed[0][1], printed[0][0]
    if not found:
        return None, None
    # the page nearest where the compile says it stands, when one page is nearest; several pages and no word from the compile is no page
    on = {p for p, _a in found}
    nearest = {p for p in on if near and abs(p - near) == abs(found[0][0] - near)}
    return None, (found[0][0] if len(on) == 1 or len(nearest) == 1 else None)


def confirm(s: Survey, auxes: list[str], pages: Pages | None = None) -> Survey:
    """A copy of `s` judged by `auxes`, the `.aux` files of its marked copy's compile, its numbers and pages kept only as confirmed.

    Nothing a source's compile says is kept on its own word, since a source nobody at loom wrote can read the person's files into what it prints: the compile's numbers and pages are hints to look with. With the work's stored PDF (`pages`), a heading's or result's number is the one the PDF heads its opening words with, and none where it shows them under no number loom can read or does not show them; without one, a number is kept where it is loom's own reading of the source's counters and the compile says the same. A page comes only from the stored PDF; a label's number is its result's or its heading's, or, for a display or an item inside a result, the compile's where the PDF numbers that result as loom reads it and shows the number in parentheses on its page. What nothing confirms is left without, and each heading and result that prints a number nothing confirmed is named in `unconfirmed`. The survey is `ready` when every mark loom added is there, else `failed`, `incomplete`, with `unseen` naming what fell short by its id in the survey.
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
    out.unseen = [name for mark, name in marks if MARK + mark not in found]
    if out.unseen:
        out.state, out.why = "failed", "incomplete"
        return out

    def hint(mark: str) -> tuple[str | None, int | None]:
        return _hint(found[MARK + mark].number, found), sheets.get(MARK + mark) or None

    unconfirmed: list[str] = []
    for k, sec in enumerate(out.sections):
        said, near = hint(f"s{k}")
        sec.number, sec.page = _confirmed(
            sec.emulated, said, "", sec.opening, near, pages, numbered=sec.emulated is not None
        )
        if sec.emulated is not None and sec.number is None:
            unconfirmed.append(sec.section)
    for k, item in enumerate(out.items):
        said, near = hint(f"i{k}")
        item.number, item.page = _confirmed(
            item.emulated, said, item.name, item.opening, near, pages, numbered=item.numbered
        )
        if item.numbered and item.number is None:
            unconfirmed.append(item.item)
        for j, proof in enumerate(item.proofs):
            _n, proof_near = hint(f"p{k}-{j}")
            _no, proof.page = _confirmed(None, None, "", proof.opening, proof_near, pages, numbered=False)
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
            # only where the PDF numbers the result as the source does, so a display's number is the PDF's too
            alike = owner.number is not None and owner.number == owner.emulated
            shown = (
                said is not None and page is not None and pages is not None and alike and pages.shows(page, f"({said})")
            )
            label.number, label.page = (said if shown else None), page
        else:
            label.number, label.page = None, None
    out.unconfirmed = unconfirmed
    out.state, out.why = "ready", None
    return out


def compile_marks(src: Path, s: Survey, pdf: Path | None = None) -> Survey:
    """Compile a marked copy of the source in a scratch folder, removed after, and keep of what it wrote only what is confirmed (`confirm`).

    Parameters
    ----------
    src : Path
        The source's folder, unpacked.
    s : Survey
        Its survey as `read` made it.
    pdf : Path, optional
        The work's stored PDF, the one `s.pdf` names, which its numbers and pages are confirmed against; without one a number is kept only as loom's own reading, and no page.

    Returns
    -------
    Survey
        As `confirm` judges what TeX wrote, so a source whose figure is missing still reads `ready` when every mark is there; or `failed` when TeX wrote no `.aux`: `no-tex` without latexmk, `timeout` past `TIMEOUT`, `stopped`, else `compile`.
    """
    if s.state == "failed":
        return s
    with tempfile.TemporaryDirectory(prefix="loom-survey-") as tmp:
        root = marked(src, s, Path(tmp) / "src")
        res = compile_tex(root, s.main, Path(tmp) / "out", s.engine, halt_on_error=False, timeout=TIMEOUT, foreign=True)
        auxes = [p.read_text(encoding="utf-8", errors="replace") for p in sorted((Path(tmp) / "out").rglob("*.aux"))]
    if res.aux is None or not auxes:
        out = Survey.from_json(s.to_json())
        out.state = "failed"
        out.why = {127: "no-tex", 124: "timeout"}.get(res.returncode, "stopped" if res.stopped else "compile")
        return out
    return confirm(s, auxes, Pages.of(pdf))


def complete(
    root: Path, tex: str, src: Path, main: str, pdf: str | None = None, pdf_path: Path | None = None
) -> Survey:
    """A source's survey once compiled: the kept one when it is `ready` or `failed`, else compiled now and kept.

    One compile at a time in a quilt: each holds `SURVEY_LOCK`, decides again under it, and waits up to `QUEUE` seconds for another to end.

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
        The hash of the work's stored PDF, which the survey is kept by and confirmed against.
    pdf_path : Path, optional
        That PDF on the disk.

    Returns
    -------
    Survey
        `ready` or `failed` (see `compile_marks`).
    """
    with locks.locked(root / SURVEY_LOCK, wait=QUEUE):
        s = survey(root, tex, src, main, pdf)
        if s.state != "reading":
            return s
        done = compile_marks(src, s, pdf_path if pdf else None)
        keep(root, done)
        return done
