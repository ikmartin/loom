"""Nothing but the door writes a person's file (`docs/design/writes.md`, "Where it stands"): every call that writes, moves or removes a file outside `writes.py` is in a module or function listed here as writing only loom's own places, each with its reason, so a new writer of a person's file fails this test until it goes through `loom.writes`."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "loom"

#: Calls on any object that write, move or remove a file.
ATTRS = {"write_text", "write_bytes", "unlink", "rename", "touch", "rmdir", "symlink_to", "hardlink_to"}
#: Module functions that do.
FUNCS = {
    ("os", "replace"),
    ("os", "rename"),
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "removedirs"),
    ("os", "symlink"),
    ("os", "link"),
    ("shutil", "move"),
    ("shutil", "copy"),
    ("shutil", "copy2"),
    ("shutil", "copyfile"),
    ("shutil", "copytree"),
    ("shutil", "rmtree"),
}

#: Whole modules that write only loom's own places, by path under `loom/`, with why.
MODULES = {
    "refs/": "the library's store and records, written under the library's lock (`refs/intake.py`)",
    "digest/": "the library's digests",
    "records/": "loom's records under `.loom/`",
    "tex/": "TeX's runs, its staging and the machine's own TeX",
    "render/serve.py": "the server's own files in `.loom/local/` and the viewer's copies on the machine",
    "render/publish.py": "the build's output",
    "render/assets.py": "the build's output",
    "render/snippets.py": "the build's output",
    "render/build.py": "the build's output",
    "render/incoming.py": "a temporary tree",
    "render/endpoints/library.py": "the library's store",
    "cli/help.py": "click's help formatter, which writes no file",
    "cli/build_cmds.py": "build reports and closures under `.loom/`",
    "cli/session.py": "an agent's session under `.loom/`",
    "cli/library/upkeep.py": "the library's store",
    "lifetimes.py": "the sweep of what is derived, under `.loom/`",
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
    "cli/quilt.py:write_minimal_quilt.write": "a quilt `loom init` makes, which did not exist",
    "cli/quilt.py:write_demo_quilt": "a quilt `loom init --demo` makes, which did not exist",
    "cli/quilt.py:undo_minimal_quilt": "taking back what `loom init` made",
    "cli/quilt.py:_write_user_config_template": "the machine's own config",
    "cli/upgrade.py:upgrade": "the annotation types, a record",
    "doctor.py:check_tools": "a temporary file",
    "gitignore.py:write_loom_ignore": "`.loom/.gitignore`",
    "history/ledger.py:append_entry": "the history, outside an act that stages it (`writes.staging`)",
    "history/steps.py:write_step": "the history, outside an act that stages it (`writes.staging`)",
    "review_origins.py:write": "a record, outside an act that stages it",
    "sync.py:SyncState.write": "the sync record, outside an act that stages it",
    "sync.py:pull_files": "a temporary stage",
    "sync.py:publish": "the sync directory, loom's clone of the workspace",
    "reshape/canon.py:plan_draft": "a temporary stage",
    "reshape/importer.py:_mirror_quilt": "a temporary stage",
    "scan/quilt.py:save_author": "the machine's own config",
}


def _writes_mode(call: ast.Call) -> bool:
    for a in [*call.args[1:2], *(k.value for k in call.keywords if k.arg == "mode")]:
        if isinstance(a, ast.Constant) and isinstance(a.value, str) and any(c in a.value for c in "wax+"):
            return True
    return False


class _Writes(ast.NodeVisitor):
    """The write calls of one module, by the function each is in."""

    def __init__(self, rel: str, found: dict[str, list[str]]) -> None:
        self.rel, self.found = rel, found
        self.stack: list[str] = []

    def visit_FunctionDef(self, n: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.stack.append(n.name)
        self.generic_visit(n)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]
    visit_ClassDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, n: ast.Call) -> None:
        fn, hit = n.func, None
        if isinstance(fn, ast.Attribute):
            if isinstance(fn.value, ast.Name) and (fn.value.id, fn.attr) in FUNCS:
                hit = f"{fn.value.id}.{fn.attr}"
            elif fn.attr in ATTRS:
                hit = fn.attr
            elif fn.attr == "open" and (
                _writes_mode(n)
                or (n.args and isinstance(n.args[0], ast.Constant) and any(c in str(n.args[0].value) for c in "wax+"))
            ):
                hit = "open"
        elif isinstance(fn, ast.Name) and fn.id == "open" and _writes_mode(n):
            hit = "open"
        if hit:
            self.found.setdefault(f"{self.rel}:{'.'.join(self.stack) or '<module>'}", []).append(f"{hit}@{n.lineno}")
        self.generic_visit(n)


def writers() -> dict[str, list[str]]:
    """Every function outside `writes.py` holding a call that writes, moves or removes a file, by `module:qualname`, with each call as `what@line`."""
    found: dict[str, list[str]] = {}
    for f in sorted(SRC.rglob("*.py")):
        rel = f.relative_to(SRC).as_posix()
        if rel != "writes.py":
            _Writes(rel, found).visit(ast.parse(f.read_text(encoding="utf-8")))
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


def test_every_function_listed_still_writes() -> None:
    """A listing outlives its reason when the function stops writing or is renamed; it is taken out then, so the list stays what is true."""
    stale = sorted(set(FUNCTIONS) - set(writers()))
    assert not stale, f"listed but writing nothing now: {stale}"
