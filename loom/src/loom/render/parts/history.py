"""Each version of a file of its own the history holds (`history.acts.FILE_VERSION`), for Review › History: `history.files` in the manifest, with its bytes published beside it and how they differ from the file now."""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.render.attach import Attaching

#: Where a file version's bytes and its comparison with now are published, under the site; pruned with the fragments.
KEPT = "fragments/kept"


def attach(build: Attaching) -> None:
    """Add `history.files`, oldest first, and publish each version's bytes and, for text, its line diff against the file now."""
    build.manifest.setdefault("history", {"steps": []})["files"] = file_rows(
        build.result.quilt.root, build.result.quilt.history_dir, build.files
    )


def file_rows(root: Path, history_dir: Path, files: dict[str, str | bytes]) -> list[dict[str, Any]]:
    """The rows of `history.files`, each version's bytes and diff added to `files` by path under the site.

    `kind` is `text` (UTF-8 up to `files.TEXT_LIMIT`), `image` by its suffix, else `other`; `same` says the file holds those bytes now; `diff`, on a text that differs, is a unified diff from the version to the file now (absent: empty). A version whose bytes the store lacks has no `kept` and says so in `cannot_restore`.
    """
    from loom import writes
    from loom.files import SUFFIX_KINDS, TEXT_LIMIT
    from loom.history.acts import cannot_restore_file, file_versions
    from loom.history.ledger import load_history

    rows: list[dict[str, Any]] = []
    for e in file_versions(load_history(history_dir)):
        path, digest = str(e.get("path")), str(e.get("from"))
        row: dict[str, Any] = {"path": path, "version": digest, "when": e.when, "message": e.message}
        if e.actor:
            row["actor"] = e.actor
        if e.get("kept_for"):
            row["kept_for"] = e.get("kept_for")
        data = writes.fetch(history_dir, digest)
        if data is None:
            row.update({"kind": "other", "cannot_restore": "Its bytes are missing from the history."})
            rows.append(row)
            continue
        text = _text(data) if len(data) <= TEXT_LIMIT else None
        image = SUFFIX_KINDS.get(Path(path).suffix.lower()) == "image"
        kind = "text" if text is not None else "image" if image else "other"
        hexd = digest.split(":", 1)[-1][:16]
        row.update({"kind": kind, "bytes": len(data), "kept": f"{KEPT}/{hexd}/{Path(path).name}"})
        files[row["kept"]] = data
        try:
            now: bytes | None = (root / path).read_bytes()
        except OSError:
            now = None
        row["same"] = now == data
        if text is not None and now != data:
            later = _text(now) if now is not None else ""
            if later is not None:
                said = "\n".join(
                    difflib.unified_diff(text.splitlines(), later.splitlines(), path, path, lineterm="", n=3)
                )
                row["diff"] = f"{KEPT}/{hexd}/{hashlib.sha256(path.encode()).hexdigest()[:8]}.diff"
                files[row["diff"]] = said + "\n"
        row["cannot_restore"] = cannot_restore_file(root, e)
        rows.append(row)
    return rows


def _text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
