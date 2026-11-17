"""Suggested edits (plan 0.30, decision 10): old words replaced with new on a key, kept or discarded by the person, in their own log.

An edit names its key, the words it replaces as a selector (`anchor`; None means the key's body), the new text (`with`; empty deletes the quoted words), where the new text goes (`placement`: `replace` takes exactly the quoted words' place, `after` and `before` go right beside them), an optional `comment`, and the annotation it `answers`. It records the key's hash when it was written (`against`); on a key named by its place in its file, the line above the block (`near`); and at the head or foot of a body, the body's first or last `EDGE` characters (`edge`, '' for an empty body), as a quote's selector records the words either side of it. An insertion is placed only while those words still stand beside its place (`place`).

`.loom/edits/log.jsonl` holds its events, appended under the log's lock: `created`; `kept`, with the key's hash once the edit is in; `discarded`, with an optional `why`; and `reopened`, the viewer's undo of either. Replay gives each edit's status; whether its key already reads as it taken is computed, never stored. Keeping an edit that answers an open annotation resolves that annotation, with the edit as its reason. Keeping writes an edit into its file on the author's act, through the door (`pending.keep`, `loom.writes`), which journals its `kept` event with the write.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom.locks import locked
from loom.paths import EDIT_LOG
from loom.records.ids import EDIT, draw
from loom.records.selectors import Selector, find_quote
from loom.records.store import Records
from loom.scan.nodes import NodeRec
from loom.scan.scan import ScanResult

PLACEMENTS = ("replace", "after", "before")
STATUSES = ("open", "kept", "discarded")
EVENTS = ("created", "kept", "discarded", "reopened")
#: An edit's id: what a link, a command and the viewer name it by.
ID = re.compile(rf"^{EDIT}$")


@dataclass
class Edit:
    """One suggested edit as its events replay."""

    id: str
    author_kind: str  # agent | person
    author_id: str
    created: str
    target_key: str
    target_hash: str  # the key's hash when it was written
    selector: Selector | None  # the words it replaces or stands beside; None: the key's body
    with_text: str  # the new text; empty deletes the quoted words
    placement: str
    near: str = ""  # on a key named by place: the line above its block when it was written; '' when none was recorded
    edge: str | None = None  # a body's head or foot when written (`body_edge`); '' an empty body; None: unrecorded
    comment: str = ""
    answers: str | None = None  # the annotation it answers
    status: str = "open"
    why: str | None = None  # why it was discarded
    kept: dict[str, Any] | None = None  # `{hash}`: its key's text once it was kept
    acts: list[dict[str, Any]] = field(default_factory=list)  # every kept, discarded and reopened event, in order

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "author": {"kind": self.author_kind, "id": self.author_id},
            "created": self.created,
            "target": {"key": self.target_key, "hash": self.target_hash},
            "quote": self.selector.exact if self.selector else None,
            "with": self.with_text,
            "placement": self.placement,
            "comment": self.comment or None,
            "answers": self.answers,
            "status": self.status,
            "why": self.why,
        }


def log_path(root: Path) -> Path:
    return root / EDIT_LOG


def append(root: Path, event: dict[str, Any]) -> None:
    """Append one event under the log's lock."""
    p = log_path(root)
    with locked(p):
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def append_new(root: Path, event: dict[str, Any], date: str) -> str:
    """Append a new edit's `created` event under an id drawn for `date`; the read and the write share the log's lock, so no two writers draw one id."""
    p = log_path(root)
    with locked(p):
        ids = {e.id for e in replay(root)[0]}
        edit_id = draw(f"e-{date}-", ids)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**event, "id": edit_id}, ensure_ascii=False, sort_keys=True) + "\n")
    return edit_id


