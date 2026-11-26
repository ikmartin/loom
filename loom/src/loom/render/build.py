"""`loom build`: scan, read records, read numbering, render, write the manifest, publish.

Rendering is cached by an input hash per fragment (the text of the files it draws on plus the numbering), so a build after a one-line edit re-renders one node and its masters. The hash carries loom's version, and in a checkout — whose version does not move between edits — a fingerprint of loom's own code, so changing the converter does not leave yesterday's HTML on disk. `--force` renders everything regardless.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import quote

from loom import own
from loom.history.ledger import load_history
from loom.lifetimes import BuildIndex, in_cache, read_index, write_index
from loom.paths import (
    BLOCK_PREVIEWS,
    BLOCKS,
    BUILD_INDEX,
    SITE,
    SITE_SVG,
    SNIPPETS,
    document_build,
    document_name,
)
from loom.records.lastseen import freeze_moved
from loom.records.store import Records
from loom.render.attach import ATTACH, Attaching
from loom.render.canon import CanonRenderer, canon_fragment_path, load_canon
from loom.render.fragments import FragmentRenderer, RenderPlan
from loom.render.keys import aux_bytes, code_hash
from loom.render.manifest import build_manifest
from loom.render.marks import MarkEntry, place_marks
from loom.render.publish import publish
from loom.render.uses import noting
from loom.render.versions import Gone, attach_versions, gone_annotations, gone_marks
from loom.scan.memo import forget, reading
from loom.scan.model import Diagnostic
from loom.scan.quilt import Quilt
from loom.scan.scan import ScanResult, scan
from loom.tex.aux import read_cite_labels, read_numbers
from loom.version import __version__


@dataclass
class BuildReport:
    result: ScanResult
    manifest: dict[str, Any]
    rendered: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    #: The digest of the index this build wrote (`lifetimes.write_index`): a sweep after it sweeps the cache only while that index is the one on disk.
    index: str = ""

    def kept(self) -> BuildReport:
        """This report without its manifest, which is on disk once published: what a server holds between builds, where a large quilt's manifest runs to tens of megabytes as objects."""
        return replace(self, manifest={})


def _write_source(result: ScanResult, fragments: dict[str, str], files: dict[str, Any]) -> None:
    """One file per key holding its own LaTeX, for the viewer's verbatim toggle (specs/manifest.md §1).

    Beside the manifest rather than inside it: the manifest is loaded whole on every poll and already runs to hundreds of kilobytes, while source is wanted one key at a time and only when a reader asks to see it.
    """
    from loom.tex.bundle import region_text

    for key, n in result.nodes.items():
        if n.kind not in ("environment", "section") and not (n.kind == "proof" and n.id):
            continue
        try:
            text = region_text(result, key)
        except (KeyError, IndexError):
            continue
        rel = f"source/{quote(key, safe='')}.tex"
        fragments[f"source:{key}"] = rel
        files[rel] = text


def fragment_path(result: ScanResult, key: str) -> str:
    n = result.nodes[key]
    if n.kind == "master":
        return f"fragments/masters/{document_name(key)}.html"
    if n.id:
        return f"fragments/nodes/{n.id}.html"
    from urllib.parse import quote

    return f"fragments/keys/{quote(key, safe='')}.html"


def _input_hash(
    result: ScanResult, key: str, aux: bytes, texts: dict[str, str] | None = None, pages: dict[str, Any] | None = None
) -> str:
    """The cache key of a node or master fragment: loom's version and code, the text of every file it draws on (its own, its claimants', and every file a section's span runs through) and what each of its citations reaches in the library (`library.citations`), `aux` from `keys.aux_bytes`, and the digest of each page as TeX made it that the fragment may be cut from.

    `texts` holds each file's text hash, filled as files are met, so a file many nodes draw on is hashed once per scan rather than once per node; `pages` maps each document to its current page, or None.
    """
    texts = {} if texts is None else texts
    n = result.nodes[key]
    h = hashlib.sha256()
    h.update(__version__.encode())
    h.update(code_hash().encode())
    files = {n.file}
    if n.kind in ("master", "file"):
        for exp in result.expansions.values():
            if exp.master == key:
                files |= set(exp.reached)
    for ck in n.claimants:
        files.add(result.nodes[ck].file)
    # a section's text runs through the files it includes, the text they hold around their own nodes too
    for master, (a, b) in n.exp_ranges.items():
        expansion = result.expansions.get(master)
        if expansion is not None:
            files.update(seg.file for seg in expansion.segments if seg.exp_start < b and seg.exp_end > a)
    for f in sorted(files):
        if f not in texts:
            # a stub made since, or a node digested, changes what a citation's `data-target` names though the text has not
            reached = sorted(
                (c.offset, c.citekey, c.postnote or "", c.target or "") for c in result.edges.cites if c.file == f
            )
            texts[f] = hashlib.sha256(
                result.files[f].text.encode("utf-8", errors="replace") + repr(reached).encode()
            ).hexdigest()
        h.update(f.encode())
        h.update(texts[f].encode())
    h.update(aux)
    for m in [key] if n.kind == "master" else n.reached_by:
        page = (pages or {}).get(m)
        h.update(f"{m}:{page.digest if page is not None else '-'}".encode())
    return h.hexdigest()


