"""Build `manifest.json` from a scan, the numbering, the fragments written, and the records (docs/specs/manifest.md).

Every section of the specification is produced here; the states vocabulary is fixed; text never appears in the manifest except titles, excerpts, and rendered annotation bodies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loom.history.steps import document_loads
from loom.paths import document_build, document_pdf_address
from loom.render.fragments import master_title, plain_text
from loom.render.threads import build_threads
from loom.scan.directives import list_value
from loom.scan.hashing import pair_hash
from loom.scan.macros import compatibility_macros, declared_alphabets, package_macros, to_mathjax
from loom.scan.model import Diagnostic
from loom.scan.nodes import NodeRec
from loom.scan.owntext import key_hash
from loom.scan.preamble import loaded_packages
from loom.scan.scan import ScanResult
from loom.scan.sections import starred_at
from loom.tex.aux import AuxNumber
from loom.version import __version__

STATE_LABELS = {
    "labels": {
        "draft": {"label": "draft", "color": "neutral"},
        "accepted": {"label": "accepted", "color": "positive"},
        "stale": {"label": "stale", "color": "warning", "modifier": True},
        "incomplete": {"label": "incomplete", "color": "negative"},
        "conflicted": {"label": "conflicted", "color": "negative"},
    },
    "derived": {
        "proved": {"label": "proved", "color": "positive"},
        "settled": {"label": "settled", "color": "positive-strong"},
    },
}


def _sessions(root: Path) -> list[dict[str, Any]]:
    """Every session the index leaves standing, with what the viewer's selector shows: the title, the state, and the round it is on."""
    from loom.mailbox import last_seq
    from loom.sessions import active, sessions

    here = active(root)
    return [
        {
            "id": s.id,
            "title": s.title,
            # what the sitting is for, in the author's words: a line under the title in the panel, absent when unset
            "purpose": s.purpose,
            "state": s.state,
            "created": s.created,
            "opened": s.last_opened,
            "rounds": len(s.rounds),
            "active": s.id == here,
            "seq": last_seq(root, s.id),
        }
        for s in sessions(root).values()
    ]


def _base_math(record: Any, base: dict[str, Any]) -> dict[str, str]:
    """`{"math": pair_hash}` of a derived node's base version, so a viewer can tell a node changed on both sides without asking loom; {} when the version cannot be read."""
    from loom.history.versions import read_version

    try:
        return {"math": pair_hash(read_version(record, str(base["key"]), str(base["step"]))[1])}
    except LookupError:
        return {}


def _numbers(
    node: NodeRec, numbers: dict[str, dict[str, AuxNumber]], starred: bool = False
) -> dict[str, dict[str, Any]]:
    """The node's number in each document reaching it, from that document's aux; none for a starred heading, whose label holds the enclosing one's."""
    out: dict[str, dict[str, Any]] = {}
    if starred:
        return out
    for master, table in numbers.items():
        if master not in node.reached_by:
            continue
        for lab in [node.id, *node.labels]:
            if lab and lab in table:
                entry: dict[str, Any] = {"number": table[lab].number}
                if table[lab].page is not None:
                    entry["page"] = table[lab].page
                out[master] = entry
                break
    return out


def _parent_of(result: ScanResult, node: NodeRec) -> dict[str, str]:
    out: dict[str, str] = {}
    if node.kind == "section":
        return {m: p for m, p in node.parent.items() if p}
    for master, exp in result.expansions.items():
        if master not in node.reached_by:
            continue
        off = exp.exp_offset(node.file, node.start)
        if off is None:
            continue
        best: NodeRec | None = None
        for s in result.nodes.values():
            if s.kind != "section" or master not in s.exp_ranges:
                continue
            a, b = s.exp_ranges[master]
            if a <= off < b and (best is None or (b - a) < (best.exp_ranges[master][1] - best.exp_ranges[master][0])):
                best = s
        if best is not None:
            out[master] = best.key
    return out


def _locator(node: NodeRec) -> str | None:
    if not node.title:
        return None
    m = re.search(r"\\cite\s*\[([^\]]*)\]", node.title)
    return m.group(1).strip() if m else None


# What a quilt has, never what a viewer should draw (specs/manifest.md §2, plan 0.9.5 §9). Every value is a property of
# loom, not of this quilt's current contents: a quilt with no documents yet is still a project that assembles into
# them, and "empty because not yet" is exactly what a viewer cannot tell from the data alone. A publisher whose corpora
# genuinely never have one says so, and a manifest that declares nothing leaves the viewer to derive from the data.
PUBLISHES = {"documents": True, "review": True, "bibliography": True, "discussions": True}


