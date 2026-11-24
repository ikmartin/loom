"""What a record names, and who acts.

A subject is one text by its hash: a node of the library, a draft's result by its label, or one macro's definition by its command (`docs/specs/evidence.md` §2). A record about a label or a macro holds wherever that label or command stands with that text, so a draft copied to a new file keeps it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from loom.identity import is_agent

#: The three things a record can be about, by the key that names each in a record.
KINDS = ("node", "label", "macro")
#: A text's hash, as records write it.
HASH = re.compile(r"sha256:[0-9a-f]{64}")
#: A macro's name without its backslash, as `scan.macros` reads it: letters (and `@`), or one other character.
MACRO = re.compile(r"[A-Za-z@]+|\{[A-Za-z@*]+\}|[^A-Za-z@\s{}]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
#: The longest label a record takes.
LONGEST = 256


def is_node(text: object, *kinds: str) -> bool:
    """Whether `text` is a node's id by the library's grammar (`library.ids`), and of one of `kinds` (`statement`, `proof`, `reference`, `macros`) where any are named."""
    from loom.library.ids import parse_id

    parsed = parse_id(text) if isinstance(text, str) else None
    return parsed is not None and (not kinds or parsed.kind in kinds)


def is_work(text: object) -> bool:
    """Whether `text` is a work's id: a reference node's."""
    return is_node(text, "reference")


def label_problem(label: object) -> str | None:
    """Why `label` cannot name a draft's result in a record; None when it can.

    Non-empty, no surrounding whitespace, no braces, no control character, at most `LONGEST` characters: what `\\label{…}` can hold and a record can quote back.
    """
    if not isinstance(label, str) or not label:
        return "a label is a non-empty string"
    if label != label.strip() or "{" in label or "}" in label or _CONTROL.search(label) or len(label) > LONGEST:
        return f"{label!r} is not a label"
    return None


@dataclass(frozen=True, order=True)
class Subject:
    """One text: a node, a draft's result by label, or a macro's definition, with the hash of that text.

    Parameters
    ----------
    kind : str
        `node`, `label` or `macro`.
    name : str
        The node's id, the label, or the macro's name without its backslash.
    hash : str
        `sha256:` and 64 hexadecimal digits.
    """

    kind: str
    name: str
    hash: str

    @property
    def key(self) -> tuple[str, str]:
        """What names the thing whatever its text: `(kind, name)`."""
        return (self.kind, self.name)

    def to_dict(self) -> dict[str, str]:
        """The subject as a record writes it, `{"node": …, "hash": …}`."""
        return {self.kind: self.name, "hash": self.hash}

    @classmethod
    def from_dict(cls, raw: Any, kinds: tuple[str, ...] = KINDS) -> Subject:
        """Read a subject a record wrote.

        Parameters
        ----------
        raw : object
            The record's value: an object with `hash` and exactly one of `kinds`.
        kinds : tuple of str, default all three
            The kinds this place in a record allows.

        Returns
        -------
        Subject

        Raises
        ------
        ValueError
            Naming what is wrong, for the log's reader to report.
        """
        if not isinstance(raw, dict):
            raise ValueError("a subject is an object")
        named = [k for k in KINDS if k in raw]
        if len(named) != 1 or set(raw) != {named[0], "hash"}:
            raise ValueError(f"a subject has `hash` and one of {', '.join(kinds)}")
        kind = named[0]
        if kind not in kinds:
            raise ValueError(f"a {kind} cannot be named here, only {' or '.join(kinds)}")
        name, digest = raw[kind], raw["hash"]
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise ValueError(f"{digest!r} is not a hash")
        problem = name_problem(kind, name)
        if problem:
            raise ValueError(problem)
        return cls(kind, name, digest)


def name_problem(kind: str, name: object) -> str | None:
    """Why `name` cannot name a thing of `kind`; None when it can."""
    if kind == "node":
        return None if is_node(name) else f"{name!r} is not a node's id"
    if kind == "macro":
        return None if isinstance(name, str) and MACRO.fullmatch(name) else f"{name!r} is not a macro's name"
    return label_problem(name)


@dataclass(frozen=True)
class Who:
    """Who acted: a person by the quilt's reviewer name, an agent by the name it writes as, or loom.

    Parameters
    ----------
    kind : str
        `person`, `agent` or `loom`.
    name : str, default ''
        Empty for loom.
    """

    kind: str
    name: str = ""

    def to_dict(self) -> dict[str, str]:
        """As a record writes it: `{"kind": "loom"}` or `{"kind": …, "name": …}`."""
        return {"kind": self.kind} if self.kind == "loom" else {"kind": self.kind, "name": self.name}

    @classmethod
    def from_dict(cls, raw: Any) -> Who:
        """Read who a record says acted; ValueError when it says nothing a reader can trust, a person whose name says it is an agent's among it."""
        if not isinstance(raw, dict):
            raise ValueError("`by` is an object")
        kind = raw.get("kind")
        if kind == "loom" and set(raw) == {"kind"}:
            return cls("loom")
        name = raw.get("name")
        if kind in ("person", "agent") and set(raw) == {"kind", "name"} and isinstance(name, str) and name.strip():
            if _CONTROL.search(name) or len(name) > LONGEST:
                raise ValueError(f"{name!r} is not a name")
            if kind == "person" and is_agent(name):
                raise ValueError(f"{name} calls itself an agent, so it does not act as a person")
            return cls(kind, name)
        raise ValueError("`by` names loom, or a person or an agent with a name")
