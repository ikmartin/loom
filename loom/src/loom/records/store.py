"""The Records object: everything durable that is not source, loaded once per query, and the states, causes, facts, and derived states computed from it.

`compute` is pure over the scan result and the records; `apply` writes those results into a manifest and the diffs directory.
"""

from __future__ import annotations

import copy
import difflib
import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from loom.clock import today
from loom.paths import ANNOTATION_LOG, ANNOTATION_TYPES, EDIT_LOG, REVIEW_OBSERVATIONS
from loom.records.annotations import Annotation, Record, load_records
from loom.records.ids import repeated
from loom.records.ledger import AcceptRow, latest_rows, read_ledger
from loom.records.locate import block_hash, follow
from loom.records.selectors import Selector, resolve_selector
from loom.records.snapshots import read_snapshot
from loom.render.uses import used
from loom.scan.hashing import hash_text, mathematical_hash, normalize
from loom.scan.memo import Memo
from loom.scan.model import Diagnostic, Fix
from loom.scan.nodes import NodeRec
from loom.scan.owntext import key_hash, own_text
from loom.scan.scan import ScanResult
from loom.sessions import INDEX as SESSION_INDEX


@dataclass
class Cause:
    kind: str
    id: str | None = None
    when: str | None = None
    before: str | None = None  # snapshot hash
    after: str | None = None  # current hash
    via: str | None = None  # direct dependency through which an indirect edit is reached

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "diff": None}
        if self.id:
            d["id"] = self.id
        if self.when:
            d["when"] = self.when
        if self.via:
            d["via"] = self.via
        return d


@dataclass
class KeyState:
    key: str
    state: str  # draft | accepted | incomplete
    row: AcceptRow | None = None
    fresh: bool = True
    causes: list[Cause] = field(default_factory=list)
    #: Open annotations on the key, by type id: only a type that stays open until resolved opens one.
    open: dict[str, int] = field(default_factory=dict)
    detached: int = 0
    previous_key_match: str | None = None

    @property
    def label(self) -> str:
        if self.state == "accepted" and not self.fresh:
            return "accepted, stale"
        return self.state


@dataclass
class ResolvedAnnotation:
    annotation: Annotation
    record: Record
    span: tuple[int, int] | None  # in the target's own text (concatenated pieces); on a page, offsets into its text
    detached: bool
    recorded: bool = True  # the text this was written against is still recoverable: it is the current text, or frozen
    work: str = ""  # the reference, when the target is a work or a page of its PDF rather than a key (plan 0.13 item 2)
    target: str = ""  # the target key now: a whole document's path followed across moves, else the key as written
    in_doc: str | None = None  # the document `in` names now, followed across moves; as written when it is gone
    # on a PDF page: where it stands now, found again on a changed file (`marks.refind`) when `refound`
    rects: list[list[float]] | None = None
    page: int | None = None
    strokes: list[list[float]] | None = None
    refound: bool = False
    # the changes still waiting on the person that its words touch (`pending.py`), by id
    on_changes: list[str] = field(default_factory=list)
    # taken in from a PDF's own annotation that is still in the file as it is now: that annotation's reference
    hides: str | None = None
    # on no block: its key names one that no longer holds the text it was written on, or none, and nothing says where that text went (`records.locate.follow`); its `target` is '', so nothing downstream names a block for it, and the manifest lists it in `unplaced`
    unplaced: bool = False


def is_document_path(result: ScanResult, path: str) -> bool:
    """Whether `path` names a document, live or not, rather than a key: a `.tex` path, which no key (`prose:` keys aside) is."""
    return path.endswith(".tex") and not path.startswith("prose:")


#: Each scan's placements by annotation id (`placed_key`), with the annotation log's size and time they were read at; one scan at a time.
_PLACED: tuple[ScanResult, tuple[int, int], dict[str, str | None]] | None = None


def placed_key(result: ScanResult, ann: Annotation) -> str | None:
    """The key of the block `ann` is shown on now, as `Records.resolved` places it, which may not be the key it was written on; None for one on no block. What a listing names a note by.

    A note the scan does not know (written since) is named by the key it was written on. What is remembered is kept for one scan and one state of the annotation log, so a note restated by a write since is placed again.
    """
    global _PLACED
    log = result.quilt.root / ANNOTATION_LOG
    try:
        st = log.stat()
        stamp_ = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp_ = (0, 0)
    held = _PLACED
    if held is None or held[0] is not result or held[1] != stamp_:
        records = Records(result.quilt.root, result.quilt.history_dir)
        held = _PLACED = (
            result,
            stamp_,
            {
                r.annotation.id: None if r.unplaced else (r.target or r.annotation.target_key)
                for r in records.resolved(result)
            },
        )
    return held[2].get(ann.id, ann.target_key)


def _why_unplaced(result: ScanResult, key: str) -> str:
    """Why a note on `key` is on no block, as a sentence a viewer shows as it is: its key names nothing, or a block in a file no document reads now, or a block that no longer holds its text."""
    owner = result.assembly.regions[key].container if key in result.assembly.regions else key
    node = result.nodes.get(owner)
    if node is None:
        return "The block it was written on is gone, and nothing says where its words went."
    if node.kind not in ("master", "file") and not node.reached_by:
        return "Its block is in a file no document reads now; it is back on that block once a document reads the file again."
    return "Its block was deleted, or changed so far that which block it is cannot be told."


def written_in(result: ScanResult, ann: Annotation) -> str:
    """The document a note on no block is listed in and opened from: the one it names (`in`), else the first that read its block's file when it was written and is a document still (`context.documents`), else one that reads the block its key names now, or the document its key is, else the quilt's default document; '' in a quilt with none.

    Every note on no block belongs to exactly one document, so no reader is left without a place to find it.
    """
    named = [ann.in_doc] if ann.in_doc else []
    named += [str(d) for d in (ann.context or {}).get("documents") or []]
    for path in named:
        found = result.current_document(path)
        if found:
            return found
    key = ann.target_key
    if key in result.masters:
        return key
    owner = result.assembly.regions[key].container if key in result.assembly.regions else key
    node = result.nodes.get(owner)
    for path in node.reached_by if node is not None else []:
        if path in result.masters:
            return str(path)
    return result.default_master or (result.masters[0] if result.masters else "")


#: Acceptance states by (reviewer, the ledger as read), each kept for the one scan it was computed against; see `Records.key_states`.
_ACCEPTANCE: dict[tuple[str | None, str], tuple[ScanResult, dict[str, KeyState], dict[str, str]]] = {}


def _fresh(states: dict[str, KeyState]) -> dict[str, KeyState]:
    """A copy of each state for the review facts to fill in: those write only the fact fields, so the causes and the row are shared."""
    return {k: replace(ks, open=dict(ks.open)) for k, ks in states.items()}