def replay(root: Path) -> tuple[list[Edit], list[str]]:
    """Every edit as it now stands, in the order written, and one problem per line that cannot be read; a bad line is skipped."""
    p = log_path(root)
    rel = EDIT_LOG
    out: dict[str, Edit] = {}
    problems: list[str] = []
    if not p.is_file():
        return [], problems
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"{rel}:{n}: {exc}")
            continue
        if not isinstance(e, dict) or e.get("event") not in EVENTS:
            problems.append(f"{rel}:{n}: not an edit's event")
            continue
        eid = str(e.get("id") or "")
        if not ID.match(eid):
            problems.append(f"{rel}:{n}: {eid!r} is not an edit's id")
            continue
        if e["event"] == "created":
            anchor = e.get("anchor")
            placement = str(e.get("placement") or "replace")
            if not e.get("target") or placement not in PLACEMENTS or not isinstance(e.get("with"), str):
                problems.append(f"{rel}:{n}: {eid} names no key, no placement or no text")
                continue
            out[eid] = Edit(
                id=eid,
                author_kind="agent" if e.get("kind") == "agent" else "person",
                author_id=str(e.get("author", "")),
                created=str(e.get("when", "")),
                target_key=str(e["target"]),
                target_hash=str(e.get("against") or ""),
                near=str(e.get("near") or ""),
                edge=e["edge"] if isinstance(e.get("edge"), str) else None,
                selector=Selector.from_dict(anchor) if isinstance(anchor, dict) else None,
                with_text=e["with"],
                placement=placement,
                comment=str(e.get("comment") or ""),
                answers=str(e["answers"]) if e.get("answers") else None,
            )
            continue
        edit = out.get(eid)
        if edit is None:
            problems.append(f"{rel}:{n}: {e['event']} names unknown edit {eid}")
            continue
        edit.acts.append(e)
        if e["event"] == "kept":
            edit.status, edit.why = "kept", None
            edit.kept = {"hash": e["hash"]} if e.get("hash") else None
        elif e["event"] == "discarded":
            edit.status, edit.why = "discarded", str(e.get("why") or "") or None
        else:
            edit.status, edit.why, edit.kept = "open", None, None
    return list(out.values()), problems


def find(root: Path, edit_id: str) -> Edit | None:
    return next((e for e in replay(root)[0] if e.id == edit_id), None)


# ---- where an edit's text goes ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Placed:
    """An edit's text placed in its key's text as it stands now."""

    key: str
    """The node the text goes in: the edit's target, or the result holding an equation it is on."""
    file: str
    """The file holding the node, relative to the quilt root."""
    own: str
    """The node's own text now, children cut out."""
    span: tuple[int, int]
    """Where the text goes in `own`: the quote it replaces, or the point beside it it is inserted at."""
    at: tuple[int, int]
    """The same place in `file`."""
    text: str
    """What goes there: the new text, with the space or line break that joins it to the text around it."""
    moved: bool
    """The node's text has changed since the edit was written, though its quote still stands."""

    @property
    def taken(self) -> str:
        """The node's own text with the edit in place."""
        a, b = self.span
        return self.own[:a] + self.text + self.own[b:]


class Unplaced(ValueError):
    """Why an edit cannot be placed: said to the author as written."""


def node_of(result: ScanResult, key: str) -> NodeRec | None:
    region = result.assembly.regions.get(key)
    node: NodeRec | None = result.nodes.get(region.container if region else key)
    return node


def home(result: ScanResult, edit: Edit) -> NodeRec | None:
    """The block `edit` is on now, or None when no block can be said to be it (`filed_on`).

    A key named by a label names its block. A key named by its place in its file names another block once one is put in before it, so an edit on one goes with the text it was filed on and the line above it, wherever they now stand, and is on no block when they do not say which.
    """
    from loom.records.store import filed_on

    return filed_on(
        result,
        edit.target_key,
        node_of(result, edit.target_key),
        edit.target_hash,
        edit.near,
        quoted=edit.selector is not None,
    )


def _delimiters(own: str) -> tuple[int, int] | None:
    """Where an environment's own text stops opening and starts closing: the end of its `\\begin{…}` and the start of its last `\\end{…}`; None for a text that is no environment."""
    opening = re.match(r"\s*\\begin\{[^}]*\}", own)
    closing = own.rfind("\\end{")
    if not opening or closing < opening.end():
        return None
    return opening.end(), closing


