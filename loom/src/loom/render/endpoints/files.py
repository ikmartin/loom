"""Files and settings: a box ticked in a Markdown file, a PDF saved, a file or an application opened, the quilt's settings and the permission files that follow them, and the reviewer's name."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _pdf_save(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Write a PDF the viewer made as a new file of the project, at a path the person names (P7).

    Refuses a path that exists, leaves the quilt, is hidden from the viewer or is not a `.pdf`, bytes that are not a PDF, and an agent: page edits are the person's act at the viewer.
    """
    from loom.files import Shown
    from loom.identity import is_agent
    from loom.scan.quilt import load_quilt, reviewer_identity

    name = (_str(body, "path", required=True) or "").strip()
    data = _str(body, "data", required=True) or ""
    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError("author-only", "An agent reads and annotates; only the author saves a PDF", status=403)
    if not name.lower().endswith(".pdf"):
        raise ApiError("bad-field", "a saved PDF's name ends in .pdf")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or name.startswith("/"):
        raise ApiError("bad-field", f"{name} is outside the quilt")
    rel = path.relative_to(root.resolve()).as_posix()
    if not Shown.of(load_quilt(root)).is_shown(rel):
        raise ApiError("hidden", f"{rel} would be hidden from the viewer: name a place it shows", status=403)
    if path.exists():
        raise ApiError("exists", f"{rel} already exists; a saved PDF never replaces a file", status=409)
    try:
        raw = base64.b64decode(data, validate=True)
    except ValueError as exc:
        raise ApiError("bad-field", "data is not base64") from exc
    if not raw.startswith(b"%PDF-"):
        raise ApiError("bad-field", "data is not a PDF")
    from loom.writes import WriteRefused, put

    quilt = load_quilt(root)
    try:
        put(root, quilt.history_dir, rel, raw, kind="pdf-save", new=True)
    except WriteRefused as exc:
        if exc.code == "exists":
            raise ApiError("exists", f"{rel} already exists; a saved PDF never replaces a file", status=409) from None
        raise
    return {"ok": True, "result": f"saved {rel}", "path": rel, "bytes": len(raw)}


def _file_tick(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`file-tick`: the person sets one box of a Markdown file (`loom.tasks`), `task` being the id the published body gives it; refused to a declared agent, which edits a file as it edits any other."""
    from loom.identity import is_agent
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.tasks import TickRefused, tick
    from loom.writes import WriteRefused

    who = reviewer_identity(root)[0]
    if is_agent(_str(body, "author") or who):
        raise ApiError("author-only", "An agent edits the file; a tick in the viewer is the person's", status=403)
    path = _str(body, "path", required=True) or ""
    task = _str(body, "task", required=True) or ""
    done = body.get("done")
    if not isinstance(done, bool):
        raise ApiError("bad-field", "done must be true or false")
    try:
        changed = tick(load_quilt(root), who, path, task, done)
    except TickRefused as exc:
        raise ApiError(exc.code, exc.message, status=404 if exc.code == "no-such-file" else 409) from exc
    except WriteRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    verb = "ticked" if done else "unticked"
    return {"ok": True, "result": f"{verb} a box in {path}" if changed else f"that box in {path} is already {verb}"}


def _settings(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """`settings-save` writes the viewer's Settings into `config.toml`, all of them or none; `agents-update` rewrites the permission files to match it, as `loom upgrade` does. The author's acts, refused to a declared agent: the config is the person's, and an agent never moves its own boundary."""
    from loom.identity import is_agent
    from loom.scan.quilt import load_quilt, reviewer_identity

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError(
            "author-only", "An agent reads and annotates; only the author changes the quilt's settings", status=403
        )
    quilt = load_quilt(root)
    if endpoint == "agents-update":
        from loom.ai.layout import SHELL, variant, write_permissions
        from loom.paths import AI
        from loom.writes import WriteRefused

        if not (root / AI).is_dir():
            raise ApiError(
                "no-agent-layer", "this quilt has no agent layer; run `loom ai init` to write one", status=409
            )
        try:
            written, _ = write_permissions(root, quilt.config, shell=variant(root) == SHELL)
        except WriteRefused as exc:
            raise ApiError(exc.code, exc.message, status=exc.status) from exc
        return {
            "ok": True,
            "result": f"rewrote {', '.join(written)}" if written else "the permission files were current",
        }
    from loom.config_edit import ConfigRefused, save
    from loom.files import Shown
    from loom.writes import WriteRefused

    changes = body.get("changes")
    if not isinstance(changes, dict) or not changes:
        raise ApiError("missing-field", "changes must name at least one setting")
    result = _scan(root)
    shown = Shown.of(quilt)
    own = {m for m in result.masters if result.document_role(m) == "person"}
    tracked = quilt.config.track_edits
    try:
        save(quilt, changes, masters=own, shown=lambda rel: (root / rel).is_file() and shown.is_shown(rel))
    except ConfigRefused as exc:
        raise ApiError("bad-value", str(exc), status=409, fields=exc.refused) from exc
    except WriteRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    except OSError as exc:
        raise ApiError("settings-refused", str(exc), status=409) from exc
    said = f"saved {', '.join(changes)} to config.toml"
    who = reviewer_identity(root)[0]
    if changes.get("review.track_edits") is True and not tracked and who:
        from loom.looks import take

        # tracking starts now, not from a look taken long ago
        take(load_quilt(root), who)
        said += "; took your look, so edits from now on wait in Your Changes"
    return {"ok": True, "result": said}


def _reviewer_settings(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`reviewer-settings`: the reviewer name in effect and where it comes from, saved first when `name` is sent; the author's, refused to a declared agent."""
    from loom.identity import is_agent
    from loom.scan.quilt import reviewer_identity, save_author

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError("author-only", "An agent reads and annotates; only the author names the reviewer", status=403)
    if "name" in body:
        try:
            save_author(_str(body, "name", required=True) or "")
        except (ValueError, OSError) as exc:
            raise ApiError("settings-refused", str(exc), status=409) from exc
    name, source = reviewer_identity(root)
    return {"ok": True, "result": "reviewer settings", "reviewer": {"name": name, "source": source}}


def _open(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`open`: the application `app`, or the shown file `file` in its application, started for the person on their click; nothing in the quilt changes (`loom.files.open_command` says what it refuses)."""
    from loom.files import OpenRefused, Shown, launch, open_command
    from loom.scan.quilt import load_quilt

    app, file = _str(body, "app"), _str(body, "file")
    if (app is None) == (file is None):
        raise ApiError("bad-request", "name an app or a file, not both")
    try:
        argv = open_command(Shown.of(load_quilt(root)), app=app, file=file)
    except OpenRefused as exc:
        raise ApiError(exc.code, exc.message, status=404 if exc.code == "no-such-file" else 400) from exc
    launch(argv)
    return {"ok": True, "result": "opened", "opened": app or file}


HANDLERS: dict[str, Handler] = {
    "file-tick": plain(_file_tick),
    "pdf-save": plain(_pdf_save),
    "settings-save": _settings,
    "agents-update": _settings,
    "reviewer-settings": plain(_reviewer_settings),
    "open": plain(_open),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("open",)
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ("file-tick", "reviewer-settings")