def build_manifest(
    result: ScanResult,
    numbers: dict[str, dict[str, AuxNumber]],
    fragments: dict[str, str],
    diagnostics: list[Diagnostic],
    records: Any | None = None,
    canon: list[Any] | None = None,
    canon_entries: list[dict[str, Any]] | None = None,
    history: Any | None = None,
) -> dict[str, Any]:
    asm = result.assembly
    root_name = result.quilt.name
    dm = result.default_master
    corpus_label = (master_title(result, dm) if dm else None) or root_name
    manifest: dict[str, Any] = {
        "publisher": {"name": "loom", "version": __version__},
        "publishes": PUBLISHES,
        "generated": _stamp(),
        # `directory`: the quilt root's own name, which the viewer's Files names as what it is a view of
        "corpus": {"name": root_name, "root_label": corpus_label, "directory": result.quilt.root.name},
        "masters": [],
        "canon": list(canon_entries or []),
        "nodes": {},
        "keys": {},
        "regions": {},
        "edges": [],
        "relations": [],
        "inclusion": {},
        "states": STATE_LABELS,
        "annotations": {},
        "threads": build_threads(result.quilt.root, result=result),
        # The selector's data (plan 0.13 §5): which sessions exist, which is active, and how much is open in each.
        "sessions": _sessions(result.quilt.root),
        "diagnostics": [d.to_dict() for d in diagnostics],
        "tags": {},
        "taxa": {},
        "macros": {"default": [], "sets": {}},
        "search": [],
    }
    # the quilt's research state, a page (plan 0.21.3); absent until one is written, and additive
    from loom.pages import published as page_published
    from loom.pages import state_page

    research_state = page_published(result, state_page(result.quilt.config))
    if research_state is not None:
        manifest["research_state"] = research_state
    # an agent document's source and each derived node's base, read from the history the scan loaded
    record = result.history
    copies = record.copies(result.masters) if record is not None else {}
    bases = {c: record.bases(c, result.masters) for c in copies} if record is not None else {}
    # the person's documents first, then the agent's: every list a viewer draws from this one reads in that order
    for m in sorted(result.masters, key=lambda m: result.document_role(m) != "person"):
        closure = result.closures.get(m)
        entry: dict[str, Any] = {
            "path": m,
            "title": master_title(result, m) or m,
            "default": m == dm,
            "fragment": fragments.get(f"master:{m}", ""),
            "engine": (closure.engine if closure and closure.engine else result.quilt.config.engine),
        }
        pdf = result.quilt.root / document_build(m) / f"{Path(m).stem}.pdf"
        aux_known = bool(numbers.get(m))
        if pdf.exists():
            entry["compiled"] = _iso(pdf.stat().st_mtime)
            entry["pdf"] = document_pdf_address(m)
        entry["numbering_known"] = aux_known
        loads = document_loads(result, m)
        if loads:
            entry["loads"] = loads
        if m in copies:
            entry["copy_of"] = copies[m]
            from loom.reshape.linearize import flatten
            from loom.scan.labels import LABEL_DEF
            from loom.section_drafts import context_changed, extract, metadata
            from loom.sync import SyncError

            meta = metadata(result, m)
            entry["scope"] = meta["scope"]
            if meta.get("context"):
                entry["context_when"] = meta["context"]["when"]
                entry["context_changed"] = context_changed(result, meta["context"])
            if meta["scope"].get("kind") == "section":
                keys = set(meta["scope"]["keys"])
                try:
                    keys.update(
                        match[2]
                        for match in LABEL_DEF.finditer(
                            extract(flatten(result.quilt.root, copies[m]).text, meta["scope"])
                        )
                    )
                except SyncError:
                    pass
                entry["scope_keys"] = sorted(keys)
        manifest["masters"].append(entry)
    for key, n in asm.nodes.items():
        if n.kind == "conflict":
            manifest["nodes"][key] = _conflict_entry(n)
            manifest["keys"][key] = _conflict_key(n)
            continue
        if n.kind not in ("environment", "section") and not (n.kind == "proof" and n.id):
            continue
        tags = list_value(n.directives.get("tags", ""))
        authors = list_value(n.directives.get("author", ""))
        entry = {
            "id": key,
            "kind": n.kind,
            "taxon": n.taxon or "",
            "style": n.style or ("plain" if n.kind == "environment" else None),
            "title": plain_text(n.title) if n.title else None,
            "aliases": list(n.aliases),
            "author": authors,
            "created": n.directives.get("created"),
            "tags": tags,
            "file": n.file,
            "src": [n.start, n.end],
            "fragment": fragments.get(key, ""),
            "numbers": _numbers(n, numbers, n.kind == "section" and starred_at(result.files[n.file].clean, n.start)),
            "reached_by": list(n.reached_by),
            "parent": _parent_of(result, n),
            "children": [c for c in n.claimants if asm.nodes[c].kind in ("environment", "section") or asm.nodes[c].id],
            "proofs": list(n.proofs),
            "external": n.external,
            "incomplete": list(n.incomplete),
            "state": "draft",
            "derived": {"proved": False, "settled": False},
        }
        if n.directives.get("name", "").strip():
            entry["name"] = n.directives["name"].strip()
        if n.derived_of:
            entry["derived_of"] = n.derived_of
            base = next((bases[c][key] for c in n.reached_by if key in bases.get(c, {})), None)
            if base is not None and record is not None:
                entry["base"] = {**base, **_base_math(record, base)}
        if n.kind == "section":
            entry["level"] = n.level  # the sectioning depth, so a viewer's contents can stop at subsubsection
        if n.kind == "environment":
            entry["basis"] = n.basis
            entry["basis_reason"] = n.basis_reason
            entry["inline_proof"] = n.inline_proof
        if n.external:
            entry["locator"] = _locator(n)
        manifest["nodes"][key] = entry
        for tag in (
            tags if not n.derived_of else ()
        ):  # an agent document's node is found through its own document, not the quilt's indexes
            manifest["tags"].setdefault(tag, []).append(key)
        if n.kind == "environment" or n.kind == "proof":
            manifest["keys"][key] = _key_entry(result, n)
        if n.kind == "environment":
            for pk in n.proofs:
                if pk not in manifest["keys"]:
                    manifest["keys"][pk] = _key_entry(result, asm.nodes[pk])
    for qkey, r in asm.regions.items():
        container = asm.nodes.get(r.container)
        entry = {
            "key": qkey,
            "container": r.container,
            "in": r.where,
            "label": r.label,
            "numbers": {},
            "src": [r.offset, r.offset],
        }
        if container is not None:
            for master, table in numbers.items():
                if master in container.reached_by and r.label in table:
                    entry["numbers"][master] = {"number": table[r.label].number}
        manifest["regions"][qkey] = entry
    for e in result.edges.edges:
        manifest["edges"].append(
            {"from": e.src, "to": e.to, "kind": e.kind, "via": e.via, "src": {"file": e.file, "line": e.line}}
        )
    for rel in result.relations:
        # a relation is never a dependency, so it sits beside the edges rather than among them; the viewer derives per-node lists from this list
        manifest["relations"].append(
            {"from": rel.from_key, "to": rel.to_key, "kind": rel.kind, "src": {"file": rel.file, "line": rel.line}}
        )
    for m in result.masters:
        manifest["inclusion"][m] = _inclusion_tree(result, m)
    for taxon_name, group in _taxa(result).items():
        manifest["taxa"][taxon_name] = group
    for doc, entry in zip(canon or [], manifest["canon"], strict=False):
        from loom.render.canon import macro_set

        published = macro_set(doc)
        if published:
            manifest["macros"]["sets"][f"canon:{doc.stem}"] = published
            entry["macros"] = f"canon:{doc.stem}"
        manifest["search"].append({"key": doc.path, "title": doc.title, "kind": "canon", "aliases": [], "tags": []})
    if history is not None:
        _versions(result, manifest, history)
        _history(result, manifest, history)
    closure = result.closures.get(dm) if dm else None
    mathjax_macros = {k: v for k, v in (closure.macros.items() if closure else []) if v.kind != "let"}
    # an alphabet declared with \DeclareMathAlphabet is a font the renderer has never heard of, and a body may use commands it does not implement; both are published as the nearest thing it can draw, so an author's own macro renders rather than reaching the page in error colour
    if closure is not None:
        for name, macro in declared_alphabets(closure.clean_text()).items():
            mathjax_macros.setdefault(name, macro)
        for name, macro in package_macros(loaded_packages(closure)).items():
            mathjax_macros.setdefault(name, macro)
    mathjax_macros.update(compatibility_macros(mathjax_macros))
    manifest["macros"]["default"] = to_mathjax(mathjax_macros)
    for key, entry in manifest["nodes"].items():
        if entry.get("derived_of"):
            continue
        manifest["search"].append(
            {
                "key": key,
                "title": entry.get("name") or entry["title"] or key,
                "taxon": entry["taxon"],
                "kind": entry["kind"],
                "aliases": entry["aliases"],
                "tags": entry["tags"],
                "excerpt": " ".join(filter(None, [entry["title"], _excerpt(result, asm.nodes[key])]))
                if entry.get("name")
                else _excerpt(result, asm.nodes[key]),
            }
        )
    for m in manifest["masters"]:
        manifest["search"].append({"key": m["path"], "title": m["title"], "kind": "master", "aliases": [], "tags": []})
    for tid, t in manifest["threads"].items():
        manifest["search"].append({"key": tid, "title": t["title"], "kind": "thread", "aliases": [], "tags": []})
    return manifest