def misplaced(own: str, pieces: list[tuple[int, int, int]], span: tuple[int, int]) -> str | None:
    """Why the quoted words at `span` of a block's own text are no place for an edit, or None when they are.

    Two places are refused. Words that reach the block's `\\begin{…}` or `\\end{…}`: text put beside them lands outside the block, where nothing afterwards reads it as the edit taken, and Keep would write it again. And words that run across a child cut out of the own text: they are not in one piece of the file, and only the first piece would be replaced.
    """
    a, b = span
    edges = _delimiters(own)
    if edges is not None and (a < edges[0] or b > edges[1]):
        return "reach the block's \\begin or \\end, so the new text would land outside the block"
    if a < b and not any(start <= a and b <= start + length for start, _, length in pieces):
        return "run across a block inside this one, so they are not in one piece of the file"
    return None


def _balanced(text: str, at: int, opening: str, closing: str) -> int:
    """The index after the group `opening`…`closing` that opens at `at`, braces inside it kept whole; `at` itself when none opens there."""
    if at >= len(text) or text[at] != opening:
        return at
    depth = braces = 0
    i = at
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if opening != "{" and ch in "{}":
            braces += 1 if ch == "{" else -1
        elif braces == 0 and ch == opening:
            depth += 1
        elif braces == 0 and ch == closing:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return at


def body_span(own: str) -> tuple[int, int]:
    """The key's body in its own text: after `\\begin{…}`, its optional title, `\\label{…}` and leading `\\uses{…}`, and before `\\end{…}`.

    A text that is no environment is all body.
    """
    m = re.match(r"\s*\\begin\{[^}]*\}", own)
    end = own.rfind("\\end{")
    if not m or end < m.end():
        return 0, len(own)
    at = _balanced(own, m.end(), "[", "]")
    while True:
        head = re.match(r"\s*\\(label|uses)\{", own[at:])
        if not head:
            break
        at = _balanced(own, at + head.end() - 1, "{", "}")
    # the body begins on the line after its head, and ends before the whitespace that precedes `\end`
    start = at + 1 if own[at : at + 1] == "\n" else at
    stop = end
    while stop > start and own[stop - 1] in " \t\n":
        stop -= 1
    return start, stop


#: How many characters of a body's head or foot an insertion at it records (`edge`), as a quote's selector records its neighbours (`selectors.CONTEXT`).
EDGE = 32


def body_edge(own: str, placement: str) -> str:
    """The body's last (`after`) or first (`before`) `EDGE` characters: what `loom suggest` records beside an insertion at its foot or head."""
    a, b = body_span(own)
    return own[max(a, b - EDGE) : b] if placement == "after" else own[a : min(b, a + EDGE)]


def _after(text: str, at: int, words: str) -> int | None:
    """Where `words` ends when it stands right after `at` in `text`, whitespace compared normalised; `at` for words that are only whitespace, None when they do not stand there."""
    if not words.split():
        return at
    m = re.compile(r"\s*" + _words(words).pattern).match(text, at)
    return m.end() if m else None


def _before(text: str, at: int, words: str) -> int | None:
    """Where `words` starts when it stands right before `at` in `text`, as `_after` reads it."""
    if not words.split():
        return at
    start = max(0, at - 4 * len(words) - 256)
    m = re.compile(_words(words).pattern + r"\s*\Z").search(text[start:at])
    return start + m.start() if m else None