class Records:
    def __init__(self, root: Path, history_dir: Path | None = None, *, reviewer: str | None = None) -> None:
        from loom.scan.quilt import load_quilt

        self.root = root
        # the history wherever `[quilt] history` puts it, read from the quilt's config when the caller has not
        self.history_dir = history_dir if history_dir is not None else load_quilt(root).history_dir
        self.rows = read_ledger(root)
        from loom.scan.quilt import reviewer_identity

        local, source = reviewer_identity(root)
        self.reviewer = local if reviewer is None else reviewer
        self.reviewer_source = (
            (source if source in ("", "git config user.name") else "local user configuration")
            if reviewer is None
            else "--as"
        )
        self.latest = latest_rows(self.rows, self.reviewer)
        self.shared_latest = latest_rows(self.rows)
        self.records, self.problems = load_records(root)
        from loom.records.types import load_types

        self.types = load_types(root)
        self._resolved_cache: tuple[ScanResult, list[ResolvedAnnotation]] | None = None
        self._snapshot_seen: dict[str, bool] = {}
        self._hash_cache: tuple[ScanResult, dict[str, str]] | None = None

    def opens(self, a: Annotation) -> bool:
        """Whether `a` is of a type that stays open until resolved; an untyped annotation, or one whose type the quilt no longer lists, only informs."""
        t = self.types.get(a.type)
        return bool(t and t.open)

    def look(self, a: Annotation) -> dict[str, Any]:
        """The whole look `a` is drawn with: its type's under what is set on it, or, its type gone, the look it was last drawn with."""
        from loom.records.types import drawn_look

        t = self.types.get(a.type)
        if t is None and a.drawn:
            return dict(a.drawn)
        return drawn_look(t, a.own_look, self.types.plain)

    # ---- text helpers --------------------------------------------------------

    @staticmethod
    def own_pieces(result: ScanResult, node: NodeRec) -> tuple[str, list[tuple[int, int, int]]]:
        """Own text without child markers plus a map [(concat_start, file_offset, length)] for selector spans."""
        src = result.files[node.file]
        pieces: list[tuple[int, int, int]] = []
        parts: list[str] = []
        pos = 0
        for a, b in node.own:
            parts.append(src.text[a:b])
            pieces.append((pos, a, b - a))
            pos += b - a
        return "".join(parts), pieces

    @staticmethod
    def to_file_span(pieces: list[tuple[int, int, int]], span: tuple[int, int]) -> tuple[int, int] | None:
        a, b = span
        for cstart, fstart, length in pieces:
            if cstart <= a < cstart + length:
                end = fstart + (b - cstart)
                if b <= cstart + length:
                    return fstart + (a - cstart), end
                return fstart + (a - cstart), fstart + length
        return None

    # ---- hashes ---------------------------------------------------------------

    @staticmethod
    def row_document(result: ScanResult, row: AcceptRow) -> str | None:
        """The document an acceptance row is read against now: its `master` followed across moves (`ScanResult.current_document`), or the default master for a row that names none.

        None when the recorded document is gone; the row's key is then stale with `document-gone`, and `loom accept --stale` falls back to `_acceptance_master`.
        """
        if not row.master:
            return result.default_master
        return result.current_document(row.master)

    @staticmethod
    def preamble_hash(result: ScanResult, master: str | None) -> str:
        closure = result.closures.get(master) if master else None
        return hash_text(closure.raw_text()) if closure else ""

    @staticmethod
    def closure_hashes(result: ScanResult, key: str) -> dict[str, str]:
        return result.dependencies.hashes(key)  # type: ignore[no-any-return]

    @staticmethod
    def direct_keys(result: ScanResult, key: str) -> list[str]:
        return result.dependencies.direct(key)  # type: ignore[no-any-return]

    def snapshot(self, digest: str) -> str | None:
        return read_snapshot(self.root, digest, self.history_dir)

    def same_mathematics(self, result: ScanResult, key: str, before: str, current: str | None) -> bool:
        """Compare saved source to current mathematics, conservatively retaining missing-snapshot differences."""
        if before == current:
            return True
        if current is None or key not in result.dependencies.texts:
            return False
        old = self.snapshot(before)
        return old is not None and mathematical_hash(old) == mathematical_hash(result.dependencies.texts[key])

    # ---- states -----------------------------------------------------------------

    def key_states(self, result: ScanResult, *, observe: bool = True) -> dict[str, KeyState]:
        """Every key's acceptance state and review facts against `result`.

        The states are read from the ledger and the scan alone, so they are kept for the scan they were computed against (`_ACCEPTANCE`) and reused while the ledger and the reviewer are the same: a served quilt rebuilds after every annotation, session and message, none of which changes one. The review facts read the annotations and are computed every time.
        """
        stamp = (self.reviewer, hashlib.sha256(repr(self.rows).encode()).hexdigest())
        kept = _ACCEPTANCE.get(stamp)
        if kept is not None and kept[0] is result:
            states, current_hashes = _fresh(kept[1]), kept[2]
        else:
            states, current_hashes = self._acceptance_states(result)
            for old in [k for k, v in _ACCEPTANCE.items() if v[0] is not result]:
                del _ACCEPTANCE[old]
            _ACCEPTANCE[stamp] = (result, _fresh(states), current_hashes)
        if observe and self.reviewer:
            self._observe_causes(states)
        self._review_facts(result, states, current_hashes)
        self._previous_key_matches(result, states, current_hashes)
        return states

    def placed(self, result: ScanResult) -> dict[str, AcceptRow]:
        """The reviewer's latest rows by the key of the block each is on now: a row is a claim about exact text, so it goes with that text as a record does (`records.locate.follow`, with the row's `context`), and is on no block where nothing says which; a row written before `context` was recorded stays on a stable key's block.

        Two rows that land on one block leave it to the one whose text it holds, or whose key it is; neither, and the block has none.
        """
        claims: dict[str, list[AcceptRow]] = {}
        for key, row in self.latest.items():
            found = follow(result, key, result.nodes.get(key), row.text, context=row.context)
            if found is not None:
                claims.setdefault(found.key, []).append(row)
        out: dict[str, AcceptRow] = {}
        for key, rows in claims.items():
            if len(rows) > 1:
                rows = [r for r in rows if r.text == block_hash(result, key)] or [r for r in rows if r.key == key]
            if len(rows) == 1:
                out[key] = rows[0]
        return out

    def _acceptance_states(self, result: ScanResult) -> tuple[dict[str, KeyState], dict[str, str]]:
        """The states and their causes, from the ledger and the scan; and the current hash of every key, which the review facts compare against."""
        states: dict[str, KeyState] = {}
        kinds = ("environment", "proof", "section")
        if self._hash_cache is None or self._hash_cache[0] is not result:
            self._hash_cache = (result, {k: key_hash(result, k) for k, n in result.nodes.items() if n.kind in kinds})
        current_hashes = dict(self._hash_cache[1])
        current_hashes.update({k: hash_text(t) for k, t in result.dependencies.texts.items() if t is not None})
        placed = self.placed(result)
        for key, n in result.nodes.items():
            if n.kind not in kinds:
                continue
            row = (self.shared_latest if n.external else placed).get(key)
            ks = KeyState(key=key, state="draft", row=row)
            if n.kind == "section":
                # A section is a container, not a claim: no state, and `loom accept` refuses one. It is carried here only so that its review facts are computed, because `loom annotate` accepts a section as a target and an annotation filed on one was stored and then shown nowhere (DR-172).
                ks.state = ""
                states[key] = ks
                continue
            if n.incomplete:
                ks.state = "incomplete"
            if row is not None:
                ks.state = "incomplete" if n.incomplete else "accepted"
                current = current_hashes[key]
                closure_now = self.closure_hashes(result, key)
                if not self.same_mathematics(result, key, row.text, current):
                    # What moved under an external node is loom's copy of somebody else's theorem, not the author's
                    # own text, and the cause is the useful half of the seal: the transcription you checked has moved.
                    moved = "transcription-changed" if n.external else "own-text-changed"
                    ks.causes.append(Cause(moved, before=row.text, after=current, when=_when(result, n)))
                if row.basis and n.kind == "environment" and row.basis != n.basis:
                    ks.causes.append(Cause("basis-changed", before=row.basis, after=n.basis, when=_when(result, n)))
                direct_now = {d: closure_now[d] for d in self.direct_keys(result, key) if d in closure_now}
                accepted_direct = row.direct
                for dep, h in accepted_direct.items():
                    if dep in result.dependencies.texts and result.dependencies.texts[dep] is None:
                        ks.causes.append(Cause("dependency-scope-unavailable", id=dep))
                    elif h == "unavailable":
                        ks.causes.append(Cause("dependency-baseline-unavailable", id=dep))
                    elif dep not in result.dependencies.texts:
                        ks.causes.append(Cause("dependency-removed", id=dep, before=h))
                    elif not self.same_mathematics(result, dep, h, direct_now.get(dep)):
                        ks.causes.append(
                            Cause(
                                "dependency-changed",
                                id=dep,
                                before=h,
                                after=direct_now.get(dep),
                                when=_when(result, result.nodes[result.dependencies.owners[dep]]),
                            )
                        )
                for dep in result.dependencies.closure(key):
                    if (
                        dep in result.dependencies.texts
                        and result.dependencies.texts[dep] is None
                        and not any(c.id == dep for c in ks.causes)
                    ):
                        ks.causes.append(Cause("dependency-scope-unavailable", id=dep))
                for dep in direct_now:
                    if dep not in accepted_direct:
                        ks.causes.append(Cause("dependency-added", id=dep))
                document = self.row_document(result, row)
                if row.master and document is None:
                    # the document the row was compiled against is gone and nothing records where it went: its preamble cannot be compared, and saying it changed would be false
                    ks.causes.append(Cause("document-gone", id=result.document_trail(row.master)[-1]))
                else:
                    pre = self.preamble_hash(result, document)
                    if row.preamble and row.preamble != pre:
                        ks.causes.append(Cause("preamble-changed", before=row.preamble, after=pre))
            states[key] = ks
        # A stable direct dependency is an acceptance boundary. Its own unresolved edit
        # propagates; reaccepting it without changing its text resolves the indirect cause.
        visited: set[str] = set()

        def propagate(key: str, visiting: set[str]) -> None:
            if key in visited or key in visiting or key not in states:
                return
            visiting.add(key)
            ks = states[key]
            if ks.row and result.graph:
                for dep in self.direct_keys(result, key):
                    if dep not in result.dependencies.texts or dep not in ks.row.closure:
                        continue
                    if not self.same_mathematics(result, dep, ks.row.closure[dep], current_hashes.get(dep)):
                        continue  # the direct dependency already has its own cause
                    upstream = states.get(dep)
                    if upstream and upstream.row:
                        propagate(dep, visiting)
                        origins = [c.id for c in upstream.causes if c.kind == "dependency-changed" and c.id]
                    else:
                        origins = [
                            ancestor
                            for ancestor in result.dependencies.closure(dep)
                            if ancestor != dep
                            and ancestor in ks.row.closure
                            and not self.same_mathematics(
                                result, ancestor, ks.row.closure[ancestor], current_hashes.get(ancestor)
                            )
                        ]
                        labels = result.dependencies.references.get(dep, set())
                        for prior, digest in ks.row.closure.items():
                            if prior in result.dependencies.texts:
                                continue
                            old = self.snapshot(digest) or ""
                            old_labels = set(re.findall(r"\\label\s*\{([^}]+)\}", old)) | {prior}
                            if labels & old_labels:
                                origins.append(prior)
                    for origin in origins:
                        if origin == key or any(c.id == origin for c in ks.causes):
                            continue
                        ks.causes.append(
                            Cause(
                                "dependency-changed" if origin in result.dependencies.texts else "dependency-removed",
                                id=origin,
                                via=dep,
                                before=ks.row.closure.get(origin),
                                after=current_hashes.get(origin),
                                when=_when(result, result.nodes[result.dependencies.owners[origin]])
                                if origin in result.dependencies.owners
                                else None,
                            )
                        )
                ks.fresh = not ks.causes
            visiting.remove(key)
            visited.add(key)

        for key in states:
            propagate(key, set())
        return states, current_hashes

    def _observe_causes(self, states: dict[str, KeyState]) -> None:
        """Remember the first scan that saw each unresolved cause, once per acceptance epoch."""
        path = self.root / REVIEW_OBSERVATIONS
        try:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, ValueError):
            old = {}
        if not isinstance(old, dict):
            old = {}
        partitions = old.get("reviewers", {})
        old_partition = partitions.get(self.reviewer, {})
        active: dict[str, str] = {}
        for key, state in states.items():
            if not state.row:
                continue
            for cause in state.causes:
                identity = json.dumps(
                    [key, state.row.date, state.row.text, cause.kind, cause.id, cause.via],
                    separators=(",", ":"),
                )
                first = old_partition.get(identity)
                active[identity] = first if isinstance(first, str) else today()
                cause.when = active[identity]
        if active != old_partition:
            partitions[self.reviewer] = active
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps({"reviewers": partitions}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, path)

    def _review_facts(self, result: ScanResult, states: dict[str, KeyState], current: dict[str, str]) -> None:
        for res in self.resolved(result):
            a = res.annotation
            ks = states.get(res.target or a.target_key)
            if ks is None or res.unplaced:
                continue
            # what awaits an answer, which is what a count is for: an untyped annotation, or one of a type that only informs, asks nothing
            if a.in_reply_to is None and a.status == "open" and self.opens(a):
                ks.open[str(a.type)] = ks.open.get(str(a.type), 0) + 1
            if res.detached:
                ks.detached += 1

    def _previous_key_matches(self, result: ScanResult, states: dict[str, KeyState], current: dict[str, str]) -> None:
        by_hash: dict[str, list[str]] = {}
        for k, h in current.items():
            by_hash.setdefault(h, []).append(k)
        for key, row in self.latest.items():
            ks = states.get(key)
            if ks is not None and ks.fresh:
                continue
            for cand in by_hash.get(row.text, []):
                cn = result.nodes.get(cand)
                if (
                    cn is not None
                    and cn.kind == "proof"
                    and cand != key
                    and cand in states
                    and states[cand].row is None
                ):
                    states[cand].previous_key_match = key

    def derived(self, result: ScanResult, states: dict[str, KeyState]) -> dict[str, dict[str, bool]]:
        assert result.graph is not None
        proved: dict[str, bool] = {}
        for key, n in result.nodes.items():
            if n.kind != "environment":
                continue
            s = states.get(key)
            ok = bool(s and s.state == "accepted" and s.fresh and not n.incomplete)
            good_proof = any(
                states.get(p) and states[p].state == "accepted" and states[p].fresh and not result.nodes[p].incomplete
                for p in n.proofs
            )
            proved[key] = ok and (
                (n.basis == "local-proof" and (good_proof or n.inline_proof)) or n.basis in ("expository", "assumption")
            )
        settled: dict[str, bool] = {}
        visiting: set[str] = set()

        def is_settled(key: str) -> bool:
            if key in settled:
                return settled[key]
            n = result.nodes.get(key)
            if n is None and key.startswith("equation:"):
                if key in visiting or result.dependencies.texts.get(key) is None:
                    return False
                visiting.add(key)
                ok = all(is_settled(d) for d in result.dependencies.direct(key))
                visiting.remove(key)
                settled[key] = ok
                return ok
            if n is None:
                return False
            # A section can be referenced as context, but has no statement or proof
            # to accept. Keep it in dependency tracking without making it a proof obligation.
            if n.kind == "section":
                settled[key] = True
                return True
            if n.basis == "cited-result":
                settled[key] = True
                return True
            if key in visiting:
                return False
            visiting.add(key)
            ok = proved.get(key, False)
            if ok:
                assert result.graph is not None
                deps = set(result.dependencies.closure(key)) - {key}
                for p in n.proofs:
                    st = states.get(p)
                    if st and st.state == "accepted" and st.fresh:
                        deps |= set(result.dependencies.closure(p)) - {key, p}
                ok = all(is_settled(d) for d in deps)
            visiting.discard(key)
            settled[key] = ok
            return ok

        out: dict[str, dict[str, bool]] = {}
        for key, n in result.nodes.items():
            if n.kind == "environment":
                out[key] = {"proved": proved.get(key, False), "settled": is_settled(key)}
        return out

    # ---- annotations -----------------------------------------------------------

    def resolved(self, result: ScanResult) -> list[ResolvedAnnotation]:
        if self._resolved_cache is not None and self._resolved_cache[0] is result:
            return self._resolved_cache[1]
        out: list[ResolvedAnnotation] = []
        texts: dict[str, str] = {}  # the text a quote is found in: no child markers
        hashed: dict[str, str] = {}  # the text a version is: with them, as every hash is taken
        works: dict[str, str] = {}
        for rec in self.records:
            for a in rec.annotations:
                if a.anchor is not None:
                    res = self._on_page(result, a, rec, works)
                    res.target = a.target_key
                    out.append(res)
                    continue
                if a.target_key not in result.nodes and (a.page is not None or self._work(result, a, works)):
                    out.append(self._on_pdf_or_work(result, a, rec, works))
                    continue
                # a document named by path is wherever the history's moves have taken it
                in_doc = (result.current_document(a.in_doc) or a.in_doc) if a.in_doc else None
                target = a.target_key
                if target not in result.nodes and is_document_path(result, target):
                    target = result.current_document(target) or target
                n = result.nodes.get(target)
                if n is None:
                    region = result.assembly.regions.get(target)
                    n = result.nodes.get(region.container) if region else None
                # a key named by place goes with the text it was written on, and is never read on the block that took its place
                found = follow(
                    result,
                    target,
                    n,
                    a.target_hash,
                    quote=a.selector.exact if a.selector else "",
                    context=a.context,
                )
                if found is None and n is not None:
                    out.append(
                        ResolvedAnnotation(
                            a, rec, None, True, self._recorded(a, None), target="", in_doc=in_doc, unplaced=True
                        )
                    )
                    continue
                if found is not None and found is not n:
                    n, target = found, found.key
                if n is None:
                    out.append(
                        ResolvedAnnotation(
                            a, rec, None, True, self._recorded(a, None), target="", in_doc=in_doc, unplaced=True
                        )
                    )
                    continue
                if in_doc and in_doc not in n.reached_by:
                    # a claim about the node in one document, and that document no longer holds it
                    out.append(
                        ResolvedAnnotation(a, rec, None, True, self._recorded(a, None), target=target, in_doc=in_doc)
                    )
                    continue
                if n.key not in texts:
                    texts[n.key], _ = self.own_pieces(result, n)
                    hashed[n.key] = own_text(result, n)
                kept = self._recorded(a, hashed[n.key])
                if a.selector is None:
                    out.append(ResolvedAnnotation(a, rec, None, False, kept, target=target, in_doc=in_doc))
                    continue
                span, touched = self._on_kept(result, n, texts[n.key], a.selector)
                out.append(
                    ResolvedAnnotation(
                        a, rec, span, span is None, kept, target=target, in_doc=in_doc, on_changes=touched
                    )
                )
        self._resolved_cache = (result, out)
        return out

    def _on_page(self, result: ScanResult, a: Annotation, rec: Record, works: dict[str, str]) -> ResolvedAnnotation:
        """An annotation on a page of a work's PDF, resolved against that PDF's page text rather than against a key's text.

        `recorded` is whether the PDF the anchor names is the one the reference holds now. `detached` is a text anchor whose quotation no longer locates in the page's text; a box is never detached, because the rectangles are the record. The target is the work's reference.
        """
        from loom.library.store import read
        from loom.refs.pages import mapped, read_map, read_page
        from loom.refs.search import locate_offsets

        assert a.anchor is not None
        ref = self._work(result, a, works)
        node = read(self.root, ref) if ref else None
        home = mapped(self.root, node.pdf) if node is not None and node.pdf else None
        if home is None:
            return ResolvedAnnotation(a, rec, None, True, False, ref)
        m = read_map(home)
        recorded = m is not None and bool(m.sha256) and m.sha256 == a.anchor.sha256
        if a.anchor.basis != "text":
            moved = None if recorded or m is None else self._box_again(result, ref, a)
            if moved is None:
                return ResolvedAnnotation(a, rec, None, False, recorded, ref, page=a.anchor.page)
            return ResolvedAnnotation(
                a, rec, None, False, recorded, ref, rects=moved.rects, page=moved.page, refound=True
            )
        exact = a.selector.exact if a.selector else ""
        page = read_page(home, a.anchor.page)
        span = locate_offsets(page, exact) if page and exact else None
        if span is not None or recorded or m is None or not exact:
            return ResolvedAnnotation(a, rec, span, span is None, recorded, ref, page=a.anchor.page)
        # the work's PDF changed: its words are looked for on every page's text, its own first
        for n in range(1, m.pages + 1):
            text = read_page(home, n) if n != a.anchor.page else None
            span = locate_offsets(text, exact) if text else None
            if span is not None:
                return ResolvedAnnotation(a, rec, span, False, recorded, ref, page=n, refound=True)
        return ResolvedAnnotation(a, rec, None, True, recorded, ref, page=a.anchor.page)

    @staticmethod
    def _on_kept(
        result: ScanResult, node: NodeRec, own: str, sel: Selector
    ) -> tuple[tuple[int, int] | None, list[str]]:
        """Where an annotation stands in its key's text now, read against the text as the person kept it, and the changes waiting on the person that its words touch.

        Its words are looked for in the key's own text with every in-place change still waiting put back (`pending.kept_own`), and placed on the text now through it; words found only in the text now, as on a change's new words, are placed there.
        """
        from loom.pending import in_place, kept_own

        kept = kept_own(result, node) if in_place(result) else None
        if kept is not None:
            found = resolve_selector(kept.text, sel)
            if found is not None:
                return kept.to_now(*found)
        span = resolve_selector(own, sel)
        if span is None or kept is None:
            return span, []
        touched = [cid for k0, k1, n0, n1, cid in kept.segments if cid and n0 < span[1] and span[0] < n1]
        return span, touched

    @staticmethod
    def _source(result: ScanResult, res: ResolvedAnnotation) -> dict[str, Any] | None:
        """Where a mark on a work's page stands in the work's source (`refs.sourcemap.source_of`), or None; computed as the manifest is published, never recorded."""
        a = res.annotation
        page = res.page or (a.anchor.page if a.anchor else a.page)
        if not res.work or not page or res.detached or a.selector is None or not a.selector.exact:
            return None
        from loom.refs.sourcemap import source_of

        return source_of(result, res.work, a.selector.exact, a.selector.prefix, a.selector.suffix, page)

    def _box_again(self, result: ScanResult, ref: str, a: Annotation) -> Any:
        """A box on a work's page found again on the reference's changed PDF by the words around it and its gap (`marks.refound`), or None; a box that records neither stands where it was drawn."""
        from loom.records.marks import artifact_of, reference_pdf, refound

        pdf = reference_pdf(self.root, ref)
        if a.gap is None or a.anchor is None or pdf is None:
            return None
        return refound(result, pdf, a, artifact_of(pdf))

    def _work(self, result: ScanResult, a: Annotation, works: dict[str, str]) -> str:
        """The reference `a`'s target names, '' when it names none; looked up once per target."""
        from loom.library.ids import REFERENCE, kind_of
        from loom.library.store import exists

        if a.target_key not in works:
            ref = a.target_key
            works[ref] = ref if kind_of(ref) == REFERENCE and exists(self.root, ref) else ""
        return works[a.target_key]

    def _on_pdf_or_work(
        self, result: ScanResult, a: Annotation, rec: Record, works: dict[str, str]
    ) -> ResolvedAnnotation:
        """An annotation on a page of a PDF that records its own place, or on a work as a whole.

        On a page, unchanged bytes keep it where it was written, and nothing reads the file. When the PDF's bytes changed under it, it is found again anywhere in the document by the words it recorded around it (`marks.refound`) and stands there, `refound`; when they are not found, or the file is gone, it is detached (A3). One that names no hash was written with nothing to compare, and nothing is claimed of it. A whole work has nothing to detach from.
        """
        from loom.records.marks import artifact_of, pdf_of, refound

        ref = self._work(result, a, works)
        if a.page is None:
            return ResolvedAnnotation(a, rec, None, False, True, ref, target=a.target_key)
        pdf = pdf_of(result, a.target_key, ref)

        def where(detached: bool, hides: str | None = None) -> ResolvedAnnotation:
            return ResolvedAnnotation(
                a,
                rec,
                None,
                detached,
                True,
                ref,
                target=a.target_key,
                rects=a.rects,
                page=a.page,
                strokes=a.strokes,
                hides=hides,
            )

        if pdf is None or not pdf.is_file():
            return where(bool(a.artifact))
        now = artifact_of(pdf)
        own, sha = (a.origin or {}).get("ref"), (a.origin or {}).get("sha")
        # the PDF's own annotation it came from is still in the file, so a viewer drawing the file's annotations hides that one
        hides = str(own) if own and sha == now else None
        if a.artifact is None or a.artifact == now:
            return where(False, hides)
        moved = refound(result, pdf, a, now)
        if moved is None:
            return where(True, hides)
        return ResolvedAnnotation(
            a,
            rec,
            None,
            False,
            True,
            ref,
            target=a.target_key,
            rects=moved.rects,
            page=moved.page,
            strokes=moved.strokes,
            refound=True,
            hides=hides,
        )

    def _recorded(self, a: Annotation, current: str | None) -> bool:
        """Whether loom can still produce the text `a` was written against: its `against` hash is the current text's, or a frozen snapshot's.

        Snapshots come from `loom accept`, from `loom annotate`, which freezes every version it writes against, and from `freeze_moved`, which keeps a key's old text when it moves under a note. A note on a work's page asks instead whether the PDF on file is the artifact it was written on (`_on_page`). The flag keeps loom from presenting the current text as what an old note was about (V3); the quote may still match new text, so `detached` cannot answer it. `anchored` is quoted, not detached and recorded. An unrecorded note is not marked in the text (`_marks_by_node`) and is counted beside its key instead, since `anchored` is false; `loom ai annotations --json` reports `recorded`, and `loom status --reading` prints it for page notes. A recorded note whose words are gone has its version published by the build (`render/versions.py`). A note with no `against` claimed no version and counts as recorded.
        """
        want = a.target_hash
        if not want:
            return True
        if current is not None and hash_text(current) == want:
            return True
        if want not in self._snapshot_seen:
            self._snapshot_seen[want] = read_snapshot(self.root, want, self.history_dir) is not None
        return self._snapshot_seen[want]

    # ---- diagnostics ------------------------------------------------------------

    def diagnostics(self, result: ScanResult, states: dict[str, KeyState]) -> list[Diagnostic]:
        diags: list[Diagnostic] = []
        for p in self.problems:
            diags.append(Diagnostic("warning", "loom:foreign-annotations", f"not a valid review record: {p}", []))
        from loom.records.edits import replay as replay_edits

        for p in replay_edits(self.root)[1]:
            diags.append(Diagnostic("warning", "loom:foreign-annotations", f"not a valid suggested edit: {p}", []))
        # a missing file is the defaults, which loses nothing, so it is said quietly; one that cannot be read is a warning
        missing = not (self.root / ANNOTATION_TYPES).is_file()
        for p in self.types.problems:
            diags.append(Diagnostic("info" if missing else "warning", "loom:annotation-types", p, [], subject="record"))
        for rel, events in (
            (ANNOTATION_LOG, ("created", "replied")),
            (EDIT_LOG, ("created",)),
            (SESSION_INDEX, ("created",)),
        ):
            for _line, said in repeated(self.root, rel, events):
                diags.append(Diagnostic("warning", "loom:repeated-id", f"{rel}: {said}", [], subject="record"))
        detached: dict[str, list[str]] = {}
        opening: set[str] = set()
        for res in self.resolved(result):
            # one resolved needs nothing more, so the finding counts the open ones its fix acts on
            if res.detached and not res.unplaced and res.annotation.status == "open":
                detached.setdefault(res.target, []).append(res.annotation.id)
                if self.opens(res.annotation):
                    opening.add(res.annotation.id)
        for key, ids in sorted(detached.items()):
            diags.append(
                Diagnostic(
                    "info",
                    "loom:detached-annotation",
                    f"{len(ids)} annotation(s) on {key} no longer match its text",
                    [],
                    [key],
                    # one that stays open is resolved once its point is met; one that only informs has nothing to resolve
                    fixes=[
                        Fix("resolve it if its point is met", f'loom annotate --resolve {i} "…"')
                        for i in ids
                        if i in opening
                    ],
                )
            )
        diags.extend(self._gone_documents(result, states))
        followed = {row.key for row in self.placed(result).values()}
        for key in sorted(self.latest):
            if key not in result.nodes and key not in followed:
                diags.append(
                    Diagnostic(
                        "info",
                        "loom:retired-ledger-key",
                        f"the ledger has rows for {key}, which no longer exists",
                        [],
                        [key],
                    )
                )
        for key, ks in states.items():
            if ks.previous_key_match:
                diags.append(
                    Diagnostic(
                        "info",
                        "loom:previous-key-match",
                        f"acceptance recorded under {ks.previous_key_match} matches the text of {key}; re-accept to confirm",
                        [],
                        [key],
                    )
                )
        return diags

    def _gone_documents(self, result: ScanResult, states: dict[str, KeyState]) -> list[Diagnostic]:
        """One `loom:document-gone` per vanished document: the rows stale with `document-gone` and the live annotations whose `in` or whole-document target leads nowhere.

        A document is named by the last path its trail reached, which is where `loom mv` records it went. One that annotations are on is class `latex`, so a person is shown it among their problems, the one place it is said to them; one only acceptance rows name is `model`. A warning either way, in no exit.
        """
        from loom.scan.diagnostics import LATEX, MODEL

        rows: dict[str, list[str]] = {}
        notes: dict[str, set[str]] = {}
        for key, ks in states.items():
            for c in ks.causes:
                if c.kind == "document-gone" and c.id:
                    rows.setdefault(c.id, []).append(key)
        for res in self.resolved(result):
            a = res.annotation
            if not res.detached:
                continue
            named = [a.in_doc] if a.in_doc else []
            if a.anchor is None and a.target_key not in result.nodes and is_document_path(result, a.target_key):
                named.append(a.target_key)
            for path in named:
                if result.current_document(path) is None:
                    notes.setdefault(result.document_trail(path)[-1], set()).add(a.id)
        out: list[Diagnostic] = []
        for path in sorted(set(rows) | set(notes)):
            n_rows, n_notes = len(rows.get(path, [])), len(notes.get(path, set()))
            accepted = f"{n_rows} acceptance row{'s' if n_rows != 1 else ''} name{'s' if n_rows == 1 else ''} it"
            if n_notes:
                message = f"{n_notes} annotation{'s are' if n_notes != 1 else ' is'} on {path}, which is gone; the history does not say where it went"
                message += f", and {accepted} too" if n_rows else ""
            else:
                message = f"{path} is gone and the history does not say where it went; {accepted}"
            out.append(
                Diagnostic(
                    "warning",
                    "loom:document-gone",
                    message,
                    [],
                    sorted(rows.get(path, [])),
                    [Fix("record where it went, NEW being its path now", f"loom mv {path} NEW")],
                    subject="record",
                    class_=LATEX if n_notes else MODEL,
                )
            )
        return out

    # ---- diffs -------------------------------------------------------------------

    def diff_for(self, result: ScanResult, cause: Cause, key: str) -> str | None:
        if cause.kind == "basis-changed":
            return None  # a source directive changed; no accepted text snapshot represents the old classification
        if not cause.before:
            return None
        before = self.snapshot(cause.before)
        if before is None:
            return None
        target = cause.id or key
        n = result.nodes.get(target)
        if cause.kind == "preamble-changed":
            row = self.latest.get(key)
            document = self.row_document(result, row) if row is not None else result.default_master
            closure = result.closures.get(document) if document else None
            after = normalize(closure.raw_text()) if closure else ""
        elif target in result.dependencies.texts:
            after = normalize(result.dependencies.texts[target] or "")
        elif n is None:
            after = ""
        else:
            after = normalize(own_text(result, n))
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"accepted/{target}",
                tofile=f"current/{target}",
            )
        )

    # ---- manifest ---------------------------------------------------------------

    def apply(self, result: ScanResult, manifest: dict[str, Any], build_dir: Path | None = None) -> None:
        states = self.key_states(result)
        derived = self.derived(result, states)
        manifest["reviewer"] = {"name": self.reviewer, "source": self.reviewer_source}
        # the quilt's annotation types, in its file's order: what a viewer offers and how an untouched annotation of each is drawn; and the plain look, how an untouched one with no type is
        from loom.ai.orient import modes_using

        using = modes_using(self.root)
        manifest["annotation_types"] = [{**t.to_dict(), "modes": using.get(t.id, [])} for t in self.types.types]
        manifest["annotation_plain"] = self.types.plain.to_dict()
        for author in sorted({row.author for row in self.rows if row.author}):
            # One ledger/source snapshot for every perspective; summaries never observe or write.
            other = copy.copy(self)
            other.reviewer = author
            other.latest = latest_rows(self.rows, author)
            summaries = states if author == self.reviewer else other.key_states(result, observe=False)
            for key, state in summaries.items():
                if state.row and key in manifest["keys"] and not result.nodes[key].external:
                    manifest["keys"][key].setdefault("acceptances", []).append(
                        {"author": author, "date": state.row.date, "fresh": state.fresh}
                    )
        diffs_dir = build_dir / "diffs" if build_dir else None
        for key, entry in manifest["keys"].items():
            ks = states.get(key)
            if ks is None:
                continue
            entry["state"] = ks.state
            if ks.row is not None:
                acc: dict[str, Any] = {"author": ks.row.author, "date": ks.row.date, "fresh": ks.fresh}
                if not ks.fresh:
                    causes = []
                    for c in ks.causes:
                        d = c.to_dict()
                        d["identity"] = "|".join((c.kind, c.id or "", c.via or ""))
                        if c.id and c.id.startswith("equation:"):
                            label = c.id.removeprefix("equation:")
                            region = manifest.get("regions", {}).get(result.assembly.labels.get(label, ""), {})
                            master = self.row_document(result, ks.row)
                            number = region.get("numbers", {}).get(master, {}).get("number")
                            d["label"] = "Equation " + (number or label)
                            d["owner"] = result.dependencies.owners.get(c.id)
                        if c.kind == "dependency-changed" and c.id and not c.via and result.graph:
                            from loom.render.markup import slug

                            edge = next(
                                (
                                    e
                                    for e in result.graph.out.get(key, [])
                                    if e.offset >= 0
                                    and e.via != "uses"
                                    and (
                                        result.dependencies.resolve_label(e.label)
                                        if e.label
                                        else result.dependencies.node_target(e.to)
                                    )
                                    == c.id
                                ),
                                None,
                            )
                            if edge:
                                label_target = result.assembly.labels.get(edge.label, edge.to)
                                d["citation"] = f"cite-{slug(edge.file)}-{edge.offset}-{slug(label_target)}"
                        text = self.diff_for(result, c, key)
                        if text and diffs_dir is not None:
                            name = f"{_slug(key)}-{c.kind}{'-' + _slug(c.id) if c.id else ''}.diff"
                            diffs_dir.mkdir(parents=True, exist_ok=True)
                            (diffs_dir / name).write_text(text, encoding="utf-8")
                            # written beside the publish, so named to the build's index here (`lifetimes.built`)
                            used(diffs_dir / name)
                            d["diff"] = f"diffs/{name}"
                        causes.append(d)
                    acc["causes"] = causes
                entry["acceptance"] = acc
            entry["reviews"] = {
                "open": dict(ks.open),
                "detached": ks.detached,
            }
            entry["previous_key_match"] = ks.previous_key_match
        for key, entry in manifest["nodes"].items():
            ks = states.get(key)
            if ks is not None:
                entry["state"] = ks.state
            if key in derived:
                entry["derived"] = derived[key]
        anns: dict[str, Any] = {}
        # oldest first, whichever clone wrote it: published in this order (`publish.WRITTEN_IN_ORDER`)
        resolved = sorted(self.resolved(result), key=lambda r: r.annotation.created)
        for res in resolved:
            a = res.annotation
            anns[a.id] = {
                "id": a.id,
                "author": {"kind": a.author_kind, "id": a.author_id, "label": a.author_id},
                "created": a.created,
                # an annotation on a work names its reference, which travels as `work` with the page, so a viewer needs no lookup to say where it is (plan 0.13 item 2)
                "target": {
                    # '' for one on no block: no block is named so, and nothing that reads a key throws on it
                    "key": res.target,
                    "hash": a.target_hash,
                    "work": res.work or None,
                    # where it stands now: the page it was found again on, on a changed PDF
                    "page": res.page or (a.anchor.page if a.anchor else a.page),
                    # a project PDF, by its path
                    "file": a.target_key if a.target_key.lower().endswith(".pdf") else None,
                },
                # the document a claim about a node is read in, or null for the node wherever it appears (plan 0.15, decision 9); where the history's moves have taken it, so a viewer draws it on the document as it is now
                "in": res.in_doc,
                "basis": a.anchor.basis if a.anchor else None,
                # its type, while the quilt lists it: an annotation whose type was deleted reads as untyped, looking as it did
                "type": a.type if self.types.get(a.type) else None,
                "look": self.look(a),
                # the comment as written, which an editor starts from, and as rendered
                "body": a.body,
                "body_html": render_markdown(a.body),
                "status": a.status,
                "in_reply_to": a.in_reply_to,
                "anchored": (a.selector is not None or a.anchor is not None or bool(a.rects))
                and not res.detached
                and res.recorded,
                "detached": res.detached,
                "recorded": res.recorded,
                "quote": (a.selector.exact or None) if a.selector else None,
                # on a PDF page that records its own place: where it stands now, its strokes, the tool it was drawn with, and where an import came from
                "rects": res.rects,
                "strokes": res.strokes if res.refound else a.strokes,
                # a drawing's gap from its pin word, by which a changed file places it; whether it stands where it was found again on a changed file; and, on a work with its source, where its words stand there
                "gap": a.gap,
                "refound": res.refound,
                "source": self._source(result, res),
                # the changes waiting on the person that its words touch, and, carried by a kept change onto its new words, the words it was on and that change
                "on_changes": list(res.on_changes),
                "earlier": dict(a.earlier) if a.earlier else None,
                "mark": a.mark,
                "origin": a.origin,
                "hides": res.hides,
                "resolved_why": a.resolved_why,
                # the version it was written on, for one whose words are gone, set when the build makes it (`render/versions.py`)
                "version": None,
            }
        manifest["annotations"] = anns
        # the notes placed on no block, which a reader is shown apart from every block (§9, `unplaced`)
        manifest["unplaced"] = [
            {
                "id": res.annotation.id,
                "key": res.annotation.target_key,
                "document": written_in(result, res.annotation),
                "why": _why_unplaced(result, res.annotation.target_key),
            }
            for res in resolved
            if res.unplaced and res.annotation.in_reply_to is None
        ]
        manifest["diagnostics"].extend(d.to_dict() for d in self.diagnostics(result, states))