def _conflict_entry(n: NodeRec) -> dict[str, Any]:
    """A doubly-defined id: published with the state `conflicted` and no text, so every view shows the id and none shows a winner."""
    return {
        "id": n.key,
        "kind": "environment",
        "taxon": n.taxon or "",
        "style": n.style or "plain",
        "title": None,
        "aliases": list(n.aliases),
        "author": [],
        "created": None,
        "tags": [],
        "file": "",
        "src": [0, 0],
        "fragment": "",
        "numbers": {},
        "reached_by": list(n.reached_by),
        "parent": {},
        "children": [],
        "proofs": [],
        "external": False,
        "incomplete": [],
        "state": "conflicted",
        "derived": {"proved": False, "settled": False},
        "conflict": list(n.conflict),
    }


def _conflict_key(n: NodeRec) -> dict[str, Any]:
    return {
        "key": n.key,
        "node": n.key,
        "kind": "statement",
        "file": "",
        "src": [0, 0],
        "hash": "",
        "incomplete": [],
        "state": "conflicted",
        "reviews": {"open": {}, "detached": 0},
        "uses": [],
        "closure": [n.key],
        "previous_key_match": None,
        "conflict": list(n.conflict),
    }


def _history(result: ScanResult, manifest: dict[str, Any], history: Any) -> None:
    """`history.steps`, every step oldest first with the document it concerns; and each landmark's `in`, the live draft its step's document now is.

    A document is followed through the history's moves, so a renamed draft still leads to its landmarks; `in` is absent where no live draft does (the draft retired, or a stamp of the whole quilt).
    """
    live = result.masters

    def document(e: Any) -> str | None:
        if e.action == "import":
            d = (e.get("drafted") or {}).get("path")
        elif e.action == "copy":
            d = e.get("to")
        elif e.action == "adopt":
            d = e.get("copy")
        else:
            d = e.get("in")
        return str(d) if isinstance(d, str) and d else None

    from loom.history.acts import cannot_restore

    steps = []
    leads: dict[str, str] = {}
    landmarks: dict[str, Any] = {}
    for e in history.steps():
        row: dict[str, Any] = {"step": e.step, "action": e.action, "name": e.name, "when": e.when}
        if e.actor:
            row["actor"] = e.actor
        if e.message:
            row["message"] = e.message
        doc = document(e)
        if doc:
            row["document"] = doc
            now = history.current_document(doc, live)
            if now:
                row["in"] = now
        if e.get("landmark"):
            landmark = history.landmark_path(e).relative_to(result.quilt.root).as_posix()
            row["landmark"] = landmark
            landmarks[landmark] = e
            if row.get("in"):
                leads[landmark] = row["in"]
        steps.append(row)
    manifest["history"] = {"steps": steps, "acts": _acts(result, history)}
    for entry in manifest["canon"]:
        if entry["path"] in leads:
            entry["in"] = leads[entry["path"]]
        e = landmarks.get(entry["path"])
        if e is not None:
            entry["action"] = e.action
            entry["cannot_restore"] = cannot_restore(result, history, e)


