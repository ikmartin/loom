"""One list of what waits on the person: the open suggested edits and, where the quilt tracks edits (`[review] track_edits`), the in-place edits to the open files since their look, cut by words; and the two verbs on each, keep and discard.

An in-place change is a run of words that differs between the person's look (`looks.py`) and the file now: words the diff finds apart by fewer than `NEAR` words are one change, never across a blank line, and a file new or gone since the look is one change. Its id is `c-` and eight hex digits of a hash of its path, its old and new text and the 32 characters of the look before it, so it stands while it does, whatever changes elsewhere. A suggested edit is its record's (`records/edits.py`), placed in its key's text now; several on one key combine (`edits.compose`).

Keeping an in-place change puts it into the look alone; discarding writes its old words back, a version of each document it is part of kept first (P7), with an `undo` line in the ledger. Keeping a suggested edit writes it into its file and records it kept, through the door (`loom.writes`), every decision made again under its lock; discarding records it discarded. Every write loom makes on the person's word goes into their look too, so the file and the look agree on those words after it. Keeping carries each annotation on the changed words onto the new ones (`records/carry.py`); discarding writes no annotation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.records.edits import Edit, Placed
    from loom.scan.nodes import NodeRec
    from loom.scan.scan import ScanResult

#: Changed words fewer than this many words apart are one change.
NEAR = 3
#: How much of the look before a change its id is made with.
BEFORE = 32
STATES = ("ready", "taken", "unplaced", "on-a-copy")
_WORD = re.compile(r"\S+")
_BLANK = re.compile(r"\n[ \t]*\n")


@dataclass
class Pending:
    """One change waiting on the person.

    `old` and `new` are its words, trimmed; `at` is where it stands in the file now, `[start, end]` of its new words for an in-place change and of the words it replaces for a suggested edit. `was` is an in-place change's place in the look's text, and `span` its place in the file now, each with the space on both sides; `edit` is a suggested edit's record.
    """

    id: str
    kind: str  # edit | suggested
    path: str
    key: str | None
    documents: list[str]
    old: str
    new: str
    at: list[int]
    author: str | None = None
    created: str | None = None
    comment: str = ""
    answers: str | None = None
    state: str = "ready"
    why: str | None = None
    blocks: list[str] = field(default_factory=list)
    was: tuple[int, int] = (0, 0)
    span: tuple[int, int] = (0, 0)
    edit: Edit | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "key": self.key,
            "documents": list(self.documents),
            "old": self.old,
            "new": self.new,
            "at": list(self.at),
            "author": self.author,
            "created": self.created,
            "comment": self.comment or None,
            "answers": self.answers,
            "state": self.state,
            "why": self.why,
        }


class PendingRefused(Exception):
    """A keep or a discard that cannot be done, and why; `code` is the write API's."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ---- cutting a file's change into changes by words ----------------------------------------------------------------


def cut(old: str, new: str) -> list[tuple[int, int, int, int]]:
    """The changes between two texts, by words: `(o0, o1, n0, n1)` each, the stretch of `old` and of `new` it replaces, from the end of the last word the two share before it to the start of the first they share after it.

    The diff runs over the words alone, so a change of spacing between words that stand is none. Two changes fewer than `NEAR` words apart are one, unless a blank line stands between them. Each stretch carries the space around its words, so putting one stretch in place of the other gives exactly either text.
    """
    import difflib

    left = [(m.group(), m.start(), m.end()) for m in _WORD.finditer(old)]
    right = [(m.group(), m.start(), m.end()) for m in _WORD.finditer(new)]
    ops = [
        op
        for op in difflib.SequenceMatcher(
            None, [t[0] for t in left], [t[0] for t in right], autojunk=False
        ).get_opcodes()
        if op[0] != "equal"
    ]
    groups: list[list[int]] = []
    for _tag, a, b, c, d in ops:
        if groups:
            pa, pb, pc, pd = groups[-1]
            gap_old = old[left[pb - 1][2] if pb else 0 : left[a][1] if a < len(left) else len(old)]
            gap_new = new[right[pd - 1][2] if pd else 0 : right[c][1] if c < len(right) else len(new)]
            if a - pb < NEAR and not _BLANK.search(gap_old) and not _BLANK.search(gap_new):
                groups[-1] = [pa, b, pc, d]
                continue
        groups.append([a, b, c, d])
    out = []
    for a, b, c, d in groups:
        o0 = left[a - 1][2] if a else 0
        o1 = left[b][1] if b < len(left) else len(old)
        n0 = right[c - 1][2] if c else 0
        n1 = right[d][1] if d < len(right) else len(new)
        out.append((o0, o1, n0, n1))
    return out