def _fact(a: Annotation | None) -> dict[str, Any] | None:
    if a is None:
        return None
    return {"author": {"kind": a.author_kind, "id": a.author_id}, "date": a.created}


def _when(result: ScanResult, n: NodeRec) -> str | None:
    """The date a node's file last changed, from its modification time.

    Under LOOM_FIXED_TIME it is the fixed date instead: a modification time depends on when and how a quilt was copied, so a fixture built from it would differ by the day it was regenerated.
    """
    import os

    if os.environ.get("LOOM_FIXED_TIME"):
        from loom.clock import today

        return today()
    try:
        import datetime

        mtime = (result.quilt.root / n.file).stat().st_mtime
        return datetime.datetime.fromtimestamp(mtime, datetime.UTC).strftime("%Y-%m-%d")
    except OSError:
        return None


def _slug(s: str | None) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9._-]+", "_", s or "")


#: Mathematics in Markdown as Pandoc reads it (`tex_math_dollars`), so "pays $5 and sells for $7" stays text: `$$…$$` is display; `$…$` is inline when the opening `$` has a non-space character to its right and the closing one a non-space character to its left and no digit right after it. Neither holds a blank line, a `$` inside an inline span is written `\$`, and `\$` outside one is a dollar sign.
_MATH = re.compile(
    r"(?<!\\)\$\$((?:[^$\n]|\n(?![ \t]*\n)|\$(?!\$))+?)\$\$"
    r"|(?<![\\$])\$(?![\s$])((?:[^$\\\n]|\\(?![ \t]*\n)[\s\S]|\n(?![ \t]*\n))+?)(?<!\s)\$(?![0-9])"
)
_HOLE = "loommathx{}x"
_HOLES = re.compile(_HOLE.format(r"(\d+)"))


