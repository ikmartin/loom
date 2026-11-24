"""Gathering: a reference for each entry of a bibliography the person's documents and landmarks read (`docs/design/library.md`, "Digesting and checking": loom alone makes "a reference for each entry of a bibliography").

A document reads a `.bib` it names (`\\bibliography`, `\\addbibresource`) or an inline `thebibliography`. An entry from a `.bib` is taken verbatim, with any `@string` it leans on written out; a `\\bibitem` is free text, so it becomes `@misc{KEY, note = {its text}}` with the identifiers the text writes as identifiers, and nothing guessed. The documents come first, then the landmarks, the first source of a key winning, keys compared ignoring case. A key a reference holds already makes nothing; a key whose work the person deleted is left alone until the person adds the work again; a reference gathering made follows its `.bib` entry until someone edits it in loom ("an entry a person corrected is not rewritten"). An entry the checks refuse is left out, and said where it is written (`problems`), and the rest go on.

Gathering runs after every build (`render/parts/library.py`, so the publisher's and `loom build`'s), when `loom stamp` or `loom import` makes a landmark, and before `loom library add` takes; never when the works are read. It looks first without a lock and writes only when something is due, then under the id lock and the library's lock, deciding again against the library as it is then.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from loom.library import log
from loom.library.entries import entries_in, entry_fault, expand_strings, read_entry, strings_of
from loom.library.references import Minter, make
from loom.library.store import NodeRefused, read, write_node
from loom.locks import locked
from loom.paths import ID_LOCK, LIBRARY_LOCK, LIBRARY_NODES, under
from loom.scan.source import blank_comments
from loom.scan.tokenize import commands, read_args, read_optional, tokenize

if TYPE_CHECKING:
    from loom.scan.expand import Expansion
    from loom.scan.model import Diagnostic
    from loom.scan.scan import ScanResult

_ARXIV = re.compile(
    r"(?:arXiv:\s*|arxiv\.org/abs/)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", re.I
)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s,;{}]+[^\s,;{}.])")
_MR = re.compile(r"\bMR\s*(\d{5,8})\b")
_ZBL = re.compile(r"\bZbl\s*(\d{4}\.\d{5}|\d{3}\.\d{5})\b")
#: The code an entry gathering cannot keep is said under (`docs/specs/diagnostics.md` §3).
REFUSED = "loom:bib-entry-refused"


@dataclass(frozen=True)
class Candidate:
    """One entry a document or a landmark reads: its key, the entry as a reference would hold it, where it was read as a person would name it, and the file and line it is written at."""

    key: str
    text: str
    source: str
    file: str = ""
    line: int = 0


class Refused(NamedTuple):
    """An entry gathering could not keep: its key, what in it to change, the file and line it is written at, and the reference that keeps its last entry when it was one being followed."""

    key: str
    why: str
    file: str
    line: int
    ref: str = ""


@dataclass
class Gathered:
    """What one gathering did: the references made and followed, the keys left alone as deleted, entries the checks refused with why, two sources of a key that disagree, and `.bib` files named and not found."""

    made: list[str] = field(default_factory=list)
    refused: list[Refused] = field(default_factory=list)
    followed: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str, str]] = field(default_factory=list)
    missing: list[tuple[str, str]] = field(default_factory=list)


def named_bibs(root: Path, text: str, base: str = "") -> tuple[list[Path], list[str]]:
    """The `.bib` files a document names (`\\bibliography`, `\\addbibresource`), resolved against `base`, the folder it compiles from; and the names that resolve to nothing or climb out."""
    clean = blank_comments(text)
    found: list[Path] = []
    absent: list[str] = []
    # read from the outline the scan keeps of a long text, so a build that changed nothing tokenizes nothing again
    for t in commands(clean, ("bibliography", "addbibresource")):
        values, _, _ = read_args(clean, t.end, "m" if t.value == "bibliography" else "om")
        for name in (values[-1] or "").split(","):
            name = name.strip()
            if not name:
                continue
            p = root / under(base, name if name.endswith(".bib") else name + ".bib")
            if ".." not in Path(name).parts and not name.startswith("/") and p.is_file():
                found.append(p)
            else:
                absent.append(name)
    return found, absent


def bibitems(text: str) -> dict[str, tuple[str, int]]:
    """Every `\\bibitem[label]{key} text` of `text`'s `thebibliography` environments, by key: its text, and the offset of its `\\bibitem` in `text`."""
    clean = blank_comments(text)
    out: dict[str, tuple[str, int]] = {}
    for env in re.finditer(r"\\begin\s*\{thebibliography\}(.*?)\\end\s*\{thebibliography\}", clean, re.S):
        start = env.start(1)
        items = [t for t in tokenize(env.group(1)) if t.kind == "cmd" and t.value == "bibitem"]
        for i, t in enumerate(items):
            _o, _s, _e, pos = read_optional(env.group(1), t.end)
            (key,), _, after = read_args(env.group(1), pos, "m")
            if key is None:
                continue
            stop = items[i + 1].start if i + 1 < len(items) else len(env.group(1))
            out.setdefault(key.strip(), (text[start + after : start + stop].strip(), start + t.start))
    return out