def _acts(result: ScanResult, history: Any) -> list[dict[str, Any]]:
    """Every line of the history, oldest first, as Review › History lists it: what was done, when, by whom, and to what; a document as it is now named, a step's landmark by its path, a text by its hash."""
    live = result.masters
    out: list[dict[str, Any]] = []
    for e in history.entries:
        row: dict[str, Any] = {"action": e.action, "when": e.when}
        if e.actor:
            row["actor"] = e.actor
        if e.step is not None:
            row["step"] = e.step
        for k in ("path", "paths", "message", "hunks", "kept_for", "copy", "page", "line", "done"):
            v = e.get(k)
            if v not in (None, "", []):
                row[k] = v
        doc = e.get("in") if e.action != "import" else (e.get("drafted") or {}).get("path")
        if isinstance(doc, str) and doc:
            row["in"] = history.current_document(doc, live) or doc
        if e.get("landmark") and e.step is not None:
            row["landmark"] = history.landmark_path(e).relative_to(result.quilt.root).as_posix()
        for k in ("from", "to"):
            v = e.get(k)
            if isinstance(v, str) and e.step is None:
                row[k] = v
        if isinstance(e.get("from"), dict) and e.action == "restore":
            row["version"] = e.get("from").get("landmark")
        out.append(row)
    return out


