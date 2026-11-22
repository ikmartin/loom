"""What a TeX source holds, read once for each source and kept by the source's hash (`docs/specs/library-views.md` §3.2, "The survey"): its sections, its results with their proofs, every label it defines, and its bibliography's files.

It is read with the scanner's own parsers, and each result is named from its counters as `library.counters` emulates them, which a work's outline shows while the survey is `reading`; nothing writes an emulated number into a node. Only files inside the source's folder are read. Made when something asks for it, never by a build or the list of works.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from loom.library.counters import Numbering
from loom.paths import LIBRARY_SURVEYS
from loom.reshape.importer import closure_of
from loom.scan.directives import parse_directives
from loom.scan.envtree import FileEnvs, labels_in, scan_environments
from loom.scan.expand import expand_master
from loom.scan.model import Env, SourceFile, Taxon
from loom.scan.preamble import build_closure, document_start
from loom.scan.sections import SectionUnit, find_sections
from loom.scan.source import read_source
from loom.tex.runner import normalise_engine

#: The survey's own format; a kept survey of another is read again.
VERSION = 1
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
#: `\setcounter` of a sectioning counter, which moves where the next heading steps from.
_SETCOUNTER = re.compile(r"\\setcounter\s*\{(chapter|section|subsection)\}\s*\{\s*(-?\d+)\s*\}")
_APPENDIX = re.compile(r"\\appendix(?![A-Za-z@])")
_BIBLIOGRAPHY = re.compile(r"\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}")


@dataclass
class Section:
    """A heading of the source: `section` its id in the survey (`s1`, `s2`, … in source order), `command` the sectioning command."""

    section: str
    command: str
    number: str | None
    title: str
    level: int
    label: str | None = None
    file: str = ""
    heading_end: int = 0
    page: int | None = None
    sheet: int | None = None


@dataclass
class Proof:
    """A proof the source attaches to a result: where it stands in its file, and once compiled its page."""

    file: str
    start: int
    end: int
    body_start: int
    body_end: int
    page: int | None = None
    sheet: int | None = None


@dataclass
class Item:
    """A result of the source, digested or not (`library-views.md` §3.2's `item`).

    `item` is its own label, else `i` and its place among the source's results. `name` is the word the source prints for it ("Lemma") and `taxon` the node's (`nodes.md` §5). `number` is emulated while the survey is `reading` and what the source printed once it is `ready`. Offsets are in `file`, the source's own text.
    """

    item: str
    env: str
    taxon: str
    name: str
    numbered: bool
    number: str | None
    title: str | None
    label: str | None
    labels: list[str]
    section: str | None
    file: str
    start: int
    end: int
    body_start: int
    body_end: int
    page: int | None = None
    sheet: int | None = None
    proofs: list[Proof] = field(default_factory=list)


@dataclass
class Label:
    """Every `\\label` of the source: whose text holds it (`owner`, an item; `proof`, which of its proofs), whether it is that item's own, and `kind`, the counter it numbers as (`section`, `equation`, `enumi`, `figure`, a result's own, or `other`)."""

    kind: str
    owner: str | None = None
    proof: int | None = None
    result: bool = False
    number: str | None = None
    page: int | None = None
    sheet: int | None = None


@dataclass
class Survey:
    """What one source holds. `state` is `reading` until its compile, then `ready`, or `failed` with `why` (`no-main`, `unreadable`, `no-document`, and the compile's own)."""

    tex: str
    main: str
    version: int = VERSION
    state: str = "reading"
    why: str | None = None
    engine: str = "pdflatex"
    sections: list[Section] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    labels: dict[str, Label] = field(default_factory=dict)
    bibliography: list[str] = field(default_factory=list)
    bbl: str | None = None

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
        `reading`, or `failed` with why when the main file is missing or unreadable or begins no document.
    """
    out = Survey(tex=tex, main=main)
    master_path = src / main
    if not master_path.is_file() or ".." in Path(main).parts:
        out.state, out.why = "failed", "no-main"
        return out
    try:
        found, _outside = closure_of(src, master_path)
        files = {rel: read_source(src, rel) for rel, p in found.items() if p.suffix.lower() in TEXT}
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
    closure = build_closure(master, src, files, parse_directives(master), foreign=True)
    out.engine = normalise_engine(closure.engine)
    exp = expand_master(master, src, files)
    units = find_sections(exp, files)
    taxa = closure.taxa
    envs: dict[str, FileEnvs] = {}
    for rel in [main, *(f for f in exp.reached if f != main)]:
        if rel in files:
            envs[rel] = scan_environments(files[rel], set(taxa), doc if rel == main else 0)
    _walk(out, exp.text, units, envs, files, taxa, exp)
    _label_all(out, units, envs, files, doc)
    _bibliography(out, src, main, files, exp.reached)
    return out


def _walk(
    out: Survey,
    text: str,
    units: list[SectionUnit],
    envs: dict[str, FileEnvs],
    files: dict[str, SourceFile],
    taxa: dict[str, Taxon],
    exp: Any,
) -> None:
    """The sections and results in the order they stand, each numbered by the emulated counters.

    Events at one place sort headings before results, as TeX steps them; a result outside every reached file is not the document's.
    """
    events: list[tuple[int, int, str, Any]] = [(u.exp_start, 0, "heading", u) for u in units]
    events += [(m.start(), 0, "appendix", None) for m in _APPENDIX.finditer(text)]
    events += [(m.start(), 0, "set", (m.group(1), int(m.group(2)))) for m in _SETCOUNTER.finditer(text)]
    for rel, fe in envs.items():
        for env in fe.theorem_envs:
            at = exp.exp_offset(rel, env.start)
            if at is not None and env.name in taxa:
                events.append((at, 1, "result", (rel, env)))
    events.sort(key=lambda e: (e[0], e[1]))
    numbering = Numbering(taxa)
    places: list[tuple[int, int, str]] = []
    statements: dict[tuple[str, int], Item] = {}
    taken: set[str] = set()
    for at, _order, kind, payload in events:
        if kind == "appendix":
            numbering.mark_appendix()
        elif kind == "set":
            numbering.set_counter(*payload)
        elif kind == "heading":
            u: SectionUnit = payload
            sid = f"s{len(out.sections) + 1}"
            out.sections.append(
                Section(
                    section=sid,
                    command=u.name,
                    number=numbering.heading(u.name, u.starred),
                    title=u.title,
                    level=u.level,
                    label=u.labels[0] if u.labels else None,
                    file=u.file,
                    heading_end=u.heading_end,
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
                number=numbering.theorem(taxon),
                title=env.optarg.strip() if env.optarg and env.optarg.strip() else None,
                label=own,
                labels=labels,
                section=within[-1][2] if within else None,
                file=rel,
                start=env.start,
                end=env.end,
                body_start=env.body_start,
                body_end=env.body_end,
            )
            out.items.append(item)
            statements[(rel, env.start)] = item
    for rel, fe in envs.items():
        for proof_start in sorted(fe.attachments):
            att = fe.attachments[proof_start]
            owner = statements.get((rel, att.statement.start)) if att.statement is not None else None
            if owner is not None:
                p = att.proof
                owner.proofs.append(Proof(rel, p.start, p.end, p.body_start, p.body_end))


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
                if (src / path).is_file() and path not in out.bibliography:
                    out.bibliography.append(path)
    bbl = Path(main).with_suffix(".bbl").as_posix()
    out.bbl = bbl if (src / bbl).is_file() else None


def path_of(root: Path, tex: str) -> Path:
    """Where the survey of the source `tex` is kept."""
    return root / LIBRARY_SURVEYS / f"{tex.removeprefix('sha256:')}.json"


def kept(root: Path, tex: str) -> Survey | None:
    """The survey kept for the source `tex`, or None when there is none of this version."""
    try:
        data = json.loads(path_of(root, tex).read_text(encoding="utf-8"))
        return Survey.from_json(data) if data.get("version") == VERSION else None
    except (OSError, ValueError, TypeError):
        return None


def keep(root: Path, survey: Survey) -> None:
    """Write a survey to its file whole: a reader sees the last one or this one, never part of it."""
    path = path_of(root, survey.tex)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(survey.to_json(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def survey(root: Path, tex: str, src: Path, main: str) -> Survey:
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

    Returns
    -------
    Survey
        As kept, or `reading` when read now (see `read`).
    """
    found = kept(root, tex)
    if found is not None:
        return found
    out = read(src, main, tex)
    keep(root, out)
    return out