def bibitem_entry(key: str, item: str) -> str:
    """The entry a `\\bibitem` makes: `@misc` with its text as `note` and the identifiers it writes as identifiers; nothing else is read into it."""
    flat = re.sub(r"\\url\s*\{([^}]*)\}|\\href\s*\{([^}]*)\}\{[^}]*\}", lambda m: f" {m.group(1) or m.group(2)} ", item)
    note = re.sub(r"\s+", " ", item).strip()
    fields = [("note", note.replace("{", "(").replace("}", ")") if _unbalanced(note) else note)]
    if m := _ARXIV.search(flat):
        fields += [("eprint", m.group(1)), ("archiveprefix", "arXiv")]
    if m := _DOI.search(flat):
        fields.append(("doi", m.group(1)))
    if m := _MR.search(flat):
        fields.append(("mrnumber", m.group(1)))
    if m := _ZBL.search(flat):
        fields.append(("zbl", m.group(1)))
    return f"@misc{{{key},\n" + "".join(f"  {name} = {{{value}}},\n" for name, value in fields) + "}\n"


def _unbalanced(text: str) -> bool:
    depth = 0
    for ch in text:
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth < 0:
            return True
    return depth != 0


def candidates(result: ScanResult, out: Gathered | None = None) -> dict[str, Candidate]:
    """Every entry the person's documents and the landmarks read, by its key folded as check 9 folds it: the documents first, the default first among them, the first source of a key winning, and a second that disagrees said in `out.conflicts`."""
    from loom.scan.scan import landmark_bases, landmark_documents

    root = result.quilt.root
    found: dict[str, Candidate] = {}
    seen = out if out is not None else Gathered()

    def offer(c: Candidate) -> None:
        kept = found.setdefault(c.key.casefold(), c)
        if kept is not c and re.sub(r"\s+", "", kept.text) != re.sub(r"\s+", "", c.text):
            seen.conflicts.append((c.key, kept.source, c.source))

    def read(text: str, base: str, said: str, place: Callable[[int], tuple[str, int]]) -> None:
        bibs, absent = named_bibs(root, text, base)
        seen.missing.extend((said, name) for name in absent)
        for bib in bibs:
            raw = bib.read_text(encoding="utf-8", errors="replace")
            strings = strings_of(raw)
            shown = bib.relative_to(root).as_posix()
            for key, entry, at in entries_in(raw):
                text_of = expand_strings(entry.strip(), strings) + "\n"
                offer(Candidate(key, text_of, f"{said} via {shown}", shown, raw.count("\n", 0, at) + 1))
        for key, (item, at) in bibitems(text).items():
            offer(Candidate(key, bibitem_entry(key, item), said, *place(at)))

    documents = sorted(m for m in result.masters if result.document_role(m) == "person" and m in result.expansions)
    for rel in sorted(documents, key=lambda m: m != result.default_master):
        expansion = result.expansions[rel]

        def placed(at: int, expansion: Expansion = expansion, rel: str = rel) -> tuple[str, int]:
            file, offset, _shift = expansion.locate(at)
            source = result.files.get(file)
            return (file, source.line_of(offset)) if source is not None else (rel, 0)

        read(expansion.text, result.base_of(rel), rel, placed)
    bases = landmark_bases(result.quilt)
    for rel in landmark_documents(result.quilt):
        text = (root / rel).read_text(encoding="utf-8", errors="replace")

        def lined(at: int, text: str = text, rel: str = rel) -> tuple[str, int]:
            return rel, text.count("\n", 0, at) + 1

        read(text, bases.get(rel, ""), rel, lined)
    return found


def held_keys(root: Path) -> dict[str, str]:
    """Every reference's entry key, folded as check 9 folds it (`casefold`), to its id, read from the files."""
    from loom.library.node import NodeUnreadable, read_node

    out: dict[str, str] = {}
    folder = root / LIBRARY_NODES
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*-ref.node")):
        try:
            node = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
        if (entry := read_entry(node.body)) is not None:
            out.setdefault(entry.key.casefold(), node.id)
    return out