def _beside(edit: Edit, own: str, span: tuple[int, int]) -> str | None:
    """Why the words recorded beside an insertion's place no longer stand there in `own`, or None when they do.

    Beside a quote at `span` these are its selector's `suffix` (`after`) or `prefix` (`before`); at a body's foot or head, `span` the body, its `edge`, and an empty `edge` is a body that was empty. An edit that recorded none is not judged.
    """
    a, b = span
    if edit.selector is not None:
        if edit.placement == "after" and _after(own, b, edit.selector.suffix) is None:
            return f"the words right after the text {edit.id} quotes have changed since it was suggested"
        if edit.placement == "before" and _before(own, a, edit.selector.prefix) is None:
            return f"the words right before the text {edit.id} quotes have changed since it was suggested"
        return None
    if edit.edge is None:
        return None
    end = "end" if edit.placement == "after" else "head"
    if not edit.edge.split():
        return (
            None
            if not own[a:b].strip()
            else f"the body {edit.id} goes in was empty when it was suggested, and is not now"
        )
    if edit.placement == "after":
        at = _before(own, b, edit.edge)
        stands = at is not None and at >= a
    else:
        to = _after(own, a, edit.edge)
        stands = to is not None and to <= b
    return None if stands else f"the {end} of the body {edit.id} goes at has changed since it was suggested"


def _joined(own: str, point: int, text: str, before: bool) -> str:
    """The text with a space to join it to the word it lands against, when neither side carries whitespace."""
    left = own[point - 1 : point] if point > 0 else " "
    right = own[point : point + 1] if point < len(own) else " "
    if before:
        return text + ("" if text[-1:].isspace() or right.isspace() or not right else " ")
    return ("" if text[:1].isspace() or left.isspace() or not left else " ") + text


def place(result: ScanResult, edit: Edit) -> Placed:
    """Where `edit`'s text goes in its key's text now.

    Parameters
    ----------
    result : ScanResult
        A scan of the quilt now.
    edit : Edit
        The suggested edit.

    Returns
    -------
    Placed

    Raises
    ------
    Unplaced
        When its key is gone or, named by place, no longer says which block; when its quote no longer stands in the text exactly once; when the quoted words are no place for an edit (`misplaced`); and when an insertion's recorded neighbours no longer stand beside its place (`_beside`), so that text the person wrote there since is never written beside again.
    """
    from loom.scan.owntext import key_hash

    node = home(result, edit)
    if node is None or node.file not in result.files:
        there = node_of(result, edit.target_key)
        if node is None and there is not None:
            raise Unplaced(
                f"{edit.id} was suggested on {edit.target_key}, a block named by its place in {there.file}; the block there has changed since or reads the same as another, so which block it is on is not known"
            )
        raise Unplaced(f"{edit.target_key}, which {edit.id} is on, is no longer in the quilt")
    own, pieces = Records.own_pieces(result, node)
    new = edit.with_text
    if edit.selector is None:
        a, b = body_span(own)
        changed = _beside(edit, own, (a, b)) if edit.placement != "replace" else None
        if changed is not None:
            raise Unplaced(f"{changed} in {node.key}, so it is not written in blind")
        if edit.placement == "after":
            span, text = (b, b), ("\n" if a < b else "") + new
        elif edit.placement == "before":
            span, text = (a, a), new + ("\n" if a < b else "")
        else:
            span, text = (a, b), new
    else:
        found = find_quote(own, edit.selector.exact)
        if not found:
            raise Unplaced(f"the text {edit.id} quotes no longer stands in {node.key}")
        if len(found) > 1:
            raise Unplaced(
                f"the text {edit.id} quotes now stands {len(found)} times in {node.key}, so where it goes is not known"
            )
        a, b = found[0]
        why = misplaced(own, pieces, (a, b))
        if why is not None:
            raise Unplaced(f"the words {edit.id} quotes in {node.key} {why}")
        changed = _beside(edit, own, (a, b)) if new and edit.placement != "replace" else None
        if changed is not None:
            raise Unplaced(f"{changed} in {node.key}, so it is not written in blind")
        if edit.placement == "after":
            span, text = (b, b), _joined(own, b, new, before=False) if new else ""
        elif edit.placement == "before":
            span, text = (a, a), _joined(own, a, new, before=True) if new else ""
        else:
            span, text = (a, b), new
    at = Records.to_file_span(pieces, span) if span[0] < span[1] else _point(pieces, span[0])
    if at is None and not pieces:
        # a key with no text of its own, as an empty file: the text goes where it starts, or where it ends after it
        at = (node.end, node.end) if edit.placement == "after" else (node.start, node.start)
    if at is None:
        raise Unplaced(f"the place {edit.id} names in {node.key} is not in one piece of its file")
    return Placed(node.key, node.file, own, span, at, text, edit.target_hash != key_hash(result, node.key))