def _canon_hash(doc, root: Path) -> str:  # type: ignore[no-untyped-def]
    """The cache key of a landmark's fragment: loom's version and code, the landmark's text, its closure's, and the `.aux` and `.bbl` it reads, its own or its live document's."""
    h = hashlib.sha256()
    h.update(__version__.encode())
    h.update(code_hash().encode())
    h.update(doc.path.encode())
    h.update(doc.src.text.encode("utf-8", errors="replace"))
    h.update(doc.closure.raw_text().encode("utf-8", errors="replace"))
    for path in filter(None, (doc.path, doc.live)):
        out = root / document_build(path)
        for p in sorted([*out.glob("*.aux"), *out.glob("*.bbl")]):
            h.update(p.read_bytes())
    return h.hexdigest()


def _marks_hash(marks: dict[str, list[MarkEntry]], key: str, result: ScanResult) -> str:
    n = result.nodes[key]
    keys = [key] if n.kind != "master" else [k for k, node in result.nodes.items() if key in node.reached_by]
    h = hashlib.sha256()
    for k in sorted(keys):
        for m in marks.get(k, []):
            h.update(
                f"{m.ann_id}|{m.start}|{m.end}|{m.in_doc or ''}|{m.gone}|{m.lead}|{m.quote if m.gone else ''}".encode()
            )
    return h.hexdigest()[:16]


def _marks_by_node(result: ScanResult, records: Records, gone: list[Gone] | None = None) -> dict[str, list[MarkEntry]]:
    """Mark entries grouped by the node whose fragment shows them: a proof's marks under its statement, and on the proof's own page.

    A comment on an equation with no quote (a box drawn round it) marks the display itself, found by the offset of its label. An annotation whose words are gone marks where they were with an empty mark (`versions.gone_marks`), from `gone` when the caller has it.
    """
    out: dict[str, list[MarkEntry]] = gone_marks(gone_annotations(result, records) if gone is None else gone)
    for res in records.resolved(result):
        # a note whose version is gone is not pinned to the text that replaced it; it is counted beside its key instead
        if not res.recorded:
            continue
        a = res.annotation
        region = result.assembly.regions.get(res.target)
        if res.span is None and a.selector is None and region is not None and a.in_reply_to is None:
            host = result.nodes.get(region.container)
            if host is not None:
                entry = MarkEntry(a.id, "", region.file, region.offset, region.offset, res.in_doc)
                owner = host.of if host.kind == "proof" and host.of else host.key
                out.setdefault(owner, []).append(entry)
                if owner != host.key:
                    out.setdefault(host.key, []).append(entry)
            continue
        if res.span is None:
            continue
        n = result.nodes.get(res.target)
        if n is None:
            n = result.nodes.get(region.container) if region else None
        if n is None:
            continue
        own, pieces = Records.own_pieces(result, n)
        if res.span[0] == res.span[1]:
            # a point where its words were removed, carried there by a kept change: drawn as the empty mark a gone annotation's place is
            from loom.render.versions import _beside, _file_point

            at = _file_point(pieces, res.span[0])
            if at is None:
                continue
            words, lead = _beside(own, res.span[0])
            entry = MarkEntry(a.id, words, n.file, at, at, res.in_doc, gone=True, lead=lead)
        else:
            span = Records.to_file_span(pieces, res.span)
            if span is None:
                continue
            # `in` as the history's moves leave it, so a note read in a document is drawn in whatever that document became
            entry = MarkEntry(a.id, a.selector.exact if a.selector else "", n.file, span[0], span[1], res.in_doc)
        owner = n.of if n.kind == "proof" and n.of else n.key
        out.setdefault(owner, []).append(entry)
        # a labelled proof has a page of its own too, and its marks belong on it as well as under its statement
        if owner != n.key:
            out.setdefault(n.key, []).append(entry)
    return out


