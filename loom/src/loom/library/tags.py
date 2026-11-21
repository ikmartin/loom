"""The tag log, `.loom/records/tags/log.jsonl` (docs/design/library.md, "Digesting and checking"): one line for each tag put on a node or taken off it, with who and when, appended and never rewritten.

A tag is a record about a node, so tagging changes no node's file and no hash. A node's tags are replayed from the log: a tag stays on while anyone who put it on still has it there; a person's untag takes it off for everyone, an agent's only its own. A tag keeps the case it was typed in, composed (NFC), and two equal ignoring case are one tag, shown as it was first written. A line that is not a tag or an untag is skipped and reported (`loom:foreign-tags`), and the rest still loads.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom import clock
from loom.library import ids
from loom.locks import locked
from loom.paths import TAG_LOG
from loom.scan.model import Diagnostic, Location

EVENTS = ("tag", "untag")
KINDS = ("person", "agent")
#: The longest tag, in characters.
LONGEST = 64
#: Control characters, but the whitespace a person types (tab, line feed, vertical tab, form feed, carriage return), which becomes a space.
_CONTROL = re.compile(r"[\x00-\x08\x0e-\x1f\x7f-\x9f]")


class TagRefused(ValueError):
    """A tag or an untag loom will not write, with the sentence that says why."""


def fold(tag: str) -> str:
    """A tag as tags are compared: composed (NFC), then without case, so `café` typed either way is one tag."""
    return unicodedata.normalize("NFC", tag).casefold()


def normalise(word: str) -> str:
    """A tag as it is written: composed (NFC), stripped, each run of whitespace inside it one space, its case kept.

    Parameters
    ----------
    word : str
        What was typed.

    Returns
    -------
    str
        The tag.

    Raises
    ------
    TagRefused
        For an empty tag, one longer than `LONGEST`, or one holding a control character.
    """
    if _CONTROL.search(word):
        raise TagRefused("a tag holds no control characters")
    tag = unicodedata.normalize("NFC", " ".join(word.split()))
    if not tag:
        raise TagRefused("a tag has at least one character other than a space")
    if len(tag) > LONGEST:
        raise TagRefused(f"a tag is at most {LONGEST} characters, and {tag[:20]}… is {len(tag)}")
    return tag


@dataclass
class Tags:
    """The tags as the log stands: who holds each tag on each node, each tag's first spelling, and the lines skipped."""

    holders: dict[str, dict[str, set[str]]] = field(default_factory=dict)
    spelled: dict[str, str] = field(default_factory=dict)
    skipped: list[tuple[int, str]] = field(default_factory=list)

    def of(self, node: str) -> list[str]:
        """The tags on `node`, as first written, in alphabetical order ignoring case."""
        on = self.holders.get(node, {})
        return sorted((self.spelled[f] for f, who in on.items() if who), key=str.casefold)

    def held(self, node: str, tag: str) -> set[str]:
        """Who has `tag` on `node`."""
        return set(self.holders.get(node, {}).get(fold(tag), set()))

    def nodes(self, tag: str) -> list[str]:
        """The nodes `tag` is on, in id order."""
        folded = fold(tag)
        return sorted(n for n, on in self.holders.items() if on.get(folded))

    def apply(self, event: dict[str, Any]) -> None:
        folded = fold(event["tag"])
        on = self.holders.setdefault(event["node"], {})
        if event["event"] == "tag":
            self.spelled.setdefault(folded, event["tag"])
            on.setdefault(folded, set()).add(event["by"])
        elif event["kind"] == "person":
            on.pop(folded, None)
        else:
            on.get(folded, set()).discard(event["by"])


def _why_not(event: Any) -> str | None:
    """What makes a parsed line no tag event, or None when it is one."""
    if not isinstance(event, dict):
        return "it is not a JSON object"
    if event.get("event") not in EVENTS:
        return "its event is neither tag nor untag"
    if not isinstance(event.get("node"), str) or ids.parse_id(event["node"]) is None:
        return "its node is not a node's id"
    tag = event.get("tag")
    if not isinstance(tag, str):
        return "it has no tag"
    try:
        if normalise(tag) != tag:
            return "its tag is not as loom writes one"
    except TagRefused as exc:
        return str(exc)
    if not isinstance(event.get("by"), str) or not event["by"].strip():
        return "it does not say who"
    if event.get("kind") not in KINDS:
        return "it does not say whether a person or an agent"
    if not isinstance(event.get("at"), str):
        return "it does not say when"
    return None


