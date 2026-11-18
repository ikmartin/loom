"""Text that arrives from elsewhere: a collaborator's pull reviewed and incorporated, and an agent's copy compared, chosen from and taken into the person's document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.paths import MANIFEST, SITE
from loom.render.endpoints.base import ApiError, Handler, _str


def _accept_keys(body: dict[str, Any]) -> list[str]:
    keys = body.get("accept", [])
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ApiError("bad-field", "accept must be a list of mathematical block keys")
    return keys


def _sync(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """`sync-preview` and `sync-incorporate`: a fetched pull prepared for review without being applied, then incorporated, with the blocks the reviewer accepted in the same act; incorporating is the author's, refused to a declared agent."""
    from loom.identity import is_agent
    from loom.incorporation_review import finish, preview, validate

    if endpoint == "sync-incorporate" and is_agent(_str(body, "author") or ""):
        raise ApiError("author-only", "Incorporating a collaborator's changes is the author's", status=403)
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.scan.scan import scan
    from loom.sync import SyncError, SyncState, pull_files
    from loom.sync import incorporate as incorporate_pull

    try:
        quilt = load_quilt(root)
        state = SyncState.read(root)
        incoming = _str(body, "incoming", required=True)
        base = _str(body, "base", required=True)
        if incoming != state.incoming:
            raise ApiError("revision-changed", "the fetched revision changed; reload Review")
        if base != state.integrated and state.integrated != state.incoming:
            raise ApiError("revision-changed", "the incorporated base changed; reload Review")
        binding = {"kind": "sync", "incoming": incoming or "", "base": base or ""}
        reviewer, _ = reviewer_identity(root)
        if endpoint == "sync-preview" or body.get("review_token") or body.get("accept"):
            if not reviewer or _str(body, "reviewer") != reviewer:
                raise ApiError("reviewer-changed", "Choose your reviewer name and reload Review", status=409)
            before = scan(quilt)
            if endpoint == "sync-preview":
                overlay = {
                    p: data.decode("utf-8") if data is not None else ""
                    for p, data in pull_files(quilt, state).items()
                    if p.endswith((".tex", ".sty", ".cls", ".bib"))
                }
                return {"ok": True, "result": preview(before, overlay, binding, reviewer)}
            accepted = _accept_keys(body)
            saved = validate(before, _str(body, "review_token", required=True) or "", binding, reviewer, accepted)
        else:
            saved = None
        sync_result = incorporate_pull(quilt, state, reviewer or None)
        if saved is not None:
            sync_result.update(finish(scan(load_quilt(root)), saved, accepted, reviewer or ""))
    except SyncError as exc:
        raise ApiError("sync-refused", str(exc), status=409) from exc
    return {"ok": True, "result": sync_result}


def _adopt(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """The `adopt-*` endpoints: an agent's copy compared with its document, the reviewer's choices saved, previewed and incorporated, and a section draft closed, reopened, refreshed or typeset in its paper; the author's acts, refused to a declared agent."""
    from loom.adopt import comparison, decisions, incorporate, prepare
    from loom.adopt import decide as adopt_decide
    from loom.identity import is_agent
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.scan.scan import scan
    from loom.sync import SyncError

    reviewer, _ = reviewer_identity(root)
    if not reviewer or _str(body, "reviewer") != reviewer:
        raise ApiError("reviewer-changed", "Choose your reviewer name and reload Review", status=409)
    if is_agent(_str(body, "author") or reviewer):
        raise ApiError("author-only", "An agent proposes; only the author incorporates", status=403)
    copy = _str(body, "copy", required=True) or ""
    try:
        result = scan(load_quilt(root))
        if endpoint in ("adopt-close", "adopt-reopen"):
            from loom.draft_lifecycle import close_draft, reopen_draft

            answer = (
                close_draft(result, copy, reviewer, confirmed=body.get("confirmed") is True)
                if endpoint == "adopt-close"
                else reopen_draft(result, copy, reviewer)
            )
        elif endpoint == "adopt-refresh":
            from loom.adopt import refresh

            answer = refresh(result, copy)
        elif endpoint == "adopt-paper":
            from loom.section_drafts import preview_in_paper

            answer = preview_in_paper(result, copy)
        elif endpoint == "adopt-finish":
            from loom.incorporation_review import finish, validate

            token = _str(body, "token", required=True) or ""
            accepted = _accept_keys(body)
            saved = (
                validate(
                    result,
                    _str(body, "review_token", required=True) or "",
                    {"kind": "adopt", "token": token},
                    reviewer,
                    accepted,
                )
                if body.get("review_token") or accepted
                else None
            )
            answer = incorporate(result, copy, token, reviewer)
            if saved is not None:
                answer.update(finish(scan(load_quilt(root)), saved, accepted, reviewer))
        elif endpoint == "adopt-decision":
            keys = body.get("keys")
            document = body.get("document")
            kept = body.get("kept", [])
            if (
                not isinstance(keys, list)
                or not all(isinstance(k, str) for k in keys)
                or not isinstance(document, bool)
                or not isinstance(body.get("preamble", False), bool)
                or not isinstance(kept, list)
                or not all(isinstance(k, str) for k in kept)
            ):
                raise ApiError("bad-field", "keys must be a list of strings and document must be a boolean")
            revision = body.get("revision", 0)
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
                raise ApiError("bad-field", "revision must be a nonnegative integer")
            data = comparison(result, copy)
            answer = adopt_decide(
                result,
                copy,
                keys,
                document,
                _str(body, "fingerprint", required=True) or "",
                reviewer,
                kept,
                revision=revision,
                data=data,
                preamble=bool(body.get("preamble", False)),
            )
            import json

            from loom.render.publish import publish

            manifest_path = root / MANIFEST
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text())
                if manifest.get("reviewer", {}).get("name") == reviewer:
                    for contribution in manifest.get("contributions", []):
                        if (
                            contribution.get("copy") == data["copy"]
                            and contribution.get("fingerprint") == data["fingerprint"]
                        ):
                            contribution["choices"] = answer
                    publish(root / SITE, {}, manifest)
        else:
            data = comparison(result, copy)
            chosen = decisions(result, copy, reviewer, data=data)
            if _str(body, "fingerprint", required=True) != chosen["fingerprint"]:
                raise SyncError("Contribution changed; reload Review")
            answer = prepare(
                result,
                copy,
                chosen["keys"],
                chosen["document"],
                reviewer,
                data=data,
                preamble=chosen.get("preamble", False),
            )
            from loom.incorporation_review import preview

            answer["review"] = preview(result, answer["overlay"], {"kind": "adopt", "token": answer["token"]}, reviewer)
        return {"ok": True, "result": answer}
    except (SyncError, ValueError, OSError) as exc:
        raise ApiError("adoption-refused", str(exc), status=409) from exc


HANDLERS: dict[str, Handler] = {
    "sync-incorporate": _sync,
    "sync-preview": _sync,
    "adopt-close": _adopt,
    "adopt-reopen": _adopt,
    "adopt-refresh": _adopt,
    "adopt-paper": _adopt,
    "adopt-decision": _adopt,
    "adopt-preview": _adopt,
    "adopt-finish": _adopt,
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("adopt-preview", "sync-preview", "adopt-paper")
#: The ones the publisher does not rebuild after: the reads, and the decision, which publishes the queue's metadata itself without rendering documents.
NO_REBUILD: tuple[str, ...] = (*READS, "adopt-decision")
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ("adopt-decision",)
