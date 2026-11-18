"""Every path loom uses inside a quilt, relative to the quilt root, named once.

Quilt-relative POSIX strings, so each works both as `root / X` and in a string comparison. Everything loom keeps lies under `.loom/`, in the folder of its kind (`KINDS`): what stays on one machine is said by the folder it is in, and `.loom/.gitignore` names the folders and nothing else. A path set in `config.toml` (`[quilt] history`, `research_state`) is read from the config; `HISTORY` here is only that setting's default. `loom/tests/unit/test_paths.py` refuses a quilt path spelled out anywhere else, and one under `.loom/` outside a kind's folder.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import PurePosixPath

#: Loom's own directory: everything loom writes in a quilt lives under it, in the folder of its kind.
LOOM = ".loom"
#: The layout's number (`loom.layout`), which a loom reads before anything else in `.loom/`.
FORMAT = f"{LOOM}/format"
#: Loom's ignore file: the folders of `.loom/` that stay on one machine.
LOOM_GITIGNORE = f"{LOOM}/.gitignore"

#: What the person and loom decided or said; travels with the quilt, and loom deletes none of it.
RECORDS = f"{LOOM}/records"
#: Other people's documents and what was drawn from them: the digests, and the store.
LIBRARY = f"{LOOM}/library"
#: The agents' places: what they are told, their sessions and copies, and their scratch.
AGENTS = f"{LOOM}/agents"
#: This machine's state: loom writes it, and it does not travel with the quilt.
LOCAL = f"{LOOM}/local"
#: Everything loom can make again; deletable at any moment, and it does not travel with the quilt.
CACHE = f"{LOOM}/cache"
#: The five kinds, a folder each.
KINDS = (RECORDS, LIBRARY, AGENTS, LOCAL, CACHE)

# ---- records ----------------------------------------------------------------------------------------------------------

#: The acceptance ledger (`records/ledger.py`).
LEDGER = f"{RECORDS}/state.toml"
#: The annotation log's directory.
ANNOTATIONS = f"{RECORDS}/annotations"
ANNOTATION_LOG = f"{ANNOTATIONS}/log.jsonl"
#: Suggested edits, and what the person did with each: their own log (`records/edits.py`).
EDITS = f"{RECORDS}/edits"
EDIT_LOG = f"{EDITS}/log.jsonl"
#: The quilt's annotation types: presets a person picks from and an agent reads, written by `loom init` with the defaults; the one record an agent may edit.
ANNOTATION_TYPES = f"{RECORDS}/annotation-types.toml"
REVIEW_DECISIONS = f"{RECORDS}/review-decisions.json"
REVIEW_ORIGINS = f"{RECORDS}/review-origins.json"
REVIEW_OBSERVATIONS = f"{RECORDS}/review-observations.json"
ADOPTION_DECISIONS = f"{RECORDS}/adoption-decisions.json"
SOURCE_SYNC = f"{RECORDS}/source-sync.json"
#: Where `atomize --retire` sets a converted source aside.
RETIRED = f"{RECORDS}/retired"
#: Each person's last look at the open files, which Review's Your Changes reads.
LOOKED = f"{RECORDS}/looked"
#: The default of `[quilt] history`; code reads the setting, never this.
HISTORY = f"{RECORDS}/history"
#: Reserved for work not built yet (docs/specs/reserved.md): nothing writes these, and an agent is already kept from them.
#: Formal evidence, and the person's attestations.
FORMAL = f"{RECORDS}/formal"
FORMAL_EVIDENCE = f"{FORMAL}/evidence.jsonl"
FORMAL_ATTESTED = f"{FORMAL}/attest.toml"

# ---- the library ------------------------------------------------------------------------------------------------------

#: The quilt's bibliography, gathered from the landmarks.
BIBLIOGRAPHY = f"{LIBRARY}/bibliography.bib"
UNREADABLE = f"{LIBRARY}/unreadable.json"
LINKS = f"{LIBRARY}/links.jsonl"
LINKS_REMOVED = f"{LIBRARY}/links-removed.jsonl"
#: Reserved (docs/specs/reserved.md): the works an agent suggested.
SUGGESTED_WORKS = f"{LIBRARY}/suggested.jsonl"
#: Loom's store of other people's documents, keyed by the work's identifier.
STORAGE = f"{LIBRARY}/storage"
#: The address the viewer reaches the store at, under its root, fixed wherever `STORAGE` sits: the server answers it and the manifest's `artifacts.dir` is written in it.
STORE_ADDRESS = "digests/storage"

# ---- the agents' places -----------------------------------------------------------------------------------------------

#: What an agent is given: orientation, rules, formatting, modes, and loom's records of the skills, rules and apps it set up.
AI = f"{AGENTS}/instructions"
SESSIONS = f"{AGENTS}/sessions"
#: The session index, a record inside an agent's place that only loom writes.
SESSION_INDEX = f"{SESSIONS}/index.jsonl"
#: Agent copies of documents, made by `loom draft DOC --ai NAME` and read by the scan on purpose.
COPIES = f"{AGENTS}/copies"
#: Each session's scratch on this machine: an agent's intermediates and the results loom hands it in a file; nothing in it is kept for the person.
SCRATCH = f"{AGENTS}/scratch"

# ---- this machine's state ---------------------------------------------------------------------------------------------

#: The running server's address and pid; the token a write carries is kept outside the quilt (`loom.machine`).
SERVE_JSON = f"{LOCAL}/serve.json"
#: How the server's compiles stand, for `loom status`.
COMPILES = f"{LOCAL}/compiles.json"
#: Where each agent last looked, which `loom since` reads.
SINCE = f"{LOCAL}/since"
#: Annotations a person deleted, one line each for the agent that wrote it, until that agent's `loom since` has reported it.
DELETED = f"{SINCE}/deleted.jsonl"
#: A record for each agent server process attached to the quilt.
LIVE = f"{LOCAL}/live"
#: What a person adds to the library, one directory a drop, while it waits and while its intake can be undone (`refs/intake.py`).
INCOMING = f"{LOCAL}/incoming"
#: Loom's cache of the last text it saw for every key, which freezes an annotation's words when the text under it changes.
LAST_SEEN = f"{LOCAL}/last-seen.json"
#: The journal of loom's writes to the person's files (docs/design/writes.md), its index, and the lock every write holds.
JOURNAL = f"{LOCAL}/writes.jsonl"
JOURNAL_INDEX = f"{LOCAL}/writes-index.json"
WRITES_LOCK = f"{LOCAL}/writes.lock"
#: What a command locks while it draws a node id (`loom.locks`), since those are read from the whole quilt and no one file holds them.
ID_LOCK = f"{LOCAL}/ids.lock"
#: The lock every writer of the library's bibliography and store holds, across processes.
LIBRARY_LOCK = f"{LOCAL}/library.lock"
#: The annotation log as it stood before the last delete.
BEFORE_DELETE = f"{LOCAL}/annotations-before-delete.jsonl"

# ---- derived ----------------------------------------------------------------------------------------------------------

#: What the viewer is served, at `/build/`: the manifest, the fragments and everything they name.
SITE = f"{CACHE}/site"
MANIFEST = f"{SITE}/manifest.json"
#: One compile folder for each document (`document_build`).
TEX = f"{CACHE}/tex"
#: The address the viewer reaches `TEX` at, under the site's: a manifest's `pdf` is written in it.
TEX_ADDRESS = "tex"
#: Rendered blocks, by key: the fragment index, the snippets, the previews and the spans.
BLOCKS = f"{CACHE}/blocks"
#: What the library draws from its stored documents: word boxes, and the answers of identifier lookups.
LIBRARY_CACHE = f"{CACHE}/library"
#: What marks on a PDF are found by: word boxes of a PDF outside the store, and where each mark was found again.
MARKS = f"{CACHE}/marks"
#: Page crops around a mark, made when first asked for.
CROPS = f"{CACHE}/crops"
#: A key's closure document and its compile.
CLOSURES = f"{CACHE}/closures"
#: An adoption's and an incorporation's saved preview, by token, until it is applied.
ADOPTION_PREVIEWS = f"{CACHE}/adoption"
INCORPORATION_PREVIEWS = f"{CACHE}/incorporation-review"

#: Where `loom new`, atomize and fork write node files, relative to the document they serve.
NODES = "nodes"


def scratch(session: str) -> str:
    """One session's scratch, `.loom/agents/scratch/<session>`."""
    return f"{SCRATCH}/{session}"


