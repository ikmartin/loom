"""Publish agent documents' changes for Review, each against the document it was copied from."""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
from typing import Any

from loom.render.prose_changes import document_body, pair
from loom.render.review_compare import _changed, _render_into
from loom.scan.hashing import mathematical_hash
from loom.scan.macros import parse_macros, to_mathjax
from loom.scan.scan import ScanResult
from loom.scan.source import blank_comments
from loom.sync import (
    SyncError,
    source_label,
)


def _citation(result: ScanResult, dependent: str, target: str) -> str | None:
    if result.graph is None:
        return None
    from loom.render.markup import slug

    edge = next(
        (
            e
            for e in result.graph.out.get(dependent, [])
            if e.offset >= 0 and e.via != "uses" and result.graph.statement_key(e.to) == target
        ),
        None,
    )
    if edge is None:
        return None
    label_target = result.assembly.labels.get(edge.label, edge.to)
    return f"cite-{slug(edge.file)}-{edge.offset}-{slug(label_target)}"


def attach_adoptions(
    result: ScanResult, renderer: Any, manifest: dict[str, Any], files: dict[str, str | bytes]
) -> None:
    """Publish agent documents' changes, each against the document it was copied from."""
    from loom.adopt import comparison, decisions
    from loom.history.ledger import load_history
    from loom.reshape.copy import derived_key

    contributions = []
    # each key's closure, read once a build and only for the keys a changed result could affect
    closures: dict[str, set[str]] = {}

    def closure_of(k: str) -> set[str]:
        if k not in closures:
            closures[k] = set(result.dependencies.closure(k))
        return closures[k]

    for copy in sorted(load_history(result.quilt.history_dir).copies(result.masters)):
        try:
            data = comparison(result, copy)
            choices = decisions(result, copy, manifest.get("reviewer", {}).get("name"), data=data)
            # the copy's macros, one set for all its rows and its prose
            proposal_pre = result.closures.get(copy)
            macro_name = "adopt:" + data["fingerprint"][:20]
            manifest["macros"]["sets"][macro_name] = to_mathjax(
                parse_macros(blank_comments(proposal_pre.raw_text() if proposal_pre else ""))
            )
            rows = []
            for row in data["changes"]:
                # a clash is shown, never offered, so the person sees why it can't be taken
                if not row["offered"] and row["class"] != "conflict":
                    continue
                key = row["key"]
                original = next(
                    (old for old, new in data["baseline"].get("mapping", {}).items() if new == key.split("/", 1)[0]),
                    key.split("/", 1)[0],
                )
                derived = derived_key(original + ("/" + key.split("/", 1)[1] if "/" in key else ""), data["suffix"])
                local_node = result.nodes.get(key)
                proposed_node = result.nodes.get(derived)
                current_pre = result.closures.get(data["source"])
                # a merged result is shown as it would be written: both edits, line by line
                before, after = row["current"], row["merged"] or row["proposed"]
                left, right = _changed(before, after)
                digest = hashlib.sha256((data["fingerprint"] + key).encode()).hexdigest()[:20]
                local_path = f"fragments/incoming/{digest}-local.html"
                proposed_path = f"fragments/incoming/{digest}-proposal.html"
                if local_node:
                    _render_into(
                        files,
                        local_path,
                        renderer,
                        result,
                        key,
                        before,
                        current_pre.raw_text() if current_pre else "",
                        left,
                    )
                if proposed_node:
                    _render_into(
                        files,
                        proposed_path,
                        renderer,
                        result,
                        proposed_node.key,
                        after,
                        proposal_pre.raw_text() if proposal_pre else "",
                        right,
                    )
                from loom.records.dependencies import historical_display

                changed_targets = {key} if row["math_changed"] else set()
                for target, owner in result.dependencies.owners.items():
                    if owner == key and target.startswith("equation:"):
                        label = target.removeprefix("equation:")
                        old_display = historical_display(before, label) or ""
                        new_display = historical_display(after, label) or ""
                        if mathematical_hash(old_display) != mathematical_hash(new_display):
                            changed_targets.add(target)
                affected = [
                    {"key": k, "citation": _citation(result, k, key)}
                    for k in (manifest["keys"] if changed_targets else ())
                    if k != key and not result.nodes[k].derived_of and changed_targets & closure_of(k)
                ]
                rows.append(
                    {
                        **row,
                        "incoming_macros": macro_name,
                        "local": local_path if local_node else None,
                        "incoming": proposed_path if proposed_node else None,
                        "proposed_key": derived if proposed_node else None,
                        "affected": affected,
                    }
                )
            current_pre = result.closures.get(data["source"])
            context_key = next((k for k, n in result.nodes.items() if data["source"] in n.reached_by), "")
            prose = pair(
                renderer,
                result,
                context_key,
                document_body(data["current_document"]),
                document_body(data["proposed_document"]),
                current_pre.raw_text() if current_pre else "",
                proposal_pre.raw_text() if proposal_pre else "",
                files,
            )
            prose["incoming_macros"] = macro_name
            if rows or data["document_changed"] or data["preamble_changed"]:
                contributions.append(
                    {
                        "kind": "adopt",
                        "scope": data["scope"],
                        "preamble_changed": data["preamble_changed"],
                        "preamble_conflict": data["preamble_conflict"],
                        "preamble_current": data["current_preamble"],
                        "preamble_proposed": data["proposed_preamble"],
                        "copy": copy,
                        "source": data["source"],
                        "label": f"{data['scope']['title']} · {Path(copy).stem}"
                        if data["scope"].get("kind") == "section"
                        else f"Incoming from agent document “{Path(copy).stem}”",
                        "fingerprint": data["fingerprint"],
                        "changes": rows,
                        "document_changed": data["document_changed"],
                        "document_comparison": prose,
                        "document_conflict": data["document_conflict"],
                        "document_diff": "".join(
                            difflib.unified_diff(
                                data["current_document"].splitlines(True),
                                data["proposed_document"].splitlines(True),
                                fromfile="Working document",
                                tofile="Proposed document",
                            )
                        ),
                        "choices": choices,
                        "issues": [],
                    }
                )
        except (SyncError, OSError, ValueError) as exc:
            contributions.append(
                {
                    "kind": "adopt",
                    "copy": copy,
                    "label": f"Incoming from agent document “{Path(copy).stem}”",
                    "changes": [],
                    "issues": [str(exc)],
                }
            )
    # Preserve the existing pull field for clients; contributions adds the common source inventory.
    pulled = manifest.get("incoming")
    manifest["contributions"] = (
        [
            {
                "kind": "workspace",
                "label": f"Incoming from {source_label(pulled['workspace'])}",
                **pulled,
            }
        ]
        if pulled
        else []
    ) + contributions
