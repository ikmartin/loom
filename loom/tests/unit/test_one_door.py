"""Nothing but the door writes a person's file (`docs/design/writes.md`, "Where it stands"): every call that writes, moves or removes a file outside `writes.py` is in a module or function listed here as writing only loom's own places, each with its reason, so a new writer of a person's file fails this test until it goes through `loom.writes`.

What it reads is the code's text: the calls in `ATTRS` and `FUNCS` under any name a module imports them by, `os.open` with a flag that writes, `open` with a mode that writes or one it cannot read, `Path.replace` (a `replace` of one argument), `getattr` of a writing name, and a writing method taken without a call. What it cannot see: a subprocess (`git mv`, `cp`, `sed -i`, `os.system`), a write made in C or by a library loom calls, a name built at run time, a file's mode or times changed (`chmod`, `utime`), and a directory made; those are read for in review."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "loom"

#: Methods that write, move or remove a file, called or not: a reference held in a variable or passed to `functools.partial` is caught where it is taken.
ATTRS = {"write_text", "write_bytes", "unlink", "rename", "touch", "rmdir", "symlink_to", "hardlink_to", "extractall"}
#: Module functions that do, under whatever name the module imports them.
FUNCS = {
    ("os", "replace"),
    ("os", "rename"),
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("os", "symlink"),
    ("os", "link"),
    ("os", "write"),
    ("os", "truncate"),
    ("os", "ftruncate"),
    ("shutil", "move"),
    ("shutil", "copy"),
    ("shutil", "copy2"),
    ("shutil", "copyfile"),
    ("shutil", "copytree"),
    ("shutil", "rmtree"),
}
#: `os.open`'s flags that let it write.
WRITE_FLAGS = {"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"}

#: Whole modules that write only loom's own places, by path under `loom/`, with why.
MODULES = {
    "refs/": "the library's store and records, written under the library's lock (`refs/intake.py`)",
    "records/": "loom's records under `.loom/`",
    "tex/": "TeX's runs, its staging and the machine's own TeX",
    "fence.py": "the fence's canary, two files in temporary folders of its own",
    "render/serve.py": "the server's own files in `.loom/local/` and the viewer's copies on the machine",
    "render/publish.py": "the build's output",
    "render/assets.py": "the build's output",
    "render/snippets.py": "the build's output",
    "render/build.py": "the build's output",
    "cli/help.py": "click's help formatter, which writes no file",
    "cli/build_cmds.py": "build reports and closures under `.loom/`",
    "cli/session.py": "an agent's session under `.loom/`",
    "lifetimes.py": "the sweep of what is derived, under `.loom/`",
    "locks.py": "the lock files loom holds, made empty and never written",
    "layout.py": "`.loom/`'s layout and its format number",
    "since.py": "`.loom/local/`",
    "mailbox.py": "loom's records",
    "sessions.py": "loom's records of agents' sessions",
    "presence.py": "`.loom/local/`",
    "machine.py": "the machine's own place",
    "own.py": "loom's own places, through folders opened without following a link; each caller is listed for what it writes",
    "app/": "the home's own places in the machine's (its list, its address and lock, the jobs it hands on over a restart, the servers' logs, the drops waiting, the records of quilts being made) and loom's app; a new quilt is made in a hidden folder beside its place and renamed into it whole, its skeleton `cli/quilt.py`'s; a paper dropped on a quilt's page is brought in through the import's act",
    "looks.py": "the person's look, a record",
    "review_queue.py": "loom's records",
    "mcp/server.py": "an agent's scratch and the server's log",
    "section_drafts.py": "an agent's copies under `.loom/` and temporary trees",
    "library/intake.py": "the intake's drops waiting in `.loom/local/incoming/`, and the documents it files into the library's store; a person's file it reads, never writes",
    "library/documents.py": "the library's documents by hash in `.loom/library/documents/`, sources unpacked under `.loom/cache/library/sources/`, and its own temporary spool",
    "library/store.py": "the node store, `.loom/library/nodes/`, and the record of a batch it is placing, `.loom/local/library-act/`, which a writer cut short rolls back",
    "library/acts.py": "the node store, and what a delete took, kept for its undo in `.loom/local/library-undo/`",
    "library/carry.py": "the old library under `.loom/library/` that it removes once carried, and the annotation log it re-keys; the research state, the person's, it writes only through the door",
    "library/index.py": "the index derived from the nodes, `.loom/cache/library/`",
    "library/log.py": "the library's log, `.loom/records/library/`",
    "library/tags.py": "the tag log, `.loom/records/tags/`",
    "library/thumbs.py": "the stored PDFs' first pages as pictures, `.loom/cache/library/thumbs/`",
    "library/drawn.py": "a node drawn by TeX and TeX's failure to draw it, `.loom/cache/library/drawn/`, with the run folder it compiles in there; and the person's word for a work's compile, one file a quilt in the machine's own place",
    "library/survey.py": "the kept surveys, `.loom/cache/library/survey/`, and a compile's marked copy in its run folder there or a temporary one: loom's own place, as the index's and the thumbnails' (ruled 2026-11-25)",
    "evidence/log.py": "the evidence log, `.loom/records/evidence/`",
    "cli/library/add.py": "a folder's source, packed into a drop in `.loom/local/incoming/`",
    "formal/switch.py": "the switch that turns formalization on, one file a quilt in the machine's own place",
}

#: Functions of mixed modules that write only loom's own places, by `module:qualname`, with why.
FUNCTIONS = {
    "adopt.py:_flat_shape_made": "a temporary tree",
    "cli/app_cmd.py:_open": "the home's own log, in the machine's place",
    "cli/open_cmd.py:_start": "the log of the server it starts, `.loom/local/open-serve.log`, beside `serve.json`",
    "adopt.py:_merge": "a temporary tree",
    "adopt.py:prepare": "the saved preview, `.loom/local/`",
    "adopt.py:decide": "the saved choices, a record",
    "adopt.py:refresh": "an agent's copy under `.loom/`",
    "ai/layout.py:_write": "the layer's own records in `.loom/`; a person's file goes through `writes.put`",
    "ai/layout.py:init_layer": "the layer's records in `.loom/`",
    "ai/layout.py:upgrade_layer": "the layer's records in `.loom/`",
    "ai/layout.py:_gone_modes": "a mode file of the layer's in `.loom/agents/instructions/modes/`, removed only while its text is the one loom recorded",
    "ai/layout.py:write_versions": "the layer's records in `.loom/`",
    "ai/skills.py:write_skills": "a skill's folder left empty once the door removed its file",
    "cli/history_cmds.py:_draft_ai": "an agent's copy under `.loom/`",
    "cli/history_cmds.py:_scan_after": "a temporary copy of the quilt",
    "cli/paper.py:_identity_for": "a temporary tree",
    "cli/quilt.py:write_minimal_quilt.write": "`.loom/`'s first files, and `config.toml` and `README.md` only where there are none",
    "cli/quilt.py:write_demo_quilt": "the demo quilt, into a folder that is new or empty (`init --demo` refuses any other)",
    "cli/quilt.py:undo_minimal_quilt": "taking back what `loom init` made",
    "cli/quilt.py:_write_user_config_template": "the machine's own config",
    "doctor.py:check_tools": "a temporary file",
    "gitignore.py:write_loom_ignore": "`.loom/.gitignore`",
    "history/ledger.py:append_entry": "the history, outside an act that stages it (`writes.staging`)",
    "history/steps.py:write_step": "the history, outside an act that stages it (`writes.staging`)",
    "review_origins.py:write": "a record, outside an act that stages it",
    "sync.py:SyncState.write": "the sync record, outside an act that stages it",
    "overleaf.py:_clone": "loom's own clone of an Overleaf project, in `.loom/local/`",
    "overleaf.py:_keep_here": "this machine's part of the mirror, in `.loom/local/`",
    "overleaf.py:_remove": "loom's own clone of an Overleaf project, in `.loom/local/`, taken away to be made again",
    "overleaf.py:unpair": "the mirror's record, loom's clone and this machine's part, all under `.loom/`",
    "reshape/canon.py:plan_draft": "a temporary stage",
    "reshape/importer.py:_mirror_quilt": "a temporary stage",
    "scan/quilt.py:save_author": "the machine's own config",
    "notes.py:set_command": "the person's own new-note commands, `notes.toml` beside the machine's own config, written whole through a temporary file beside it",
    "upgrade.py:upgrade": "the annotation types, `.loom/records/annotation-types.toml`, written only where there are none",
    "formal/check.py:check": "loom's probe, copied into a temporary folder of its own",
    "formal/check.py:_check": "two folders in the Lake project's `.lake`, refused where it or they are a link: `.lake/loom`, loom's own folder for a check's home and temporary files, made anew each check; and `.lake/build`, Lake's build of the project's own modules, which the check builds again from clean; never a source, a package or anything outside the project",
    "formal/install.py:_install_elan": "elan's installer, downloaded into a temporary folder of its own",
}


def _writes_mode(call: ast.Call, at: int) -> bool:
    """Whether an `open` call's mode (positional at `at`, or `mode=`) writes, or cannot be read off the code: a mode held in a variable is taken to write."""
    given = [*call.args[at : at + 1], *(k.value for k in call.keywords if k.arg == "mode")]
    for a in given:
        if not isinstance(a, ast.Constant):
            return True
        if isinstance(a.value, str) and any(c in a.value for c in "wax+"):
            return True
    return False