def _protect_math(text: str) -> tuple[str, list[tuple[bool, str]]]:
    """Lift `$...$` and `$$...$$` out of Markdown before it is rendered, leaving a bare word in their place.

    Commonmark has no math, so `$O(n^2)$` renders as literal dollars and `$a_i b_i$` loses both subscripts to emphasis. Lifting first is what stops the second: a placeholder is an ordinary word, and whatever the TeX contains is never seen by the parser.
    """
    spans: list[tuple[bool, str]] = []

    def take(m: re.Match[str]) -> str:
        display = m.group(1) is not None
        spans.append((display, (m.group(1) if display else m.group(2)).strip()))
        return _HOLE.format(len(spans) - 1)

    # Code is quoted as written: `$` inside backticks is the source's own, not mathematics to typeset.
    parts = _CODE.split(text)
    return "".join(part if i % 2 else _MATH.sub(take, part) for i, part in enumerate(parts)), spans


#: Fenced code blocks and inline code spans, as CommonMark reads them; `split` keeps them at the odd indices.
_CODE = re.compile(r"(```[\s\S]*?```|(?<!`)`+(?!`)[\s\S]*?(?<!`)`+(?!`))")


def source_line(text: str) -> Callable[[int], int]:
    """Where a line of `text` with its mathematics lifted (`_protect_math`) stands in `text` itself.

    A lifted span takes the line breaks inside it with it, which puts every later `token.map` out by as many; for a token pass that must name a line of the file (`loom.tasks`).
    """
    gone: list[tuple[int, int]] = []
    at = 0
    for i, part in enumerate(_CODE.split(text)):
        last = 0
        for m in () if i % 2 else _MATH.finditer(part):
            at += part.count("\n", last, m.start())
            last = m.end()
            if "\n" in m.group(0):
                gone.append((at, m.group(0).count("\n")))
        at += part.count("\n", last)
    return lambda line: line + sum(n for held, n in gone if held < line)


