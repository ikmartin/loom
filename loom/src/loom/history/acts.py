"""A version of a document at each of the author's acts, a version of a file no document's version holds, and a version put back.

A version is a landmark (`stamp_document`): Keep and Undo in Your Changes keep one, taking changes in and applying a suggested edit keep one first, the author records one by hand, and restoring keeps the text it replaces as one. A file an update from Overleaf writes over that no such version holds (a bibliography, a figure, a file no document reads) is kept as a version of its own, a `file-version` line naming its bytes by hash. `restore` writes a version back into its document file by file; `restore_file` writes a file's version back; `put_back` writes back the text an undo set aside.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.history.ledger import Entry, History, load_history
from loom.scan.scan import ScanResult

#: The ledger's line for a file kept in Your Changes, beside `undo`'s.
KEEP = "keep"
#: The ledger's line for a version or a set-aside text put back.
RESTORE = "restore"
#: The ledger's line for a suggested edit written into its file (`pending.keep`).
APPLY = "apply"
#: The ledger's line for the Keep of a suggested edit undone (`pending.unkeep`).
UNAPPLY = "unapply"
#: The ledger's line for a version of one file no document's version holds: its bytes before an act wrote over them, by hash (`from`).
FILE_VERSION = "file-version"
#: The ledger's line for a file's version put back (`restore_file`).
FILE_RESTORE = "file-restore"


@dataclass
class Kept:
    """What keeping a version of each document did: the documents a version was kept of, and those none was kept of, with why ('' when nothing had changed since its newest)."""

    kept: list[str]
    skipped: dict[str, str]

    def said(self) -> str:
        """The answer's tail: which versions were kept, and why one was not, in the person's words."""
        out = []
        if self.kept:
            out.append(f"a version of {' and of '.join(Path(d).name for d in self.kept)} is kept")
        for doc, why in self.skipped.items():
            if why:
                out.append(f"no version of {Path(doc).name} was kept: {why}")
        return "; ".join(out)


def documents_reaching(result: ScanResult, paths: list[str] | None) -> list[str]:
    """The person's live documents whose text is made of one of `paths` (`steps.document_files`), or every one of them for None."""
    from loom.history.steps import document_files

    docs = [m for m in result.masters if result.document_role(m) == "person"]
    if paths is None:
        return docs
    wanted = set(paths)
    return [d for d in docs if wanted & set(document_files(result, d))]


def versions_of(history: History, doc: str, live: list[str]) -> list[Entry]:
    """Every landmark whose document is now `doc`, oldest first: its versions."""
    out = []
    for e in history.landmarks():
        recorded = (e.get("drafted") or {}).get("path") if e.action == "import" else e.get("in")
        if isinstance(recorded, str) and history.current_document(recorded, live) == doc:
            out.append(e)
    return out


def keep_versions(result: ScanResult, paths: list[str] | None, kept_for: str, message: str, actor: str | None) -> Kept:
    """Keep a version of each of the person's documents made of one of `paths`, as the act `kept_for` (`keep`, `undo`, `restore`, `apply`), unless its text is its newest version's.

    A document that cannot be stamped (one reaching a conflicted key) is skipped with the reason; the act it accompanies goes ahead, since a version is kept for it, never asked of it.
    """
    from loom.history.steps import free_name, plan_document_stamp, slug, stamp_document, text_hash

    out = Kept([], {})
    for doc in documents_reaching(result, paths):
        history = load_history(result.quilt.history_dir)
        try:
            _, text = plan_document_stamp(result, history, doc)
        except ValueError as exc:
            out.skipped[doc] = str(exc).split(";")[0]
            continue
        newest = versions_of(history, doc, result.masters)
        if newest and (newest[-1].get("to") or {}).get("hash") == text_hash(text):
            out.skipped[doc] = ""
            continue
        name = free_name(history, slug(f"{Path(doc).stem} {kept_for}", limit=120))
        stamp_document(result, history, doc, name, message, actor, kept_for=kept_for)
        out.kept.append(doc)
    return out


def ledger_line(history_dir: Path, action: str, data: dict[str, Any], actor: str | None) -> tuple[Path, str]:
    """The ledger and one line for it, as `append_entry` writes it: what an act through the door (`loom.writes`) journals and appends with its files."""
    import json

    from loom.clock import stamp
    from loom.history.ledger import LEDGER

    return history_dir / LEDGER, json.dumps(
        {"when": stamp(), "actor": actor, "action": action, **data}, ensure_ascii=False
    )