def _versions(result: ScanResult, manifest: dict[str, Any], history: Any) -> None:
    """`keys[k].version` when a key's current text is one the history recorded: what the viewer shows as "text of @3"."""
    from loom.history.versions import matching_version

    for key, entry in manifest["keys"].items():
        h = entry.get("hash")
        if not h:
            continue
        v = matching_version(history, key, h)
        if v is not None:
            entry["version"] = {"step": f"{v.step:04d}", "name": v.name}


def _key_entry(result: ScanResult, n: NodeRec) -> dict[str, Any]:
    assert result.graph is not None
    return {
        "key": n.key,
        "node": n.of if n.kind == "proof" and n.of else n.key,
        "kind": "proof" if n.kind == "proof" else "statement",
        **({"ordinal": n.ordinal} if n.kind == "proof" else {}),
        "file": n.file,
        "src": [n.start, n.end],
        "hash": key_hash(result, n.key),
        "incomplete": list(n.incomplete),
        "state": "incomplete" if n.incomplete else "draft",
        "reviews": {"open": {}, "detached": 0},
        "uses": result.graph.direct(n.key),
        "closure": result.graph.closure(n.key),
        "previous_key_match": None,
    }


def _taxa(result: ScanResult) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in result.nodes.values():
        if n.kind != "environment" or not n.taxon:
            continue
        entry = out.setdefault(
            n.taxon,
            {"style": n.style or "plain", "slug": re.sub(r"[^a-z0-9]+", "-", n.taxon.lower()).strip("-"), "count": 0},
        )
        entry["count"] += 1
    return out


def _inclusion_tree(result: ScanResult, master: str) -> dict[str, Any]:
    asm = result.assembly
    exp = result.expansions[master]
    sites = {(inc.parent, inc.site_start): inc for inc in exp.inclusions if inc.child and inc.child in asm.nodes}

    # The files currently being expanded. Only an INCLUSION enters one -- a section claimant lives in the file it was
    # already in, and guarding those would cut every master's own sections off the tree. `inclusion-cycle` is already
    # an error the scanner reports; a tree that follows the cycle turns that error into a traceback.
    including: set[str] = set()

    def children_of(container: NodeRec, shift: int) -> list[dict[str, Any]]:
        src = result.files[container.file]
        events: list[tuple[int, str, Any]] = []
        for ck in container.claimants:
            events.append((asm.nodes[ck].start, "claimant", ck))
        for (parent, off), inc in sites.items():
            if parent == container.file and any(a <= off < b for a, b in container.own):
                events.append((off, "include", inc))
        events.sort(key=lambda e: e[0])
        out: list[dict[str, Any]] = []
        for _, kind, payload in events:
            if kind == "claimant":
                c = asm.nodes[payload]
                if c.kind == "proof" and not c.id:
                    continue
                via = "section" if c.kind == "section" else "nested-env"
                out.append({"key": c.key, "via": via, "shift": shift, "children": children_of(c, shift)})
            else:
                inc = payload
                child = asm.nodes[inc.child]
                if inc.child in including:
                    # The cycle is named where it closes, so a reader of the tree can see why it stops.
                    out.append(
                        {
                            "key": inc.child,
                            "via": inc.kind,
                            "file": inc.child,
                            "shift": inc.shift,
                            "children": [],
                            "cycle": True,
                        }
                    )
                    continue
                including.add(inc.child)
                try:
                    kids = children_of(child, inc.shift)
                finally:
                    including.discard(inc.child)
                out.append({"key": inc.child, "via": inc.kind, "file": inc.child, "shift": inc.shift, "children": kids})
        _ = src
        return out

    return {"key": master, "children": children_of(asm.nodes[master], 0)}


def _excerpt(result: ScanResult, n: NodeRec, limit: int = 160) -> str:
    src = result.files[n.file]
    text = "".join(src.clean[a:b] for a, b in n.own)
    text = re.sub(r"\\begin\{[^}]*\}(\[[^\]]*\])?|\\end\{[^}]*\}|\\label\{[^}]*\}|\\uses\{[^}]*\}|%[^\n]*", " ", text)
    text = re.sub(r"\\(section|subsection|subsubsection|paragraph)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _stamp() -> str:
    from loom.clock import stamp

    return stamp()


def _iso(mtime: float) -> str:
    import os
    from datetime import UTC, datetime

    if os.environ.get("LOOM_FIXED_TIME"):
        return _stamp()
    return datetime.fromtimestamp(mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
