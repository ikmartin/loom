"""Links an agent or a person writes into what the viewer shows (plan 0.14 phase 3, specs/dialect.md §2.13).

Two schemes and one grammar. `quilt:KEY[#PLACE]` names something this quilt owns by its fixed key -- a node, a document, an annotation, a session, the research state (`quilt:state`), or a shown file by its path with its suffix (`quilt:notes/day1.md#setup`) -- and `cited:SCHEME:VALUE[?page=N&quote=…]` names a place in a cited work by its global identifier. **Only what the viewer can show is linkable**: an included `.tex` file, a hidden file (a session's drafts among them), a deleted session are refused, because a link to something the viewer does not display is a link to nothing.

A link is checked when it is posted (`loom session say`, `loom annotate`) and printed correctly by `loom link`, so an agent never composes one by hand. A link written into a shown Markdown file is checked by `loom lint` through the same `resolve` (`scan.lint.markdown_links`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote

from loom.records import ids

#: A markdown link whose destination is one of the two schemes.
LINK = re.compile(r"\]\(((?:quilt|cited):[^)\s]+)\)")
ANNOTATION = re.compile(rf"^{ids.ANNOTATION}$")
SESSION = re.compile(rf"^{ids.SESSION}$")


class LinkError(ValueError):
    """A link that names nothing the viewer shows; the message says what and why, and `part` which part of the link is at fault: `target` (the thing), `place` (a place in it) or `work` (a cited work's identifier)."""

    def __init__(self, message: str, part: str = "target") -> None:
        super().__init__(message)
        self.part = part


@dataclass(frozen=True)
class Target:
    """What a link names: its kind, the key it is addressed by, and the place in it, if any."""

    kind: str  # node | document | annotation | session | work | page | file
    key: str
    place: str = ""
    href: str = ""


def resolve(result: Any, root: Path, href: str, records: list[Any] | None = None) -> Target:
    """The thing `href` names, or LinkError.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned: its nodes, documents and bibliography.
    root : Path
        The quilt root, for its sessions and its annotation log.
    href : str
        A `quilt:` or `cited:` link.
    records : list, optional
        The annotation records; read from the log when not given.

    Returns
    -------
    Target

    Raises
    ------
    LinkError
        When the link names nothing the viewer shows.
    """
    if href.startswith("quilt:"):
        return _quilt(result, root, href, records)
    if href.startswith("cited:"):
        return _cited(result, href)
    raise LinkError(f"{href}: a link is quilt:KEY or cited:SCHEME:VALUE")


def _quilt(result: Any, root: Path, href: str, records: list[Any] | None) -> Target:
    from loom.cli._quilt import resolve_key
    from loom.errors import EnvError

    body = href[len("quilt:") :]
    key, _, place = body.partition("#")
    # the viewer decodes the place as it decodes the key, so a heading written in other than ASCII is the same place either way
    place = unquote(place)
    if not key:
        raise LinkError(f"{href}: names no key")
    if ANNOTATION.match(key):
        from loom.records.annotations import find_annotation, load_records

        if records is None:
            records, _ = load_records(root)
        if find_annotation(records, key) is None:
            raise LinkError(f"{href}: no annotation {key}")
        return Target("annotation", key, href=href)
    if SESSION.match(key):
        from loom.sessions import sessions

        if key not in sessions(root):
            raise LinkError(f"{href}: no session {key}")
        return Target("session", key, href=href)
    if key == "state":
        # the quilt's research state, a page (plan 0.21.3): before landmarks and labels, so `state` always means it
        if place:
            raise LinkError(f"{href}: the research state is linked whole", "place")
        if not (root / result.quilt.config.research_state).is_file():
            raise LinkError(f"{href}: this quilt has no research state yet")
        return Target("page", "state", href=href)
    path = unquote(key)
    if Path(path).suffix and not path.endswith(".tex") and (root / path).is_file():
        return _file(result, root, href, path, place)
    landmarks = {**{Path(p).stem: p for p in result.canon_files}, **{p: p for p in result.canon_files}}
    if key in landmarks:
        if place:
            raise LinkError(f"{href}: a landmark is linked whole", "place")
        return Target("document", landmarks[key], href=href)
    library = _library_node(root, href, key, place)
    if library is not None:
        return library
    try:
        canonical = resolve_key(result, key)
    except EnvError:
        raise LinkError(f"{href}: no key {key} in this quilt") from None
    node = result.nodes.get(canonical)
    if node is not None and node.kind == "master":
        if place:
            _reached(result, href, place, canonical)
        return Target("document", canonical, place, href)
    if node is not None and node.kind == "file":
        raise LinkError(f"{href}: {key} is a file the documents include; link the keys it holds, or the document")
    if place:
        owner = _owner(result, _key(result, href, place, "place"))
        if owner != _owner(result, canonical):
            raise LinkError(f"{href}: {place} is not in {key}", "place")
    return Target("node", canonical, place, href)


def _file(result: Any, root: Path, href: str, path: str, place: str) -> Target:
    """A shown file by its path: a Markdown file or notebook at one of its headings, a PDF at `page=N`, a text file at `L` and a line number, an HTML page at an anchor, anything else whole."""
    from loom.files import DRAWN, LINKABLE, Shown, headings_of, kind_of

    if not Shown.of(result.quilt).is_shown(path):
        raise LinkError(f"{href}: {path} is hidden from the viewer")
    kind = kind_of(root, path, set(result.masters))
    if kind not in LINKABLE:
        raise LinkError(f"{href}: a LaTeX file is linked by its document or its keys")
    if place and kind in DRAWN:
        if place not in headings_of(root, path, kind):
            raise LinkError(f"{href}: {path} has no heading {place}", "place")
    elif place and kind == "pdf":
        if not re.fullmatch(r"page=[1-9]\d*", place):
            raise LinkError(f"{href}: a place in a PDF is page=N, from 1", "place")
    elif place and kind == "text":
        line = re.fullmatch(r"L([1-9]\d*)", place)
        if line is None:
            raise LinkError(f"{href}: a place in a text file is L and a line number, from L1", "place")
        count = len((root / path).read_text(encoding="utf-8", errors="replace").split("\n"))
        if int(line.group(1)) > count:
            raise LinkError(f"{href}: {path} has {count} lines", "place")
    elif place and kind != "html":
        raise LinkError(f"{href}: {path} is linked whole", "place")
    return Target("file", path, place, href)


def _key(result: Any, href: str, key: str, part: str = "target") -> str:
    from loom.cli._quilt import resolve_key
    from loom.errors import EnvError

    try:
        return resolve_key(result, key)
    except EnvError:
        raise LinkError(f"{href}: no key {key} in this quilt", part) from None


def _owner(result: Any, key: str) -> str:
    """The node a key is shown in: a region's container, a proof's statement, else the key itself."""
    region = result.assembly.regions.get(key)
    if region is not None:
        key = region.container
    return key.split("/proof", 1)[0]


def _reached(result: Any, href: str, place: str, master: str) -> None:
    """Refuse a place a document does not reach."""
    owner = _owner(result, _key(result, href, place, "place"))
    node = result.nodes.get(owner)
    if node is None or master not in node.reached_by:
        raise LinkError(f"{href}: {master} does not include {place}", "place")


def _library_node(root: Path, href: str, key: str, place: str) -> Target | None:
    """A node of the library by its id (`quilt:tq-00K3`), a place in it one of its anchors; None when `key` is no library node's id, so the quilt's own keys are tried. A library id and a draft's key are minted from one namespace and never equal (`nodes.md` §3)."""
    from loom.library.ids import anchor_owner, parse_id
    from loom.library.node import file_name
    from loom.paths import LIBRARY_NODES

    if parse_id(key) is None or not (root / LIBRARY_NODES / file_name(key)).is_file():
        return None
    if place and anchor_owner(place) != key:
        raise LinkError(f"{href}: {place} is not a place in {key}", "place")
    return Target("library", key, place, href)


#: The schemes a `cited:` link names a work by, as a person writes them, to the scheme an entry's identifier carries.
_CITED = {"doi": "doi", "arxiv": "arxiv", "mr": "mr", "zbl": "zbl", "zbmath": "zbl"}


def _cited(result: Any, href: str) -> Target:
    from loom.library.entries import matchable
    from loom.library.intake import Library

    m = re.match(r"([^?#]*)(?:[?#](.*))?$", href[len("cited:") :], re.S)
    target, rest = (m.group(1), m.group(2) or "") if m else ("", "")
    scheme, _, value = target.partition(":")
    if scheme.lower() == "work":
        raise LinkError(f"{href}: a work is no longer linked by work:…; link it by its identifier, or as quilt:REF", "work")
    if scheme.lower() not in _CITED or not value:
        raise LinkError(f"{href}: cited: takes a work's identifier, doi:…, arXiv:…, MR…, zbMATH…", "work")
    held = Library.read(result.quilt.root).stating([matchable(f"{_CITED[scheme.lower()]}:{value}")])
    if not held:
        raise LinkError(f"{href}: no work in the library states {target}", "work")
    keys = parse_qs(rest.replace("#", "&"))
    page = (keys.get("page") or [""])[0]
    if page and not (page.isdigit() and int(page) > 0):
        raise LinkError(f"{href}: page must be a number from 1", "place")
    return Target("work", held[0], f"page={page}" if page else "", href)


def check(result: Any, root: Path, text: str) -> list[str]:
    """One sentence per link in `text` that names nothing the viewer shows; empty when every link resolves."""
    from loom.records.annotations import load_records

    hrefs = LINK.findall(text)
    if not hrefs:
        return []
    records, _ = load_records(root)
    out: list[str] = []
    for href in hrefs:
        try:
            resolve(result, root, href, records)
        except LinkError as exc:
            out.append(str(exc))
    return out


def refuse_bad_links(result: Any, root: Path, text: str) -> None:
    """Raise EnvError naming every bad link in `text`, with the command that prints a good one: a link that names nothing is an argument that names nothing, exit 2."""
    from loom.errors import EnvError

    bad = check(result, root, text)
    if bad:
        raise EnvError(
            "links that name nothing the viewer shows:\n  "
            + "\n  ".join(bad)
            + "\n`loom link THING` prints a correct one"
        )


def quilt_link(key: str, place: str = "") -> str:
    """`[](quilt:KEY#PLACE)`, the empty text the viewer fills with its own name for the thing; a file's path is percent-encoded, so a space does not end the link."""
    return f"[](quilt:{quote(key, safe='/:._-~')}{'#' + place if place else ''})"


def cited_link(scheme: str, value: str, page: int | None = None, text: str | None = None) -> str:
    """`[](cited:SCHEME:VALUE?page=N&quote=…)`."""
    keys = []
    if page:
        keys.append(f"page={page}")
    if text:
        keys.append("quote=" + quote(text, safe=""))
    return f"[](cited:{scheme}:{value}{'?' + '&'.join(keys) if keys else ''})"