class RestoreRefused(Exception):
    """A version that cannot be put back, and why; `code` is the write API's."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def cannot_restore(result: ScanResult, history: History, entry: Entry) -> str:
    """Why the version `entry` cannot be put back into its document, in the person's words; '' when it can.

    The import is the paper as received, before loom gave its blocks ids. A version that kept no file texts (stamped before they were kept) is one flat text, which goes back only into a document of one file.
    """
    from loom.history.steps import document_files

    if entry.action == "import":
        return "This is the paper as loom received it, before its blocks had ids; putting it back would take every id away."
    recorded = entry.get("in")
    doc = history.current_document(recorded, result.masters) if isinstance(recorded, str) else None
    if not doc or result.document_role(doc) != "person":
        return "Its document is no longer one of yours."
    if not entry.get("files") and len(document_files(result, doc)) > 1:
        return "This version was kept as one text, and the document is now several files."
    return ""


def restore(result: ScanResult, doc: str, version: str, actor: str | None) -> dict[str, Any]:
    """Put `doc` back as the version `version` (a landmark's path or name) holds it, keeping its text now as a version first (P7), and record it.

    Writes each file the version kept (`files`), byte for byte, or its flat text into a document of one file, through the door (`loom.writes`): one act for every file, so a crash between two files undoes the first, and the bytes of each file it replaces are kept whether or not the document still reaches it. A suggested edit whose words it takes out or brings back is recorded so in the act (`pending.follow_words`). Raises RestoreRefused for a version that is not `doc`'s or cannot be put back (`cannot_restore`), for a path outside the quilt (`outside-quilt`), and for a file that changed at the last moment (`changed`). Returns the paths written, the version's label, and the label of the version that holds the text it replaced (a new one, or the newest when nothing had changed since).
    """
    from loom import writes
    from loom.pending import follow_words

    root, hist = result.quilt.root, result.quilt.history_dir
    history = load_history(hist)
    entry = _version(history, root, version)
    if entry is None or entry not in versions_of(history, doc, result.masters):
        raise RestoreRefused("unknown-version", f"{version} is not a version of {doc}")
    why = cannot_restore(result, history, entry)
    if why:
        raise RestoreRefused("cannot-restore", why)
    files: dict[str, bytes] = {}
    if entry.get("files"):
        for path, digest in entry.get("files").items():
            data = writes.fetch(hist, digest)
            if data is None:
                raise RestoreRefused("no-text", f"the text of {path} in this version is missing from the history")
            files[path] = data
    else:
        files[doc] = history.landmark_path(entry).read_bytes()
    label = _label(history, entry, doc, result.masters)
    written: list[str] = []
    try:
        files = {writes.contained(root, path): data for path, data in files.items()}
        with writes.act(root, hist, "restore", actor) as w:
            kept = keep_versions(result, [doc], "restore", f"Before restoring “{label}”", actor)
            if doc in kept.skipped and kept.skipped[doc]:
                raise RestoreRefused("cannot-keep", f"its text now cannot be kept first: {kept.skipped[doc]}")
            written = [path for path, data in files.items() if w.read(path) != data]
            for path in written:
                follow_words(w, path, w.before.get(path), files[path], ("human", actor or ""))
                w.replace(path, files[path])
            w.log(
                *ledger_line(
                    hist,
                    RESTORE,
                    {"from": {"landmark": entry.get("landmark"), "step": entry.step}, "in": doc, "paths": written},
                    actor,
                )
            )
    except writes.WriteRefused as exc:
        raise RestoreRefused(exc.code, exc.message) from exc
    history = load_history(hist)
    newest = versions_of(history, doc, result.masters)[-1]
    return {"paths": written, "label": label, "before": _label(history, newest, doc, result.masters)}


def _label(history: History, entry: Entry, doc: str, live: list[str]) -> str:
    """A version as an answer names it: its message, with its time when another version of the document has the same message ("Kept an edit, 2026-11-04 07:52")."""
    said = entry.message or entry.name
    alike = [e for e in versions_of(history, doc, live) if (e.message or e.name) == said]
    return f"{said}, {entry.when[:16].replace('T', ' ')}" if len(alike) > 1 else said


def _version(history: History, root: Path, ref: str) -> Entry | None:
    """A landmark by its quilt-relative path, else by its name or step (`History.landmark`)."""
    for e in history.landmarks():
        if history.landmark_path(e).relative_to(root).as_posix() == ref:
            return e
    return history.landmark(ref)


def put_back(root: Path, history_dir: Path, path: str, digest: str, actor: str | None, texts: dict[str, str]) -> str:
    """Write back into `path` the bytes an undo set aside (`digest`), through the door (`loom.writes`), keeping the file's bytes now first, a suggested edit whose words that takes out or brings back recorded so (`pending.follow_words`); returns the hash it replaced, '' for a file that was gone.

    `texts` is the open files' texts now (`looks.open_texts`); only a file loom shows may be put back. Raises RestoreRefused for a path outside the quilt (`outside-quilt`), a text the history does not hold, and a file that changed at the last moment (`changed`).
    """
    from loom import writes
    from loom.pending import follow_words

    try:
        rel = writes.contained(root, path)
    except writes.WriteRefused as exc:
        raise RestoreRefused(exc.code, exc.message) from exc
    data = writes.fetch(history_dir, digest)
    if data is None:
        raise RestoreRefused("no-text", f"that text of {rel} is missing from the history")
    if (root / rel).exists() and rel not in texts:
        raise RestoreRefused("not-text", f"{rel} is no longer a text file loom keeps")
    try:
        with writes.act(root, history_dir, "put-back", actor) as w:
            now = w.read(rel)
            before = writes.digest(now)
            follow_words(w, rel, now, data, ("human", actor or ""))
            w.replace(rel, data)
            w.log(*ledger_line(history_dir, RESTORE, {"path": rel, "from": before, "to": digest}, actor))
    except writes.WriteRefused as exc:
        raise RestoreRefused(exc.code, exc.message) from exc
    return before or ""


def file_versions(history: History) -> list[Entry]:
    """Every version of a file of its own (`FILE_VERSION`), oldest first: its path and its bytes by hash (`from`)."""
    return [
        e
        for e in history.entries
        if e.action == FILE_VERSION and isinstance(e.get("path"), str) and isinstance(e.get("from"), str)
    ]


def file_version_line(
    history_dir: Path, path: str, digest: str, kept_for: str, message: str, actor: str | None
) -> tuple[Path, str]:
    """The ledger and a `file-version` line for it: `path`'s bytes `digest`, kept at the act `kept_for` (`sync`, `restore`), which the act's text store holds as the bytes it replaced."""
    return ledger_line(
        history_dir, FILE_VERSION, {"path": path, "from": digest, "kept_for": kept_for, "message": message}, actor
    )


def cannot_restore_file(root: Path, entry: Entry) -> str:
    """Why the file version `entry` cannot be put back, in the person's words; '' when it can.

    A file in the folder that mirrors Overleaf is written by an update alone (the door's `mirrored`), as a document's version there is.
    """
    from loom.overleaf import mirrored

    if mirrored(root, str(entry.get("path"))):
        return "This file mirrors Overleaf, and only an update from Overleaf writes it; take what you need from this version into Overleaf."
    return ""


def restore_file(root: Path, history_dir: Path, path: str, version: str, actor: str | None) -> dict[str, Any]:
    """Put the file `path` back as its version `version` (the hash a `file-version` line names for it) holds it, byte for byte, through the door (`loom.writes`).

    Its bytes now are kept first as a version of their own (`kept_for: "restore"`), and a `file-restore` line records it, both landing with the file in one act; a suggested edit whose words it takes out or brings back is recorded so (`pending.follow_words`).

    Parameters
    ----------
    root : Path
        The quilt.
    history_dir : Path
        Its history.
    path : str
        The file, quilt-relative.
    version : str
        The version's hash, `sha256:<hex>`.
    actor : str, optional
        Who restores it.

    Returns
    -------
    dict
        `path`, the file; `written`, False when the file already held those bytes; `label`, the version as an answer names it.

    Raises
    ------
    RestoreRefused
        `outside-quilt` for a path outside the quilt; `unknown-version` for a hash no version of `path` names; `no-text` when the history lacks its bytes; and the door's refusals (`mirrored`, `changed`, `not-writable`).

    See Also
    --------
    restore : a document's version, every file it kept.
    """
    from loom import writes
    from loom.pending import follow_words

    try:
        rel = writes.contained(root, path)
    except writes.WriteRefused as exc:
        raise RestoreRefused(exc.code, exc.message) from exc
    history = load_history(history_dir)
    entry = next(
        (e for e in reversed(file_versions(history)) if e.get("path") == rel and e.get("from") == version), None
    )
    if entry is None:
        raise RestoreRefused("unknown-version", f"{version} is not a version of {rel}")
    data = writes.fetch(history_dir, version)
    if data is None:
        raise RestoreRefused("no-text", f"the bytes of {rel} in this version are missing from the history")
    label = entry.message or Path(rel).name
    try:
        with writes.act(root, history_dir, "restore", actor) as w:
            now = w.read(rel)
            if now == data:
                return {"path": rel, "written": False, "label": label}
            before = writes.digest(now)
            if before is not None:
                w.log(*file_version_line(history_dir, rel, before, "restore", f"Before restoring “{label}”", actor))
            follow_words(w, rel, now, data, ("human", actor or ""))
            w.replace(rel, data)
            w.log(*ledger_line(history_dir, FILE_RESTORE, {"path": rel, "from": before, "to": version}, actor))
    except writes.WriteRefused as exc:
        raise RestoreRefused(exc.code, exc.message) from exc
    return {"path": rel, "written": True, "label": label}
