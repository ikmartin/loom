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
    "digest/": "the library's digests",
    "records/": "loom's records under `.loom/`",
    "tex/": "TeX's runs, its staging and the machine's own TeX",
    "fence.py": "the fence's canary, two files in temporary folders of its own",
    "render/serve.py": "the server's own files in `.loom/local/` and the viewer's copies on the machine",
    "render/publish.py": "the build's output",
    "render/assets.py": "the build's output",
    "render/snippets.py": "the build's output",
    "render/build.py": "the build's output",
    "render/endpoints/library.py": "the library's store",
    "cli/help.py": "click's help formatter, which writes no file",
    "cli/build_cmds.py": "build reports and closures under `.loom/`",
    "cli/session.py": "an agent's session under `.loom/`",
    "cli/library/upkeep.py": "the library's store",
    "lifetimes.py": "the sweep of what is derived, under `.loom/`",
    "locks.py": "the lock files loom holds, made empty and never written",
    "layout.py": "`.loom/`'s layout and its format number",
    "since.py": "`.loom/local/`",
    "mailbox.py": "loom's records",
    "sessions.py": "loom's records of agents' sessions",
    "presence.py": "`.loom/local/`",
    "machine.py": "the machine's own place",
    "looks.py": "the person's look, a record",
    "review_queue.py": "loom's records",
    "mcp/server.py": "an agent's scratch and the server's log",
    "section_drafts.py": "an agent's copies under `.loom/` and temporary trees",
}

#: Functions of mixed modules that write only loom's own places, by `module:qualname`, with why.
FUNCTIONS = {
    "adopt.py:_flat_shape_made": "a temporary tree",
    "adopt.py:_merge": "a temporary tree",
    "adopt.py:prepare": "the saved preview, `.loom/local/`",
    "adopt.py:decide": "the saved choices, a record",
    "adopt.py:refresh": "an agent's copy under `.loom/`",
    "ai/layout.py:_write": "the layer's own records in `.loom/`; a person's file goes through `writes.put`",
    "ai/layout.py:init_layer": "the layer's records in `.loom/`",
    "ai/layout.py:upgrade_layer": "the layer's records in `.loom/`",
    "ai/layout.py:write_versions": "the layer's records in `.loom/`",
    "ai/skills.py:write_skills": "a skill's folder left empty once the door removed its file",
    "cli/history_cmds.py:_draft_ai": "an agent's copy under `.loom/`",
    "cli/history_cmds.py:_scan_after": "a temporary copy of the quilt",
    "cli/paper.py:_identity_for": "a temporary tree",
    "cli/quilt.py:write_minimal_quilt.write": "`.loom/`'s first files, and `config.toml` and `README.md` only where there are none",
    "cli/quilt.py:write_demo_quilt": "the demo quilt, into a folder that is new or empty (`init --demo` refuses any other)",
    "cli/quilt.py:undo_minimal_quilt": "taking back what `loom init` made",
    "cli/quilt.py:_write_user_config_template": "the machine's own config",
    "cli/upgrade.py:upgrade": "the annotation types, a record",
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

    def visit_Attribute(self, n: ast.Attribute) -> None:
        if n.attr in ATTRS:
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
        if (module, func) in FUNCS:
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