def replay(root: Path) -> Tags:
    """The tags as the quilt's log stands, every line read in order.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Tags
        Empty when there is no log.
    """
    tags = Tags()
    path = root / TAG_LOG
    if not path.is_file():
        return tags
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            tags.skipped.append((number, "it is not JSON"))
            continue
        why = _why_not(event)
        if why:
            tags.skipped.append((number, why))
            continue
        tags.apply(event)
    return tags


def problems(tags: Tags) -> list[Diagnostic]:
    """One `loom:foreign-tags` for each line of the log `replay` skipped, naming the line and why."""
    return [
        Diagnostic(
            "warning",
            "loom:foreign-tags",
            f"Line {number} of {TAG_LOG} is not a tag or an untag ({why}), so it is skipped.",
            [Location(TAG_LOG, number)],
            subject="record",
        )
        for number, why in tags.skipped
    ]


def _append(root: Path, event: dict[str, Any]) -> None:
    """Append one event as a line, after a line feed when the log's last line was cut short, so a crash mid-line costs that line alone."""
    path = root / TAG_LOG
    with path.open("a+b") as fh:
        cut = fh.tell() > 0 and os.pread(fh.fileno(), 1, fh.tell() - 1) != b"\n"
        fh.write(
            (b"\n" if cut else b"") + (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        )


def tag(root: Path, node: str, word: str, *, by: str, kind: str) -> bool:
    """Put a tag on a node, unless whoever is tagging already has it there.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        The node's id; its file must be in the library.
    word : str
        The tag as typed; `normalise` makes it the tag.
    by : str
        Who is tagging, by name.
    kind : str
        `person` or `agent`.

    Returns
    -------
    bool
        Whether a line was written.

    Raises
    ------
    TagRefused
        For what is no node's id, a node not in the library (an id in another case is not it), or a tag `normalise` refuses.

    See Also
    --------
    untag : take a tag off.
    """
    written = normalise(word)
    _who(by, kind)
    _id(node)
    from loom.library.store import exists  # the store reads the index, which replays this log

    if not exists(root, node):
        raise TagRefused(f"{node} is not in the library, so it cannot be tagged")
    path = root / TAG_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        if by.strip() in replay(root).held(node, written):
            return False
        _append(
            root, {"event": "tag", "node": node, "tag": written, "by": by.strip(), "kind": kind, "at": clock.stamp()}
        )
    return True


def untag(root: Path, node: str, word: str, *, by: str, kind: str) -> bool:
    """Take a tag off a node: a person's untag takes it off for everyone, an agent's only its own.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        The node's id.
    word : str
        The tag, in any case.
    by : str
        Who is taking it off, by name.
    kind : str
        `person` or `agent`.

    Returns
    -------
    bool
        Whether a line was written; False when the tag is not on the node.

    Raises
    ------
    TagRefused
        For what is no node's id, or when an agent takes off a tag it did not put on.

    See Also
    --------
    tag : put a tag on.
    """
    written = normalise(word)
    _who(by, kind)
    _id(node)
    path = root / TAG_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        tags = replay(root)
        holders = tags.held(node, written)
        if not holders:
            return False
        if kind == "agent" and by.strip() not in holders:
            shown = tags.spelled.get(written.casefold(), written)
            raise TagRefused(
                f"an agent takes off only its own tags, and {', '.join(sorted(holders))} put {shown} on {node}"
            )
        _append(
            root, {"event": "untag", "node": node, "tag": written, "by": by.strip(), "kind": kind, "at": clock.stamp()}
        )
    return True


def _id(node: str) -> None:
    if ids.parse_id(node) is None:
        raise TagRefused(f"{node!r} is not a node's id, as tq-00K3 is")


def _who(by: str, kind: str) -> None:
    if not by.strip():
        raise TagRefused("a tag says who put it on, and no name was given")
    if kind not in KINDS:
        raise TagRefused(f"who tags is a person or an agent, not {kind}")