def _restore_math(html_text: str, spans: list[tuple[bool, str]]) -> str:
    """Put each lifted span back as the dialect writes it (specs/dialect.md §2.6), or in its words where it stands inside a tag, since an attribute holds no markup.

    Everything that reaches here escapes `>` in an attribute (markdown-it, and `loom.raw_html` for what a file wrote), so each `<...>` is one tag.
    """
    import html as _html

    def block(m: re.Match[str]) -> str:
        i = int(m.group(1))
        if i >= len(spans):
            return m.group(0)
        display, tex = spans[i]
        tex = _html.escape(tex, quote=False)
        return (
            f'<div class="math display">\\[{tex}\\]</div>'
            if display
            else f'<span class="math inline">\\({tex}\\)</span>'
        )

    def word(m: re.Match[str]) -> str:
        return _html.escape(_lifted(m.group(0), spans), quote=True)

    parts = re.split(r"(<[^>]*>)", html_text)
    return _lift_display_math("".join(_HOLES.sub(word if i % 2 else block, part) for i, part in enumerate(parts)))


def _lifted(value: str, spans: list[tuple[bool, str]]) -> str:
    """`value` with each lifted span back as it was written, for a place no formula can be typeset: an attribute."""

    def words(m: re.Match[str]) -> str:
        i = int(m.group(1))
        if i >= len(spans):
            return m.group(0)
        display, tex = spans[i]
        return f"$${tex}$$" if display else f"${tex}$"

    return _HOLES.sub(words, value)


