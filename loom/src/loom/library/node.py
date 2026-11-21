"""One node's file (docs/specs/nodes.md §1–2): a line `+++`, a TOML header, a line `+++`, and the body, raw LaTeX to the end of the file.

Loom writes one form of header (`node_bytes`), so a file it wrote reads and writes back byte for byte. A header in another valid TOML form is read as it is and written in loom's form when loom next writes the node. Checks 1 to 5 of §11 are what reading a file takes, so they are here, each failure a `Problem`; `checks` gives them their codes and adds the rest.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass
from typing import Any, NamedTuple

from loom.library import ids

#: The format's number; a file of any other number is refused.
SCHEMA = 1
READABLE = frozenset({SCHEMA})
#: A node file's name is its id and this.
SUFFIX = ".node"
FENCE = "+++"

_STR, _IDS, _STRS, _HASH = "a string", "a list of ids", "a list of names", "a hash"
#: The header's keys in the order loom writes them, each with its type, the kinds it is allowed on, and whether it needs a `source` (True), forbids one (False) or neither (None).
KEYS: dict[str, tuple[str, frozenset[str], bool | None]] = {
    "number": (_STR, frozenset({ids.STATEMENT}), None),
    "title": (_STR, frozenset({ids.STATEMENT}), None),
    "source": (_STR, frozenset({ids.STATEMENT, ids.PROOF}), None),
    "label": (_STR, frozenset({ids.STATEMENT}), True),
    "pages": (_STR, frozenset({ids.STATEMENT, ids.PROOF}), True),
    "uses": (_IDS, frozenset({ids.STATEMENT, ids.PROOF}), None),
    "mentions": (_IDS, frozenset({ids.STATEMENT, ids.PROOF}), None),
    "authors": (_STRS, frozenset({ids.STATEMENT, ids.PROOF}), False),
    "pdf": (_HASH, frozenset({ids.REFERENCE}), None),
    "tex": (_HASH, frozenset({ids.REFERENCE}), None),
}
#: The three every node has, which come first.
REQUIRED = ("schema", "id", "taxon")
#: A statement's taxon: a word of lower-case ASCII letters and hyphens.
TAXON = re.compile(r"[a-z]+(-[a-z]+)*")
#: The taxon each other kind has.
TAXA = {ids.REFERENCE: "reference", ids.MACROS: "macros", ids.PROOF: "proof"}
_HASH_FORM = re.compile(r"sha256:[0-9a-f]{64}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}
_KINDS_SAID = {
    ids.STATEMENT: "a statement",
    ids.PROOF: "a proof",
    ids.REFERENCE: "a reference",
    ids.MACROS: "a macros node",
}


class Problem(NamedTuple):
    """One way a file fails: the number of its check in nodes.md §11, the sentence that says it, and its line where there is one, counted in the body when `body` is set and in the file otherwise."""

    check: int
    message: str
    line: int | None = None
    body: bool = False


class NodeUnreadable(Exception):
    """A file that fails a check reading it takes (1 to 5): no node can be made of it."""

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(p.message for p in problems))
        self.problems = problems


@dataclass(frozen=True)
class Node:
    """A node as its file says it: the header's keys, absent ones empty, and the body exactly."""

    id: str
    taxon: str
    body: str = ""
    number: str | None = None
    title: str | None = None
    source: str | None = None
    label: str | None = None
    pages: str | None = None
    uses: tuple[str, ...] = ()
    mentions: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    pdf: str | None = None
    tex: str | None = None
    schema: int = SCHEMA

    @property
    def kind(self) -> str:
        """Statement, proof, reference or macros, by the id's suffix."""
        return ids.kind_of(self.id) or ids.STATEMENT

    @property
    def parent(self) -> str | None:
        """A proof's statement or a macros node's reference, by the id."""
        return ids.parent_of(self.id)

    @property
    def empty(self) -> bool:
        """Whether the body holds nothing but whitespace: a stub's, or a pointer's."""
        return not self.body.strip()

    @property
    def file_name(self) -> str:
        return file_name(self.id)

    def header(self) -> dict[str, Any]:
        """The header's keys and values as the file states them, in loom's order, absent ones left out."""
        out: dict[str, Any] = {"schema": self.schema, "id": self.id, "taxon": self.taxon}
        for key in KEYS:
            value = getattr(self, key)
            if value:
                out[key] = list(value) if isinstance(value, tuple) else value
        return out


