"""Taking an update in from the Overleaf project a quilt mirrors: the record of the pairing, and the act that writes what an update brings and says whose changes it brought.

The record (`.loom/records/source-sync.json`) travels with the quilt, so it holds only what loom checks again at every read: the project's id, the mirrored folder's name, the main file's name in the project, and the revisions taken in and waiting. Git runs only in loom's own clone, through `loom.overleaf.run`, never in the quilt's own repository. Nothing here writes to the project: loom has no way to push.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from loom.clock import stamp
from loom.paths import LOOM, OVERLEAF_CLONE, SOURCE_SYNC, document_dir, under
from loom.reshape.importer import closure_of
from loom.scan.quilt import Quilt

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


class SyncError(Exception):
    """A step of the Overleaf mirror that could not be taken; nothing of the quilt was changed."""


class MirrorError(SyncError):
    """Overleaf could not be read, or the mirror's record or clone could not be used, and why, in the person's words; `code` is the write API's."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


#: A project id as Overleaf writes it: 24 hex digits, or digits for an old project.
PROJECT_ID = re.compile(r"[0-9a-f]{24}|[0-9]+")
#: A revision as git names it.
REVISION = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
#: A main file's name in the project: a `.tex` at its top, not dot-named and never read as an option.
MAIN_FILE = re.compile(r"[^./\\\-\s][^/\\]*\.tex")
#: What the person reads when the record cannot be used.
BAD_RECORD = "This quilt's record of its Overleaf project is not one loom can use; end the pairing and pair it again."


def plain_folder(folder: object) -> bool:
    """Whether `folder` is spelt as a folder of the person's can be: quilt-relative, normal, no part dot-named, empty or read as an option. Where it really lies is `checked_folder`'s."""
    if not isinstance(folder, str) or not folder or "\\" in folder or folder.startswith(("/", "-")):
        return False
    parts = PurePosixPath(folder).parts
    return PurePosixPath(*parts).as_posix() == folder and not any(p.startswith(".") or p in ("", "..") for p in parts)


def checked_folder(root: Path, history: Path, folder: str) -> str:
    """`folder`, refused unless the real folder it names is one the mirror may write: inside the quilt, under no dot-named folder (the door's place rule, `writes._place`), neither loom's own `.loom/` nor the history, and spelt as the folder spells itself.

    Asked at every use, so a record that came with the quilt names no place the mirror writes until it is judged here. Raises MirrorError `bad-record`.
    """
    from loom.writes import _place

    if not plain_folder(folder) or _place(root, folder) is None:
        raise MirrorError("bad-record", BAD_RECORD)
    # spelt as the folder spells itself: where case is ignored another spelling reaches it, and paths would no longer match the scan's
    parent = root
    for part in PurePosixPath(folder).parts:
        try:
            names = os.listdir(parent)
        except OSError:
            break
        if part not in names:
            if part.casefold() in {n.casefold() for n in names}:
                raise MirrorError("bad-record", BAD_RECORD)
            break
        parent = parent / part
    real = Path(os.path.realpath(root / folder))
    for own in (root / LOOM, history):
        mine = Path(os.path.realpath(own))
        if real == mine or real.is_relative_to(mine) or mine.is_relative_to(real):
            raise MirrorError("bad-record", BAD_RECORD)
    return folder