def _aliases(tree: ast.AST) -> dict[str, str]:
    """What each imported name stands for: a module under another name (`import shutil as sh`) or a module's function (`from os import remove`)."""
    out: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out[a.asname or a.name] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                out[a.asname or a.name] = f"{n.module}.{a.name}"
    return out


class _Writes(ast.NodeVisitor):
    """The write calls of one module, by the function each is in."""

    def __init__(self, rel: str, found: dict[str, list[str]], aliases: dict[str, str] | None = None) -> None:
        self.rel, self.found = rel, found
        self.aliases = aliases or {}
        self.stack: list[str] = []

    def hit(self, what: str, n: ast.AST) -> None:
        self.found.setdefault(f"{self.rel}:{'.'.join(self.stack) or '<module>'}", []).append(f"{what}@{n.lineno}")  # type: ignore[attr-defined]

    def visit_FunctionDef(self, n: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.stack.append(n.name)
        self.generic_visit(n)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]
    visit_ClassDef = visit_FunctionDef  # type: ignore[assignment]

    def _own(self, n: ast.expr) -> bool:
        """Whether `n` is the module `loom.own`, under whatever name it is imported."""
        return isinstance(n, ast.Name) and self.aliases.get(n.id) == "loom.own"

    def visit_Attribute(self, n: ast.Attribute) -> None:
        if self._own(n.value):
            # `own.write_text`, called or taken: a write never through a link, named so (`test_own_writes_follow_no_link`)
            self.hit(f"own.{n.attr}", n)
        elif n.attr in ATTRS:
            self.hit(n.attr, n)
        self.generic_visit(n)

    def visit_Call(self, n: ast.Call) -> None:
        fn = n.func
        named = ""
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            named = f"{self.aliases.get(fn.value.id, fn.value.id)}.{fn.attr}"
        elif isinstance(fn, ast.Name):
            named = self.aliases.get(fn.id, fn.id)
        module, _, func = named.rpartition(".")
        if module == "loom.own":
            if isinstance(fn, ast.Name):  # `from loom.own import write_text`; `own.write_text` is seen as an attribute
                self.hit(f"own.{func}", n)
        elif (module, func) in FUNCS:
            self.hit(named, n)
        elif (
            named == "os.open"
            and len(n.args) > 1
            and {x.attr for x in ast.walk(n.args[1]) if isinstance(x, ast.Attribute)} & WRITE_FLAGS
        ):
            self.hit("os.open", n)
        elif named == "open" and _writes_mode(n, 1):
            self.hit("open", n)
        elif (
            isinstance(fn, ast.Attribute)
            and fn.attr == "open"
            and named != "os.open"
            and (
                named in ("io.open", "codecs.open")
                or not (isinstance(fn.value, ast.Name) and fn.value.id in self.aliases)
            )
        ):
            # `Path.open(mode)`, `io.open(path, mode)`, `codecs.open(path, mode)`: the mode is the first argument a path's own method takes
            if _writes_mode(n, 1 if named in ("io.open", "codecs.open") else 0):
                self.hit("open", n)
        elif isinstance(fn, ast.Attribute) and fn.attr == "replace" and len(n.args) == 1 and not n.keywords:
            # `Path.replace(target)`, which a `str.replace` never is: it takes two
            self.hit("replace", n)
        elif named == "getattr" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
            if n.args[1].value in ATTRS or n.args[1].value in {f for _, f in FUNCS}:
                self.hit(f"getattr {n.args[1].value}", n)
        self.generic_visit(n)