def cuts(path: str, old: str, text: str | None) -> list[tuple[str, tuple[int, int], tuple[int, int]]]:
    """The changes of one file between its look's text `old` and its text now (None for a file gone), each as its id, its place in `old` and its place in the text now; a file new or gone since the look is one change."""
    new = text or ""
    spans = [(0, len(old), 0, len(new))] if not old or text is None else cut(old, text)
    return [(change_id(path, old[o0:o1], new[n0:n1], old[:o0]), (o0, o1), (n0, n1)) for o0, o1, n0, n1 in spans]


def change_id(path: str, old: str, new: str, before: str) -> str:
    """`c-` and eight hex digits of the change's path, its old and new text, and the look's text just before it."""
    said = "\0".join((path, old, new, before[-BEFORE:]))
    return "c-" + hashlib.sha256(said.encode("utf-8")).hexdigest()[:8]


# ---- the list --------------------------------------------------------------------------------------------------


def reviewer(result: ScanResult) -> str:
    """Whose look the changes are since: the reviewer name Review resolves; '' when there is none."""
    from loom.scan.quilt import reviewer_identity

    return reviewer_identity(result.quilt.root)[0] or ""


#: Each scan's in-place changes by reviewer, kept for the one scan they were cut against.
_INPLACE: dict[tuple[str, str], tuple[Any, dict[str, Any]]] = {}


#: Each scan's look texts by reviewer, kept for the one scan and the one state of the look they were read for.
_TEXTS: dict[tuple[str, str], tuple[Any, int, Any]] = {}


def look_texts(result: ScanResult, who: str) -> tuple[dict[str, str], dict[str, str | None]] | None:
    """`who`'s look as texts, `(look, now)` by path, for the files that changed since it; None before a first look, and when the quilt does not track edits (`[review] track_edits`). Read once for each scan and each state of the look."""
    from loom.looks import look_path

    if not result.quilt.config.track_edits:
        return None
    try:
        stamp = look_path(result.quilt.root, who).stat().st_mtime_ns if who else 0
    except OSError:
        stamp = 0
    key = (str(result.quilt.root), who)
    kept = _TEXTS.get(key)
    if kept is not None and kept[0] is result and kept[1] == stamp:
        return kept[2]  # type: ignore[no-any-return]
    out = _look_texts(result, who)
    _TEXTS[key] = (result, stamp, out)
    return out


def _look_texts(result: ScanResult, who: str) -> tuple[dict[str, str], dict[str, str | None]] | None:
    from loom.files import is_latex_aux
    from loom.looks import open_texts, read_look
    from loom.records.snapshots import read_raw
    from loom.scan.hashing import sha256

    quilt = result.quilt
    look = read_look(quilt.root, who) if who else None
    if look is None:
        return None
    current = open_texts(quilt)
    then: dict[str, str] = {}
    now: dict[str, str | None] = {}
    # a look taken before LaTeX's auxiliary files were left out of it may still hold them
    for rel in sorted(set(current) | {f for f in look.files if not is_latex_aux(f)}):
        held = look.files.get(rel)
        text = current.get(rel)
        if held == (sha256(text) if text is not None else None):
            continue
        then[rel] = (read_raw(quilt.root, held, quilt.history_dir) or "") if held else ""
        now[rel] = text
    return then, now


def in_place(result: ScanResult, who: str | None = None) -> list[Pending]:
    """The in-place changes since `who`'s look (the reviewer's by default), by path and place; empty before a first look, and when the quilt does not track edits."""
    from loom.history.acts import documents_reaching

    who = reviewer(result) if who is None else who
    root = str(result.quilt.root)
    texts = look_texts(result, who)
    kept = _INPLACE.get((root, who))
    if kept is not None and kept[0] is result and kept[1]["texts"] is texts:
        return list(kept[1]["list"])
    out: list[Pending] = []
    if texts is not None:
        then, now = texts
        for rel in then:
            old, text = then[rel], now[rel]
            docs = documents_reaching(result, [rel])
            new_text = text or ""
            for cid, (o0, o1), (n0, n1) in cuts(rel, old, text):
                p = Pending(
                    id=cid,
                    kind="edit",
                    path=rel,
                    key=None,
                    documents=docs,
                    old=old[o0:o1].strip(),
                    new=new_text[n0:n1].strip(),
                    at=[_inside(new_text, n0, n1)[0], _inside(new_text, n0, n1)[1]],
                    was=(o0, o1),
                    span=(n0, n1),
                )
                p.key, p.blocks = _blocks(result, rel, p.at[0], p.at[1])
                out.append(p)
    _INPLACE[(root, who)] = (result, {"list": out, "texts": texts})
    return list(out)


