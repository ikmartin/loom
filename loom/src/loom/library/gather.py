"""Gathering: a reference for each entry of a bibliography the person's documents and landmarks read (`docs/design/library.md`, "Digesting and checking": loom alone makes "a reference for each entry of a bibliography").

A document reads a `.bib` it names (`\\bibliography`, `\\addbibresource`) or an inline `thebibliography`. An entry from a `.bib` is taken verbatim, with any `@string` it leans on written out; a `\\bibitem` is free text, so it becomes `@misc{KEY, note = {its text}}` with the identifiers the text writes as identifiers, and nothing guessed. The documents come first, then the landmarks, the first source of a key winning. A key a reference holds already, compared ignoring case, makes nothing; a key whose work the person deleted is left alone until the person adds the work again; a reference gathering made follows its `.bib` entry until someone edits it in loom ("an entry a person corrected is not rewritten").

Gathering runs when it is asked for: when the library's works are read or added to, and when a landmark is made, never on every build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import log
from loom.library.entries import expand_strings, read_entry
from loom.library.references import Minter, make
from loom.library.store import NodeRefused, read, write_node
from loom.locks import locked
from loom.paths import ID_LOCK, LIBRARY_NODES, under
from loom.scan.bib import raw_entries
from loom.scan.source import blank_comments
from loom.scan.tokenize import match_group, read_args, read_optional, tokenize

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

_ARXIV = re.compile(
    r"(?:arXiv:\s*|arxiv\.org/abs/)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", re.I
)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s,;{}]+[^\s,;{}.])")
_MR = re.compile(r"\bMR\s*(\d{5,8})\b")
_ZBL = re.compile(r"\bZbl\s*(\d{4}\.\d{5}|\d{3}\.\d{5})\b")
_STRING = re.compile(r"@string\s*[{(]\s*([A-Za-z][\w:.-]*)\s*=\s*", re.I)


@dataclass(frozen=True)
class Candidate:
    """One entry a document or a landmark reads: its key, the entry as a reference would hold it, and where it was read, as a person would name it."""

    key: str
    text: str
    source: str


@dataclass
class Gathered:
    """What one gathering did: the references made and followed, the keys left alone as deleted, entries the checks refused with why, two sources of a key that disagree, and `.bib` files named and not found."""

    made: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)
    followed: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str, str]] = field(default_factory=list)
    missing: list[tuple[str, str]] = field(default_factory=list)


def named_bibs(root: Path, text: str, base: str = "") -> tuple[list[Path], list[str]]:
    """The `.bib` files a document names (`\\bibliography`, `\\addbibresource`), resolved against `base`, the folder it compiles from; and the names that resolve to nothing or climb out."""
    clean = blank_comments(text)
    found: list[Path] = []
    absent: list[str] = []
    for t in tokenize(clean):
        if t.kind != "cmd" or t.value not in ("bibliography", "addbibresource"):
            continue
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


def bibitems(text: str) -> dict[str, str]:
    """Every `\\bibitem[label]{key} text` of `text`'s `thebibliography` environments, by key."""
    clean = blank_comments(text)
    out: dict[str, str] = {}
    for env in re.finditer(r"\\begin\s*\{thebibliography\}(.*?)\\end\s*\{thebibliography\}", clean, re.S):
        start = env.start(1)
        items = [t for t in tokenize(env.group(1)) if t.kind == "cmd" and t.value == "bibitem"]
        for i, t in enumerate(items):
            _o, _s, _e, pos = read_optional(env.group(1), t.end)
            (key,), _, after = read_args(env.group(1), pos, "m")
            if key is None:
                continue
            stop = items[i + 1].start if i + 1 < len(items) else len(env.group(1))
            out.setdefault(key.strip(), text[start + after : start + stop].strip())
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