def _lift_display_math(html_text: str) -> str:
    """Take every display equation out of the paragraph Commonmark wrapped it in, splitting the paragraph around it.

    The dialect writes display math as a `div` (specs/dialect.md §2.6) and Commonmark wraps a paragraph's content in a `p`, so an equation that is not separated by blank lines lands inside one -- which is invalid, and which a browser fixes by closing the paragraph early and leaving the prose after the equation outside it. Writing a sentence, a newline, `$$...$$`, a newline and another sentence is how annotations are actually written, so this is the ordinary case rather than the edge one.
    """
    div = re.compile(r'<div class="math display">.*?</div>', re.S)

    def split(m: re.Match[str]) -> str:
        inner = m.group(1)
        if not div.search(inner):
            return m.group(0)
        out: list[str] = []
        pos = 0
        for d in div.finditer(inner):
            before = inner[pos : d.start()].strip()
            if before:
                out.append(f"<p>{before}</p>")
            out.append(d.group(0))
            pos = d.end()
        rest = inner[pos:].strip()
        if rest:
            out.append(f"<p>{rest}</p>")
        return "\n".join(out)

    return re.sub(r"<p>(.*?)</p>", split, html_text, flags=re.S)


def render_markdown(
    text: str,
    *,
    tokens: Callable[[list[Any]], None] | None = None,
    raw: Callable[[str, Callable[[str], str]], str] | None = None,
) -> str:
    """Markdown rendered into the dialect's inline subset, math included.

    Every body loom publishes as HTML comes through here -- annotations, transcript messages and the project's Markdown files -- and all of them are written by people and agents who use `$...$` without thinking about it. A body given neither callable is rendered once for its text while builds ask for it (`_rendered`), since a build renders every annotation's body again.

    Parameters
    ----------
    text : str
        The Markdown as it was written.
    tokens : callable, optional
        Given the parsed tokens to change in place before they are rendered; a file's headings and relative links are set this way (`loom.files`). Mathematics is already lifted out, as `loommathxNx` words.
    raw : callable, optional
        What each piece of raw HTML becomes, given the piece and a function that puts lifted mathematics back in its words, for an attribute's value. It sees everything raw HTML can write, so it is the only way raw HTML reaches the output; with none, raw HTML is escaped and shows as text.

    Returns
    -------
    str
        Dialect HTML.
    """
    if tokens is None and raw is None:
        return _rendered.get(text, lambda: _render_markdown(text, None, None))
    return _render_markdown(text, tokens, raw)