def _inside(text: str, a: int, b: int) -> tuple[int, int]:
    """`text[a:b]` less the space either side; a point where it holds only space."""
    head = len(text[a:b]) - len(text[a:b].lstrip())
    tail = len(text[a:b]) - len(text[a:b].rstrip())
    return (a + head, b - tail) if a + head < b - tail else (a + head, a + head)


def _blocks(result: ScanResult, path: str, a: int, b: int) -> tuple[str | None, list[str]]:
    """The statement or proof holding `a`..`b` of `path` (the innermost), and every one it touches."""
    spans = [
        (n.start, n.end, key)
        for key, n in result.nodes.items()
        if n.file == path and n.kind in ("environment", "proof")
    ]
    touched = [key for s, e, key in spans if (s < b and a < e) or (a == b and s <= a <= e)]
    holding = [(e - s, key) for s, e, key in spans if s <= a and b <= e]
    return (min(holding)[1] if holding else None), sorted(touched, key=lambda k: result.nodes[k].start)


def suggested(result: ScanResult) -> list[Pending]:
    """The open suggested edits, each placed in its key's text now with its state: `ready` to keep, `taken` when loom wrote it already (the door's journal) or its key reads as it taken, `unplaced` when its words no longer stand once (or a suggested edit before it is on them) or its file is not UTF-8, `on-a-copy` when none of the person's documents reads its key."""
    from loom.history.acts import documents_reaching
    from loom.records.edits import Placed, compose, generation, home, replay, taken_how
    from loom.writes import written

    out: list[Pending] = []
    edits = [e for e in replay(result.quilt.root)[0] if e.status == "open"]
    loom_wrote = written(result.quilt.root, result.quilt.history_dir)
    for edit, placed in compose(result, edits):
        node = home(result, edit)
        p = Pending(
            id=edit.id,
            kind="suggested",
            path=node.file if node is not None else "",
            key=node.key if node is not None else edit.target_key,
            documents=documents_reaching(result, [node.file]) if node is not None else [],
            old=edit.selector.exact if edit.selector else "",
            new=edit.with_text,
            at=[0, 0],
            author=edit.author_id,
            created=edit.created,
            comment=edit.comment,
            answers=edit.answers,
            edit=edit,
        )
        if isinstance(placed, Placed):
            p.at, p.span = list(placed.at), placed.at
            p.old = placed.own[placed.span[0] : placed.span[1]].strip() if edit.selector else p.old
            p.blocks = [placed.key]
        # a file no document reads yet, as an empty one, is the person's to write
        if (
            node is not None
            and node.reached_by
            and not any(result.document_role(d) == "person" for d in node.reached_by)
        ):
            copy = next((d for d in node.reached_by if result.document_role(d) == "agent"), None)
            p.state = "on-a-copy"
            p.why = (
                f"It is on the agent's copy “{copy.rsplit('/', 1)[-1]}”; it comes in with the copy"
                if copy
                else "It is on a block none of your documents reads"
            )
        elif node is not None and node.file in result.files and result.files[node.file].encoding != "utf-8":
            p.state, p.why = "unplaced", _not_utf8(node.file)
        elif f"{edit.id}:{generation(edit)}" in loom_wrote:
            p.state = "taken"
            p.why = "Loom wrote it in already; keeping it records it kept and writes nothing"
        elif (how := taken_how(result, edit)) is not None:
            p.state = "taken"
            p.why = (
                "Its text is in its block already, edited since; keeping it records it kept and writes nothing"
                if how == "edited"
                else "Its block reads as it taken already; keeping it records it kept"
            )
        elif not isinstance(placed, Placed):
            p.state, p.why = "unplaced", str(placed)
        out.append(p)
    return out


def pending(result: ScanResult, who: str | None = None) -> list[Pending]:
    """Every change waiting on the person: the in-place changes since `who`'s look (the reviewer's by default), then the open suggested edits, each list in its files' order.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    who : str, optional
        Whose look; default the reviewer name Review resolves.

    Returns
    -------
    list of Pending
        Each with its id, kind, place and state.
    """
    return in_place(result, who) + suggested(result)


