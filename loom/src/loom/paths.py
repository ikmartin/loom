"""Every path loom uses inside a quilt, relative to the quilt root, named once.

Quilt-relative POSIX strings, so each works both as `root / X` and in a string comparison. Everything loom keeps lies under `.loom/`, in the folder of its kind (`KINDS`): what stays on one machine is said by the folder it is in, and `.loom/.gitignore` names the folders and nothing else. A path set in `config.toml` (`[quilt] history`, `research_state`) is read from the config; `HISTORY` here is only that setting's default.

`loom/tests/unit/test_paths.py` pins the kind of every constant here, refuses one under `.loom/` outside a kind's folder, and refuses, in any other module, a quilt path spelled as a string, a string joined to `LOOM` or to a kind's folder, and an f-string that builds a path from them.
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
#: The library: its nodes, the documents its works hold, and what is reserved beside them.
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
#: The tags put on the library's nodes and taken off them, one line an act (`library.tags`).
TAGS = f"{RECORDS}/tags"
TAG_LOG = f"{TAGS}/log.jsonl"
#: Every act on a work, one line each, with who and when: how a reference was made, looked up, edited, given or relieved of a document, deleted and restored (`library.log`).
LIBRARY_RECORDS = f"{RECORDS}/library"
LIBRARY_LOG = f"{LIBRARY_RECORDS}/log.jsonl"
#: The default of `[quilt] history`; code reads the setting, never this.
HISTORY = f"{RECORDS}/history"
#: What is known of a result: who digested it, compared it with its paper, what Lean said and who attested it (`evidence/log.py`, `docs/specs/evidence.md`).
EVIDENCE = f"{RECORDS}/evidence"
EVIDENCE_LOG = f"{EVIDENCE}/log.jsonl"
#: What a person asked of an agent and an agent of a person: tasks, questions and papers to fetch (`evidence/asks.py`).
ASKS = f"{RECORDS}/asks"
ASK_LOG = f"{ASKS}/log.jsonl"

# ---- the library ------------------------------------------------------------------------------------------------------

#: Reserved (docs/specs/reserved.md): the works an agent suggested.
SUGGESTED_WORKS = f"{LIBRARY}/suggested.jsonl"
#: The library's nodes, one `<id>.node` file each (docs/specs/nodes.md).
LIBRARY_NODES = f"{LIBRARY}/nodes"
#: The works' documents by hash, `<hex>.pdf` and a TeX source as `<hex>.tar` (`library.documents`).
LIBRARY_DOCUMENTS = f"{LIBRARY}/documents"

# ---- the agents' places -----------------------------------------------------------------------------------------------

#: What an agent is given: orientation, rules, formatting, modes, and loom's records of the skills, rules and apps it set up.
AI = f"{AGENTS}/instructions"
SESSIONS = f"{AGENTS}/sessions"
#: The session index, a record inside an agent's place that only loom writes.
SESSION_INDEX = f"{SESSIONS}/index.jsonl"
#: The id of the session commands write in when none is named.
ACTIVE_SESSION = f"{SESSIONS}/active"
#: Agent copies of documents, made by `loom draft DOC --ai NAME` and read by the scan on purpose.
COPIES = f"{AGENTS}/copies"
#: Each session's scratch on this machine: an agent's intermediates and the results loom hands it in a file; nothing in it is kept for the person.
SCRATCH = f"{AGENTS}/scratch"

# ---- this machine's state ---------------------------------------------------------------------------------------------

#: The running server's address and pid; the token a write carries is kept outside the quilt (`loom.machine`).
SERVE_JSON = f"{LOCAL}/serve.json"
#: A batch of nodes being written, while its files are renamed into place: what it replaces and what it makes, which the next writer rolls back when its writer died midway (`library.store`).
LIBRARY_ACT = f"{LOCAL}/library-act"
#: How the server's compiles stand, for `loom status`.
COMPILES = f"{LOCAL}/compiles.json"
#: Where each agent last looked, which `loom since` reads.
SINCE = f"{LOCAL}/since"
#: Annotations a person deleted, one line each for the agent that wrote it, until that agent's `loom since` has reported it.
DELETED = f"{SINCE}/deleted.jsonl"
#: The files the viewer shows as the last look by any agent found them, and what was added, changed or removed at each look since, one record for the quilt, which `loom since` reads.
SHOWN_SEEN = f"{SINCE}/files/shown.json"
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
#: The Overleaf mirror's clone of its project, loom's own and without a checkout (`loom.overleaf`).
OVERLEAF_CLONE = f"{LOCAL}/overleaf"
#: Who the person is on Overleaf, and what the last reach of Overleaf could not do (`loom.overleaf`).
OVERLEAF_HERE = f"{LOCAL}/overleaf.json"
#: The lock every writer of the library's bibliography and store holds, across processes.
LIBRARY_LOCK = f"{LOCAL}/library.lock"
#: The annotation log as it stood before the last delete.
BEFORE_DELETE = f"{LOCAL}/annotations-before-delete.jsonl"
#: An adoption's and an incorporation's saved preview, by token, from the preview until it is applied: a step in progress on this machine, which no build makes again.
ADOPTION_PREVIEWS = f"{LOCAL}/adoption"
INCORPORATION_PREVIEWS = f"{LOCAL}/incorporation-review"

# ---- derived ----------------------------------------------------------------------------------------------------------

#: What the viewer is served, at `/build/`: the manifest, the fragments and everything they name.
SITE = f"{CACHE}/site"
MANIFEST = f"{SITE}/manifest.json"
#: The figures and pictures fragments name, by their content.
SITE_SVG = f"{SITE}/svg"
#: A section draft compiled in its paper, which the viewer opens; made when asked for, and named by what it was made from.
DRAFT_PREVIEWS = f"{SITE}/draft-previews"
#: One compile folder for each document (`document_build`).
TEX = f"{CACHE}/tex"
#: The address the viewer reaches `TEX` at, under the site's: a manifest's `pdf` is written in it.
TEX_ADDRESS = "tex"
#: What the build as it stands names under `CACHE`: each fragment's input hash and the cache files it was made from, what the build read or wrote beside its fragments, and every file of the site it published (`loom.lifetimes`).
BUILD_INDEX = f"{CACHE}/index.json"
#: Rendered blocks, by key: the snippets and the previews; a render plan may be given another folder (`render.fragments.RenderPlan.cache`), which holds the same names.
BLOCKS = f"{CACHE}/blocks"
SNIPPETS = f"{BLOCKS}/snippets"
BLOCK_PREVIEWS = f"{BLOCKS}/previews"
#: What the library draws from its stored documents and its nodes.
LIBRARY_CACHE = f"{CACHE}/library"
#: A stored PDF's page text, section map and word boxes, `<hex>/`, made when first read (`refs.pages.mapped`).
LIBRARY_PAGES = f"{LIBRARY_CACHE}/pages"
#: What the library's nodes and the tag log are asked by: made when first asked for, brought up to date at each asking, and made again at will (`library.index`).
NODE_INDEX = f"{LIBRARY_CACHE}/nodes.sqlite3"
#: What a stored TeX source holds, read once for each source and kept by its hash (`library.survey`).
LIBRARY_SURVEYS = f"{LIBRARY_CACHE}/survey"
#: Held while a source's survey compiles, so a quilt compiles one source at a time.
SURVEY_LOCK = f"{LOCAL}/library-survey.lock"
#: Where a source's survey compiles, emptied by the next compile (`library.survey.complete`).
SURVEY_RUN = f"{LIBRARY_SURVEYS}/run"
#: A stored source unpacked, `<hex>/`, made when something reads it.
LIBRARY_SOURCES = f"{LIBRARY_CACHE}/sources"
#: A stored PDF's first page, `<hex>.png`, made when first asked for (`library.thumbs`).
LIBRARY_THUMBS = f"{LIBRARY_CACHE}/thumbs"
#: What a delete took, kept on this machine for its one undo (`library.acts.delete`).
LIBRARY_UNDO = f"{LOCAL}/library-undo"
#: The undo of a delete under way, named from before anything is removed until its last node is (`library.acts.finish`).
LIBRARY_DELETING = f"{LIBRARY_UNDO}/deleting"
#: What marks on a PDF are found by: word boxes of a PDF the library does not store, by its hash, and where each mark was found again.
MARKS = f"{CACHE}/marks"
MARK_BOXES = f"{MARKS}/boxes"
REFOUND = f"{MARKS}/refound"
#: Page crops around a mark, made when first asked for.
CROPS = f"{CACHE}/crops"
#: A key's closure document and its compile.
CLOSURES = f"{CACHE}/closures"

#: Where `loom new`, atomize and fork write node files, relative to the document they serve.
NODES = "nodes"

#: Lake's folder in a Lake project, relative to the project: the quilt's Lean project, or a package it depends on, which is a Lake project of its own.
LAKE = ".lake"
#: Lake's build of a project's own modules, the same place in the quilt's project and in each package.
LAKE_BUILD = f"{LAKE}/build"
#: The packages a project depends on, `<name>/` each, as Lake fetched them.
LAKE_PACKAGES = f"{LAKE}/packages"
#: Loom's own folder in the quilt's Lean project, the HOME and TMPDIR of a check's runs, emptied by each check (`formal.check`).
LAKE_LOOM = f"{LAKE}/loom"
#: Held while loom checks the quilt's Lean, so two checks never share the project.
LAKE_LOCK = f"{LAKE}/loom.lock"


def within(folder: str, path: str) -> str:
    """`path` relative to `folder`, one of the constants here inside another: what a caller joins to a folder it was handed in `folder`'s place (a render plan's cache)."""
    return PurePosixPath(path).relative_to(folder).as_posix()


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


def document_page(path: str) -> str:
    """The folder of a document's page as TeX4ht made it, `html/` in its compile folder."""
    return f"{document_build(path)}/html"


def document_pdf_address(path: str) -> str:
    """A document's compiled PDF as the viewer addresses it under the site's root, `tex/<stem>-<hash>/<stem>.pdf`: the manifest's `pdf`."""
    return f"{TEX_ADDRESS}/{_compile_folder(path)}/{PurePosixPath(path).stem}.pdf"