def strings_of(text: str) -> dict[str, str]:
    """The `@string` abbreviations a `.bib` defines, by name, each value as its braces or quotes hold it."""
    out: dict[str, str] = {}
    for m in _STRING.finditer(text):
        rest = text[m.end() :].lstrip()
        if rest[:1] == "{" and (close := match_group(rest, 0)) > 0:
            out[m.group(1)] = rest[1 : close - 1]
        elif rest[:1] == '"' and (close := rest.find('"', 1)) > 0:
            out[m.group(1)] = rest[1:close]
    return out


def candidates(result: ScanResult, out: Gathered | None = None) -> dict[str, Candidate]:
    """Every entry the person's documents and the landmarks read, by key: the documents first, the default first among them, the first source of a key winning, and a second that disagrees said in `out.conflicts`."""
    from loom.scan.scan import landmark_bases, landmark_documents

    root = result.quilt.root
    found: dict[str, Candidate] = {}
    seen = out if out is not None else Gathered()

    def offer(c: Candidate) -> None:
        kept = found.setdefault(c.key, c)
        if kept is not c and re.sub(r"\s+", "", kept.text) != re.sub(r"\s+", "", c.text):
            seen.conflicts.append((c.key, kept.source, c.source))

    def read(text: str, base: str, said: str) -> None:
        bibs, absent = named_bibs(root, text, base)
        seen.missing.extend((said, name) for name in absent)
        for bib in bibs:
            raw = bib.read_text(encoding="utf-8", errors="replace")
            strings = strings_of(raw)
            shown = bib.relative_to(root).as_posix()
            for key, entry in raw_entries(raw).items():
                offer(Candidate(key, expand_strings(entry.strip(), strings) + "\n", f"{said} via {shown}"))
        for key, item in bibitems(text).items():
            offer(Candidate(key, bibitem_entry(key, item), said))

    documents = sorted(m for m in result.masters if result.document_role(m) == "person" and m in result.expansions)
    for rel in sorted(documents, key=lambda m: m != result.default_master):
        read(result.expansions[rel].text, result.base_of(rel), rel)
    bases = landmark_bases(result.quilt)
    for rel in landmark_documents(result.quilt):
        read((root / rel).read_text(encoding="utf-8", errors="replace"), bases.get(rel, ""), rel)
    return found


def held_keys(root: Path) -> dict[str, str]:
    """Every reference's entry key, folded to lower case, to its id."""
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
            out.setdefault(entry.key.lower(), node.id)
    return out


def gather(result: ScanResult, *, write: bool = True) -> Gathered:
    """Make a reference for each entry the documents and landmarks read that no reference holds, and follow the `.bib` entries of those gathering made.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    write : bool, default True
        Write the references; False says what would be made.

    Returns
    -------
    Gathered
        The references made (or, not writing, the keys that would make one), followed, and left alone, and what disagreed or was not found.
    """
    root = result.quilt.root
    out = Gathered()
    found = candidates(result, out)
    acts = log.replay(root)
    deleted = {k.lower() for k in acts.deleted_keys()}
    minter: Minter | None = None
    with locked(root / ID_LOCK) if write else _nothing():
        held = held_keys(root)
        for key, cand in found.items():
            folded = key.lower()
            if folded in deleted:
                out.deleted.append(key)
                continue
            ref = held.get(folded)
            if ref is None:
                if not write:
                    out.made.append(key)
                    continue
                minter = minter or Minter.of(result)
                try:
                    node = make(
                        root,
                        cand.text,
                        minter,
                        by="loom",
                        kind="loom",
                        how="gather",
                        found_by="entry",
                        source=cand.source,
                    )
                except NodeRefused as exc:
                    out.refused.append((key, str(exc)))
                    continue
                held[folded] = node.id
                out.made.append(node.id)
            elif acts.follows(ref) and (was := read(root, ref)) is not None and was.body != cand.text:
                if write:
                    write_node(root, replace(was, body=cand.text))
                    log.record(root, "followed", ref, by="loom", kind="loom", source=cand.source)
                out.followed.append(ref)
    return out


class _nothing:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_exc: object) -> None:
        return None