# ---- what the person kept: a key's text with the changes still waiting put back ------------------------------------


@dataclass
class Kept:
    """A node's own text as the person has kept it, and how it maps onto the text now: `segments` are `(kept start, kept end, now start, now end, change id or None)`, in order."""

    text: str
    segments: list[tuple[int, int, int, int, str | None]]

    def to_now(self, a: int, b: int) -> tuple[tuple[int, int], list[str]]:
        """A span of the kept text as a span of the text now, and the changes it touches: a place inside a change goes to that change's new words."""
        touched: list[str] = []
        lo = hi = None
        for k0, k1, n0, n1, cid in self.segments:
            if cid is not None and (k0 < b and a < k1 or (a == b and k0 <= a <= k1)):
                touched.append(cid)
            if lo is None and a <= k1:
                lo = n0 + (a - k0) if cid is None else n0
            if hi is None and b <= k1:
                hi = n0 + (b - k0) if cid is None else n1
        end = self.segments[-1][3] if self.segments else 0
        return ((lo if lo is not None else end), (hi if hi is not None else end)), touched


def kept_own(result: ScanResult, node: NodeRec) -> Kept | None:
    """`node`'s own text with every in-place change still waiting put back as it was at the look, mapped onto the text now; None when no change waits in it.

    What the person has kept is what an annotation is read against (decision 11 of plan 0.30): one written before an agent's in-place edit stays where it was until the edit is kept or discarded.
    """
    from loom.records.store import Records

    changes = [c for c in in_place(result) if c.path == node.file and c.kind == "edit"]
    if not changes:
        return None
    texts = look_texts(result, reviewer(result))
    if texts is None:
        return None
    then = texts[0].get(node.file, "")
    src = result.files[node.file].text
    _own, pieces = Records.own_pieces(result, node)
    parts: list[str] = []
    segments: list[tuple[int, int, int, int, str | None]] = []
    k = c = 0  # where the kept text and the text now have got to
    hit = False
    for _cstart, fstart, length in pieces:
        pos, stop = fstart, fstart + length
        for ch in sorted(changes, key=lambda x: x.span[0]):
            n0, n1 = ch.span
            if n0 < pos or n1 > stop or (n0 == n1 and not pos < n0 < stop):
                continue
            if n0 > pos:
                parts.append(src[pos:n0])
                segments.append((k, k + n0 - pos, c, c + n0 - pos, None))
                k, c = k + n0 - pos, c + n0 - pos
            old = then[ch.was[0] : ch.was[1]]
            parts.append(old)
            segments.append((k, k + len(old), c, c + n1 - n0, ch.id))
            k, c, pos, hit = k + len(old), c + n1 - n0, n1, True
        if stop > pos:
            parts.append(src[pos:stop])
            segments.append((k, k + stop - pos, c, c + stop - pos, None))
            k, c = k + stop - pos, c + stop - pos
    return Kept("".join(parts), segments) if hit else None


# ---- keeping and discarding -----------------------------------------------------------------------------------------


def _chosen(result: ScanResult, who: str, ids: list[str]) -> list[Pending]:
    by_id = {p.id: p for p in pending(result, who)}
    gone = [i for i in ids if i not in by_id]
    if gone:
        raise PendingRefused("no-such-change", f"no change {gone[0]} waits on you; `loom changes` lists them", 404)
    return [by_id[i] for i in dict.fromkeys(ids)]


