"""One list of what waits on the person: the open suggested edits and the in-place edits to the open files since their look, cut by words; and the two verbs on each, keep and discard.

An in-place change is a run of words that differs between the person's look (`looks.py`) and the file now: words the diff finds apart by fewer than `NEAR` words are one change, never across a blank line, and a file new or gone since the look is one change. Its id is `c-` and eight hex digits of a hash of its path, its old and new text and the 32 characters of the look before it, so it stands while it does, whatever changes elsewhere. A suggested edit is its record's (`records/edits.py`), placed in its key's text now; several on one key combine (`edits.compose`).

Keeping an in-place change puts it into the look alone; discarding writes its old words back, a version of each document it is part of kept first (P7), with an `undo` line in the ledger. Keeping a suggested edit writes it into its file and records it kept, through the door (`loom.writes`), every decision made again under its lock; discarding records it discarded. Every write loom makes on the person's word goes into their look too, so the file and the look agree on those words after it. Keeping carries each annotation on the changed words onto the new ones (`records/carry.py`); discarding writes no annotation.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from bisect import bisect_left
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

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

    The diff is difflib's (`SequenceMatcher`, no junk), its blocks found by `_matching`, which lists exactly what difflib lists without looking at every recurrence of a word; an input it cannot answer exactly is listed by `_cut_by_difflib`, today's listing, kept as the oracle the tests hold it to.
    """
    left = [(m.group(), m.start(), m.end()) for m in _WORD.finditer(old)]
    right = [(m.group(), m.start(), m.end()) for m in _WORD.finditer(new)]
    try:
        blocks = _matching([t[0] for t in left], [t[0] for t in right])
    except _Inexact:
        return _cut_by_difflib(old, new)
    ops = []
    i = j = 0
    for ai, bj, size in [*blocks, (len(left), len(right), 0)]:
        if i < ai or j < bj:
            ops.append((i, ai, j, bj))
        i, j = ai + size, bj + size
    groups: list[list[int]] = []
    for a, b, c, d in ops:
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


#: A range is searched by window (`_longest_by_window`) where its old words occur, counted over the whole of the new text, more than this many times per word of the two ranges: a bound above what difflib's search would look at, which stops at the range's end. Both searches answer the same, so it decides time alone.
_CHEAP = 8
#: What follows a run, in words of the two ranges, short enough to look for more runs as long in it at once (`_runs_after`); past it they are looked for only once a step has found a run as long as the one before it, so a recursion that never repeats a length pays no pass.
_NEAR = 256
#: The window hash: a polynomial in the words' numbers, modulo a Mersenne prime, its base drawn once a process above every word's number, so that no text can be written to collide and send the listing down `_cut_by_difflib`'s path.
_HASH_MOD = (1 << 61) - 1
_HASH_BASE = secrets.randbelow(_HASH_MOD - (1 << 32)) + (1 << 32)


class _Inexact(Exception):
    """Two different runs of words share a window hash, so the window search cannot say which is which: the input is listed by `_cut_by_difflib`."""


def _matching(a: list[str], b: list[str]) -> list[tuple[int, int, int]]:
    """`difflib.SequenceMatcher(None, a, b, autojunk=False)`'s matching blocks, without its closing one, as triples in order.

    Its own recursion, each step's longest shared run found by difflib where that is cheap and by `_longest_by_window` where its search would look at every recurrence of a frequent word, the cost that grows with the square of how often a word recurs; and, once a step's run is as long as the one before it, the runs as long that difflib would take one step at a time on what follows (`_runs_after`), the cost of an edit of one shape on every line, found in one pass. A step whose run is shorter pays nothing for it, so a recursion that never repeats a length costs what difflib's does. Each gives difflib's run, so the blocks are difflib's; raises `_Inexact` where a hash collides.
    """
    import difflib
    from collections import Counter

    if a == b:
        return [(0, 0, len(a))] if a else []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    numbers: dict[str, int] = {}
    na = [numbers.setdefault(w, len(numbers) + 1) for w in a]
    nb = [numbers.setdefault(w, len(numbers) + 1) for w in b]
    count = Counter(nb)
    # how often the words of a's first x words occur in b, so that a range's estimate is one subtraction
    occurs = [0]
    for x in na:
        occurs.append(occurs[-1] + count[x])
    # each range with the length of the run just before it, where it is what follows that run
    queue = [(0, len(a), 0, len(b), 0)]
    blocks = []
    while queue:
        alo, ahi, blo, bhi, before = queue.pop()
        if occurs[ahi] - occurs[alo] <= _CHEAP * (ahi - alo + bhi - blo):
            i, j, k = sm.find_longest_match(alo, ahi, blo, bhi)
        else:
            i, j, k = _longest_by_window(na, nb, alo, ahi, blo, bhi)
        if not k:
            continue
        blocks.append((i, j, k))
        if alo < i and blo < j:
            queue.append((alo, i, blo, j, 0))
        at_a, at_b = i + k, j + k
        if k == before or (ahi - at_a) + (bhi - at_b) <= _NEAR:
            # a run as long as the one before it, so difflib is taking runs of one length one step at a time, or what follows is short enough that a pass costs little: the rest of the runs as long are found in one pass
            for x, y in _runs_after(na, nb, at_a, ahi, at_b, bhi, k):
                blocks.append((x, y, k))
                if at_a < x and at_b < y:
                    queue.append((at_a, x, at_b, y, 0))
                at_a, at_b = x + k, y + k
        if at_a < ahi and at_b < bhi:
            queue.append((at_a, ahi, at_b, bhi, k))
    blocks.sort()
    return blocks