def _marks_by_file(result: ScanResult, records: Records) -> dict[str, list[MarkEntry]]:
    """Mark entries for the annotations on Markdown files, by path: each on its words' place in the file, placed by the blocks' `data-src`, which give the words as the page prints them and which occurrence of them it is (`files.attach_files`)."""
    from loom.records.mdtext import is_markdown, printed, text_of

    out: dict[str, list[MarkEntry]] = {}
    texts: dict[str, str | None] = {}
    for res in records.resolved(result):
        a = res.annotation
        if res.span is None or not res.recorded or a.target_key in result.nodes or not is_markdown(a.target_key):
            continue
        text = texts.setdefault(a.target_key, text_of(result.quilt.root, a.target_key))
        if text is None:
            continue
        lo, hi = res.span
        out.setdefault(a.target_key, []).append(
            MarkEntry(a.id, printed(text[lo:hi])[0], a.target_key, lo, hi, plain=True)
        )
    return out


def _write_transcripts(root: Path, files: dict[str, str | bytes]) -> set[str]:
    """Every session's transcript as pages under `transcripts/<id>/<n>.json`, so a viewer with no publisher running still reads the chat; returns the pages of sessions nobody wrote in since this process last published them, which are on disk as they should be, for `publish` to keep.

    Out of the manifest, which every viewer polls: a long conversation would make every poll pay for it.
    """
    from loom.mailbox import inbox_path, pages
    from loom.sessions import sessions

    kept: set[str] = set()
    for sid in sessions(root):
        inbox = inbox_path(root, sid)
        try:
            stamp: tuple[int, int] | None = (inbox.stat().st_mtime_ns, inbox.stat().st_size)
        except OSError:
            stamp = None
        known = _TRANSCRIPTS.get(inbox)
        if stamp is not None and known is not None and known[0] == stamp:
            if all((root / SITE / rel).is_file() for rel in known[1]):
                kept.update(known[1])
                continue
        made = {
            f"transcripts/{sid}/{n}.json": json.dumps(page, ensure_ascii=False, indent=1, sort_keys=True)
            for n, page in pages(root, sid).items()
        }
        if stamp is not None:
            _TRANSCRIPTS[inbox] = (stamp, frozenset(made))
        files.update(made)
    return kept


#: Each session's transcript pages as last published, by its inbox's modification time and size: a session nobody wrote in since is neither rendered nor held again by a server that rebuilds on every change.
_TRANSCRIPTS: dict[Path, tuple[tuple[int, int], frozenset[str]]] = {}


#: The fragments' input hashes for the last scan built from, the numbering they were hashed with, and each file's text hash; a build from the same scan (`reuse`) reads them rather than hashing every file again.
_INPUT_HASHES: tuple[ScanResult | None, bytes, dict[str, str], dict[str, str]] = (None, b"", {}, {})


def build(
    quilt: Quilt,
    keys: list[str] | None = None,
    records: Records | None = None,
    force: bool = False,
    reuse: ScanResult | None = None,
    progress: Callable[[str, str, int, int | None], None] | None = None,
    tex: bool = True,
) -> BuildReport:
    """Scan, read the records, render what changed and publish the build directory.

    Parameters
    ----------
    quilt : Quilt
        The quilt to build.
    keys : list of str, optional
        Render only these keys, their proofs and the documents reaching them; default every fragment.
    records : Records, optional
        Records already read; default read here.
    force : bool, default False
        Render every fragment again, and retry every figure that failed before.
    reuse : ScanResult, optional
        A scan of this quilt to build from instead of scanning again. Only a caller that knows no scan input changed passes one: `loom serve`, after a change to records alone or a version kept, whose landmark is read again here.
    progress : callable, optional
        Told `(stage, item, n, total)` as the build moves: `scanning`, `rendering` once per fragment with its place in the count, `recording`, `publishing`; what a caller shows as progress (T6).
    tex : bool, default True
        Whether TeX may run for text no compile makes (snippets, pictures); without it that text comes from the cache or shows as its source.

    Returns
    -------
    BuildReport
        The scan, the manifest, and what was rendered and skipped.

    Notes
    -----
    A build is one `memo.reading`, so what the scan and the rendering after it derive from a file's text is kept for the next build while the file is unchanged, and let go once it has changed. A build from `reuse` reads no file of the quilt's and keeps what the last build derived, letting go only what it made itself. Every memo is emptied first when the index on disk is not the one this process last wrote: another process has built the quilt since, and a forced build there made again what the memos stand in for.
    """
    if quilt.root in _INDEXED and _index_stamp(quilt.root) != _INDEXED[quilt.root]:
        # another process built this quilt since this one last did, a `--force` in a terminal among them: what it made again is not what this process remembers
        forget()
    with reading(keep=reuse is not None, build=True), noting() as beside:
        return _build(quilt, keys, records, force, reuse, progress, tex, beside)