def writers() -> dict[str, list[str]]:
    """Every function outside `writes.py` holding a call that writes, moves or removes a file, by `module:qualname`, with each call as `what@line`."""
    found: dict[str, list[str]] = {}
    for f in sorted(SRC.rglob("*.py")):
        rel = f.relative_to(SRC).as_posix()
        if rel != "writes.py":
            tree = ast.parse(f.read_text(encoding="utf-8"))
            _Writes(rel, found, _aliases(tree)).visit(tree)
    return found


def test_nothing_but_the_door_writes_a_person_s_file() -> None:
    unlisted = {
        where: calls
        for where, calls in writers().items()
        if where not in FUNCTIONS and not any(where.startswith(m) for m in MODULES)
    }
    assert not unlisted, (
        "these write, move or remove a file outside the door; route a person's file through `loom.writes` "
        "(`act`, `put`, `save`), or list a function that writes only loom's own places here with why: "
        + "; ".join(f"{w} ({', '.join(c)})" for w, c in sorted(unlisted.items()))
    )


def test_every_listing_still_writes() -> None:
    """A listing outlives its reason when the function or module stops writing or is renamed; it is taken out then, so the list stays what is true."""
    found = writers()
    stale = sorted(set(FUNCTIONS) - set(found)) + sorted(m for m in MODULES if not any(w.startswith(m) for w in found))
    assert not stale, f"listed but writing nothing now: {stale}"