def keep(
    result: ScanResult, who: str, ids: list[str], writer: tuple[str, str], said: list[str] | None = None
) -> tuple[list[str], list[dict[str, str]]]:
    """Keep the changes `ids`: an in-place change goes into `who`'s look alone; a suggested edit is written into its file through the door (`loom.writes`), a version of each document it changes kept first, and recorded kept, resolving the annotation it answers. Each annotation on the changed words is carried onto the new ones.

    Every decision is made again under the door's lock (`_keep_suggested`): the list was made before it.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    who : str
        Whose look.
    ids : list of str
        The changes, by id.
    writer : (str, str)
        Who keeps them, as `_annotator` gives it.
    said : list of str, optional
        Where to say which versions were kept.

    Returns
    -------
    (list of str, list of dict)
        The ids kept, and `{id, why}` for each that cannot be, with `code` where it has one: one unplaced, on an agent's copy, no longer open, in a file that is not UTF-8 (`not-utf8`), or in a file that changed while it was being placed (`changed`).
    """
    from loom import writes
    from loom.history.acts import KEEP, keep_versions
    from loom.history.ledger import append_entry
    from loom.records.carry import carry_all
    from loom.records.edits import home

    chosen = _chosen(result, who, ids)
    refused = [{"id": p.id, "why": p.why or p.state} for p in chosen if p.state in ("unplaced", "on-a-copy")]
    chosen = [p for p in chosen if p.state not in ("unplaced", "on-a-copy")]
    if not chosen:
        return [], refused
    before = _kept_texts(result, chosen)
    root, hist = result.quilt.root, result.quilt.history_dir
    edits = [p for p in chosen if p.kind == "edit"]
    asked = [p for p in chosen if p.kind == "suggested" and p.edit is not None]
    done: list[str] = []
    kept: _Kept | None = None
    try:
        with writes.act(root, hist, "keep", writer[1]) as w:
            for path in sorted({p.path for p in edits}):
                mine = [p for p in edits if p.path == path]
                _into_look(result, who, path, mine)
                append_entry(hist, KEEP, {"who": who, "path": path, "changes": [p.id for p in mine]}, who)
            if edits:
                # what was kept is a version of each document it is part of
                _say(said, keep_versions(result, sorted({p.path for p in edits}), KEEP, "Kept an edit", writer[1]))
            done += [p.id for p in edits]
            if asked:
                kept = _keep_suggested(w, result, [p.id for p in asked], writer, said)
                refused += kept.refused
                done += kept.ids

            def follow() -> None:
                after = _rescan(kept.result if kept else result)
                spans = {path: list(s) for path, s in kept.spans.items()} if kept else {}
                for edit in kept.taken if kept else []:
                    node = home(after, edit)
                    if node is not None:
                        spans.setdefault(node.file, []).extend(_where_taken(after, edit))
                for path, s in spans.items():
                    absorb(after, who, path, s)
                after = _rescan(after)
                carry_all(after, before, [p for p in chosen if p.id in done], writer)

            w.then(follow)
    except writes.WriteRefused as exc:
        # the act was undone, its files and its records: no suggested edit of it is kept
        lost = set(kept.ids if kept else [])
        refused += [{"id": i, "why": exc.message, "code": exc.code} for i in sorted(lost)]
        done = [i for i in done if i not in lost]
    return done, refused


@dataclass
class _Kept:
    """What the Keep of suggested edits staged in an act: the scan its places are in, the ids recorded kept, the refusals, where in each file (in the scan's reading, after the write) loom's words now stand, and the edits recorded kept without writing."""

    result: ScanResult
    ids: list[str] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)
    spans: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    taken: list[Edit] = field(default_factory=list)