def compose(result: ScanResult, edits: list[Edit]) -> list[tuple[Edit, Placed | Unplaced]]:
    """Several edits placed together, in the order they were written: each placed in its key's text now (`place`), and one whose place meets an earlier one's in the same file Unplaced, since the earlier stands there first.

    Parameters
    ----------
    result : ScanResult
        A scan of the quilt now.
    edits : list of Edit
        The suggested edits.

    Returns
    -------
    list of (Edit, Placed or Unplaced)
        In the order written. Two places meet when they overlap, or one is a point inside or at the edge of the other.
    """
    out: list[tuple[Edit, Placed | Unplaced]] = []
    held: dict[str, list[tuple[int, int, str]]] = {}
    for edit in sorted(edits, key=lambda e: e.created):
        try:
            placed = place(result, edit)
        except Unplaced as exc:
            out.append((edit, exc))
            continue
        a, b = placed.at
        clash = next(
            (
                other
                for x, y, other in held.get(placed.file, [])
                if (a < y and x < b) or (a == b and x <= a <= y) or (x == y and a <= x <= b)
            ),
            None,
        )
        if clash is not None:
            out.append(
                (edit, Unplaced(f"{clash}, suggested before it, is on the same words; keep or discard that first"))
            )
            continue
        held.setdefault(placed.file, []).append((a, b, edit.id))
        out.append((edit, placed))
    return out


def _point(pieces: list[tuple[int, int, int]], at: int) -> tuple[int, int] | None:
    """A point of the own text in the file: inside a piece, or at the end of the one it closes."""
    for cstart, fstart, length in pieces:
        if cstart <= at <= cstart + length:
            return fstart + (at - cstart), fstart + (at - cstart)
    return None


def taken_file(result: ScanResult, placed: Placed) -> str:
    """The text of the node's file with the edit in place."""
    text = result.files[placed.file].text
    a, b = placed.at
    return text[:a] + placed.text + text[b:]


def patch(result: ScanResult, placed: Placed) -> str:
    """The edit in place, as a unified diff of the node's file against the quilt root."""
    from loom.reshape.ids import unified_diff

    return unified_diff(result.files[placed.file].text, taken_file(result, placed), placed.file)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _words(text: str) -> re.Pattern[str]:
    """`text` as a pattern that matches it with any run of whitespace for each of its own."""
    return re.compile(r"\s+".join(re.escape(w) for w in text.split()))


#: The share of a new text's words that must stand in order for it to read as written in and edited since, and the fewest words that judgement is made on: a shorter text must stand as it is.
WRITTEN_SHARE = 0.9
WRITTEN_WORDS = 20


def _written_since(edit: Edit, whole: str) -> bool:
    """Whether most of the edit's new text stands in `whole`, its words in order with others between: written in, then edited.

    A text the person took in and then worked inside no longer stands as it was suggested, and writing it again would put in a second copy.
    """
    new = edit.with_text.split()
    if len(new) < WRITTEN_WORDS:
        return False
    matcher = difflib.SequenceMatcher(None, new, whole.split(), autojunk=False)
    return sum(b.size for b in matcher.get_matching_blocks()) >= WRITTEN_SHARE * len(new)