def test_the_visitor_sees_a_writer_however_it_is_spelled() -> None:
    """The spellings the review planted in an unlisted module, each one a writer this test must see."""
    snippets = {
        "Path.replace": "def f(tmp, p):\n    tmp.replace(p)",
        "an aliased os.remove": "from os import remove as rm\ndef f(a):\n    rm(a)",
        "from shutil import move": "from shutil import move\ndef f(a, b):\n    move(a, b)",
        "import shutil as sh": "import shutil as sh\ndef f(a, b):\n    sh.copyfile(a, b)",
        "getattr write_text": "def f(p):\n    getattr(p, 'write_text')('x')",
        "os.open to write": "import os\ndef f(p):\n    fd = os.open(p, os.O_WRONLY | os.O_TRUNC)",
        "os.write": "import os\ndef f(fd):\n    os.write(fd, b'x')",
        "os.truncate": "import os\ndef f(p):\n    os.truncate(p, 0)",
        "a mode in a variable": "def f(p, m):\n    with open(p, m) as fh:\n        fh.read()",
        "Path.open with a mode in a variable": "def f(p, m):\n    p.open(m)",
        "a method kept in a variable": "def f(p):\n    w = p.write_text\n    w('x')",
        "functools.partial": "import functools\ndef f(p):\n    functools.partial(p.write_text, 'x')()",
        "extractall": "import tarfile\ndef f(a, d):\n    tarfile.open(a).extractall(d)",
    }
    missed = []
    for name, code in snippets.items():
        tree = ast.parse(code)
        found: dict[str, list[str]] = {}
        _Writes("cli/nodes.py", found, _aliases(tree)).visit(tree)
        if not found:
            missed.append(name)
    assert not missed, missed
    readers = {
        "str.replace": "def f(s):\n    return s.replace('a', 'b')",
        "open to read": "def f(p):\n    return open(p).read()",
    }
    for code in readers.values():
        tree = ast.parse(code)
        found = {}
        _Writes("cli/nodes.py", found, _aliases(tree)).visit(tree)
        assert not found, code