def _held(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Each reference's entry key, case folded as check 9 folds it, to its id, and each reference's body; read from the index, which opens no node file it has read before."""
    from loom.library.index import NodeIndex

    if not (root / LIBRARY_NODES).is_dir():
        return {}, {}
    with NodeIndex.open(root) as index:
        rows = index.db.execute("SELECT id, citekey, body FROM nodes WHERE kind = 'reference' ORDER BY id").fetchall()
    keys: dict[str, str] = {}
    for ref, citekey, _body in rows:
        if citekey:
            keys.setdefault(citekey, ref)
    return keys, {ref: body for ref, _citekey, body in rows}


@contextmanager
def writing(root: Path) -> Iterator[None]:
    """The id lock and then the library's lock, as every writer that mints a stem takes them."""
    with locked(root / ID_LOCK), locked(root / LIBRARY_LOCK):
        yield


def gather(result: ScanResult, *, write: bool = True) -> Gathered:
    """Make a reference for each entry the documents and landmarks read that no reference holds, and follow the `.bib` entries of those gathering made.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan. What gathering makes or follows is added to its citekeys (`bib`, `refs`), as a scan made after it would read them.
    write : bool, default True
        Write the references; False says what would be made, and takes no lock.

    Returns
    -------
    Gathered
        The references made (or, not writing, the keys that would make one), followed, and left alone, the entries refused with what in each to change, and what disagreed or was not found.

    See Also
    --------
    problems : the entries refused, as the diagnostics a build publishes.
    """
    root = result.quilt.root
    looked = Gathered()
    found = candidates(result, looked)
    if not found:
        return looked
    _settle(result, found, looked, write=False)
    if not write or not (looked.made or looked.followed):
        return looked
    out = Gathered(conflicts=looked.conflicts, missing=looked.missing)
    with writing(root):
        _settle(result, found, out, write=True)
    if out.made or out.followed:
        from loom.library.references import entries

        for key, (ref, entry) in entries(root).items():
            result.bib[key] = entry
            result.refs[key] = ref
    return out


def _settle(result: ScanResult, found: dict[str, Candidate], out: Gathered, *, write: bool) -> None:
    """Decide each candidate against the library as it is now, writing what is due when `write`; an entry the checks refuse is said in `out.refused` and the rest go on."""
    root = result.quilt.root
    acts = log.replay(root)
    deleted = {k.casefold() for k in acts.deleted_keys()}
    held, bodies = _held(root)
    minter: Minter | None = None
    for folded, cand in found.items():
        if folded in deleted:
            out.deleted.append(cand.key)
            continue
        ref = held.get(folded)
        if ref is None:
            if not write:
                out.made.append(cand.key)
                continue
            minter = minter or Minter.of(result)
            try:
                node = make(
                    root, cand.text, minter, by="loom", kind="loom", how="gather", found_by="entry", source=cand.source
                )
            except NodeRefused:
                out.refused.append(_refused(cand))
                continue
            held[folded] = node.id
            out.made.append(node.id)
        elif bodies.get(ref) != cand.text and acts.follows(ref):
            if write:
                was = read(root, ref)
                if was is None:
                    continue
                try:
                    write_node(root, replace(was, body=cand.text))
                except NodeRefused:
                    out.refused.append(_refused(cand, ref))
                    continue
                log.record(root, "followed", ref, by="loom", kind="loom", source=cand.source)
            out.followed.append(ref)


def _refused(cand: Candidate, ref: str = "") -> Refused:
    """An entry the checks refused, said as what in it to change; the check's own words name loom's files, which a person never reads."""
    where = f" in {cand.file}" if cand.file.endswith(".bib") else ""
    why = entry_fault(cand.text, where=where) or f"loom could not keep {cand.key} as a work, by a fault of its own"
    return Refused(cand.key, why, cand.file, cand.line, ref)


def problems(result: ScanResult, done: Gathered) -> list[Diagnostic]:
    """Each entry `done` could not keep, as `REFUSED`, a warning of the person's, on the line that writes it; `[lint] disable` applied.

    Parameters
    ----------
    result : ScanResult
        The scan gathering read.
    done : Gathered
        What it did.

    Returns
    -------
    list of Diagnostic
        One an entry, saying what in it to change and what the library holds of it meanwhile.
    """
    from loom.scan.diagnostics import can_disable
    from loom.scan.model import Diagnostic, Location

    if REFUSED in result.quilt.config.lint_disable and can_disable(REFUSED):
        return []
    out = []
    for r in done.refused:
        meanwhile = f"the library keeps {r.key} as it was" if r.ref else f"the library holds no work for {r.key}"
        out.append(
            Diagnostic(
                "warning",
                REFUSED,
                f"{r.why}; until then {meanwhile}",
                [Location(r.file, r.line or 1)] if r.file else [],
            )
        )
    return out