def _keep_suggested(
    w: Any, result: ScanResult, ids: list[str], writer: tuple[str, str], said: list[str] | None
) -> _Kept:
    """Decide, place and stage in the act `w` the Keep of the suggested edits `ids`, all under the door's lock.

    By record: an edit no longer open is refused; one whose `<id>:<generation>` the journal says loom wrote is recorded kept and not written again; one named by an act recovery could not settle is refused. From the files: each remaining edit is judged taken or placed in `result`, and when a file it writes no longer reads as `result` read it, the quilt is scanned again here and the edits placed again, once; a file that moved again is refused (`changed`). An edit in a file that is not UTF-8 is never written (`not-utf8`). What is written is spliced into the file's own bytes, with its `kept` line (the key's hash from the plan), the `resolved` line of the annotation it answers and the ledger's `apply` line journalled with it.
    """
    from loom import writes
    from loom.history.acts import APPLY, keep_versions, ledger_line
    from loom.paths import EDIT_LOG
    from loom.records.edits import answered_event, generation, home, kept_event, replay
    from loom.records.log import log_path as annotation_log
    from loom.scan.hashing import hash_text
    from loom.scan.owntext import key_hash

    root, hist = result.quilt.root, result.quilt.history_dir
    out = _Kept(result)
    fresh = {e.id: e for e in replay(root)[0]}
    live: list[Edit] = []
    for i in ids:
        e = fresh.get(i)
        if e is None or e.status != "open":
            out.refused.append({"id": i, "why": f"{i} is {e.status if e else 'gone'} already"})
        elif w.wrote_before(f"{e.id}:{generation(e)}"):
            out.taken.append(e)  # loom wrote it in already, and a crash kept its record from being written
        elif f"{e.id}:{generation(e)}" in w.unsettled_edits():
            out.refused.append(
                {
                    "id": i,
                    "why": f"a write of {i} was cut short and its file changed since; look at the file before keeping it",
                }
            )
        else:
            live.append(e)
    stale: set[str] = set()
    for again in (False, True):
        if again:
            # a file moved since the scan this was planned from: plan once more, from a scan taken under the lock
            result = out.result = _rescan(result)
        taken, placed, refused = _place_kept(result, live)
        files = sorted({pl.file for _, pl in placed})
        stale = {f for f in files if not w.reads_as(f, result.files[f].text)}
        if not stale and placed:
            _say(said, keep_versions(result, files, APPLY, "Before keeping a suggested edit", writer[1]))
            # stamping the versions takes a moment: what is spliced is the bytes read after it, still as planned
            stale = {f for f in files if not w.reads_as(f, result.files[f].text)}
        if not stale:
            break
    refused += [
        {
            "id": e.id,
            "why": f"{pl.file} changed while loom was placing {e.id}; nothing was written, look at it again",
            "code": "changed",
        }
        for e, pl in placed
        if pl.file in stale
    ]
    placed = [(e, pl) for e, pl in placed if pl.file not in stale]
    out.refused += refused
    out.taken += taken
    answered: set[str] = set()

    def records(e: Edit, key_hash_: str) -> None:
        w.log(root / EDIT_LOG, kept_event(e, writer, key_hash_))
        line = answered_event(root, e, writer)
        if line is not None and line["id"] not in answered:
            answered.add(line["id"])
            w.log(annotation_log(root), line)
        out.ids.append(e.id)

    for path in sorted({pl.file for _, pl in placed}):
        mine = sorted(((e, pl) for e, pl in placed if pl.file == path), key=lambda x: x[1].at)
        try:
            raw = w.text(path, again=False) or ""  # the bytes just checked against the plan
        except writes.WriteRefused as exc:
            out.refused += [{"id": e.id, "why": exc.message, "code": exc.code} for e, _ in mine]
            continue
        new, made = writes.splice(raw, [(pl.at[0], pl.at[1], pl.text) for _, pl in mine])
        shift = 0
        for m, (e, pl) in zip(made, mine, strict=True):
            m["edit"] = f"{e.id}:{generation(e)}"
            a, b = pl.at
            out.spans.setdefault(path, []).append((a + shift, a + shift + len(pl.text)))
            shift += len(pl.text) - (b - a)
        w.replace(path, new.encode("utf-8"), made)
        for e, pl in mine:
            w.wrote(f"{e.id}:{generation(e)}")
            records(e, hash_text(pl.taken))
            w.log(*ledger_line(hist, APPLY, {"edit": e.id, "key": pl.key, "path": path}, writer[1]))
    for e in out.taken:
        node = home(result, e)
        records(e, key_hash(result, node.key) if node is not None else "")
    return out


def _place_kept(
    result: ScanResult, edits: list[Edit]
) -> tuple[list[Edit], list[tuple[Edit, Placed]], list[dict[str, str]]]:
    """Each edit taken already, placed, or refused, in `result`: the edits whose block reads as them taken, the rest placed together (`edits.compose`), and `{id, why, code?}` for one unplaced or in a file that is not UTF-8."""
    from loom.records.edits import Placed, compose, home, taken_how

    taken: list[Edit] = []
    rest: list[Edit] = []
    refused: list[dict[str, str]] = []
    for e in edits:
        node = home(result, e)
        if node is not None and node.file in result.files and result.files[node.file].encoding != "utf-8":
            refused.append({"id": e.id, "why": _not_utf8(node.file), "code": "not-utf8"})
        elif taken_how(result, e) is not None:
            taken.append(e)
        else:
            rest.append(e)
    placed: list[tuple[Edit, Placed]] = []
    for e, pl in compose(result, rest):
        if isinstance(pl, Placed):
            placed.append((e, pl))
        else:
            refused.append({"id": e.id, "why": str(pl)})
    return taken, placed, refused


def _not_utf8(path: str) -> str:
    return f"{path} is not UTF-8 text, so loom does not write into it; save it as UTF-8 first"


