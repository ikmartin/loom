"""Taking in a pull from the project a quilt mirrors: the record of the pairing, the git it runs in loom's own clone, and the act that writes what a pull brings.

Loom runs git only in its clone (`.loom/local/overleaf/`, `loom.overleaf` makes it), and moves only its own refs (`refs/loom/*`) and the remote's branch. The quilt's own version control, if it has any, is never touched. Nothing here writes to the project: loom has no way to push.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    review_by: dict[str, list[str]] = field(default_factory=dict)
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
            state.review_by = {}
            for key, row in read(root).items():
                if row["source"].startswith("pull:"):
                    state.review_origins[key] = row["source"].removeprefix("pull:")
                    state.review_changed[key] = row["changed"]
                    if row.get("baseline"):
                        state.review_baselines[key] = row["baseline"]
                    state.review_local_changed[key] = row["local_before"]
                    state.review_by[key] = list(row.get("by") or [])
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
                "by": self.review_by.get(key, []),
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


def incorporate(quilt: Quilt, state: SyncState, me: list[str], actor: str | None = None) -> dict[str, Any]:
    """Take the fetched revision into the mirrored folder as Overleaf holds it, stamping first each document it reaches, as one act through the door.

    Each file is written with Overleaf's bytes (`theirs`), so a change made here never stops an update: it is written over, its bytes kept in the version stamped first and in the act's journal, and named in the answer. Nothing is committed and no mathematics is accepted.

    Parameters
    ----------
    quilt : Quilt
        The mirroring quilt.
    state : SyncState
        The record, with a fetched revision not yet taken in; updated and written.
    me : list of str
        The addresses the person goes by on Overleaf: a block only their commits touched is not listed for Review.
    actor : str, optional
        Who the act and its stamps are recorded as; default the quilt's author.

    Returns
    -------
    dict
        `integrated`, the revision now taken in; `paths`, the files written; `landmarks`, one per stamped document; `by`, the names of the others whose changes Review lists; `own`, how many changed blocks it leaves out as the person's alone; `overwritten`, the files that held a change made here.
    """
    from loom import writes
    from loom.history.ledger import actor_for

    root = quilt.root
    if not state.folder:
        raise SyncError("this quilt mirrors no Overleaf project")
    if not state.incoming or state.incoming == state.integrated:
        # refused before the door is opened, so a refusal leaves nothing behind, not even the lock's file
        raise SyncError("there is nothing new to take in")
    who = actor if actor is not None else actor_for(root)
    try:
        # one act through the door: the files, the versions that keep each document as it was, the records of what moved and the record of the pairing, written together or not at all, and a crash finished or put back whole by recovery (`docs/design/writes.md`)
        with writes.act(root, quilt.history_dir, "pull", who) as w, writes.staging(w):
            # the record read again under the lock: an update another process took in since leaves nothing to take
            now = SyncState.read(root)
            if now.incoming != state.incoming or now.incoming == now.integrated:
                raise SyncError("there is nothing new to take in; it was taken in already")
            said = _incorporate(quilt, now, w, who, me)
            state.__dict__.update(now.__dict__)
            return said
    except ValueError as exc:
        if isinstance(exc, SyncError):
            raise
        raise SyncError(str(exc)) from exc


def _incorporate(quilt: Quilt, state: SyncState, w: Any, who: str | None, me: list[str]) -> dict[str, Any]:
    """`incorporate` under the door's lock, staged into the act `w`, which stages loom's records (`writes.staging`): Overleaf's bytes against the files as read through the act, so what is written over is what the act replaces."""
    from loom.review_queue import fingerprint
    from loom.scan.scan import scan
    from loom.scan.source import decode

    root = quilt.root
    clone = workspace(root)
    after, overwritten = theirs(clone, state, w.read)
    result = scan(quilt)
    main = current_selection(state, result)[0]
    moves = [
        {
            "from": local_path(state, main, gone),
            "to": local_path(state, main, came),
            "remote": came,
            "main": gone == state.published_main,
        }
        for gone, came in exact_renames(clone, state.integrated, state.incoming)
        if local_path(state, main, gone) in result.masters and came.endswith(".tex")
    ]
    documents = _reaching(root, current_selection(state, result)[1], set(after))
    landmarks = _stamp(
        quilt, result, documents, "before update from Overleaf", f"Before an update from {source_label(state.url)}", who
    )
    for path, data in after.items():
        w.replace(path, data)
    # the quilt as the act will leave it, scanned before anything is written so the records go with the files
    incorporated = scan(
        quilt, overlay={path: None if data is None else decode(data)[0] for path, data in after.items()}
    )
    _record_moves(quilt, state, moves, incorporated)
    listed, own = _changed_blocks(clone, state, result, incorporated, after, me)
    by = sorted({name for names in listed.values() for name in names})
    state.last_pull = {
        "commit": state.incoming,
        "observed": state.observed,
        "files": len(after),
        "by": by,
        "own": own,
        "overwritten": overwritten,
    }
    for key, names in listed.items():
        state.review_origins[key] = state.incoming
        state.review_changed[key] = True
        state.review_baselines[key] = fingerprint(incorporated, key)
        state.review_local_changed[key] = False
        state.review_by[key] = names
    state.integrated = state.incoming
    state.write(root)
    return {
        "integrated": state.integrated,
        "paths": sorted(after),
        "landmarks": landmarks,
        "by": by,
        "own": own,
        "overwritten": overwritten,
    }


