"""Review: the author's acceptance of blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.paths import MANIFEST
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _review_accept(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`review-accept`: the author's acceptance of the blocks named, against the manifest the page was drawn from; an edit that touches only blocks just accepted is kept as seen."""
    import json

    from loom.identity import is_agent
    from loom.review_queue import accept
    from loom.scan.quilt import reviewer_identity

    reviewer, _ = reviewer_identity(root)
    if not reviewer:
        raise ApiError("no-reviewer", "Choose your reviewer name in Settings", status=409)
    if _str(body, "reviewer") != reviewer:
        raise ApiError("reviewer-changed", "Reviewer changed; reload Review before continuing", status=409)
    if is_agent(_str(body, "author") or reviewer):
        raise ApiError("author-only", "An agent reads and annotates; only the author accepts", status=403)
    keys = body.get("keys")
    if not isinstance(keys, list) or not keys or not all(isinstance(k, str) and k for k in keys):
        raise ApiError("bad-field", "keys must be a nonempty list of block keys")
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        raise ApiError("review-unavailable", "build the quilt before reviewing", status=409)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("reviewer", {}).get("name") != reviewer:
        raise ApiError("reviewer-changed", "Rebuild and reload Review before continuing", status=409)
    try:
        answer = accept(_scan(root), manifest, keys, reviewer)
    except KeyError as exc:
        raise ApiError("not-unresolved", f"{exc.args[0]} is not awaiting review; reload Review", status=409) from exc
    except ValueError as exc:
        raise ApiError("compile-failed", str(exc), status=409) from exc
    if answer["accepted"]:
        # what the page showed with its Accept: an edit touching only blocks just accepted has been seen
        from loom.history.acts import keep_versions
        from loom.pending import keep_accepted

        after = _scan(root)
        moved = keep_accepted(after, reviewer, answer["accepted"])
        if moved:
            keep_versions(after, moved, "keep", "Kept an edit", reviewer)
    return {
        "ok": True,
        "result": f"accepted {len(answer['accepted'])} of {len(answer['accepted']) + len(answer['refused'])}",
        **answer,
    }


HANDLERS: dict[str, Handler] = {
    "review-accept": plain(_review_accept),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ()
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ()