def discard(
    result: ScanResult,
    who: str,
    ids: list[str],
    writer: tuple[str, str],
    why: str | None = None,
    said: list[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Discard the changes `ids`: an in-place change's old words are written back through the door (`loom.writes`), one act for every file, cut again under its lock from the bytes then, a version of each document it is part of kept first (P7), with an `undo` line naming it in the ledger; a suggested edit is recorded discarded, with `why`. No annotation is written.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    who : str
        Whose look.
    ids : list of str
        The changes, by id.
    writer : (str, str)
        Who discards them.
    why : str, optional
        Why, which the agent that made a suggested edit reads.
    said : list of str, optional
        Where to say which versions were kept.

    Returns
    -------
    (list of str, list of dict)
        The ids discarded, and `{id, why}` for each that cannot be.
    """
    from loom import writes
    from loom.history.acts import keep_versions
    from loom.looks import UNDO
    from loom.records.edits import EditRefused
    from loom.records.edits import discard as record_discarded

    chosen = _chosen(result, who, ids)
    root, hist = result.quilt.root, result.quilt.history_dir
    done: list[str] = []
    refused: list[dict[str, str]] = []
    edits = [p for p in chosen if p.kind == "edit"]
    if edits:
        texts = look_texts(result, who)
        then = texts[0] if texts else {}
        looked = _look_files(result, who)
        try:
            with writes.act(root, hist, "discard", writer[1]) as w:
                _say(
                    said,
                    keep_versions(
                        result, sorted({p.path for p in edits}), UNDO, "Before discarding a change", writer[1]
                    ),
                )
                for path in sorted({p.path for p in edits}):
                    done_here, refused_here = _discard_in(
                        w,
                        hist,
                        who,
                        path,
                        then.get(path, ""),
                        path in looked,
                        [p.id for p in edits if p.path == path],
                        why,
                        writer,
                    )
                    done += done_here
                    refused += refused_here
        except writes.WriteRefused as exc:
            # the commit undid every file: nothing of this request was discarded
            refused += [{"id": i, "why": exc.message, "code": exc.code} for i in done]
            done = []
    for p in chosen:
        if p.kind != "suggested" or p.edit is None:
            continue
        try:
            record_discarded(root, p.edit, writer, why)
            done.append(p.id)
        except EditRefused as exc:
            refused.append({"id": p.id, "why": exc.message})
    return done, refused


def _discard_in(
    w: Any,
    hist: Any,
    who: str,
    path: str,
    old: str,
    looked: bool,
    wanted: list[str],
    why: str | None,
    writer: tuple[str, str],
) -> tuple[list[str], list[dict[str, str]]]:
    """Stage in the act `w` the discard of the changes `wanted` of `path`, with its `undo` line; the ids discarded, and `{id, why, code}` for each refused.

    The changes are cut again from the look's text `old` and the file's bytes read under the door's lock, since the list was made before it: a change still there is discarded however the file moved elsewhere, and one no longer there is refused (`changed`). A file the look did not hold that the discard empties is removed.
    """
    from loom import writes
    from loom.history.acts import ledger_line
    from loom.looks import UNDO

    try:
        current = w.text(path)
    except writes.WriteRefused as exc:
        return [], [{"id": i, "why": exc.message, "code": exc.code} for i in wanted]
    mine = sorted((c for c in cuts(path, old, current) if c[0] in wanted), key=lambda c: c[2], reverse=True)
    found = {c[0] for c in mine}
    refused = [
        {
            "id": i,
            "why": f"{path} changed where that change was since it was listed; look at it again",
            "code": "changed",
        }
        for i in wanted
        if i not in found
    ]
    if not mine:
        return [], refused
    text = current or ""
    for _cid, (o0, o1), (n0, n1) in mine:
        text = text[:n0] + old[o0:o1] + text[n1:]
    data = None if not text and not looked else text.encode("utf-8")
    w.replace(path, data)
    entry: dict[str, Any] = {
        "who": who,
        "path": path,
        "from": writes.digest(current.encode("utf-8")) if current is not None else None,
        "to": writes.digest(data),
        "changes": [c[0] for c in mine],
    }
    if why:
        entry["why"] = why
    w.log(*ledger_line(hist, UNDO, entry, writer[1]))
    return [c[0] for c in mine], refused


def _say(said: list[str] | None, kept: Any) -> None:
    """Add what keeping versions did to `said`, when there is something to say."""
    if said is not None and kept.said():
        said.append(kept.said())


def _look_files(result: ScanResult, who: str) -> dict[str, str]:
    from loom.looks import read_look

    look = read_look(result.quilt.root, who)
    return look.files if look else {}


def _rescan(result: ScanResult) -> ScanResult:
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    return scan(load_quilt(result.quilt.root))


def _kept_texts(result: ScanResult, chosen: list[Pending]) -> dict[str, str]:
    """Each touched key's own text as kept before the act, for carrying annotations after it."""
    from loom.records.edits import node_of
    from loom.records.store import Records

    out: dict[str, str] = {}
    for p in chosen:
        for key in [p.key, *p.blocks]:
            node = node_of(result, key) if key else None
            if node is None or node.key in out:
                continue
            kept = kept_own(result, node)
            out[node.key] = kept.text if kept else Records.own_pieces(result, node)[0]
    return out


def _into_look(result: ScanResult, who: str, path: str, changes: list[Pending]) -> None:
    """Put `changes` of `path` into `who`'s look, each alone: the look's text with each change's new words in place of its old."""
    from loom.looks import _write, read_look
    from loom.records.snapshots import write_raw

    look = read_look(result.quilt.root, who)
    texts = look_texts(result, who)
    if look is None or texts is None:
        return
    then, now = texts
    text = then.get(path, "")
    current = now.get(path) or ""
    for p in sorted(changes, key=lambda x: x.was, reverse=True):
        text = text[: p.was[0]] + current[p.span[0] : p.span[1]] + text[p.was[1] :]
    if now.get(path) is None and not text:
        look.files.pop(path, None)
    else:
        look.files[path] = write_raw(result.quilt.root, text, result.quilt.history_dir)
    _write(result.quilt.root, look)


def absorb(result: ScanResult, who: str, path: str, spans: list[tuple[int, int]]) -> None:
    """After loom wrote the person's words at `spans` of `path`, put into `who`'s look every in-place change on those words, so the file and the look agree there; nothing before a first look."""
    changes = [
        p for p in in_place(result, who) if p.path == path and any(p.span[0] <= b and a <= p.span[1] for a, b in spans)
    ]
    if changes:
        _into_look(result, who, path, changes)


def _where_taken(result: ScanResult, edit: Edit) -> list[tuple[int, int]]:
    """Where a suggested edit's new text stands in its file, when its key reads as it taken already.

    Looked for in the key's whole text, as `is_taken` does: new text that opens a section is the key's child once it is in.
    """
    from loom.records.edits import home
    from loom.records.selectors import find_quote

    node = home(result, edit)
    if node is None or node.file not in result.files or not edit.with_text.strip():
        return []
    whole = result.files[node.file].text[node.start : node.end]
    return [(node.start + a, node.start + b) for a, b in find_quote(whole, edit.with_text)]


def keep_accepted(result: ScanResult, who: str, keys: list[str]) -> list[str]:
    """Keep each in-place change that touches only blocks `keys`, which the person just accepted having seen it; returns the paths whose look moved.

    A change running across a block not accepted stays, since that one still waits. For the viewer's Accept, which shows the change it keeps; `loom accept` shows none, and leaves the look alone.
    """
    from loom.history.acts import KEEP
    from loom.history.ledger import append_entry

    accepted = set(keys)
    chosen = [p for p in in_place(result, who) if p.blocks and accepted.issuperset(p.blocks)]
    for path in sorted({p.path for p in chosen}):
        mine = [p for p in chosen if p.path == path]
        _into_look(result, who, path, mine)
        append_entry(result.quilt.history_dir, KEEP, {"who": who, "path": path, "changes": [p.id for p in mine]}, who)
    return sorted({p.path for p in chosen})


def patch_of(result: ScanResult, change: Pending, who: str | None = None) -> str:
    """The change as a unified diff of its file against the quilt root: an in-place change from the file with its old words back, a suggested edit from the file now."""
    from loom.records.edits import Placed, compose, patch
    from loom.reshape.ids import unified_diff

    root = result.quilt.root
    if change.kind == "suggested":
        if change.edit is None:
            return ""
        placed = next((pl for e, pl in compose(result, [change.edit]) if isinstance(pl, Placed)), None)
        return patch(result, placed) if placed is not None else ""
    texts = look_texts(result, reviewer(result) if who is None else who)
    then = texts[0].get(change.path, "") if texts else ""
    now = (root / change.path).read_text(encoding="utf-8") if (root / change.path).is_file() else ""
    back = now[: change.span[0]] + then[change.was[0] : change.was[1]] + now[change.span[1] :]
    return unified_diff(back, now, change.path)