def _runs_after(
    a: list[int], b: list[int], alo: int, ahi: int, blo: int, bhi: int, k: int
) -> Iterator[tuple[int, int]]:
    """The runs of `k` words, `k` the longest the range before held, that difflib takes one after another on what follows: each the earliest in `a`, then in `b`, of those after the one before, while there is one.

    A range left after a longest run holds none longer, so while it holds one as long, that is the one difflib takes next; and none as long lies between two that follow each other, so the stretch between them is searched as any range is. Raises `_Inexact` where a hash collides.
    """
    if k > ahi - alo or k > bhi - blo:
        return
    mod, base = _HASH_MOD, _HASH_BASE
    top = pow(base, k - 1, mod)
    places: dict[int, list[int]] = {}
    h = 0
    for x in b[blo : blo + k]:
        h = (h * base + x) % mod
    places[h] = [blo]
    for p in range(blo + k, bhi):
        h = ((h - b[p - k] * top) * base + b[p]) % mod
        places.setdefault(h, []).append(p - k + 1)
    at_b = blo
    x = alo
    while x + k <= ahi:
        h = 0
        for w in a[x : x + k]:
            h = (h * base + w) % mod
        while True:
            ys = places.get(h)
            if ys is not None:
                q = bisect_left(ys, at_b)
                if q < len(ys):
                    y = ys[q]
                    if a[x : x + k] != b[y : y + k]:
                        raise _Inexact
                    yield x, y
                    at_b = y + k
                    x += k
                    break
            if x + k >= ahi:
                return
            h = ((h - a[x] * top) * base + a[x + k]) % mod
            x += 1


def _longest_by_window(a: list[int], b: list[int], alo: int, ahi: int, blo: int, bhi: int) -> tuple[int, int, int]:
    """`find_longest_match(alo, ahi, blo, bhi)` without junk: the longest run the two ranges share, of those the one starting earliest in `a`, then earliest in `b`.

    The shared head and tail are runs both ranges hold; a longer run is looked for by its length, halving, each length one pass of window hashes over each range.
    """
    n = min(ahi - alo, bhi - blo)
    head = _shared(a, b, alo, blo, n, ahead=True)
    if head == n:
        return alo, blo, head
    tail = _shared(a, b, ahi, bhi, n, ahead=False)
    longer = _first_run(a, b, alo, ahi, blo, bhi, max(head, tail) + 1)
    if longer is None:
        if head >= tail:
            # starts where both ranges start, so earliest in each
            return alo, blo, head
        at = _first_run(a, b, alo, ahi, blo, bhi, tail)
        assert at is not None, "the shared tail is a run both ranges hold"
        return at[0], at[1], tail
    lo, hi, best = max(head, tail) + 1, n, longer
    while lo < hi:
        mid = (lo + hi + 1) // 2
        at = _first_run(a, b, alo, ahi, blo, bhi, mid)
        if at is None:
            hi = mid - 1
        else:
            lo, best = mid, at
    return best[0], best[1], lo


def _shared(a: list[int], b: list[int], at_a: int, at_b: int, n: int, *, ahead: bool) -> int:
    """How many words the ranges share at their head, from `at_a` and `at_b` on, or at their tail, up to them; at most `n`, found by halving with slice comparisons."""
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        same = a[at_a : at_a + mid] == b[at_b : at_b + mid] if ahead else a[at_a - mid : at_a] == b[at_b - mid : at_b]
        if same:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _first_run(a: list[int], b: list[int], alo: int, ahi: int, blo: int, bhi: int, k: int) -> tuple[int, int] | None:
    """Where the run of `k` words the ranges share starts that starts earliest in `a`, then earliest in `b`; None when they share none.

    Each window of `b` is hashed once, its first place kept; the windows of `a` are hashed in order until one is found in `b`, and its words compared, so a collision raises `_Inexact` rather than answering.
    """
    if k > ahi - alo or k > bhi - blo:
        return None
    mod, base = _HASH_MOD, _HASH_BASE
    top = pow(base, k - 1, mod)
    seen: dict[int, int] = {}
    h = 0
    for x in b[blo : blo + k]:
        h = (h * base + x) % mod
    seen[h] = blo
    for p in range(blo + k, bhi):
        h = ((h - b[p - k] * top) * base + b[p]) % mod
        seen.setdefault(h, p - k + 1)
    h = 0
    for x in a[alo : alo + k]:
        h = (h * base + x) % mod
    p = alo + k
    while True:
        j = seen.get(h)
        if j is not None:
            if a[p - k : p] != b[j : j + k]:
                raise _Inexact
            return p - k, j
        if p >= ahi:
            return None
        h = ((h - a[p - k] * top) * base + a[p]) % mod
        p += 1


def _cut_by_difflib(old: str, new: str) -> list[tuple[int, int, int, int]]:
    """`cut` as difflib finds it, every recurrence of a word looked at: the oracle `cut` lists exactly what it lists, and its path for an input the window search cannot answer exactly."""
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
    """`who`'s look as texts, `(look, now)` by path, for the files that changed since it; None before a first look. A file the scan read is its text in the scan, not on disk now. Read once for each scan and each state of the look."""
    from loom.looks import look_path

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
    from loom.looks import held as looks_held
    from loom.looks import read_look, watched_texts, watching
    from loom.records.snapshots import read_raw
    from loom.scan.hashing import sha256

    quilt = result.quilt
    look = read_look(quilt.root, who) if who else None
    if look is None:
        return None
    # only the LaTeX files agents may edit: one they are denied is the person's own, and a change there or to any other file is never listed
    current = watched_texts(quilt)
    watched = watching(quilt.config, quilt.root)
    # a file the scan read is as the scan read it: one saved since is the next build's, so a change is never cut from one reading of a file and drawn against another
    for rel, src in result.files.items():
        text = current.get(rel)
        if text is not None and text != src.text and "\r" not in text and src.encoding == "utf-8":
            current[rel] = src.text
    then: dict[str, str] = {}
    now: dict[str, str | None] = {}
    # a look taken before LaTeX's auxiliary files were left out of it may still hold them
    for rel in sorted(set(current) | {f for f in look.files if not is_latex_aux(f) and watched(f)}):
        held = looks_held(look, rel)
        text = current.get(rel)
        if held == (sha256(text) if text is not None else None):
            continue
        then[rel] = (read_raw(quilt.root, held, quilt.history_dir) or "") if held else ""
        now[rel] = text
    return then, now