@dataclass
class SyncState:
    """The mirror's record: the project's id, the folder it is kept in, its main file's name there, the revision last taken in, and the one fetched and waiting. Every field is checked as it is read; loom builds the project's address from the id and never reads one from here."""

    project: str
    folder: str
    main: str
    integrated: str
    incoming: str = ""
    observed: str = ""
    last_pull: dict[str, Any] = field(default_factory=dict)
    # Projections of the shared origin store (`loom.review_origins`), where they are persisted.
    review_origins: dict[str, str] = field(default_factory=dict)
    review_changed: dict[str, bool] = field(default_factory=dict)
    review_baselines: dict[str, str] = field(default_factory=dict)
    review_local_changed: dict[str, bool] = field(default_factory=dict)
    review_by: dict[str, list[str]] = field(default_factory=dict)
    review_here: dict[str, bool] = field(default_factory=dict)

    @property
    def master(self) -> str:
        """The main document's quilt path."""
        return f"{self.folder}/{self.main}"

    @classmethod
    def read(cls, root: Path) -> SyncState:
        """The record, each field checked; MirrorError `not-paired` where there is none and `bad-record` where a field is not what loom wrote."""
        path = root / SOURCE_SYNC
        if not path.is_file():
            raise MirrorError("not-paired", "This quilt mirrors no Overleaf project.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = cls(**{k: v for k, v in data.items() if not k.startswith("review_")})
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise MirrorError("bad-record", BAD_RECORD) from exc
        if not (
            isinstance(state.project, str)
            and PROJECT_ID.fullmatch(state.project)
            and plain_folder(state.folder)
            and isinstance(state.main, str)
            and MAIN_FILE.fullmatch(state.main)
            and isinstance(state.integrated, str)
            and REVISION.fullmatch(state.integrated)
            and isinstance(state.incoming, str)
            and (state.incoming == "" or REVISION.fullmatch(state.incoming))
            and isinstance(state.observed, str)
            and isinstance(state.last_pull, dict)
        ):
            raise MirrorError("bad-record", BAD_RECORD)
        from loom.review_origins import read

        for key, row in read(root).items():
            if str(row.get("source", "")).startswith("pull:"):
                state.review_origins[key] = row["source"].removeprefix("pull:")
                state.review_changed[key] = bool(row.get("changed"))
                if row.get("baseline"):
                    state.review_baselines[key] = row["baseline"]
                state.review_local_changed[key] = bool(row.get("local_before"))
                state.review_by[key] = [str(n) for n in row.get("by") or []]
                state.review_here[key] = bool(row.get("here"))
        return state

    def write(self, root: Path) -> None:
        """Write the record and the review origins it projects; inside an update's act, staged with the files it took in (`writes.staging`)."""
        path = root / SOURCE_SYNC
        path.parent.mkdir(parents=True, exist_ok=True)
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
                "label": "Taken in from Overleaf",
                "by": self.review_by.get(key, []),
                "here": self.review_here.get(key, False),
            }
        if origins or self.last_pull:
            write(root, origins)
        data = {key: value for key, value in vars(self).items() if not key.startswith("review_")}
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if stage(path, text.encode("utf-8")):
            return
        temporary = path.with_suffix(".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def git(clone: Path, *args: str, input: bytes | None = None) -> bytes:
    """Git in loom's clone, as the mirror runs it (`overleaf.run`): hooks off, and nothing a repository's own configuration says choosing a program, a helper or an address."""
    from loom.overleaf import run

    return run(clone, *args, input=input)


def skipped_directory(root: Path) -> str | None:
    """The mirror's clone, quilt-relative, when the quilt mirrors a project: every tree walker skips it, though it lies in `.loom/`, which they skip already."""
    return OVERLEAF_CLONE if (root / SOURCE_SYNC).is_file() else None


def copy_ignore(root: Path, *patterns: str) -> Callable[[str, list[str]], set[str]]:
    """A `shutil.copytree` ignore for a copy of the quilt at `root`: a pattern with a `/` is a quilt-relative path (`CACHE`), the others names as `shutil.ignore_patterns` takes them; the mirror's clone is left out by path."""
    by_name = shutil.ignore_patterns(*(p for p in patterns if "/" not in p))
    synced = skipped_directory(root)
    pruned = {root / p for p in patterns if "/" in p} | ({root / synced} if synced else set())

    def ignore(folder: str, names: list[str]) -> set[str]:
        return set(by_name(folder, names)) | {n for n in names if Path(folder) / n in pruned}

    return ignore


def workspace(root: Path, project: str) -> Path:
    """Loom's clone of `project`, used only where this machine made it (`overleaf._marked`); MirrorError `no-clone` anywhere else, and an update makes it again."""
    from loom.overleaf import _marked

    clone = root / OVERLEAF_CLONE
    if not _marked(clone, project):
        raise MirrorError(
            "no-clone", "Loom's copy of the project is not one this machine made; update again to make it."
        )
    return clone


def revision(clone: Path, ref: str) -> str:
    """The commit `ref`, a full ref name of loom's or a revision, names in the clone."""
    return git(clone, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def changed_files(clone: Path, before: str, after: str) -> list[dict[str, str]]:
    """`{status, path}` for each file of the project that differs between two revisions."""
    if before == after:
        return []
    raw = git(clone, "diff", "--name-status", "--no-renames", "--no-ext-diff", "-z", before, after, "--")
    parts = raw.decode("utf-8", errors="replace").split("\0")
    return [{"status": parts[i], "path": parts[i + 1]} for i in range(0, len(parts) - 1, 2)]


def exact_renames(clone: Path, before: str, after: str) -> list[tuple[str, str]]:
    """(deleted, added) path pairs between two revisions whose blobs are identical: a rename git would call exact. A blob deleted or added more than once pairs nothing, since which went where cannot be told."""
    if before == after:
        return []
    raw = git(clone, "diff", "--raw", "--no-renames", "--no-abbrev", "-z", before, after, "--")
    parts = raw.decode("utf-8", errors="replace").split("\0")
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


def blobs(clone: Path, rev: str) -> dict[str, tuple[str, bytes]]:
    """Every file of `rev`, by its path in the project: its blob's id and its bytes, read in one pass (`git cat-file --batch`). A path no folder of the person's could hold is left out."""
    listed = git(clone, "ls-tree", "-r", "-z", "--end-of-options", rev).split(b"\0")
    entries: list[tuple[str, str]] = []
    for line in listed:
        if not line:
            continue
        meta, _, path = line.partition(b"\t")
        kind, oid = meta.split()[1:3]
        name = path.decode("utf-8", errors="replace")
        if kind == b"blob" and not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts:
            entries.append((name, oid.decode()))
    out = git(clone, "cat-file", "--batch", input=b"".join(oid.encode() + b"\n" for _, oid in entries))
    files: dict[str, tuple[str, bytes]] = {}
    at = 0
    for name, blob in entries:
        head_end = out.index(b"\n", at)
        size = int(out[at:head_end].split()[2])
        files[name] = (blob, out[head_end + 1 : head_end + 1 + size])
        at = head_end + 1 + size + 1
    return files


def tree_files(clone: Path, rev: str) -> dict[str, bytes]:
    """Every file of `rev`, by its path in the project, with its bytes."""
    return {name: data for name, (_, data) in blobs(clone, rev).items()}


def blob_id(data: bytes) -> str:
    """The id git gives `data` as a blob."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def theirs(
    clone: Path, state: SyncState, folder: str, read: Callable[[str], bytes | None]
) -> tuple[dict[str, bytes | None], list[str]]:
    """What taking the fetched revision in writes: each file Overleaf holds, as Overleaf holds it, where the folder holds anything else, and None for each file it no longer holds that the folder still does; a file only here is left. With it, the files here that held anything but what the last update left, which are written over.

    `folder` is the record's, judged (`checked_folder`); `read` is how a file's bytes are read now (None for one that is not there): through the act, so what is written over is what the act replaces.
    """
    now = blobs(clone, state.incoming)
    before = {name: blob for name, (blob, _) in blobs(clone, state.integrated).items()}
    after: dict[str, bytes | None] = {}
    over: list[str] = []
    for remote in sorted(set(now) | set(before)):
        local = under(folder, remote)
        here = read(local)
        want = now[remote][1] if remote in now else None
        if here == want:
            continue
        after[local] = want
        if here is not None and blob_id(here) != before.get(remote):
            over.append(local)
    return after, over


# ---- whose changes an update brought ---------------------------------------------------------------------------------


@dataclass
class Changes:
    """What an update brought, for Review: each block it changed with whose commits touched it (`by`, the person left out), each block whose change was one made here and written over (`here`), each place outside a block with whose commits touched it, and how many of either were left out as touched only by the person's own commits."""

    blocks: dict[str, list[str]] = field(default_factory=dict)
    here: list[str] = field(default_factory=list)
    places: list[dict[str, Any]] = field(default_factory=list)
    own: int = 0


#: What kind of place outside a block a change fell in, as the record names it and the viewer words it.
PLACES = ("preamble", "between", "removed", "not-a-document")

_HUNK = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def _commits(clone: Path, state: SyncState, *spec: str) -> list[tuple[str, str]]:
    """(name, address) of each commit of the update that `spec` selects: `-L<range>:<path>` for those that touched a range of a file, or `--`, `<path>` for those that touched the file at all."""
    span = f"{state.integrated}..{state.incoming}"
    where = [span, *spec] if spec[0] == "--" else [*spec, span]
    said = git(clone, "log", "-s", "--no-ext-diff", "--format=%x01%aN%x00%aE", *where)
    out = []
    for record in said.decode("utf-8", errors="replace").split("\x01")[1:]:
        name, _, email = record.strip().partition("\0")
        out.append((name, email))
    return out


_RANGE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)
_OLD_PATH = re.compile(r"^--- (?:a/(.+)|/dev/null)$", re.M)


def _touched(clone: Path, state: SyncState, remote: str, first: int, last: int) -> list[tuple[str, str]]:
    """(name, address) of each commit of the update that touched lines `first` to `last` of `remote`, read back past the commit that wrote them.

    `git log -L` follows lines back to the commit that made them and no further. Where that commit made the lines where there were none, every earlier commit of the update that touched that place, the lines either side of where they went in, touched it too: so a block a co-author removed and the person then wrote again, or the other way round, counts both. Followed back at most eight times.
    """
    out: list[tuple[str, str]] = []
    path, lo, hi, until = remote, first, last, state.incoming
    for _ in range(8):
        said = git(
            clone,
            "log",
            "--no-ext-diff",
            "--no-color",
            "--format=%x01%H%x00%aN%x00%aE",
            f"-L{lo},{hi}:{path}",
            f"{state.integrated}..{until}",
        ).decode("utf-8", errors="replace")
        records = said.split("\x01")[1:]
        if not records:
            break
        for record in records:
            fields = record.partition("\n")[0].split("\0")
            out.append((fields[1] if len(fields) > 1 else "", fields[2] if len(fields) > 2 else ""))
        oldest = records[-1]
        made = _RANGE.search(oldest)
        before = _OLD_PATH.search(oldest)
        if made is None or made.group(2) != "0" or before is None or before.group(1) is None:
            break
        sha = oldest.split("\0", 1)[0].strip()
        if not REVISION.fullmatch(sha):
            break
        parent = revision(clone, f"{sha}^")
        if parent == state.integrated:
            break
        size = len(git(clone, "show", f"{parent}:{before.group(1)}").splitlines())
        if size == 0:
            break
        at = int(made.group(1))
        path, lo, hi, until = before.group(1), max(1, min(at - 1, size)), max(1, min(at, size)), parent
    return out


def _hunks(clone: Path, state: SyncState, remote: str) -> list[tuple[int, int, int, int]]:
    """(old start, old length, new start, new length) of each change to `remote` over the whole update, in lines."""
    said = git(
        clone,
        "diff",
        "-U0",
        "--no-color",
        "--no-ext-diff",
        "--no-renames",
        state.integrated,
        state.incoming,
        "--",
        remote,
    )
    return [
        (int(a), int(b) if b is not None else 1, int(c), int(d) if d is not None else 1)
        for a, b, c, d in ((m.group(1), m.group(2), m.group(3), m.group(4)) for m in _HUNK.finditer(said))
    ]


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _changes(
    clone: Path,
    state: SyncState,
    folder: str,
    scans: tuple[ScanResult, ScanResult, ScanResult],
    texts: dict[str, str | None],
    me: list[str],
) -> Changes:
    """Whose changes the update brought, read by commit over everything each commit changed, never by which lines survive.

    `scans` are the quilt before the act (its files here), as the last update left the files Overleaf changed (`base`), and after the act; `texts` the text after the act of each file the update brought or wrote. A block whose words are not the last update's is changed by the commits that touched its lines over the update (`git log -L` over the whole block, which sees a line a commit removed though another later rewrote its neighbour); one whose words are the last update's but not those here held a change made here, written over. A change that falls in no changed block is a place: the preamble, text between results, a result removed, or a file that is no document, with the commits that touched it. A block or a place is left out only where every commit that touched it is one the person alone is named for (`me`).
    """
    from loom.scan.owntext import own_text
    from loom.scan.source import decode

    before, base, after = scans
    mine = {m.lower() for m in me}
    out = Changes()

    def keep(where: str | dict[str, Any], who: list[tuple[str, str]]) -> None:
        others = sorted({name for name, email in who if email.lower() not in mine})
        if who and not others:
            out.own += 1
        elif isinstance(where, str):
            out.blocks[where] = others
        else:
            out.places.append({**where, "by": others})

    def blocks(scan: ScanResult, local: str) -> list[Any]:
        return [n for n in scan.nodes.values() if n.file == local and n.kind not in ("master", "file", "conflict")]

    in_git = {row["path"]: row["status"] for row in changed_files(clone, state.integrated, state.incoming)}
    for local in sorted({under(folder, r) for r in in_git} | set(texts)):
        remote = local[len(folder) + 1 :]
        text = texts.get(local)
        if remote not in in_git:
            # nothing Overleaf changed: a block whose words differ here held a change made here, written over
            had = Counter(own_text(before, n) for n in blocks(before, local))
            out.here += [n.key for n in blocks(after, local) if text is not None and own_text(after, n) not in had]
            continue
        if not remote.endswith(".tex"):
            keep({"file": local, "place": "not-a-document"}, _commits(clone, state, "--", remote))
            continue
        if text is None:
            keep({"file": local, "place": "removed"}, _commits(clone, state, "--", remote))
            continue
        last = Counter(own_text(base, n) for n in blocks(base, local))
        had = Counter(own_text(before, n) for n in blocks(before, local))
        hunks = _hunks(clone, state, remote)
        taken = [False] * len(hunks)
        lines = text.count("\n") + (0 if text.endswith("\n") else 1)
        changed = []
        for node in blocks(after, local):
            words = own_text(after, node)
            first, final = _line(text, node.start), _line(text, max(node.start, node.end - 1))
            if words not in last:
                changed.append((node.key, first, final))
            elif words not in had:
                out.here.append(node.key)
        # the innermost changed block a change falls in is the one it belongs to: a section around a changed result is not changed by it
        for key, first, final in changed:
            inner = [
                (f, e) for k, f, e in changed if k != key and first <= f and e <= final and (f, e) != (first, final)
            ]
            for i, (_, _, start, length) in enumerate(hunks):
                lo, hi = (start, start + length - 1) if length else (start, start + 1)
                inside = (lo <= final and hi >= first) if length else (first <= lo and hi <= final)
                if inside and not any(f <= lo and hi <= e for f, e in inner):
                    taken[i] = True
            keep(
                key,
                _touched(clone, state, remote, first, min(final, max(lines, 1)))
                or _commits(clone, state, "--", remote),
            )
        old: list[str] | None = None
        start_of_document = text.find("\\begin{document}")
        for i, (a, b, start, length) in enumerate(hunks):
            if taken[i]:
                continue
            if old is None:
                held = git(clone, "show", f"{state.integrated}:{remote}") if in_git[remote] != "A" else b""
                old = decode(held)[0].splitlines()
            removed = "\n".join(old[a - 1 : a - 1 + b]) if b else ""
            if re.search(r"\\begin\{(?!document\})", removed):
                place = "removed"
            elif start_of_document >= 0 and start < _line(text, start_of_document):
                place = "preamble"
            else:
                place = "between"
            lo, hi = max(1, start - 1), min(max(lines, 1), start + max(length, 1))
            keep({"file": local, "place": place}, _touched(clone, state, remote, lo, hi))
    # one row a place, whoever touched it
    merged: dict[tuple[str, str], set[str]] = {}
    for p in out.places:
        merged.setdefault((p["file"], p["place"]), set()).update(p["by"])
    out.places = [{"file": f, "place": k, "by": sorted(by)} for (f, k), by in sorted(merged.items())]
    return out


# ---- the act ---------------------------------------------------------------------------------------------------------


def _reaching(root: Path, documents: list[str], paths: set[str]) -> list[str]:
    """The documents among `documents` whose source closure includes one of `paths`: the ones an update stamps."""
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
    """Stamp each document as a landmark named `<stem> <name>`; one that reaches two definitions of a key has no one text to stamp and is passed over, so what a co-author wrote never stops an update (the scan reports the two as a problem in the document)."""
    from loom.history.ledger import load_history
    from loom.history.steps import conflicted_in, free_name, slug, stamp_document

    landmarks = []
    for document in documents:
        if conflicted_in(result, document):
            continue
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
        The addresses the person goes by on Overleaf: a change only their commits touched is not listed for Review.
    actor : str, optional
        Who the act and its stamps are recorded as; default the quilt's author.

    Returns
    -------
    dict
        `integrated`, the revision now taken in; `paths`, the files written; `landmarks`, one per stamped document; `by`, the names of the others whose changes Review lists; `own`, how many changed blocks and places it leaves out as the person's alone; `places`, each change outside a block (`{file, place, by}`); `here`, the blocks whose change was one made here, written over; `overwritten`, the files that held a change made here.

    Raises
    ------
    MirrorError
        `taken-in` when another update took the revision in first; `bad-record` when the record's folder is not one the mirror may write.
    """
    from loom import writes
    from loom.history.ledger import actor_for

    root = quilt.root
    if not state.incoming or state.incoming == state.integrated:
        # refused before the door is opened, so a refusal leaves nothing behind, not even the lock's file
        raise MirrorError("taken-in", "Overleaf holds nothing new; it was taken in already.")
    who = actor if actor is not None else actor_for(root)
    with writes.act(root, quilt.history_dir, "pull", who) as w, writes.staging(w):
        # the record read again under the lock: an update another process took in since leaves nothing to take
        now = SyncState.read(root)
        if now.incoming != state.incoming or now.incoming == now.integrated:
            raise MirrorError("taken-in", "Overleaf holds nothing new; it was taken in already.")
        said = _incorporate(quilt, now, w, who, me)
        state.__dict__.update(now.__dict__)
        return said


def _incorporate(quilt: Quilt, state: SyncState, w: Any, who: str | None, me: list[str]) -> dict[str, Any]:
    """`incorporate` under the door's lock, staged into the act `w`, which stages loom's records (`writes.staging`): Overleaf's bytes against the files as read through the act, so what is written over is what the act replaces."""
    from loom.review_queue import fingerprint
    from loom.scan.scan import scan
    from loom.scan.source import decode

    root = quilt.root
    folder = checked_folder(root, quilt.history_dir, state.folder)
    clone = workspace(root, state.project)
    after, overwritten = theirs(clone, state, folder, w.read)
    result = scan(quilt)
    moves = [
        {"from": under(folder, gone), "to": under(folder, came), "remote": came}
        for gone, came in exact_renames(clone, state.integrated, state.incoming)
        if under(folder, gone) in result.masters and came.endswith(".tex")
    ]
    documents = _reaching(root, [state.master], set(after))
    landmarks = _stamp(quilt, result, documents, "before update from Overleaf", "Before an update from Overleaf", who)
    for path, data in after.items():
        w.replace(path, data)
    # the quilt as the act will leave it, and as the last update left the files Overleaf changed, scanned before anything is written so the records go with the files
    in_git = changed_files(clone, state.integrated, state.incoming)
    texts: dict[str, str | None] = {p: None if d is None else decode(d)[0] for p, d in after.items()}
    for row in in_git:
        local = under(folder, row["path"])
        if local not in texts:
            held = w.read(local)
            texts[local] = None if held is None else decode(held)[0]
    incorporated = scan(quilt, overlay={p: t for p, t in texts.items() if p in after})
    last = {p: decode(d)[0] for p, d in tree_files(clone, state.integrated).items() if p.endswith(".tex")}
    base = scan(quilt, overlay={under(folder, r["path"]): last.get(r["path"]) for r in in_git})
    _record_moves(quilt, state, moves, incorporated)
    changes = _changes(clone, state, folder, (result, base, incorporated), texts, me)
    by = sorted({n for names in changes.blocks.values() for n in names} | {n for p in changes.places for n in p["by"]})
    state.last_pull = {
        "commit": state.incoming,
        "observed": state.observed,
        "when": stamp(),
        "files": len(after),
        "by": by,
        "own": changes.own,
        "places": changes.places,
        "here": changes.here,
        "overwritten": overwritten,
    }
    for key in [*changes.blocks, *changes.here]:
        state.review_origins[key] = state.incoming
        state.review_changed[key] = True
        state.review_baselines[key] = fingerprint(incorporated, key)
        state.review_local_changed[key] = key in changes.here
        state.review_by[key] = changes.blocks.get(key, [])
        state.review_here[key] = key in changes.here
    state.integrated = state.incoming
    state.write(root)
    return {
        "integrated": state.integrated,
        "paths": sorted(after),
        "landmarks": landmarks,
        "by": by,
        "own": changes.own,
        "places": changes.places,
        "here": changes.here,
        "overwritten": overwritten,
    }


def _record_moves(quilt: Quilt, state: SyncState, moves: list[dict[str, Any]], incorporated: ScanResult) -> None:
    """Append a `move` line (`via: "sync"`) for each exact rename the update carries whose new path is now a live document; Overleaf's main renamed at the project's top takes the record's main with it, and moving the default document moves `[quilt] main`, as `loom mv` does."""
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
        if move["from"] == state.master and MAIN_FILE.fullmatch(move["remote"]):
            state.main = move["remote"]
        if move["from"] == quilt.config.main:
            set_main_forced(quilt, move["to"])