#: Each body rendered with neither callable, by its text.
_rendered: Memo[str, str] = Memo(built=True)


def _render_markdown(
    text: str,
    tokens: Callable[[list[Any]], None] | None,
    raw: Callable[[str, Callable[[str], str]], str] | None,
) -> str:
    """`render_markdown`'s work, every time."""
    protected, spans = _protect_math(text)
    try:
        from markdown_it import MarkdownIt

        # CommonMark has no tables, so an agent's `| a | b |` comparison arrived as one run-on paragraph; the dialect has them (specs/dialect.md §2.12), so the GFM table rule is enabled
        md = MarkdownIt("commonmark", {"html": raw is not None}).enable("table")
        if raw is not None:
            clean = raw

            def drawn(_renderer: Any, parsed: list[Any], index: int, _options: Any, _env: Any) -> str:
                return clean(parsed[index].content, lambda value: _lifted(value, spans))

            md.add_render_rule("html_block", drawn)
            md.add_render_rule("html_inline", drawn)
        if tokens is None:
            out = str(md.render(protected)).strip()
        else:
            env: dict[str, Any] = {}
            parsed = md.parse(protected, env)
            tokens(parsed)
            out = str(md.renderer.render(parsed, md.options, env)).strip()
    except Exception:  # noqa: BLE001
        import html

        out = "<p>" + html.escape(protected) + "</p>"
    # a column's alignment arrives as an inline style, which the dialect does not carry: the viewer sets a table's look
    out = re.sub(r' style="text-align:(?:left|right|center)"', "", out)
    return _restore_math(out, spans)