def in_place(result: ScanResult, who: str | None = None) -> list[Pending]:
    """The in-place changes since `who`'s look (the reviewer's by default), by path and place; empty before a first look."""
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
    from loom.records.edits import Placed, compose, file_encoding, generation, home, on_file, replay, taken_how
    from loom.writes import written

    out: list[Pending] = []
    edits = [e for e in replay(result.quilt.root)[0] if e.status == "open"]
    loom_wrote = written(result.quilt.root, result.quilt.history_dir)
    for edit, placed in compose(result, edits):
        node = home(result, edit)
        # one on a Markdown file is on the file, by its path, and on no block
        path = edit.target_key if on_file(edit) else node.file if node is not None else ""
        p = Pending(
            id=edit.id,
            kind="suggested",
            path=path,
            # on no block, its key is no block's: never the one that took the key it was suggested on
            key=node.key if node is not None else None,
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
            p.blocks = [] if on_file(edit) else [placed.key]
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
        elif on_file(edit) and file_encoding(result, path) != "utf-8":
            p.state, p.why = "unplaced", _not_utf8(path)
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
    from loom.history.acts import KEEP, keep_versions, ledger_line
    from loom.records.carry import carry, carry_all
    from loom.records.edits import file_text, home, on_file, where_taken

    chosen = _chosen(result, who, ids)
    refused = [{"id": p.id, "why": p.why or p.state} for p in chosen if p.state in ("unplaced", "on-a-copy")]
    chosen = [p for p in chosen if p.state not in ("unplaced", "on-a-copy")]
    if not chosen:
        return [], refused
    before = _kept_texts(result, chosen)
    root, hist = result.quilt.root, result.quilt.history_dir
    edits = [p for p in chosen if p.kind == "edit"]
    asked = [p for p in chosen if p.kind == "suggested" and p.edit is not None]
    # a Markdown file's annotations are on the file's text, carried from it as it stood before the Keep
    files_before = {p.path: file_text(result, p.path) or "" for p in asked if p.edit is not None and on_file(p.edit)}
    done: list[str] = []
    kept: _Kept | None = None
    try:
        with writes.act(root, hist, "keep", writer[1]) as w:
            # the in-place changes go into the look with the act, and their keep lines with it, so a cut Keep writes neither
            looked: dict[str, str | None] = {}
            taken: list[str] = []
            for path in sorted({p.path for p in edits}):
                # cut again under the door, from the look and the file as they are now: a change listed before another act moved them goes in at its place now, never at a stale offset, and one no longer there is refused
                ids = [p.id for p in edits if p.path == path]
                held, entry, found = _look_entry_now(root, hist, who, path, ids)
                refused += [{"id": i, "why": CHANGED_SINCE_LISTED, "code": "changed"} for i in ids if i not in found]
                if not found:
                    continue
                if held:
                    looked[path] = entry
                w.log(*ledger_line(hist, KEEP, {"who": who, "path": path, "changes": found}, who))
                taken += found
            if taken:
                # what was kept is a version of each document it is part of
                paths = sorted({p.path for p in edits if p.id in taken})
                _say(said, keep_versions(result, paths, KEEP, "Kept an edit", writer[1]))
            done += taken
            if asked:
                kept = _keep_suggested(w, result, [p.id for p in asked], writer, said)
                refused += kept.refused
                done += kept.ids
            # what the follow-up does to the look, for recovery to do if a crash comes first (`relook`)
            record: dict[str, Any] = {"looked": looked} if who and looked else {}
            if who and kept and kept.spans:
                record["spans"] = {f: [list(s) for s in v] for f, v in kept.spans.items()}
            if record:
                w.look = {"who": who, **record}

            def follow() -> None:
                if who and looked:
                    _set_look(root, who, looked)
                after = _rescan(kept.result if kept else result)
                spans = {path: list(s) for path, s in kept.spans.items()} if kept else {}
                for edit in kept.taken if kept else []:
                    node = home(after, edit)
                    path = edit.target_key if on_file(edit) else node.file if node is not None else None
                    if path is not None:
                        spans.setdefault(path, []).extend(where_taken(after, edit))
                for path, s in spans.items():
                    absorb(after, who, path, s)
                after = _rescan(after)
                carry_all(after, before, [p for p in chosen if p.id in done], writer)
                for path, was in files_before.items():
                    mine = [p for p in chosen if p.path == path and p.id in done]
                    if mine:
                        carry(after, path, was, file_text(after, path) or "", mine, writer)

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
    from loom.records.edits import answered_event, file_text, generation, home, kept_event, on_file, replay
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
        # the text each file was placed in: a scanned file's from the scan, a Markdown file's as its placement read it (`Placed.own`), never read again here
        planned = {pl.file: pl.own for _, pl in placed if pl.file not in result.files}
        stale = {f for f in files if not w.reads_as(f, planned.get(f, file_text(result, f)))}
        if not stale and placed:
            _say(said, keep_versions(result, files, APPLY, "Before keeping a suggested edit", writer[1]))
            # stamping the versions takes a moment: what is spliced is the bytes read after it, still as planned
            stale = {f for f in files if not w.reads_as(f, planned.get(f, file_text(result, f)))}
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
        if on_file(e):
            records(e, hash_text(file_text(result, e.target_key) or ""))
        else:
            records(e, key_hash(result, node.key) if node is not None else "")
    return out


def _place_kept(
    result: ScanResult, edits: list[Edit]
) -> tuple[list[Edit], list[tuple[Edit, Placed]], list[dict[str, str]]]:
    """Each edit taken already, placed, or refused, in `result`: the edits whose block reads as them taken, the rest placed together (`edits.compose`), and `{id, why, code?}` for one unplaced or in a file that is not UTF-8."""
    from loom.records.edits import Placed, compose, file_encoding, home, on_file, taken_how

    taken: list[Edit] = []
    rest: list[Edit] = []
    refused: list[dict[str, str]] = []
    for e in edits:
        node = home(result, e)
        if node is not None and node.file in result.files and result.files[node.file].encoding != "utf-8":
            refused.append({"id": e.id, "why": _not_utf8(node.file), "code": "not-utf8"})
        elif on_file(e) and file_encoding(result, e.target_key) != "utf-8":
            refused.append({"id": e.id, "why": _not_utf8(e.target_key), "code": "not-utf8"})
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


# ---- undoing a Keep -------------------------------------------------------------------------------------------------


def called(edit: Edit) -> str:
    """A suggested edit as a person knows it, by its words: what it puts in, or for a deletion what it takes out; never its id."""
    words = " ".join((edit.with_text or (edit.selector.exact if edit.selector else "")).split())
    short = words if len(words) <= 48 else words[:47].rstrip() + "…"
    return f"the suggestion “{short}”" if edit.with_text else f"the deletion of “{short}”"


def _not_written(edit: Edit) -> str:
    return f"loom has no write of {called(edit)} to undo on this machine: its words were in your text already when it was kept, or it was kept on another machine; restoring a version from History takes them out"


def _changed_since(edit: Edit, how: str = "changed") -> str:
    if how == "too-much":
        return f"the file has changed too much around {called(edit)} since it was kept to be sure where it was written, so its Keep is not undone; restore a version from History instead"
    return f"{called(edit)} has changed where it was written since it was kept, so its Keep is not undone; restore a version from History instead"


def _ending_at(raw: str, a: int, b: int) -> str:
    """The file's own line ending at a place: that of the nearest line break before it, else after it, else the file's most common."""
    from loom import writes

    k = raw.rfind("\n", 0, a)
    if k < 0:
        k = raw.find("\n", b)
    if k >= 0:
        return "\r\n" if k > 0 and raw[k - 1] == "\r" else "\n"
    return writes.newline_of(raw)


def keep_of(wrote: dict[str, int], edit: Edit) -> str | None:
    """The `<id>:<generation>` of the Keep whose words `edit`'s record stands on, by the journal's `wrote`; None when loom wrote none.

    A kept edit stands on the Keep of its generation when that Keep wrote; one a restore recorded kept (`why: "restored"`) on the last Keep that wrote it; one whose Keep wrote nothing, its words being in already, on none. An open edit opened again stands on the last Keep that wrote it before.
    """
    from loom.records.edits import generation

    g = generation(edit)
    if edit.status == "kept":
        if f"{edit.id}:{g}" in wrote:
            return f"{edit.id}:{g}"
        last = next((a for a in reversed(edit.acts) if a.get("event") == "kept"), {})
        if last.get("why") != "restored":
            return None
        top = g
    elif edit.status == "open":
        top = g - 1
    else:
        return None
    return next((f"{edit.id}:{k}" for k in range(top, -1, -1) if f"{edit.id}:{k}" in wrote), None)


def unkeep(
    result: ScanResult, who: str, ids: list[str], writer: tuple[str, str], said: list[str] | None = None
) -> tuple[list[str], list[dict[str, str]]]:
    """Undo the Keep of each suggested edit `ids`, in one act through the door (`loom.writes`): the words its Keep wrote come out and the words they replaced go back, a version of each document it changes kept first, and the edit is open again.

    Every decision is made under the door's lock (`_unkeep`). Each edit's Keep is found in this machine's journal by `<id>:<generation>`; its words are found by the bytes the Keep left, or with their neighbours as it wrote them; every other byte of the file is kept.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    who : str
        Whose look takes the words put back.
    ids : list of str
        The suggested edits, by id.
    writer : (str, str)
        Who undoes them, as `_annotator` gives it.
    said : list of str, optional
        Where to say which versions were kept, and any step after the write that could not be done.

    Returns
    -------
    (list of str, list of dict)
        The ids undone, and `{id, why, code}` for each that is not: one not kept (`not-kept`), one whose Keep loom has no write of here (`not-written`), one whose words have changed where it was written (`changed-since`), one in a file that is not UTF-8 (`not-utf8`) or that moved while it was being undone (`changed`).

    Raises
    ------
    PendingRefused
        `no-such-change` (404) for an id that names no suggested edit.

    See Also
    --------
    keep : what this undoes.
    """
    from loom import writes
    from loom.records.edits import find

    root, hist = result.quilt.root, result.quilt.history_dir
    ids = list(dict.fromkeys(ids))
    gone = [i for i in ids if find(root, i) is None]
    if gone:
        raise PendingRefused("no-such-change", "a suggestion it names is not in this quilt", 404)
    out = _Unkept(result)
    try:
        with writes.act(root, hist, "undo", writer[1]) as w:
            _unkeep(w, out, ids, writer, said)
            if who and out.spans:
                w.look = {"who": who, "spans": {f: [list(s) for s in v] for f, v in out.spans.items()}}

            def follow() -> None:
                if out.ids:
                    after = _after_unkeep(out, who, writer)
                    if said is not None:
                        said.extend(after)

            w.then(follow)
    except writes.WriteRefused as exc:
        # the act was undone, its files and its records: no Keep of this request is undone
        said_no = {r["id"] for r in out.refused}
        tried = [i for i in [*out.ids, *out.trying] if i not in said_no]
        return [], out.refused + [{"id": i, "why": exc.message, "code": exc.code} for i in dict.fromkeys(tried)]
    return out.ids, out.refused


@dataclass
class _Unkept:
    """What the undo of Keeps staged in an act: the scan it was planned with, the ids being undone and those undone, the refusals, where in each file (in the scan's reading, after the write) the words put back stand, and what carrying annotations back needs."""

    result: ScanResult
    trying: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    refused: list[dict[str, str]] = field(default_factory=list)
    spans: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    changes: list[Pending] = field(default_factory=list)
    before: dict[str, str] = field(default_factory=dict)
    wrote: dict[str, tuple[str, str, list[tuple[int, int, str]]]] = field(default_factory=dict)


def _unkeep(w: Any, out: _Unkept, ids: list[str], writer: tuple[str, str], said: list[str] | None) -> None:
    """Decide and stage in the act `w` the undo of the Keeps of `ids`, all under the door's lock, into `out`.

    By record, each edit must be kept and its Keep in the journal; by the bytes now, its words must stand where the Keep left them (`_undo_in`); an edit refused in one file is undone in none. The versions are stamped from a scan that reads as the files do, taken again once when one moved; a file that moves after its undo was planned refuses the act (`changed`), which then writes nothing.
    """
    from loom import writes
    from loom.history.acts import UNAPPLY, keep_versions, ledger_line
    from loom.looks import UNDO
    from loom.paths import EDIT_LOG
    from loom.records.edits import file_text, home, reopened_event, replay, unanswered_event
    from loom.records.log import log_path as annotation_log
    from loom.records.mdtext import is_markdown

    result = out.result
    root, hist = result.quilt.root, result.quilt.history_dir
    fresh = {e.id: e for e in replay(root)[0]}
    items: list[tuple[Edit, str, writes.Written]] = []
    for i in ids:
        e = fresh.get(i)
        if e is None or e.status != "kept":
            why = f"{called(e)} is {e.status}, so there is no Keep of it to undo" if e else f"{i} is gone"
            out.refused.append({"id": i, "why": why, "code": "not-kept"})
            continue
        gen = keep_of(w.journal.wrote, e)
        at = w.journal.wrote.get(gen) if gen else None
        entry = writes.entry_at(root, at) if at is not None else None
        if gen is None or entry is None or entry.get("event") != "begin" or gen not in (entry.get("edits") or []):
            out.refused.append({"id": i, "why": _not_written(e), "code": "not-written"})
            continue
        # what recovery would not act on, an undo does not either: a file reached through a link out of the quilt among it
        why = writes.untrusted(root, hist, entry)
        made = None if why else writes.splices_of(hist, entry, gen)
        if not made:
            said_why = why or "the texts it names are missing from the history or do not bear it out"
            out.refused.append(
                {
                    "id": i,
                    "why": f"loom will not undo the Keep of {called(e)} from its record: {said_why}; restore a version from History instead",
                    "code": "not-written",
                }
            )
            continue
        items += [(e, gen, m) for m in made]
    # where each edit's words stand in each file now; an edit refused in one file is undone in none, so plan again without it
    plans: dict[str, tuple[bytes, bytes, list[dict[str, Any]], list[tuple[int, int]], list[tuple[int, int, str]]]] = {}
    named = {e.id: e for e, *_ in items}
    while items:
        failed: dict[str, dict[str, str]] = {}
        plans = {}
        for rel in sorted({m.rel for *_, m in items}):
            mine = [(e, gen, m) for e, gen, m in items if m.rel == rel]
            # the plan is made from one read of the file, the bytes the commit checks it still holds
            data = w.read(rel)
            try:
                raw = w.text(rel, again=False)
            except writes.WriteRefused as exc:
                failed.update({e.id: {"why": exc.message, "code": exc.code} for e, *_ in mine})
                continue
            if raw is None or data is None:
                failed.update({e.id: {"why": _changed_since(e), "code": "changed-since"} for e, *_ in mine})
                continue
            plan = _undo_in(hist, raw, data, mine)
            if isinstance(plan, dict):
                failed.update(
                    {i: {"why": _changed_since(named[i], how), "code": "changed-since"} for i, how in plan.items()}
                )
            else:
                plans[rel] = (data, *plan)
        if not failed:
            break
        out.refused += [{"id": i, **f} for i, f in failed.items()]
        items = [it for it in items if it[0].id not in failed]
    if not items:
        return
    out.trying = list(dict.fromkeys(e.id for e, *_ in items))
    files = sorted(plans)
    # the versions are of the text the undo replaces: stamp them from a scan that reads as the files now do
    for again in (False, True):
        if again:
            result = out.result = _rescan(result)
        if all((f in result.files or is_markdown(f)) and w.reads_as(f, file_text(result, f)) for f in files):
            break
    else:
        raise writes.WriteRefused(
            "changed", "a file changed while loom was undoing a Keep; nothing was written, look at it again"
        )
    for e, _, m in items:
        node = home(result, e)
        key = node.key if node is not None else e.target_key
        if not any(p.id == e.id for p in out.changes):
            out.changes.append(
                Pending(
                    id=e.id,
                    kind="suggested",
                    path=m.rel,
                    key=key,
                    documents=[],
                    old=m.new.strip(),
                    new=m.old.strip(),
                    at=[0, 0],
                    edit=e,
                )
            )
    # carrying annotations back needs the blocks' text before; only worth reading when an annotation stands on one of them
    if _annotated(root, {p.key for p in out.changes if p.key}):
        out.before = _kept_texts(result, out.changes)
    _say(said, keep_versions(result, files, UNDO, "Before undoing a kept edit", writer[1]))
    # stamping takes a moment: what is written replaces the bytes the plan was made from, or nothing is
    if any(w.read(f) != plans[f][0] for f in files):
        raise writes.WriteRefused(
            "changed", "a file changed while loom was undoing a Keep; nothing was written, look at it again"
        )
    for rel in files:
        data, new, splices, spans, done = plans[rel]
        w.replace(rel, new, splices)
        out.spans[rel] = spans
        out.wrote[rel] = (data.decode("utf-8"), new.decode("utf-8"), done)
    answered: set[str] = set()
    for e, gen, _ in items:
        if e.id in out.ids:
            continue
        w.undid(gen)
        w.log(root / EDIT_LOG, reopened_event(e, writer))
        line = unanswered_event(root, e, writer)
        if line is not None and line["id"] not in answered:
            answered.add(line["id"])
            w.log(annotation_log(root), line)
        for rel in sorted({m.rel for f, _, m in items if f is e}):
            w.log(*ledger_line(hist, UNAPPLY, {"edit": e.id, "path": rel}, writer[1]))
        out.ids.append(e.id)


def _undo_in(
    hist: Path, raw: str, data: bytes, items: list[tuple[Edit, str, Any]]
) -> tuple[bytes, list[dict[str, Any]], list[tuple[int, int]], list[tuple[int, int, str]]] | dict[str, str]:
    """The bytes `data` (read as `raw`) of one file with the Keeps `items` undone, the undo's splices, and where the words put back stand in the scan's reading after it; or, by id, why a place is not established (`changed`, or `too-much` when the file changed too much around it to compare).

    Each Keep's words are taken out only at the place that Keep wrote them (`writes.place_in`), never wherever like words stand. The words put back are the Keep's own bytes where the file is as that Keep left it, and otherwise take the file's own line ending at their place. Where the file holds exactly one Keep's after bytes and every edit that Keep wrote in it is undone, its before bytes come back whole.
    """
    from loom import writes

    now = writes.digest(data)
    places: list[tuple[int, int, Any, str, str]] = []
    bad: dict[str, str] = {}
    for e, gen, m in items:
        try:
            span = writes.place_in(m, raw)
        except writes.TooChanged:
            bad[e.id] = "too-much"
            continue
        if span is None:
            bad[e.id] = "changed"
        else:
            places.append((*span, m, gen, e.id))
    places.sort(key=lambda x: x[0])
    for (_, b, _, _, i), (a, _, _, _, j) in zip(places, places[1:], strict=False):
        if b > a:
            bad.setdefault(i, "changed")
            bad.setdefault(j, "changed")
    if bad:
        return bad
    out: list[str] = []
    made: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    last = shift = 0
    for a, b, m, gen, _ in places:
        # the words it replaced: its own bytes where the file is as the Keep left it, else in the file's own line ending there
        old = (
            m.old
            if now == m.after
            else m.old.replace("\r\n", "\n").replace("\r", "\n").replace("\n", _ending_at(raw, a, b))
        )
        out += [raw[last:a], old]
        made.append({"edit": gen, "at": a + shift, "old": raw[a:b], "new": old})
        spans.append((a + shift, a + shift + len(old)))
        shift += len(old) - (b - a)
        last = b
    out.append(raw[last:])
    text = "".join(out)
    new = text.encode("utf-8")
    first = places[0][2]
    if (
        {m.act for _, _, m, _, _ in places} == {first.act}
        and now == first.after
        and set(first.edits) <= {g for *_, g, _ in places}
        and first.before is not None
    ):
        # the file is as that one Keep left it and every edit it wrote here is undone: its bytes before come back whole
        back = writes.fetch(hist, first.before)
        if back is not None and back.decode("utf-8", "replace") == text:
            new = back
    done = [(a, b, str(made_one["new"])) for (a, b, _, _, _), made_one in zip(places, made, strict=True)]
    return new, made, [(writes.reading_offset(text, a), writes.reading_offset(text, b)) for a, b in spans], done


def _moves(made: list[Any], was: str, now: str, cut: tuple[int, int, int]) -> bool:
    """Whether an act that changed `was[cut[0]:cut[1]]` into `now[cut[0]:cut[2]]` (both read as the scan reads them) can have moved a Keep's words: whether the region of its words, or of the words they replaced, stands once in either text and overlaps what the act changed there. A region that stands twice is never placed, so it is never moved either."""
    from loom import writes

    for m in made:
        for part in (writes.region(m), writes.region(m, side="before")):
            for text, end in ((was, cut[1]), (now, cut[2])):
                i = text.find(part)
                if i >= 0 and text.find(part, i + 1) < 0 and i < end and cut[0] < i + len(part):
                    return True
    return False


def follow_words(w: Any, path: str, before: bytes | None, after: bytes | None, writer: tuple[str, str]) -> None:
    """Stage in an act the records of the suggested edits whose words it moves in one file, by what the journal says loom wrote.

    For an act that writes a file's text whole or puts words back (a restore, a put-back, a Discard). A kept edit is opened again (`reopened`, `why: "restored"`) when `after` is the very bytes its Keep replaced, or when its Keep's words stand at their place in `before` (`writes.place_in`), the words they replaced stand at their place in `after`, and its words stand nowhere in `after` at all. An edit open again is recorded kept (`kept`, `why: "restored"`) when `after` is the very bytes its last Keep wrote, or when that Keep's words stand at their place in `after` and did not in `before`. Anything else leaves the record as it is: an edit is left kept with its words gone rather than open with its words in the file, which a Keep could write a second time. The annotation a Keep resolved follows its edit.

    Parameters
    ----------
    w : Act
        The act, under the door's lock; its journal is read as recovery left it.
    path : str
        The file the act writes.
    before, after : bytes or None
        The file's bytes before and after the act; None for a file absent.
    writer : (str, str)
        Who acts, for the records.

    See Also
    --------
    unkeep : the undo of a Keep, which updates its own edit's record.
    """
    from loom import writes
    from loom.paths import EDIT_LOG
    from loom.records.edits import answered_event, kept_event, reopened_event, replay, unanswered_event
    from loom.records.log import log_path as annotation_log

    try:
        was = before.decode("utf-8") if before is not None else ""
        now = after.decode("utf-8") if after is not None else ""
    except UnicodeDecodeError:
        return
    root, hist = w.root, w.history
    flat = " ".join(now.split())
    # what the act changes, read as the scan reads it: a Keep whose region it does not touch is passed over with no diff
    was_lf, now_lf = (x.replace("\r\n", "\n").replace("\r", "\n") for x in (was, now))
    pre, suf = writes.shared(was_lf, now_lf)
    cut = (pre, len(was_lf) - suf, len(now_lf) - suf)

    def placed(m: Any, text: str, side: str = "after") -> bool:
        try:
            return writes.place_in(m, text, side=side) is not None
        except writes.TooChanged:
            return False

    for e in replay(root)[0]:
        gen = keep_of(w.journal.wrote, e)
        at = w.journal.wrote.get(gen) if gen else None
        entry = writes.entry_at(root, at) if at is not None else None
        # only a Keep that wrote this file, so a restore of many files reads the store for the edits each holds
        if entry is None or path not in (entry.get("splices") or {}) or writes.untrusted(root, hist, entry):
            continue
        made = [m for m in writes.splices_of(hist, entry, gen) or [] if m.rel == path]
        if not made:
            continue
        # the very bytes on the other side of that Keep, in the direction this edit could move
        exact = writes.digest(after) == (made[0].before if e.status == "kept" else made[0].after)
        if not exact and not _moves(made, was_lf, now_lf, cut):
            continue
        if e.status == "kept":
            out = writes.digest(after) == made[0].before or all(
                placed(m, was)
                and placed(m, now, "before")
                and (not m.new.strip() or " ".join(m.new.split()) not in flat)
                for m in made
            )
            if out:
                w.log(root / EDIT_LOG, reopened_event(e, writer, "restored"))
                line = unanswered_event(root, e, writer)
                if line is not None:
                    w.log(annotation_log(root), line)
        elif e.status == "open":
            back = writes.digest(after) == made[0].after or all(placed(m, now) and not placed(m, was) for m in made)
            if back:
                kept = next((a for a in reversed(e.acts) if a.get("event") == "kept"), {})
                event = kept_event(e, writer, str(kept.get("hash") or ""))
                event["why"] = "restored"
                w.log(root / EDIT_LOG, event)
                line = answered_event(root, e, writer)
                if line is not None:
                    w.log(annotation_log(root), line)


def relook(root: Path, look: dict[str, Any]) -> None:
    """For a Keep or an undo that recovery finished, do what its follow-up does to the person's look: its in-place changes, then the words it wrote.

    The words loom wrote go into the reviewer's look, as `absorb` puts them, so they are not listed as the person's own edit. A journal travels with a copied quilt, so only the quilt's own reviewer's look is touched, and only at places in files the scan reads.

    Parameters
    ----------
    root : Path
        The quilt.
    look : dict
        The act's `look` from its `begin` line: `who`, whose look; `looked`, by file what the look holds once the act's in-place changes are in it (a text's hash, or None for a file it drops); and `spans`, by file the `[start, end]` places in the scan's reading after the act of the words loom wrote.

    See Also
    --------
    absorb : what puts in-place changes on loom's words into the look.
    """
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.scan.scan import scan

    who = look.get("who") if isinstance(look, dict) else None
    if not isinstance(who, str) or not who or who != (reviewer_identity(root)[0] or ""):
        return
    looked = look.get("looked")
    if isinstance(looked, dict):
        _set_look(root, who, {str(p): (h if isinstance(h, str) else None) for p, h in looked.items()})
    spans = look.get("spans")
    if not isinstance(spans, dict):
        return
    result = scan(load_quilt(root))
    for path, places in spans.items():
        if path not in result.files or not isinstance(places, list):
            continue
        at = [
            (s[0], s[1]) for s in places if isinstance(s, list) and len(s) == 2 and all(isinstance(x, int) for x in s)
        ]
        absorb(result, who, path, at)


def _after_unkeep(out: _Unkept, who: str, writer: tuple[str, str]) -> list[str]:
    """After the undo of Keeps is written: the words put back go into `who`'s look, so the undo is not listed as an edit in the file (`_undo_into_look`, with no listing of the person's changes where the look can be given the undo's own change), and where an annotation stands on the blocks, the annotations on the words taken out are carried onto the words put back.

    The files are written, so the undo is done whatever happens here: a failure of the look's shortcut falls back to the listing (`absorb`), and one of a step itself is returned in words, for the answer to say.
    """
    from loom.records.carry import carry_all

    said: list[str] = []
    after = None
    for path, (was, now, done) in out.wrote.items():
        if not who:
            continue
        try:
            if _undo_into_look(out.result.quilt, who, path, was, now, done):
                continue
        except Exception:  # noqa: BLE001 -- the shortcut's failure is not the person's news: the listing does what it would have
            pass
        try:
            after = after or _rescan(out.result)
            absorb(after, who, path, out.spans[path])
        except Exception as exc:  # noqa: BLE001 -- the undo is done; its look is a convenience, said when it fails
            said.append(
                f"the words put back in {path} did not go into your look ({type(exc).__name__}): Your Changes may list them as your edit"
            )
    from loom.records.carry import carry
    from loom.records.mdtext import is_markdown

    for path, (was, now, _done) in out.wrote.items():
        mine = [p for p in out.changes if p.path == path]
        if not is_markdown(path) or not mine:
            continue
        # a Markdown file's annotations are on its text, which the undo changed as a whole
        try:
            after = after or _rescan(out.result)
            carry(after, path, _lf(was), _lf(now), mine, writer)
        except Exception as exc:  # noqa: BLE001 -- the undo is done; the annotations stay on the words taken out, said
            said.append(
                f"the annotations on the words taken out of {path} were not carried onto the words put back ({type(exc).__name__})"
            )
    if out.before:
        try:
            carry_all(_rescan(after or out.result), out.before, out.changes, writer)
        except Exception as exc:  # noqa: BLE001 -- the undo is done; the annotations stay on the words taken out, said
            said.append(
                f"the annotations on the words taken out were not carried onto the words put back ({type(exc).__name__})"
            )
    return said


def _lf(text: str) -> str:
    """`text` with its line endings read as the scan reads them."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _undo_into_look(quilt: Any, who: str, path: str, was: str, now: str, done: list[tuple[int, int, str]]) -> bool:
    """Give `who`'s look of `path` the undo's own change, with no listing of the person's changes: where the look held the file as it was before the undo, it holds the file now; else each stretch the undo wrote over is carried to its place in the look (`writes.carry`) and the same words put there. False when a stretch's place in the look is not established, for `absorb` to do it by listing."""
    from loom import writes
    from loom.looks import _write, read_look, watching
    from loom.records.snapshots import read_raw, write_raw
    from loom.scan.hashing import sha256

    look = read_look(quilt.root, who)
    if look is None or not watching(quilt.config, quilt.root)(path):
        return True  # no look yet, or a place agents are denied, where nothing is listed
    held = look.files.get(path) or None
    if held is None:
        return False
    if held == sha256(was):
        text = now
    else:
        seen = read_raw(quilt.root, held, quilt.history_dir)
        if seen is None:
            return False
        try:
            spans = [writes.carry(was, seen, a, b) for a, b, _ in done]
        except writes.TooChanged:
            return False
        if any(s is None for s in spans):
            return False
        placed = sorted(((s[0], s[1], words) for s, (_, _, words) in zip(spans, done, strict=True) if s), reverse=True)
        if any(x1 > y0 for (y0, _, _), (_, x1, _) in zip(placed, placed[1:], strict=False)):
            return False
        text = seen
        for x0, x1, words in placed:
            text = text[:x0] + words + text[x1:]
    look.files[path] = write_raw(quilt.root, text, quilt.history_dir)
    _write(quilt.root, look)
    return True


def _annotated(root: Path, keys: set[str]) -> bool:
    """Whether an annotation on words stands on one of the blocks `keys`: the only case in which carrying annotations has anything to carry."""
    from loom.records.annotations import load_records

    return any(
        a.target_key in keys and a.selector is not None and not a.in_reply_to
        for r in load_records(root)[0]
        for a in r.annotations
    )


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
                        bool(
                            looked.get(path)
                        ),  # a file the look holds as absent at it (`looks.ABSENT`) is one it did not hold
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
    # words it puts back may be a suggested edit's: its record follows them
    follow_words(w, path, w.before.get(path), data, writer)
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


def _look_entry(result: ScanResult, who: str, path: str, changes: list[Pending]) -> tuple[bool, str | None]:
    """What `who`'s look holds of `path` once `changes` are in it, each alone (the look's text with each change's new words in place of its old), its text stored: `(True, hash)`, `(True, None)` for a file it drops, `(False, None)` before a first look. Writes no look (`_set_look`)."""
    from loom.records.snapshots import write_raw

    texts = look_texts(result, who)
    if texts is None:
        return False, None
    then, now = texts
    text = then.get(path, "")
    current = now.get(path) or ""
    for p in sorted(changes, key=lambda x: x.was, reverse=True):
        text = text[: p.was[0]] + current[p.span[0] : p.span[1]] + text[p.was[1] :]
    if now.get(path) is None and not text:
        return True, None
    return True, write_raw(result.quilt.root, text, result.quilt.history_dir)


#: Why an in-place change is not kept when it is no longer where it was listed: another act, or a save, moved the look or the file since.
CHANGED_SINCE_LISTED = "it changed since it was listed; look at it again"


def _look_entry_now(
    root: Path, history: Path, who: str, path: str, ids: list[str]
) -> tuple[bool, str | None, list[str]]:
    """What `who`'s look holds of `path` once the in-place changes `ids` are in it, each alone, cut again from the look and the file as they are now (`cuts`): `(held, entry, found)`, `found` the ids still there, `entry` a text's hash or None for a file the look drops, and `(False, None, [])` before a first look. Called under the door's lock, so a change listed against an earlier look or file goes in at its place now, never at a stale offset (Discard does the same, `_discard_in`). Writes no look (`_set_look`)."""
    from loom.looks import held as looks_held
    from loom.looks import read_look
    from loom.records.snapshots import read_raw, write_raw

    look = read_look(root, who)
    if look is None:
        return False, None, []
    seen = looks_held(look, path)
    old = (read_raw(root, seen, history) or "") if seen else ""
    try:
        text: str | None = (root / path).read_bytes().decode("utf-8")
    except FileNotFoundError:
        text = None
    except (OSError, UnicodeDecodeError):
        return True, seen, []
    wanted = set(ids)
    found = [(cid, was, span) for cid, was, span in cuts(path, old, text) if cid in wanted]
    now = text or ""
    out = old
    for _, (o0, o1), (n0, n1) in sorted(found, key=lambda f: f[1], reverse=True):
        out = out[:o0] + now[n0:n1] + out[o1:]
    kept = [cid for cid in ids if cid in {f[0] for f in found}]
    if text is None and not out:
        return True, None, kept
    return True, write_raw(root, out, history), kept


def _set_look(root: Path, who: str, looked: dict[str, str | None]) -> None:
    """Give `who`'s look each entry of `looked`, a text's hash or None for a file it drops (`_look_entry`); nothing before a first look."""
    from loom.looks import _write, read_look

    look = read_look(root, who)
    if look is None:
        return
    for path, entry in looked.items():
        if entry is None:
            look.files.pop(path, None)
        else:
            look.files[path] = entry
    _write(root, look)


def _into_look(result: ScanResult, who: str, path: str, changes: list[Pending]) -> None:
    """Put `changes` of `path` into `who`'s look, each alone, at once (`_look_entry`, `_set_look`): for a follow-up inside its act, whose recovery redoes it from the act's `look`."""
    held, entry = _look_entry(result, who, path, changes)
    if held:
        _set_look(result.quilt.root, who, {path: entry})


def absorb(result: ScanResult, who: str, path: str, spans: list[tuple[int, int]]) -> None:
    """After loom wrote the person's words at `spans` of `path`, put into `who`'s look every in-place change on those words, so the file and the look agree there; nothing before a first look."""
    changes = [
        p for p in in_place(result, who) if p.path == path and any(p.span[0] <= b and a <= p.span[1] for a, b in spans)
    ]
    if changes:
        _into_look(result, who, path, changes)


def keep_accepted(result: ScanResult, who: str, keys: list[str]) -> list[str]:
    """Keep each in-place change that touches only blocks `keys`, which the person just accepted having seen it; returns the paths whose look moved.

    A change running across a block not accepted stays, since that one still waits. For the viewer's Accept, which shows the change it keeps; `loom accept` shows none, and leaves the look alone.
    """
    from loom import writes
    from loom.history.acts import KEEP, ledger_line

    accepted = set(keys)
    chosen = [p for p in in_place(result, who) if p.blocks and accepted.issuperset(p.blocks)]
    if not chosen:
        return []
    root, hist = result.quilt.root, result.quilt.history_dir
    # the look's change and the keep lines in one act, as Keep's, so a cut accept writes neither; cut again under the door, as Keep's
    looked: dict[str, str | None] = {}
    moved: list[str] = []
    with writes.act(root, hist, "keep", who) as w:
        for path in sorted({p.path for p in chosen}):
            held, entry, found = _look_entry_now(root, hist, who, path, [p.id for p in chosen if p.path == path])
            if not found:
                continue
            if held:
                looked[path] = entry
            w.log(*ledger_line(hist, KEEP, {"who": who, "path": path, "changes": found}, who))
            moved.append(path)
        if looked:
            w.look = {"who": who, "looked": looked}
            w.then(lambda: _set_look(root, who, looked))
    return moved


def patch_of(result: ScanResult, change: Pending, who: str | None = None) -> str:
    """The change as a unified diff of its file against the quilt root: an in-place change from the text it was cut from with its old words back, a suggested edit from the file now."""
    from loom.records.edits import Placed, compose, patch
    from loom.reshape.ids import unified_diff

    if change.kind == "suggested":
        if change.edit is None:
            return ""
        placed = next((pl for e, pl in compose(result, [change.edit]) if isinstance(pl, Placed)), None)
        return patch(result, placed) if placed is not None else ""
    texts = look_texts(result, reviewer(result) if who is None else who)
    then, now = (texts[0].get(change.path, ""), texts[1].get(change.path) or "") if texts else ("", "")
    back = now[: change.span[0]] + then[change.was[0] : change.was[1]] + now[change.span[1] :]
    return unified_diff(back, now, change.path)
