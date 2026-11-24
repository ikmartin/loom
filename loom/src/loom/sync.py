"""Taking in a pull from the project a quilt mirrors: the record of the pairing, the git it runs in loom's own clone, and the act that writes what a pull brings.

Loom runs git only in its clone (`.loom/local/overleaf/`, `loom.overleaf` makes it), and moves only its own refs (`refs/loom/*`) and the remote's branch. The quilt's own version control, if it has any, is never touched. Nothing here writes to the project: loom has no way to push.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.clock import stamp
from loom.paths import SOURCE_SYNC, document_dir, under
from loom.reshape.importer import closure_of
from loom.scan.quilt import Quilt

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


class SyncError(Exception):
    """A sync precondition failed without changing the quilt source."""


class SourceError(SyncError):
    """A sync refusal the author resolves in the quilt's own source: a document that does not compile or reaches outside the quilt, a pull that does not apply, a file in the way (exit 1)."""


@dataclass
class SyncState:
    # the person's clone: quilt-relative when it sits inside the quilt, absolute otherwise
    directory: str
    # the remote and branch it follows, and the remote's URL when it was paired, which names the workspace
    remote: str
    url: str
    branch: str
    master: str
    integrated: str
    incoming: str = ""
    observed: str = ""
    published_main: str = ""
    # the quilt folder an Overleaf mirror keeps the project in, as Overleaf holds it (`loom.overleaf`); '' for any other pairing
    folder: str = ""
    last_pull: dict[str, Any] = field(default_factory=dict)
    # Projections of the shared origin store (`loom.review_origins`), where they are persisted.
    review_origins: dict[str, str] = field(default_factory=dict)
    review_changed: dict[str, bool] = field(default_factory=dict)
    review_baselines: dict[str, str] = field(default_factory=dict)
    review_local_changed: dict[str, bool] = field(default_factory=dict)
    documents: list[str] = field(default_factory=list)

    @classmethod
    def read(cls, root: Path) -> SyncState:
        path = root / SOURCE_SYNC
        if not path.is_file():
            raise SyncError("this quilt mirrors no Overleaf project")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = cls(**data)
            from loom.review_origins import read

            state.review_origins = {}
            state.review_changed = {}
            state.review_baselines = {}
            state.review_local_changed = {}
            for key, row in read(root).items():
                if row["source"].startswith("pull:"):
                    state.review_origins[key] = row["source"].removeprefix("pull:")
                    state.review_changed[key] = row["changed"]
                    if row.get("baseline"):
                        state.review_baselines[key] = row["baseline"]
                    state.review_local_changed[key] = row["local_before"]
            if not state.documents:
                state.documents = [state.master]
            elif state.master not in state.documents:
                state.documents.insert(0, state.master)
            return state
        except (ValueError, TypeError) as exc:
            raise SyncError(f"{path} is not a record loom can read; pair the quilt with its project again") from exc

    def write(self, root: Path) -> None:
        if self.master not in self.documents:
            self.documents.insert(0, self.master)
        path = root / SOURCE_SYNC
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        from loom.review_origins import read, write
        from loom.writes import stage

        origins = read(root)
        for key, commit in self.review_origins.items():
            # Adoption may have superseded a pull's origin since this transport object was read.
            if origins.get(key, {}).get("source", "").startswith("adopt:") and commit != self.incoming:
                continue
            origins[key] = {
                "source": "pull:" + commit,
                "changed": self.review_changed.get(key, False),
                "baseline": self.review_baselines.get(key),
                "local_before": self.review_local_changed.get(key, False),
                "label": f"Taken in from {source_label(self.url)}",
            }
        if origins or self.last_pull:
            write(root, origins)
        data = {key: value for key, value in vars(self).items() if not key.startswith("review_")}
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        # inside a pull's act the sync record goes with the files it took in (`writes.staging`)
        if stage(path, text.encode("utf-8")):
            return
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def git(cwd: Path, *args: str, env: dict[str, str] | None = None, input: bytes | None = None) -> bytes:
    """Run git in `cwd`, which is the sync directory or a scratch directory, never the quilt's own repository."""
    from loom import gitprog

    try:
        if not gitprog.usable():
            raise FileNotFoundError("git")
        run = subprocess.run(["git", *args], cwd=cwd, env=env, input=input, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise SyncError("Git is required to reach Overleaf") from exc
    if run.returncode:
        detail = run.stderr.decode("utf-8", errors="replace").strip()
        raise SyncError(f"git {' '.join(args)}: {detail or f'exited {run.returncode}'}")
    return run.stdout


def reason(exc: SyncError) -> str:
    """Git's own reason for a failure, one line: its last `fatal:` or `error:` line, without the prefix or the command loom ran."""
    lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
    said = [ln.split("fatal: ", 1)[1] for ln in lines if "fatal: " in ln] or [
        ln.split("error: ", 1)[1] for ln in lines if "error: " in ln
    ]
    return (said[-1] if said else lines[-1] if lines else str(exc)).rstrip(".")


def _named(root: Path) -> str | None:
    """The record's `directory` as written, or None before a pairing or when the record cannot be read."""
    try:
        named = json.loads((root / SOURCE_SYNC).read_text(encoding="utf-8")).get("directory")
    except (OSError, ValueError, AttributeError):
        return None
    return named if isinstance(named, str) and named else None


def skipped_directory(root: Path) -> str | None:
    """The sync directory's quilt-relative path when it sits inside the quilt, else None.

    Every tree walker skips it: it holds copies of the quilt's own sources, which read as the quilt's would define every id twice. The record keeps a directory inside the quilt relative and any other absolute.
    """
    named = _named(root)
    return named if named is not None and not Path(named).is_absolute() else None


def copy_ignore(root: Path, *patterns: str) -> Callable[[str, list[str]], set[str]]:
    """A `shutil.copytree` ignore for a copy of the quilt at `root`: a pattern with a `/` is a quilt-relative path (`CACHE`), the others names as `shutil.ignore_patterns` takes them; the sync directory is left out by path."""
    by_name = shutil.ignore_patterns(*(p for p in patterns if "/" not in p))
    synced = skipped_directory(root)
    pruned = {root / p for p in patterns if "/" in p} | ({root / synced} if synced else set())

    def ignore(folder: str, names: list[str]) -> set[str]:
        return set(by_name(folder, names)) | {n for n in names if Path(folder) / n in pruned}

    return ignore


def workspace(root: Path) -> Path:
    """The sync directory the record names, refused by name when there is no record or the directory is no longer a repository.

    Every Git call runs here. The directory is the person's: loom adds objects and its own refs (`refs/loom/*`), and a fetch or a push moves the remote's branch, but its files, index and checked-out branch are never touched.
    """
    named = _named(root)
    if named is None:
        raise SyncError("this quilt mirrors no Overleaf project")
    clone = root / named
    if not (clone / ".git").exists():
        raise SyncError(f"loom's clone of the project, {named}, is gone or no longer a git repository")
    return clone


def source_label(url: str) -> str:
    """A readable name for a document workspace: Overleaf for its Git transport, otherwise the URL without its scheme or `.git`.

    Parameters
    ----------
    url : str
        The project's git address.

    Returns
    -------
    str
        The name Review shows.
    """
    if "git.overleaf.com/" in url:
        return "Overleaf"
    name = url.split("://", 1)[-1].rstrip("/")
    return name.removesuffix(".git") or url


def revision(cwd: Path, ref: str) -> str:
    return git(cwd, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()


def revision_time(cwd: Path, rev: str) -> str:
    """When `rev` was made, `2026-10-28 14:02` in its own zone: how a revision is named to its reader, the hash staying in the JSON; '' when git cannot say."""
    try:
        made = git(cwd, "log", "-1", "--format=%ci", rev).decode().strip()
    except SyncError:
        return ""
    return made[:16]


def current_selection(state: SyncState, result: ScanResult) -> tuple[str, list[str]]:
    """The sync record's main and selected documents as they are now, main first.

    Each recorded path is followed across the history's moves (`ScanResult.current_document`), so a record written before a `linearize` publishes what the document became; the record itself is never rewritten. A path that leads nowhere is kept as written, so `selected_documents` refuses it by name.

    Parameters
    ----------
    state : SyncState
        The sync record as read.
    result : ScanResult
        A scan of the quilt, for its live documents and history.

    Returns
    -------
    tuple of (str, list of str)
        The local path Overleaf's main maps to, and every selected document without duplicates.
    """

    def now(path: str) -> str:
        return result.current_document(path) or path

    main = now(state.master)
    documents = list(dict.fromkeys(now(d) for d in (state.documents or [state.master])))
    if main not in documents:
        documents.insert(0, main)
    return main, documents


def local_main(quilt: Quilt, state: SyncState) -> str:
    """The local path Overleaf's main file maps to now: `current_selection`'s main, from a fresh scan."""
    from loom.scan.scan import scan

    return current_selection(state, scan(quilt))[0]


def local_path(state: SyncState, main: str, remote: str) -> str:
    """The quilt path a workspace path stands for: Overleaf's main is `main`, the local document it maps to, and any other path is read against `main`'s directory, which is the workspace's root (P12)."""
    return main if remote == state.published_main else under(document_dir(main), remote)


def fetch(quilt: Quilt, state: SyncState) -> SyncState:
    clone = workspace(quilt.root)
    git(clone, "fetch", "--quiet", "--no-tags", state.remote, state.branch)
    new = revision(clone, "FETCH_HEAD")
    # Keep a ref to the reviewed object even when a later fetch moves FETCH_HEAD.
    git(clone, "update-ref", f"refs/loom/incoming/{new}", new)
    if new != state.incoming:
        state.incoming = new
        state.observed = stamp()
    state.write(quilt.root)
    return state


def changed_files(cwd: Path, before: str, after: str) -> list[dict[str, str]]:
    if before == after:
        return []
    raw = git(cwd, "diff", "--name-status", "--no-renames", "-z", before, after)
    parts = raw.decode("utf-8", errors="replace").split("\0")
    return [{"status": parts[i], "path": parts[i + 1]} for i in range(0, len(parts) - 1, 2)]


def exact_renames(cwd: Path, before: str, after: str) -> list[tuple[str, str]]:
    """(deleted, added) remote path pairs between two commits whose blobs are identical: a rename Git would call exact.

    A blob deleted or added more than once in the diff pairs nothing, since which went where cannot be told. Paths are the remote's; `prepare_incorporation` maps Overleaf's main to its local path.
    """
    if before == after:
        return []
    raw = git(cwd, "diff", "--raw", "--no-renames", "--no-abbrev", "-z", before, after).decode(
        "utf-8", errors="replace"
    )
    parts = raw.split("\0")
    deleted: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    for i in range(0, len(parts) - 1, 2):
        meta = parts[i].split()
        if len(meta) < 5:
            continue
        old_blob, new_blob, status = meta[2], meta[3], meta[4]
        if status == "D":
            deleted.setdefault(old_blob, []).append(parts[i + 1])
        elif status == "A":
            added.setdefault(new_blob, []).append(parts[i + 1])
    return sorted(
        (gone[0], came[0]) for blob, gone in deleted.items() if len(gone) == 1 and len(came := added.get(blob, [])) == 1
    )


def tree_files(cwd: Path, commit: str) -> dict[str, bytes]:
    names = git(cwd, "ls-tree", "-r", "--name-only", "-z", commit).split(b"\0")
    return {name.decode("utf-8"): git(cwd, "show", f"{commit}:{name.decode('utf-8')}") for name in names if name}


def incoming_patch(quilt: Quilt, state: SyncState, main: str | None = None) -> bytes:
    """The pinned pull as a Git patch against local paths: Overleaf's main is rewritten to `main`, default `local_main`."""
    if not state.incoming or state.incoming == state.integrated:
        return b""
    # The remote is source-only, and collaborators may add a new input that
    # cannot yet be in the local master closure.
    main = main or local_main(quilt, state)
    base = document_dir(main)
    # every workspace path is the main document's directory's: the prefixes put the patch's paths there (P12)
    prefixes = (f"--src-prefix=a/{base}/", f"--dst-prefix=b/{base}/") if base else ()
    patch = git(workspace(quilt.root), "diff", "--binary", "--no-renames", *prefixes, state.integrated, state.incoming)
    if under(base, state.published_main) != main:
        old = under(base, state.published_main).encode()
        new = main.encode()
        rewritten = []
        for line in patch.splitlines(keepends=True):
            if line.startswith((b"diff --git ", b"--- ", b"+++ ")):
                line = line.replace(b"a/" + old, b"a/" + new).replace(b"b/" + old, b"b/" + new)
            rewritten.append(line)
        patch = b"".join(rewritten)
    return patch


def _incoming_paths(quilt: Quilt, state: SyncState, main: str) -> list[str]:
    paths = [
        local_path(state, main, row["path"])
        for row in changed_files(workspace(quilt.root), state.integrated, state.incoming)
    ]
    if len(paths) != len(set(paths)) or any(Path(p).is_absolute() or ".." in Path(p).parts for p in paths):
        raise SyncError("incoming source contains an unsafe or duplicate path")
    return paths


def pull_files(
    quilt: Quilt, state: SyncState, read: Callable[[str], bytes | None] | None = None
) -> dict[str, bytes | None]:
    """The pinned pull applied to the quilt's current files in a scratch directory: each path it touches and what that path would then hold, None for a removal.

    Every check incorporation makes is made here and nothing in the quilt is written; `incorporate` writes exactly this, and the write API's `sync-preview` reads it. The patch applies hunk by hunk, so an author's edit elsewhere in a file the pull touches survives.

    Parameters
    ----------
    quilt : Quilt
        The paired quilt.
    state : SyncState
        The sync record, with a fetched revision not yet incorporated.
    read : callable, optional
        How a file's current bytes are read (None for one that is not there); default from disk. `incorporate` reads through its act, so what the pull is applied to is what the act replaces.

    Returns
    -------
    dict of str to bytes or None
        Quilt-relative path to its content after the pull.
    """
    root = quilt.root
    if not state.incoming or state.incoming == state.integrated:
        raise SyncError("there is no incoming revision to incorporate")
    main = local_main(quilt, state)
    paths = _incoming_paths(quilt, state, main)
    if not paths:
        raise SyncError("the incoming revision changes no files")
    for row in changed_files(workspace(root), state.integrated, state.incoming):
        path = local_path(state, main, row["path"])
        if row["status"].startswith("A") and (root / path).exists():
            raise SourceError(f"{path} already exists locally; rename or remove it, then incorporate again")
    for path in paths:
        target = root / path
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise SourceError(f"unsafe source path: {path}")
    patch = incoming_patch(quilt, state, main)
    with tempfile.TemporaryDirectory(prefix="loom-pull-") as temporary:
        stage = Path(temporary) / "quilt"
        stage.mkdir()
        for path in paths:
            data = read(path) if read is not None else ((root / path).read_bytes() if (root / path).is_file() else None)
            if data is not None:
                (stage / path).parent.mkdir(parents=True, exist_ok=True)
                (stage / path).write_bytes(data)
        # outside any repository, so `git apply` patches these files and nothing else
        env = {**os.environ, "GIT_CEILING_DIRECTORIES": temporary}
        try:
            git(stage, "apply", "--whitespace=nowarn", "-", env=env, input=patch)
        except SyncError as exc:
            # git's own words name its temporary paths; what the author needs is the file and line (T3)
            at = sorted(set(re.findall(r"patch failed: ([^:\s]+:\d+)", str(exc))))
            where = f" at {', '.join(at)}" if at else ""
            raise SourceError(
                f"the pull does not apply to your current files{where}. "
                "Bring those files in line, then take the pull in again"
            ) from exc
        return {path: (stage / path).read_bytes() if (stage / path).is_file() else None for path in paths}


def _review(quilt: Quilt, state: SyncState, result: ScanResult) -> dict[str, Any]:
    """What the pull asks to be reviewed, read from the incoming review a build publishes: changed and affected keys, collaborator renames, and which keys the author had edited since the last pull."""
    from loom.render.build import build
    from loom.review_queue import fingerprint

    main = current_selection(state, result)[0]
    incoming_review = build(quilt).manifest.get("incoming") or {}
    if incoming_review.get("commit") != state.incoming:
        raise SyncError("the incoming review changed; fetch and review it again")
    changed_keys = [c["key"] for c in incoming_review.get("changes", []) if c.get("category") != "prose"]
    review_keys = sorted(
        set(changed_keys)
        | set(incoming_review.get("affected", []))
        | {d["key"] for c in incoming_review.get("changes", []) for d in c.get("affected", [])}
    )
    # a live document deleted and an identical document added is a collaborator's rename, recorded only once the pull is incorporated and the new file is live (`_record_moves`)
    moves = [
        {
            "from": local_path(state, main, gone),
            "to": local_path(state, main, came),
            "remote": came,
            "main": gone == state.published_main,
        }
        for gone, came in exact_renames(workspace(quilt.root), state.integrated, state.incoming)
        if local_path(state, main, gone) in result.masters and came.endswith(".tex")
    ]
    local_before = {
        key: state.review_local_changed.get(key, False)
        or (
            key in state.review_baselines
            and key in result.nodes
            and fingerprint(result, key) != state.review_baselines[key]
        )
        for key in review_keys
    }
    return {"changed_keys": changed_keys, "review_keys": review_keys, "moves": moves, "local_before": local_before}


def _reaching(root: Path, documents: list[str], paths: set[str]) -> list[str]:
    """The documents among `documents` whose source closure includes one of `paths`: the ones a publish or a pull stamps."""
    out = []
    for document in documents:
        base = document_dir(document)
        if (root / document).is_file() and {
            under(base, k) for k in closure_of(root / base, root / document)[0]
        } & paths:
            out.append(document)
    return out


def _stamp(
    quilt: Quilt, result: ScanResult, documents: list[str], name: str, message: str, actor: str | None
) -> list[str]:
    """Stamp each document as a landmark named `<stem> <name>`, refusing before any is written when one reaches a conflicted key."""
    from loom.history.ledger import load_history
    from loom.history.steps import conflicted_in, free_name, slug, stamp_document

    for document in documents:
        conflicted = conflicted_in(result, document)
        if conflicted:
            raise SourceError(
                f"{document} reaches two definitions of {', '.join(conflicted)}, so it has no one text to stamp; `loom lint --nodes` shows them"
            )
    landmarks = []
    for document in documents:
        history = load_history(quilt.history_dir)
        landmark = free_name(history, slug(f"{Path(document).stem} {name}", limit=120))
        stamp_document(result, history, document, landmark, message.format(document=document), actor, kept_for="sync")
        landmarks.append(landmark)
    return landmarks


def incorporate(quilt: Quilt, state: SyncState, actor: str | None = None) -> dict[str, Any]:
    """Apply the fetched pull to the quilt's files, stamping first each selected document it reaches.

    The landmark keeps each document as it was, uncommitted edits included, so nothing here needs a clean tree and nothing is committed. Mathematics is left for review; acceptance is a separate act.

    Parameters
    ----------
    quilt : Quilt
        The paired quilt.
    state : SyncState
        The sync record, with a fetched revision not yet incorporated; updated and written.
    actor : str, optional
        Who the stamps are recorded as; default the quilt's author.

    Returns
    -------
    dict
        `integrated` (the revision now incorporated), `paths` (the files written) and `landmarks` (one per stamped document).

    See Also
    --------
    pull_files : The same checks and result, writing nothing.
    """
    from loom import writes
    from loom.history.ledger import actor_for

    root = quilt.root
    if not state.incoming or state.incoming == state.integrated:
        # refused before the door is opened, so a refusal leaves nothing behind, not even the lock's file
        raise SyncError("there is no incoming revision to incorporate")
    who = actor if actor is not None else actor_for(root)
    try:
        # one act through the door: the files the pull changes, the landmarks that keep each document as it was, the records of what moved and the sync record are written together or not at all, and a crash is finished or put back whole by recovery (`docs/design/writes.md`)
        with writes.act(root, quilt.history_dir, "pull", who) as w, writes.staging(w):
            # the record read again under the lock: a pull another process took in since leaves nothing to take
            now = SyncState.read(root)
            if now.incoming != state.incoming or now.incoming == now.integrated:
                raise SyncError("there is no incoming revision to incorporate; it was taken in already")
            said = _incorporate(quilt, now, w, who)
            state.__dict__.update(now.__dict__)
            return said
    except ValueError as exc:
        if isinstance(exc, SyncError):
            raise
        raise SyncError(str(exc)) from exc


def _incorporate(quilt: Quilt, state: SyncState, w: Any, who: str | None) -> dict[str, Any]:
    """`incorporate` under the door's lock, staged into the act `w`, which stages loom's records (`writes.staging`): the pull applied to the files as read through the act, so what it replaces is what the patch was applied to."""
    from loom.review_queue import fingerprint
    from loom.scan.scan import scan
    from loom.scan.source import decode

    root = quilt.root
    after = pull_files(quilt, state, read=w.read)
    result = scan(quilt)
    review = _review(quilt, state, result)
    documents = _reaching(root, current_selection(state, result)[1], set(after))
    label = source_label(state.url)
    landmarks = _stamp(
        quilt,
        result,
        documents,
        f"before pull {state.incoming[:12]}",
        f"Before taking a pull from {label}",
        who,
    )
    for path, data in after.items():
        w.replace(path, data)
    # the quilt as the act will leave it, scanned before anything is written so the records go with the files
    incorporated = scan(
        quilt, overlay={path: None if data is None else decode(data)[0] for path, data in after.items()}
    )
    _record_moves(quilt, state, review["moves"], incorporated)
    state.last_pull = {
        "commit": state.incoming,
        "observed": state.observed,
        "keys": review["review_keys"],
        "changed": review["changed_keys"],
    }
    for key in review["review_keys"]:
        state.review_origins[key] = state.incoming
        state.review_changed[key] = key in review["changed_keys"]
        if key in incorporated.nodes:
            state.review_baselines[key] = fingerprint(incorporated, key)
        state.review_local_changed[key] = review["local_before"].get(key, False)
    state.integrated = state.incoming
    state.write(root)
    return {"integrated": state.integrated, "paths": sorted(after), "landmarks": landmarks}


def _record_moves(quilt: Quilt, state: SyncState, moves: list[dict[str, Any]], incorporated: ScanResult) -> None:
    """Append a `move` line (`via: "sync"`) for each exact rename the prepared pull carries whose new path is now a live document.

    Called once, when `finish_incorporation` first records the pull. Overleaf's main renamed takes `published_main` with it, so a publish keeps the collaborator's name, and moving the default document moves `[quilt] main`, as `loom mv` does.
    """
    from loom.history.ledger import actor_for, append_entry
    from loom.reshape.importer import set_main_forced

    for move in moves:
        if move["to"] not in incorporated.masters:
            continue
        append_entry(
            quilt.history_dir,
            "move",
            {"from": move["from"], "to": move["to"], "moved": False, "via": "sync"},
            actor_for(quilt.root),
        )
        if move["main"]:
            state.published_main = move["remote"]
        if move["from"] == quilt.config.main:
            set_main_forced(quilt, move["to"])