#: Writers of loom's own places that still write by path, by module or `module:qualname`, each with why; every other writer listed above writes only through `loom.own`, so a link planted in its path carries nothing (`docs/design/writes.md`, "Loom's own places").
BY_PATH = {
    "own.py": "the helper itself, which writes by name in folders it opened without following a link",
    "lifetimes.py": "the sweep, which removes by name through folders opened from their home without following a link (`_remove_in`)",
    "presence.py": "the server's presence record, written only where `.loom/local/live/` and every folder on its way is no link (`_place`), and opened with `O_NOFOLLOW`",
    "layout.py:stamp": "a `.loom/` made by `tempfile` in the quilt's root and renamed into place, with nothing below the root to plant in yet",
    "formal/check.py:_check": "Lake's `.lake/loom` and `.lake/build`, each refused where it or `.lake` is a link before it is removed",
    "render/serve.py": "the viewer's copies in the machine's place, which a start removes only where they are loom's shapes and never through a link (`hold_viewer`, `_let_go`), its own mark made with `O_NOFOLLOW` once a link at its name is taken away; a `viewers` folder the person made a link is followed, as a run of the person's",
    "tex/": "TeX's runs and staging, in temporary folders of their own, where a compile folder in the cache is reached through no link before TeX writes in it by path (`runner._compile_once`, `tex4ht._html_once`); and the machine's own TeX, which loom installs and assembles in its data folder by path, not moved: a link planted in `tex/` there would carry an install's files, by a hand that can already write the data folder",
    "app/create.py:Makings.close": "a quilt being made, in a hidden folder beside the place the person chose",
    "app/create.py:make": "a quilt being made, in a hidden folder beside the place the person chose, and renamed into it",
    "app/create.py:recover": "a quilt a create cut short, in a hidden folder beside the place the person chose",
    "app/create.py:_unpack": "a drop's archive opened by `zipfile` and `tarfile`'s `data` filter into a folder made through no link the moment before",
    "app/launcher.py:write_launcher": "the launcher, in the person's own Applications folder",
    "ai/skills.py:write_skills": "a skill's folder in an app's place, the person's, left empty once the door removed its file",
    "cli/quilt.py:write_minimal_quilt.write": "a quilt `loom init` makes, before it holds a `.loom/` anyone could plant in",
    "cli/quilt.py:write_demo_quilt": "the demo quilt, into a folder that is new or empty",
    "cli/quilt.py:undo_minimal_quilt": "taking back what `loom init` made",
    "cli/quilt.py:_write_user_config_template": "the person's own config, where a link is their arrangement (a folder of dotfiles) and is followed",
    "scan/quilt.py:save_author": "the person's own config, where a link is their arrangement and is followed",
    "notes.py:set_command": "the person's own new-note commands beside their config, where a link is their arrangement and is followed",
    "adopt.py:_flat_shape_made": "a temporary tree of its own",
    "adopt.py:_merge": "a temporary tree of its own",
    "cli/history_cmds.py:_scan_after": "a temporary copy of the quilt",
    "cli/paper.py:_identity_for": "a temporary tree of its own",
    "section_drafts.py:preview_in_paper": "a temporary stage of its own",
    "reshape/": "temporary stages of their own",
    "doctor.py:check_tools": "a temporary file of its own",
    "fence.py": "the fence's canary, in temporary folders of its own",
    "formal/check.py:check": "loom's probe, copied into a temporary folder of its own",
    "formal/install.py:_install_elan": "elan's installer, downloaded into a temporary folder of its own",
    "cli/help.py": "click's help formatter, which writes no file",
    "app/server.py:_open": "no file: the supervisor's `open`",
    "app/supervise.py:Supervisor._keep": "no file: the supervisor's `open`",
    "library/documents.py:_from_zip": "no file: `ZipFile.open`, which reads",
    "library/index.py:opened": "no file: the index's own `open`",
}


def _by_path(where: str) -> bool:
    return any(where == k or ((k.endswith("/") or k.endswith(".py")) and where.startswith(k)) for k in BY_PATH)


def test_loom_s_own_writes_follow_no_planted_link() -> None:
    """Every writer of loom's own places writes through `loom.own` (folders opened without following a link, the file `O_NOFOLLOW`), but those `BY_PATH` names with why, so a new raw write into `.loom/`, the history or the machine's place fails here until it goes through `loom.own` or says why it need not."""
    raw = {w: [c for c in calls if not c.startswith("own.")] for w, calls in writers().items()}
    left = {w: c for w, c in raw.items() if c and not _by_path(w)}
    assert not left, (
        "these write loom's own places by path, following any link planted on the way: use `loom.own`, or list in BY_PATH with why: "
        + "; ".join(f"{w} ({', '.join(c)})" for w, c in sorted(left.items()))
    )
    stale = sorted(k for k in BY_PATH if not any(w == k or w.startswith(k) for w, c in raw.items() if c))
    assert not stale, f"listed as writing by path but writing nothing so now: {stale}"