def blobs(cwd: Path, rev: str) -> dict[str, tuple[str, bytes]]:
    """Every file of `rev`, by path: its blob's id and its bytes, read in one pass (`git cat-file --batch`) rather than one git run a file."""
    listed = git(cwd, "ls-tree", "-r", "-z", rev).split(b"\0")
    entries: list[tuple[str, str]] = []
    for line in listed:
        if not line:
            continue
        meta, _, path = line.partition(b"\t")
        kind, oid = meta.split()[1:3]
        if kind == b"blob":
            entries.append((path.decode("utf-8"), oid.decode()))
    out = git(cwd, "cat-file", "--batch", input=b"".join(oid.encode() + b"\n" for _, oid in entries))
    files: dict[str, tuple[str, bytes]] = {}
    at = 0
    for name, blob in entries:
        head_end = out.index(b"\n", at)
        size = int(out[at:head_end].split()[2])
        files[name] = (blob, out[head_end + 1 : head_end + 1 + size])
        at = head_end + 1 + size + 1
    return files


def blob_id(data: bytes) -> str:
    """The id git gives `data` as a blob."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def theirs(
    clone: Path, state: SyncState, read: Callable[[str], bytes | None]
) -> tuple[dict[str, bytes | None], list[str]]:
    """What taking the fetched revision in writes: each file Overleaf holds, as Overleaf holds it, where the folder holds anything else, and None for each file it no longer holds that the folder still does; a file only here is left. With it, the files here that held anything but what the last update left, which are written over.

    `read` is how a file's bytes are read now (None for one that is not there): through the act, so what is written over is what the act replaces.
    """
    now = blobs(clone, state.incoming)
    before = {name: blob for name, (blob, _) in blobs(clone, state.integrated).items()}
    after: dict[str, bytes | None] = {}
    over: list[str] = []
    for remote in sorted(set(now) | set(before)):
        local = under(state.folder, remote)
        here = read(local)
        want = now[remote][1] if remote in now else None
        if here == want or (want is None and here is None):
            continue
        after[local] = want
        if here is not None and blob_id(here) != before.get(remote):
            over.append(local)
    return after, over


def _authors(clone: Path, state: SyncState, remote: str, first: int, last: int) -> list[tuple[str, str]]:
    """(name, address) of each commit of the update that touched lines `first` to `last` of `remote`, read with `git blame`; where none did, as when a change only removed lines, every commit of the update that touched the file."""
    said = git(
        clone, "blame", "--porcelain", "-L", f"{first},{last}", f"{state.integrated}..{state.incoming}", "--", remote
    )
    commits: dict[str, dict[str, Any]] = {}
    current = ""
    for raw in said.decode("utf-8", errors="replace").splitlines():
        if raw.startswith("\t"):
            continue
        word, _, rest = raw.partition(" ")
        if len(word) == 40 and all(c in "0123456789abcdef" for c in word):
            current = word
            commits.setdefault(current, {"boundary": False, "name": "", "email": ""})
        elif word == "author" and current:
            commits[current]["name"] = rest
        elif word == "author-mail" and current:
            commits[current]["email"] = rest.strip("<>")
        elif word == "boundary" and current:
            commits[current]["boundary"] = True
    touched = [(c["name"], c["email"]) for c in commits.values() if not c["boundary"]]
    if touched:
        return touched
    log = git(clone, "log", "--format=%aN%x00%aE", f"{state.integrated}..{state.incoming}", "--", remote)
    return [tuple(line.split("\0", 1)) for line in log.decode("utf-8", errors="replace").splitlines() if "\0" in line]  # type: ignore[misc]


def _changed_blocks(
    clone: Path,
    state: SyncState,
    before: ScanResult,
    after: ScanResult,
    written: dict[str, bytes | None],
    me: list[str],
) -> tuple[dict[str, list[str]], int]:
    """The blocks the update changed that Review lists, each with the names of whoever else's commits touched it, and how many it left out because every commit that touched them is the person's alone (`me`)."""
    from loom.review_queue import fingerprint
    from loom.scan.source import decode

    mine = {m.lower() for m in me}
    listed: dict[str, list[str]] = {}
    own = 0
    texts = {path: decode(data)[0] for path, data in written.items() if data is not None}
    for key, node in after.nodes.items():
        if node.kind in ("master", "file", "conflict") or node.file not in texts:
            continue
        if key in before.nodes and fingerprint(before, key) == fingerprint(after, key):
            continue
        text = texts[node.file]
        first, last = text.count("\n", 0, node.start) + 1, text.count("\n", 0, max(node.start, node.end - 1)) + 1
        who = _authors(clone, state, node.file[len(state.folder) + 1 :], first, last)
        if not who:
            continue
        others = sorted({name for name, email in who if email.lower() not in mine})
        if others:
            listed[key] = others
        else:
            own += 1
    return listed, own


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