def document_name(path: str) -> str:
    """A document's name: its quilt-relative path without `.tex`, kept as a path (`paper/main.tex` is `paper/main`).

    The key of its fragment and its address in the viewer; two documents' names never collide, as their stems may.
    """
    return path.removesuffix(".tex")


def documents_named(word: str, pool: Iterable[str]) -> list[str]:
    """The documents among `pool` that `word` names: the one whose path or name it is, else every one whose file name or stem it is.

    Callers take a single match and refuse several, naming them: stems repeat across directories, so a stem is a name only while one document has it.
    """
    docs = list(pool)
    exact = [d for d in docs if word in (d, document_name(d))]
    return exact or [d for d in docs if word in (PurePosixPath(d).name, PurePosixPath(d).stem)]


def document_dir(path: str) -> str:
    """The quilt-relative directory a file sits in, '' at the root: the base a document's names resolve against."""
    parent = PurePosixPath(path).parent.as_posix()
    return "" if parent == "." else parent


def under(base: str, name: str) -> str:
    """`name` read against the quilt-relative directory `base`, as a quilt-relative path; `name` itself at the root."""
    return (PurePosixPath(base) / name).as_posix() if base else PurePosixPath(name).as_posix()


def _compile_folder(path: str) -> str:
    """A document's compile folder's name, `<stem>-<hash>`: its file name without `.tex`, then eight hex digits of its name's SHA-256, so two documents of one file name never share one."""
    name = document_name(path)
    return f"{PurePosixPath(name).name}-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]}"


def document_build(path: str) -> str:
    """Where a document compiles to, `.loom/cache/tex/<stem>-<hash>`; latexmk names what it writes there by the file's own stem."""
    return f"{TEX}/{_compile_folder(path)}"


def document_pdf_address(path: str) -> str:
    """A document's compiled PDF as the viewer addresses it under the site's root, `tex/<stem>-<hash>/<stem>.pdf`: the manifest's `pdf`."""
    return f"{TEX_ADDRESS}/{_compile_folder(path)}/{PurePosixPath(path).stem}.pdf"