#: The build's index as this process last wrote it, by quilt: its inode, modification time and size. One that differs was written by a build in another process, or is gone.
_INDEXED: dict[Path, tuple[int, int, int] | None] = {}


def _index_stamp(root: Path) -> tuple[int, int, int] | None:
    """The build index's inode, modification time and size as it is on disk; None when there is none."""
    try:
        st = (root / BUILD_INDEX).stat()
    except OSError:
        return None
    return st.st_ino, st.st_mtime_ns, st.st_size


def _build(
    quilt: Quilt,
    keys: list[str] | None,
    records: Records | None,
    force: bool,
    reuse: ScanResult | None,
    progress: Callable[[str, str, int, int | None], None] | None,
    tex: bool,
    beside: set[str],
) -> BuildReport:
    root = quilt.root
    build_dir = root / SITE
    cache_dir = root / BLOCKS

    def told(stage: str, item: str = "", n: int = 0, total: int | None = None) -> None:
        if progress is not None:
            progress(stage, item, n, total)

    told("scanning")
    result = reuse if reuse is not None else scan(quilt)
    if reuse is not None:
        from loom.scan.scan import landmark_documents

        # a version kept since (a keep's, a recorded one) adds a landmark and nothing else the scan reads
        result.canon_files = landmark_documents(quilt)
    # the references the drafts' entries want and the stubs their citations want, made before any fragment is drawn, so each citation's target is what this build publishes
    from loom.library.gather import gather
    from loom.library.stubs import make as make_stubs

    gathered = gather(result)
    make_stubs(result)
    records = records or Records(root, quilt.history_dir)
    # the one moment loom can still see both the text an annotation was written against and the text that replaced it
    freeze_moved(result, records.records)
    gone = gone_annotations(result, records)
    marks = _marks_by_node(result, records, gone)
    numbers = {m: read_numbers(root, m) for m in result.masters}
    cite_labels = {m: read_cite_labels(root, m) for m in result.masters}
    from loom.render.fromhtml import page_for

    # each document's page as TeX made it, where one is current with its sources; the rest show as their source
    pages = {m: page_for(result, m) for m in result.masters}
    plan = RenderPlan(
        result=result,
        numbers=numbers,
        cite_labels=cite_labels,
        cache=cache_dir,
        svg_out=root / SITE_SVG,
        pages=pages,
        tex=tex,
    )
    if force:
        # a text TeX refused may have been refused for the machine's sake, a package since installed; --force tries each once more, and nothing this process remembers stands in for it
        for failed in [*(root / SNIPPETS).glob("*.failed"), *(root / BLOCK_PREVIEWS).glob("*.html")]:
            own.unlink(failed, root=root)
        forget()
    renderer = FragmentRenderer(plan)
    before = read_index(root)
    # each fragment's input hash, and what it was made from, as the last build left them; a fragment rendered here replaces both, and `force` only stops a wanted one being skipped as unchanged, so a forced build of some keys leaves the rest as they were
    index: dict[str, str] = dict(before.fragments)
    uses: dict[str, list[str]] = dict(before.uses)
    fragments: dict[str, str] = {}
    files: dict[str, str | bytes] = {}
    report = BuildReport(result=result, manifest={})
    wanted: set[str] | None = None
    if keys:
        wanted = set()
        for k in keys:
            n = result.nodes.get(k)
            if n is None:
                continue
            wanted.add(k)
            wanted |= set(n.proofs)
            wanted |= set(n.reached_by)
    targets: list[tuple[str, str]] = []
    for key, n in result.nodes.items():
        if n.kind in ("environment", "section") or (n.kind == "proof" and n.id):
            targets.append((key, "node"))
        elif n.kind == "master":
            targets.append((key, "master"))

    def render_one(key: str, kind: str) -> str:
        # a mark that names a document is drawn in that document and nowhere else (plan 0.15, decision 9)
        if kind == "node":
            return place_marks(renderer.node_fragment(key), [m for m in marks.get(key, []) if m.in_doc is None])
        return place_marks(
            renderer.master_fragment(key),
            [m for k, ms in marks.items() for m in ms if key in result.nodes[k].reached_by and m.in_doc in (None, key)],
        )

    jobs: list[tuple[str, str, str, str]] = []
    aux = aux_bytes(numbers, cite_labels)
    global _INPUT_HASHES
    if _INPUT_HASHES[0] is not result or _INPUT_HASHES[1] != aux:
        _INPUT_HASHES = (result, aux, {}, {})
    hashes, texts = _INPUT_HASHES[2], _INPUT_HASHES[3]
    for key, kind in targets:
        rel = fragment_path(result, key)
        label = key if kind == "node" else f"{kind}:{key}"
        fragments[label] = rel
        if key not in hashes:
            hashes[key] = _input_hash(result, key, aux, texts, pages)
        digest = hashes[key] + _marks_hash(marks, key, result)
        existing = build_dir / rel
        if (wanted is not None and key not in wanted) or (not force and index.get(rel) == digest and existing.exists()):
            report.skipped.append(key)
            continue
        jobs.append((key, kind, rel, digest))
    history = load_history(quilt.history_dir)
    canon_docs = load_canon(quilt, result, history)
    canon_renderer = CanonRenderer(renderer)
    canon_entries: list[dict[str, Any]] = []
    canon_jobs: list[tuple[Any, str, str]] = []
    from loom.render.canon import canon_entry

    for doc in canon_docs:
        rel = canon_fragment_path(doc)
        digest = _canon_hash(doc, root)
        if (wanted is not None) or (not force and index.get(rel) == digest and (build_dir / rel).exists()):
            report.skipped.append(f"canon:{doc.path}")
        else:
            canon_jobs.append((doc, rel, digest))
        fragments[f"canon:{doc.path}"] = rel
        canon_entries.append(canon_entry(doc, rel, digest))
    # What no compile makes, nodes no document reaches, is made by TeX first, in one batch, so the pool below only cuts fragments.
    renderer.prepare([key for key, _kind, _rel, _digest in jobs])
    # Rendered on a pool, assembled in order. The expensive part is waiting on TeX, a landmark's snippets or a page's diagrams, and waiting on a subprocess releases the GIL, so threads overlap exactly that.
    # Landmarks share the pool and are submitted first: each is one long job, so started last it would run alone after every node had finished.
    from concurrent.futures import ThreadPoolExecutor
    from functools import partial

    tasks = [partial(canon_renderer.fragment, doc) for doc, _rel, _digest in canon_jobs]
    tasks += [partial(render_one, key, kind) for key, kind, _rel, _digest in jobs]

    def render_job(task: Any) -> tuple[str, list[Any], set[str]]:
        # what the job read and made in the cache, which the index keeps as what its fragment was made from
        with renderer.collecting() as diags, noting() as noted:
            return task(), diags, noted

    names = [doc.path for doc, _rel, _digest in canon_jobs] + [key for key, _kind, _rel, _digest in jobs]
    told("rendering", "", 0, len(tasks))
    done: list[tuple[str, list[Any], set[str]]] = []
    with ThreadPoolExecutor(max_workers=max(1, os.cpu_count() or 1)) as pool:
        for n, out in enumerate(pool.map(render_job, tasks), 1):
            done.append(out)
            told("rendering", names[n - 1], n, len(tasks))
    canon_done, node_done = done[: len(canon_jobs)], done[len(canon_jobs) :]
    # every job's diagnostics, nodes then landmarks, each in job order: the order a single thread would have produced, whatever order they finished
    for _, diags, _noted in node_done + canon_done:
        plan.diagnostics.extend(diags)
    for (key, _kind, rel, digest), (html_out, _, noted) in zip(jobs, node_done, strict=True):
        files[rel] = html_out
        index[rel] = digest
        uses[rel] = in_cache(root, noted)
        report.rendered.append(key)
    for (doc, rel, digest), (html_out, _, noted) in zip(canon_jobs, canon_done, strict=True):
        files[rel] = html_out
        index[rel] = digest
        uses[rel] = in_cache(root, noted)
        report.rendered.append(f"canon:{doc.path}")
    from loom.render.compiles import compile_problems

    # what the documents' last compiles say, read from their logs, beside what the scan and the rendering found
    report.diagnostics = list(result.lint) + plan.diagnostics + compile_problems(result)
    manifest = build_manifest(
        result, numbers, fragments, report.diagnostics, canon=canon_docs, canon_entries=canon_entries, history=history
    )
    told("recording")
    records.apply(result, manifest, build_dir)
    from loom.draft_lifecycle import attach_closed

    attach_closed(result, manifest, files)
    from loom.section_drafts import attach_context

    attach_context(result, manifest, files, marks)
    from loom.render.review_compare import attach_comparisons

    attach_comparisons(result, records, renderer, manifest, files)
    from loom.render.incoming import attach_adoptions

    attach_adoptions(result, renderer, manifest, files)
    from loom.render.pending import attach_pending

    # every change waiting on the person, each drawn in its block, and the suggested edits' record
    attach_pending(result, records, renderer, manifest, files, marks)
    attach_versions(result, records, renderer, manifest, files, gone)
    # what the other parts of loom publish, each by its own function (`render/attach.py`)
    for attach in ATTACH:
        attach(Attaching(result, records, renderer, manifest, files, gathered))
    # every preview asked for above, made by TeX together, one batch per preamble
    renderer.previews.make()
    from loom.review_queue import rows_for

    manifest["unresolved"] = rows_for(result, manifest)
    _write_source(result, fragments, files)
    transcripts = _write_transcripts(result.quilt.root, files)
    from loom.files import BODIES, attach_files
    from loom.render.pending import DIFFS
    from loom.scan.lint import link_words_missing, markdown_links

    # a Markdown file's links are judged on the page just drawn of it
    drawn = attach_files(result, manifest, files, _marks_by_file(result, records))
    manifest["diagnostics"] += [d.to_dict() for d in markdown_links(result, drawn)]
    manifest["diagnostics"] += [d.to_dict() for d in link_words_missing(result, manifest.get("backlinks", []))]
    from loom.render.threads import last_active

    for s in manifest.get("sessions", []):
        s["last"] = last_active(result.quilt.root, s["id"], manifest)
    from loom.config_edit import published as published_config

    manifest["config"] = published_config(result)
    from loom.overleaf import published as published_overleaf

    manifest["overleaf"] = published_overleaf(result.quilt.root)
    # every diagnostic, lint's, the renderer's and the records', whole and with whose it is to fix
    from loom.scan.diagnostics import stamped

    report.diagnostics = stamped(result, [Diagnostic.from_dict(d) for d in manifest["diagnostics"]])
    manifest["diagnostics"] = [d.to_dict() for d in report.diagnostics]
    report.manifest = manifest
    prune = ("fragments/", "source/", "transcripts/", f"{BODIES}/", f"{DIFFS}/") if wanted is None else ()
    if wanted is None:
        for rel in list(index):
            if rel not in fragments.values():
                index.pop(rel)
    # a fragment the cache skipped, or a transcript nobody wrote in since, is already on disk as it should be: kept from the prune, not read back and rewritten
    told("publishing")
    keep = {rel for rel in fragments.values() if rel not in files} | transcripts
    publish(build_dir, files, manifest, prune, keep=keep)
    cache_dir.mkdir(parents=True, exist_ok=True)
    uses = {rel: uses.get(rel, []) for rel in index}
    read_beside = in_cache(root, beside)
    shared = {n[1:] for said in [*uses.values(), read_beside] for n in said if n.startswith("@")}
    # a group made in this build is as this build made it; one no fragment rendered here took from is as the build that made it left it
    groups = {
        g: in_cache(root, renderer.groups[g]) if g in renderer.groups else before.groups.get(g, []) for g in shared
    }
    report.index = write_index(root, BuildIndex(index, uses, groups, read_beside, sorted({*files, *keep})))
    _INDEXED[root] = _index_stamp(root)
    return report
