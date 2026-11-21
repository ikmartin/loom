"""Pages (plan 0.21.3): a Markdown file loom keeps for one thing, the quilt's research state.

The person edits a page directly; an agent writes one through `loom write`, never by hand. A page is a reading, never a source: it says who wrote it, nothing in it is checked, and it is never cited as the paper. Every write is a `page-write` line in the history with its texts kept raw, so who changed what can be read back, and an edit made outside loom shows as one on the next write.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.scan.hashing import sha256

#: TARGET for the quilt's research state.
STATE = "state"
#: The history's action for a write.
ACTION = "page-write"


@dataclass(frozen=True)
class Page:
    """One page: which kind, and where it is."""

    kind: str  # "state"
    path: str  # quilt-relative

    @property
    def name(self) -> str:
        return "the research state"


def state_page(config: Any) -> Page:
    """The quilt's research state, wherever `[quilt] research_state` puts it."""
    return Page(STATE, config.research_state)


def read(root: Path, page: Page) -> str | None:
    p = root / page.path
    return p.read_text(encoding="utf-8") if p.is_file() else None


def text_hash(text: str) -> str:
    """A page's hash, of its exact text: what a reader is shown and `--base` names."""
    return sha256(text)


def writes(root: Path, history_dir: Path, page: Page) -> list[Any]:
    """Every recorded write of `page`, oldest first."""
    from loom.history.ledger import load_history

    return [e for e in load_history(history_dir).entries if e.action == ACTION and e.get("path") == page.path]


def linked(result: Any, root: Path, text: str) -> dict[str, dict[str, str]]:
    """Each link in `text` with what it names, and for a result its hash now, so a later reader can be told it has moved."""
    from loom.links import LINK, resolve
    from loom.records.annotations import load_records
    from loom.scan.owntext import key_hash

    records, _ = load_records(root)
    out: dict[str, dict[str, str]] = {}
    for href in LINK.findall(text):
        target = resolve(result, root, href, records)
        entry = {"kind": target.kind, "key": target.key}
        if target.kind == "node" and target.key in result.nodes:
            entry["hash"] = key_hash(result, target.key)
        out[href] = entry
    return out


def write(result: Any, page: Page, text: str, *, actor: str, session: str | None) -> Any:
    """Write `page` and record it; the checks (`--base`, links) are the caller's, made first.

    The file is replaced whole and atomically, then the history line is appended last, so an interrupted write leaves the record saying nothing that did not happen. `outside` says the file had changed since the last recorded write: the person's own edit, which the trail would otherwise not show.
    """
    from loom.history.ledger import append_entry
    from loom.records.snapshots import write_raw

    root, history_dir = result.quilt.root, result.quilt.history_dir
    current = read(root, page)
    before = writes(root, history_dir, page)
    last_to = before[-1].get("to") if before else None
    outside = current is not None and text_hash(current) != last_to
    links = linked(result, root, text)
    from_hash = write_raw(root, current, history_dir) if current is not None else None
    to_hash = write_raw(root, text, history_dir)
    p = root / page.path
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".loom-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)
    data: dict[str, Any] = {
        "page": page.kind,
        "path": page.path,
        "from": from_hash,
        "to": to_hash,
        "outside": outside,
        "links": links,
    }
    if session:
        data["session"] = session
    return append_entry(history_dir, ACTION, data, actor)


def published(result: Any, page: Page) -> dict[str, Any] | None:
    """`page` as the manifest publishes it, or None when there is none: its text rendered, who last wrote it through loom and when, whether it was edited by hand since, and its links that name nothing now or whose result has moved since the write.

    Rendered as a transcript message is (`render_body`), so a page written in a report's `## [name]` blocks shows its blocks by name.
    """
    from loom.identity import is_agent
    from loom.links import LINK, LinkError, resolve
    from loom.mailbox import render_body
    from loom.records.annotations import load_records
    from loom.scan.owntext import key_hash

    root = result.quilt.root
    text = read(root, page)
    if text is None:
        return None
    h = text_hash(text)
    done = writes(root, result.quilt.history_dir, page)
    last = done[-1] if done else None
    records, _ = load_records(root)
    broken, moved = [], []
    recorded = (last.get("links") or {}) if last else {}
    for href in dict.fromkeys(LINK.findall(text)):
        try:
            target = resolve(result, root, href, records)
        except LinkError as exc:
            broken.append({"href": href, "why": str(exc)})
            continue
        then = recorded.get(href, {}).get("hash")
        if not then or target.kind != "node":
            continue
        if target.key not in result.nodes:
            # it named a result when written; its key now finds only a label (the environment deleted, or no longer declared)
            broken.append({"href": href, "why": f"{href}: the result it named when written is gone"})
        elif key_hash(result, target.key) != then:
            moved.append({"href": href, "key": target.key})
    out: dict[str, Any] = {
        "path": page.path,
        "hash": h,
        "body_html": render_body(text),
        "edited_since": last is None or last.get("to") != h,
        "links": {"broken": broken, "moved": moved},
    }
    if last is not None:
        out["by"] = {"kind": "agent" if is_agent(last.actor or "") else "person", "id": last.actor or ""}
        out["when"] = last.when
    return out