def taken_how(result: ScanResult, edit: Edit) -> str | None:
    """How the block's text now reads as the edit taken: `as-written` when its new text stands, `edited` when most of it does with the person's words between, None when it is not taken.

    The new text is looked for in the block's whole text, its children's included, since text that opens a section or an environment is read as the block's child once it is in. A replacement is taken when its text stands and its quote no longer does in the block's own text outside it, or, edited, when its quote is gone from the own text; an insertion when its text stands; a deletion when its quote is gone from the own text. Whitespace is compared normalised, as a quote is.
    """
    node = home(result, edit)
    if node is None or node.file not in result.files:
        return None
    text = result.files[node.file].text
    quote = _flat(edit.selector.exact) if edit.selector else ""
    if not edit.with_text.strip():
        return "as-written" if quote and quote not in _flat(Records.own_pieces(result, node)[0]) else None
    holes = [m.span() for m in _words(edit.with_text).finditer(text, node.start, node.end)]
    if not holes:
        if not _written_since(edit, text[node.start : node.end]):
            return None
        if edit.placement == "replace" and quote and quote in _flat(Records.own_pieces(result, node)[0]):
            return None
        return "edited"
    if edit.placement != "replace" or not quote:
        return "as-written"

    def blanked(a: int, b: int) -> str:
        piece = text[a:b]
        for x, y in holes:
            lo, hi = max(a, x), min(b, y)
            if lo < hi:
                piece = piece[: lo - a] + "\0" * (hi - lo) + piece[hi - a :]
        return piece

    return "as-written" if quote not in _flat("".join(blanked(a, b) for a, b in node.own)) else None


def is_taken(result: ScanResult, edit: Edit) -> bool:
    """Whether the block's text now reads as the edit taken, as written or edited since (`taken_how`)."""
    return taken_how(result, edit) is not None


# ---- what the person does with one ----------------------------------------------------------------------------------


class EditRefused(Exception):
    """An edit that cannot be written, kept or discarded, and why in the person's words; `code` is the write API's."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def generation(edit: Edit) -> int:
    """How many times `edit` has been opened again: the Keep of an edit is named by its id and this (`<id>:<generation>`), so an edit undone and kept again is a new write, and no other can repeat the name."""
    return sum(1 for e in edit.acts if e.get("event") == "reopened")


def kept_event(edit: Edit, writer: tuple[str, str], key_hash: str) -> dict[str, Any]:
    """The `kept` event of `edit`, with the hash of its key's text with the edit in; what `pending.keep` journals with the write (`loom.writes`)."""
    from loom.clock import stamp

    akind, aid = writer
    return {"event": "kept", "id": edit.id, "when": stamp(), "author": aid, "kind": akind, "hash": key_hash}


def answered_event(root: Path, edit: Edit, writer: tuple[str, str]) -> dict[str, Any] | None:
    """The `resolved` event for the open annotation `edit` answers, with the edit as the reason; None when it answers none, or one that is not open or whose type does not open."""
    from loom.clock import stamp
    from loom.records.annotations import find_annotation, load_records
    from loom.records.types import load_types

    found = find_annotation(load_records(root)[0], edit.answers) if edit.answers else None
    if found is None:
        return None
    ann = found[1]
    t = load_types(root).get(ann.type)
    if ann.status != "open" or t is None or not t.open:
        return None
    akind, aid = writer
    return {
        "event": "resolved",
        "id": ann.id,
        "when": stamp(),
        "author": aid,
        "kind": akind,
        "body": f"kept suggested edit {edit.id}",
    }


def discard(root: Path, edit: Edit, writer: tuple[str, str], why: str | None = None, *, undo: bool = False) -> str:
    """Discard `edit`, with why; with `undo`, open a kept or discarded edit again. A person may discard any edit, an agent only its own. Returns what to say."""
    from loom.clock import stamp

    akind, aid = writer
    if akind == "agent" and not (edit.author_kind == "agent" and edit.author_id == aid):
        raise EditRefused(
            "not-yours", f"{edit.id} is {edit.author_id}'s, and an agent discards only its own edits", 403
        )
    if undo:
        if edit.status == "open":
            raise EditRefused("not-settled", f"{edit.id} is open; there is nothing to undo")
        append(root, {"event": "reopened", "id": edit.id, "when": stamp(), "author": aid, "kind": akind})
        return f"reopened {edit.id}"
    if edit.status != "open":
        raise EditRefused("not-open", f"{edit.id} is {edit.status} already")
    event: dict[str, Any] = {"event": "discarded", "id": edit.id, "when": stamp(), "author": aid, "kind": akind}
    if why:
        event["why"] = why
    append(root, event)
    return f"discarded {edit.id}"
