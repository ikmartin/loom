"""Text that arrives from elsewhere: an Overleaf project paired, its token given and its text taken in by update, and an agent's copy compared, chosen from and taken into the person's document."""

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


def _overleaf(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """The `overleaf-*` endpoints: pair the quilt with a project from a pasted link, give the git token once, update from Overleaf, and end the pairing; the person's acts, refused to a declared agent. A failure to reach Overleaf answers 409 with its code (`overleaf.MirrorError`), and the token goes from the request to the credential helper and nowhere else."""
    from loom import overleaf
    from loom.identity import is_agent
    from loom.scan.quilt import load_quilt, reviewer_identity

    if is_agent(_str(body, "author") or ""):
        raise ApiError("author-only", "Pairing with Overleaf and updating from it are the author's", status=403)
    quilt = load_quilt(root)
    reviewer = reviewer_identity(root)[0] or None
    try:
        if endpoint == "overleaf-update":
            return {"ok": True, "result": overleaf.update(quilt, reviewer)}
        if endpoint == "overleaf-unpair":
            overleaf.unpair(quilt)
            return {"ok": True, "result": {"paired": False}}
        state = overleaf.paired(root)
        link = _str(body, "link", required=endpoint == "overleaf-pair" or state is None) or ""
        address = overleaf.address(link) if link else state.url if state is not None else ""
        if endpoint == "overleaf-token":
            overleaf.store_token(address, _str(body, "token", required=True) or "")
            return {"ok": True, "result": {"stored": True}}
        folder, main, me = body.get("folder"), body.get("main"), body.get("me")
        if folder is None or main is None or me is None:
            return {"ok": True, "result": {"choose": overleaf.prepare(quilt, address)}}
        if not isinstance(folder, str) or not isinstance(main, str):
            raise ApiError("bad-field", "folder and main must be strings")
        if not isinstance(me, list) or not all(isinstance(m, str) for m in me):
            raise ApiError("bad-field", "me must be a list of addresses")
        return {"ok": True, "result": {"paired": overleaf.pair(quilt, address, folder, main, me, reviewer)}}
    except overleaf.LinkRefused as exc:
        raise ApiError(exc.code, str(exc), status=409) from exc
    except overleaf.MirrorError as exc:
        raise ApiError(exc.code, str(exc), status=400 if exc.code == "bad-token" else 409) from exc


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
    "overleaf-pair": _overleaf,
    "overleaf-token": _overleaf,
    "overleaf-update": _overleaf,
    "overleaf-unpair": _overleaf,
    "adopt-close": _adopt,
    "adopt-reopen": _adopt,
    "adopt-refresh": _adopt,
    "adopt-paper": _adopt,
    "adopt-decision": _adopt,
    "adopt-preview": _adopt,
    "adopt-finish": _adopt,
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("adopt-preview", "adopt-paper")
#: The ones the publisher does not rebuild after: the reads, and the decision, which publishes the queue's metadata itself without rendering documents.
NO_REBUILD: tuple[str, ...] = (*READS, "adopt-decision", "overleaf-token")
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ("adopt-decision",)
#: The ones that wait on Overleaf over the network and take the door's lock only to write, so the publisher runs them outside the publication's lock.
OWN_LOCK: tuple[str, ...] = ("overleaf-pair", "overleaf-token", "overleaf-update")