def file_name(node_id: str) -> str:
    """The name of the file holding the node `node_id`."""
    return node_id + SUFFIX


def node_hash(data: bytes) -> str:
    """A node's hash, `sha256:` and the lower-case hexadecimal SHA-256 of its file's bytes, which records name its text by.

    Parameters
    ----------
    data : bytes
        The whole file, header and body.

    Returns
    -------
    str
        `sha256:` and 64 hexadecimal digits.
    """
    return "sha256:" + hashlib.sha256(data).hexdigest()


def body_start(data: bytes, body: str) -> int:
    """The line of the file `data` on which its body, `body`, begins."""
    return data[: len(data) - len(body.encode("utf-8"))].count(b"\n") + 1


def split(data: bytes, name: str) -> tuple[str, str]:
    """The header's text and the body of the file `name`, or `NodeUnreadable` (check 1) when its fences are not where §1 puts them or it is not UTF-8.

    The body is every byte after the line feed that ends the second line `+++`.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NodeUnreadable([Problem(1, f"{name} is not UTF-8 text (byte {exc.start} is not).")]) from None
    first, nl, rest = text.partition("\n")
    if first != FENCE or not nl:
        crlf = first == FENCE + "\r"
        said = (
            f"{name} ends its lines with a carriage return and a line feed, where a node file ends them with a line feed alone."
            if crlf
            else f"{name} does not begin with a line `+++`."
        )
        raise NodeUnreadable([Problem(1, said, 1)])
    m = re.search(r"^\+\+\+\n", rest, re.M)
    if m is None:
        said = (
            f"{name}'s second line `+++` does not end with a line feed."
            if rest.endswith("\n" + FENCE) or rest == FENCE
            else f"{name} has no second line `+++` to end its header."
        )
        raise NodeUnreadable([Problem(1, said)])
    return rest[: m.start()], rest[m.end() :]


def read_node(data: bytes, name: str) -> Node:
    """The node the file `name` holds, read as §1 and §2 say.

    Parameters
    ----------
    data : bytes
        The file's bytes.
    name : str
        The file's name, `<id>.node`, which its `id` must be.

    Returns
    -------
    Node
        Every key of the header and the body exactly.

    Raises
    ------
    NodeUnreadable
        With every problem of checks 1 to 5 found: the fences, the TOML, the schema, the id, the taxon, and each key's place and type.
    """
    header_text, body = split(data, name)
    try:
        header = tomllib.loads(header_text)
    except tomllib.TOMLDecodeError as exc:
        raise NodeUnreadable([Problem(1, f"{name}'s header is not TOML: {exc}.")]) from None
    problems = header_problems(header, name, header_text)
    if problems:
        raise NodeUnreadable(problems)
    keys: dict[str, Any] = {key: tuple(v) if isinstance(v, list) else v for key, v in header.items() if key in KEYS}
    return Node(id=header["id"], taxon=header["taxon"], body=body, schema=header["schema"], **keys)


def header_problems(header: dict[str, Any], name: str, header_text: str = "") -> list[Problem]:
    """Every failure of checks 2 to 5 in a header read from the file `name`: the schema, the id against the name and §3, the taxon against the id, and each key against §2's table.

    `header_text`, where given, places each problem on its key's line.
    """
    out: list[Problem] = []

    def line(key: str) -> int | None:
        found = re.search(rf"^[ \t]*{re.escape(key)}[ \t]*=", header_text, re.M)
        return header_text.count("\n", 0, found.start()) + 2 if found else None

    schema = header.get("schema")
    if "schema" not in header:
        out.append(Problem(2, f"{name} has no `schema`."))
    elif type(schema) is not int:
        out.append(Problem(2, f"{name}'s `schema` is not a number.", line("schema")))
    elif schema not in READABLE:
        out.append(Problem(2, f"{name} is schema {schema}, and this loom reads schema {SCHEMA}.", line("schema")))

    stem = name.removesuffix(SUFFIX)
    named = ids.parse_id(stem) if name.endswith(SUFFIX) else None
    node_id = header.get("id")
    if named is None:
        out.append(Problem(3, f"{name} is not named by a node's id, as `tq-00K3.node` is."))
    if "id" not in header:
        out.append(Problem(3, f"{name} has no `id`."))
    elif not isinstance(node_id, str):
        out.append(Problem(3, f"{name}'s `id` is not a string.", line("id")))
    elif named is not None and node_id != stem:
        out.append(Problem(3, f"{name}'s `id` is {node_id}, where it is its file's name, {stem}.", line("id")))
    kind = named.kind if named is not None else None

    taxon = header.get("taxon")
    if "taxon" not in header:
        out.append(Problem(4, f"{name} has no `taxon`."))
    elif not isinstance(taxon, str):
        out.append(Problem(4, f"{name}'s `taxon` is not a string.", line("taxon")))
    elif kind in TAXA and taxon != TAXA[kind]:
        out.append(
            Problem(
                4, f"{name} is {_KINDS_SAID[kind]} by its id, so its taxon is {TAXA[kind]}, not {taxon}.", line("taxon")
            )
        )
    elif kind == ids.STATEMENT and taxon in TAXA.values():
        out.append(
            Problem(4, f"{name} is a statement by its id, and {taxon} is not a statement's taxon.", line("taxon"))
        )
    elif kind == ids.STATEMENT and not TAXON.fullmatch(taxon):
        out.append(
            Problem(4, f"{name}'s taxon `{taxon}` is not a word of lower-case letters and hyphens.", line("taxon"))
        )

    sourced = "source" in header
    for key, value in header.items():
        if key in REQUIRED:
            continue
        if key not in KEYS:
            out.append(Problem(5, f"{name} has a key `{key}`, which a node's file does not have.", line(key)))
            continue
        typ, kinds, needs_source = KEYS[key]
        if kind is not None and kind not in kinds:
            out.append(Problem(5, f"`{key}` is not a key of {_KINDS_SAID[kind]}, and {name} is one.", line(key)))
        elif kind is not None and needs_source is True and not sourced:
            out.append(
                Problem(
                    5, f"{name} has `{key}` and no `source`; `{key}` says where in its source the text is.", line(key)
                )
            )
        elif kind is not None and needs_source is False and sourced:
            out.append(
                Problem(
                    5,
                    f"{name} has `{key}` and a `source`; the authors of a node read from a work are the work's.",
                    line(key),
                )
            )
        said = _type_problem(typ, value)
        if said:
            out.append(Problem(5, f"{name}'s `{key}` {said}.", line(key)))
    return out


def _type_problem(typ: str, value: Any) -> str | None:
    """What is wrong with `value` as a value of type `typ`, as the rest of a sentence; None when nothing is."""
    if typ in (_STR, _HASH):
        if not isinstance(value, str):
            return f"is not {typ}"
        if not value:
            return "is empty, where a key with nothing to say is left out"
        if typ == _HASH and not _HASH_FORM.fullmatch(value):
            return "is not `sha256:` and 64 lower-case hexadecimal digits"
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return f"is not {typ}"
    if not value:
        return "is an empty list, where a key with nothing to say is left out"
    if not all(value):
        return "holds an empty string"
    return None


def node_bytes(node: Node) -> bytes:
    """The file loom writes for `node`: §2's keys in their order, one `key = value` a line, and the body exactly.

    A string is a basic string, except one with a backslash that a literal string can hold, which is written `'…'` so that LaTeX reads as LaTeX. A list is written on one line.

    Parameters
    ----------
    node : Node
        The node; nothing here checks it.

    Returns
    -------
    bytes
        The whole file, UTF-8.
    """
    lines = [FENCE]
    for key, value in node.header().items():
        lines.append(f"{key} = {_toml(value)}")
    lines.append(FENCE)
    return ("\n".join(lines) + "\n" + node.body).encode("utf-8")


def _toml(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_string(v) for v in value) + "]"
    return _string(value)


def _string(s: str) -> str:
    if "\\" in s and "'" not in s and not _CONTROL.search(s):
        return f"'{s}'"
    return '"' + "".join(_ESCAPES.get(c) or (f"\\u{ord(c):04X}" if _CONTROL.match(c) else c) for c in s) + '"'
