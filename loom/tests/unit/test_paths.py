"""`loom.paths` owns every path loom uses inside a quilt: each lies in the folder of its kind, no other module spells one out, and `[quilt] history` is honoured wherever the history is reached."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

import loom
from loom import paths
from loom.agents import AGENT_FILES, AGENT_PLACES, LOOM_DIRS, LOOM_FILES, claude_denies, denied_by
from loom.records.store import Records
from loom.scan.quilt import load_quilt
from tests.helpers import ok
from tests.unit._quilts import demo

SRC = Path(loom.__file__).parent
#: Directories loom names, and one it named before; a path built from one of these as a literal belongs in `loom.paths`.
DIRS = (
    "build",
    ".loom",
    "records",
    "library",
    "agents",
    "local",
    "cache",
    "digests",
    "annotations",
    "ai",
    "nodes",
    "retired",
)
#: The prefixes a literal quilt path starts with.
PREFIXES = tuple(
    f"{d}/"
    for d in (
        "build",
        ".loom",
        "records",
        "library",
        "agents",
        "local",
        "cache",
        "digests",
        "annotations",
        "ai",
        "retired",
    )
)
#: loom's record files, by name.
RECORDS = {
    "state.toml",
    "serve.json",
    "review-decisions.json",
    "review-origins.json",
    "review-observations.json",
    "adoption-decisions.json",
    "source-sync.json",
    "last-seen.json",
    "writes.jsonl",
    "compiles.json",
}
#: Literals that look like quilt paths and are not, each with its reason, by file and the stripped source line.
ALLOWED = {
    # an output directory inside a temporary stage, not the quilt's build output
    ("sync.py", 'stage / "build" / f"{index}-{Path(projected).stem}",'),
    ("section_drafts.py", 'stage, base, under(base, "paper.tex"), stage / "build", result.quilt.config.engine'),
    # the viewer's route to a work, not a folder
    ("cli/library/agent.py", 'link = open_url(result.quilt.root, f"library/{citekey}?page={page_no}&{locator}")'),
    ("cli/review.py", 'where = open_url(result.quilt.root, f"library/{citekey}?page={page}&annot={ann_id}")'),
    # a module of loom's own source, not of a quilt
    ("render/keys.py", 'RENDERING = ("render", "scan", "tex", "records/selectors.py")'),
}


def _docstrings(tree: ast.AST) -> set[int]:
    """The ids of every docstring constant in `tree`, which are prose and never paths."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.add(id(first.value))
    return out


#: `.loom/` and the folders of its kinds, by their names in `loom.paths`: a string joined to one of these, or an f-string built from one, is a path that belongs in `loom.paths`.
FOLDERS = frozenset({"LOOM", "RECORDS", "LIBRARY", "AGENTS", "LOCAL", "CACHE"})


def _folder(node: ast.AST) -> str | None:
    """The name of `.loom/` or a kind's folder that `node` is, by itself or as `paths.NAME`; else None."""
    name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
    return name if name in FOLDERS else None


def _offences(path: Path) -> list[tuple[int, str]]:
    """(line, why) for each literal in one module that spells out a quilt path, joins a string to `.loom/` or a kind's folder, or builds one from them in an f-string."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    prose = _docstrings(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            right = node.right
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                left = (
                    node.left.right
                    if isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Div)
                    else node.left
                )
                if right.value.split("/")[0] in DIRS:
                    found.append((node.lineno, f"joins {right.value!r}"))
                elif (folder := _folder(left)) is not None:
                    found.append((node.lineno, f"joins {right.value!r} to {folder}"))
        elif isinstance(node, ast.JoinedStr) and id(node) not in prose:
            parts = node.values
            for i, part in enumerate(parts):
                if isinstance(part, ast.FormattedValue) and (folder := _folder(part.value)) is not None:
                    after = parts[i + 1] if i + 1 < len(parts) else None
                    # `f"{LOOM}/"` is the folder itself, as a prefix or a label, and prose may follow it; a name after the slash is a path
                    if (
                        isinstance(after, ast.Constant)
                        and isinstance(after.value, str)
                        and re.match(r"/\.?[\w<-]", after.value)
                    ):
                        found.append((node.lineno, f"builds {folder}{after.value!r}"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose:
            if node.value.startswith(PREFIXES) or node.value in RECORDS:
                found.append((node.lineno, f"spells {node.value!r}"))
    return found


def test_the_offences_are_caught() -> None:
    """Each way of building a quilt path outside `loom.paths` is caught, and naming `.loom/` itself is not."""
    import tempfile

    caught = [
        'root / LOOM / "sessions" / "index.jsonl"',
        'root / AGENTS / "scratch" / "s-1"',
        'root / CACHE / "site" / "manifest.json"',
        'root / f"{LOOM}/build/manifest.json"',
        'root / paths.LOCAL / "serve.json"',
        'x = f"{RECORDS}/state.toml"',
    ]
    fine = [
        'x = f"{LOOM}/"',
        'rel.startswith(f"{LOOM}/")',
        'f"{LOOM}/ (but these)"',
        "root / LOOM",
        'root / SITE_SVG / "a.svg"',
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for line in caught + fine:
            mod = Path(tmp) / "m.py"
            mod.write_text(line + "\n", encoding="utf-8")
            assert bool(_offences(mod)) == (line in caught), line


def _named() -> dict[str, str]:
    """Every quilt path `loom.paths` names under `.loom/`, by constant."""
    return {
        k: v for k, v in vars(paths).items() if k.isupper() and isinstance(v, str) and v.startswith(f"{paths.LOOM}/")
    }


#: The kind of every path constant `loom.paths` names under `.loom/`, by name; None for the folders themselves and the two files at the top. Moving a path to another kind is a change of this table, made on purpose.
KIND = {
    "FORMAT": None,
    "LOOM_GITIGNORE": None,
    "RECORDS": None,
    "LIBRARY": None,
    "AGENTS": None,
    "LOCAL": None,
    "CACHE": None,
    **dict.fromkeys(
        (
            "LEDGER", "ANNOTATIONS", "ANNOTATION_LOG", "EDITS", "EDIT_LOG", "ANNOTATION_TYPES", "REVIEW_DECISIONS",
            "REVIEW_ORIGINS", "REVIEW_OBSERVATIONS", "ADOPTION_DECISIONS", "SOURCE_SYNC", "RETIRED", "LOOKED", "HISTORY",
            "EVIDENCE", "EVIDENCE_LOG", "ASKS", "ASK_LOG", "TAGS", "TAG_LOG",
        ),
        "RECORDS",
    ),
    **dict.fromkeys(
        ("BIBLIOGRAPHY", "UNREADABLE", "LINKS", "LINKS_REMOVED", "SUGGESTED_WORKS", "LIBRARY_NODES", "STORAGE", "STORE_LEDGER"),
        "LIBRARY",
    ),
    **dict.fromkeys(("AI", "SESSIONS", "SESSION_INDEX", "ACTIVE_SESSION", "COPIES", "SCRATCH"), "AGENTS"),
    **dict.fromkeys(
        (
            "SERVE_JSON", "COMPILES", "SINCE", "DELETED", "SHOWN_SEEN", "LIVE", "INCOMING", "LAST_SEEN", "JOURNAL", "JOURNAL_INDEX",
            "WRITES_LOCK", "ID_LOCK", "LIBRARY_LOCK", "SURVEY_LOCK", "BEFORE_DELETE", "ADOPTION_PREVIEWS", "INCORPORATION_PREVIEWS",
        ),
        "LOCAL",
    ),
    **dict.fromkeys(
        (
            "SITE", "MANIFEST", "SITE_SVG", "DRAFT_PREVIEWS", "TEX", "BLOCKS", "BUILD_INDEX", "SNIPPETS",
            "BLOCK_PREVIEWS", "BLOCK_SPANS", "LIBRARY_CACHE", "STORE_BOXES", "RESOLVED", "MARKS", "MARK_BOXES",
            "REFOUND", "CROPS", "CLOSURES", "NODE_INDEX", "LIBRARY_SURVEYS",
        ),
        "CACHE",
    ),
}  # fmt: skip


def test_every_path_is_of_the_kind_this_table_gives_it() -> None:
    """A path constant added, removed or moved to another kind changes the table above, so no move goes unseen."""
    named = _named()
    assert set(named) == set(KIND), (
        f"named but not in KIND: {sorted(set(named) - set(KIND))}; in KIND but not named: {sorted(set(KIND) - set(named))}"
    )
    wrong = [
        f"{name} = {p!r} is not under {KIND[name]}"
        for name, p in named.items()
        if KIND[name] is not None and not p.startswith(f"{getattr(paths, KIND[name])}/")
    ]
    assert not wrong, "\n".join(wrong)


def test_every_path_lies_in_the_folder_of_one_kind() -> None:
    """Each path under `.loom/` is in exactly one kind's folder, or is the layout's number or loom's ignore file: what a folder holds says what it is."""
    kinds = set(paths.KINDS)
    loose = []
    for name, p in _named().items():
        if p in kinds or p in (paths.FORMAT, paths.LOOM_GITIGNORE):
            continue
        holding = [k for k in kinds if p.startswith(f"{k}/")]
        if len(holding) != 1:
            loose.append(f"{name} = {p!r}: in {holding or 'no kind'}")
    assert not loose, "\n".join(loose)
    assert paths.document_build("paper/main.tex").startswith(f"{paths.TEX}/") and paths.TEX.startswith(
        f"{paths.CACHE}/"
    )
    assert paths.scratch("s-1").startswith(f"{paths.SCRATCH}/") and paths.SCRATCH.startswith(f"{paths.AGENTS}/")


def test_the_ignore_file_names_the_three_folders_that_stay_on_one_machine() -> None:
    """`.loom/.gitignore` is this machine's state, what loom derives and the agents' scratch, each by its folder anchored to `.loom/`, and nothing else."""
    from loom.gitignore import LOOM_IGNORE, LOOM_LINES, OWN

    inside = lambda p: "/" + p.removeprefix(f"{paths.LOOM}/") + "/"  # noqa: E731
    assert LOOM_LINES == (inside(paths.LOCAL), inside(paths.CACHE), inside(paths.SCRATCH))
    rules = [line for line in LOOM_IGNORE.splitlines() if line and not line.startswith("#")]
    assert rules == list(LOOM_LINES) and LOOM_IGNORE.endswith(f"{OWN}\n")


def test_git_ignores_the_three_folders_and_nothing_of_the_same_name_deeper_down(tmp_path: Path) -> None:
    """A session's `cache/`, a session's `local/` and a stored source's `local/` are files of the quilt and travel; a file in each of the three folders stays on this machine."""
    import shutil
    import subprocess

    from loom.gitignore import write_loom_ignore

    if shutil.which("git") is None:
        pytest.skip("no git")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_loom_ignore(tmp_path)
    travels = [
        f"{paths.SESSIONS}/s-x/cache/result.csv",
        f"{paths.SESSIONS}/s-x/local/notes.md",
        f"{paths.STORAGE}/arxiv/1234/src/local/macros.sty",
    ]
    stays = [f"{paths.LOCAL}/serve.json", f"{paths.CACHE}/site/manifest.json", f"{paths.scratch('s-x')}/run.tex"]
    for rel in travels + stays:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x", encoding="utf-8")
    said = subprocess.run(
        ["git", "-C", str(tmp_path), "check-ignore", *travels, *stays], capture_output=True, text=True
    )
    assert said.stdout.split() == stays


def test_a_compile_folder_is_named_by_the_document_and_kept_apart_by_its_path() -> None:
    """Two documents of one file name compile into two folders, each found by its name."""
    a, b = paths.document_build("paper/main.tex"), paths.document_build("talk/main.tex")
    assert a != b and a.rsplit("/", 1)[1].startswith("main-") and b.rsplit("/", 1)[1].startswith("main-")
    assert paths.document_build("paper/main.tex") == paths.document_build("paper/main")
    assert paths.document_pdf_address("paper/main.tex") == f"{paths.TEX_ADDRESS}/{a.rsplit('/', 1)[1]}/main.pdf"


def test_no_module_but_paths_spells_out_a_quilt_path() -> None:
    """Every path loom uses inside a quilt is named once, in `loom.paths`, so moving one is a change in one place."""
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel == "paths.py":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, why in _offences(path):
            if (rel, lines[lineno - 1].strip()) not in ALLOWED:
                bad.append(f"{rel}:{lineno}: {why}")
    assert not bad, "name these in loom/src/loom/paths.py:\n" + "\n".join(bad)


def test_the_history_setting_is_honoured_wherever_the_history_is_reached(tmp_path: Path) -> None:
    """A quilt whose `[quilt] history` names another directory has its agents' protection, its records' snapshots and `init`'s ledger there."""
    q = demo(tmp_path)
    config = q / "config.toml"
    config.write_text(config.read_text().replace("[quilt]\n", '[quilt]\nhistory = "hist"\n', 1))
    quilt = load_quilt(q)
    assert "/hist/**" in claude_denies(quilt.config) and denied_by(quilt.config, "hist/ledger.jsonl") == "hist/"
    assert Records(q).history_dir == q / "hist"

    user = Path(os.environ["XDG_CONFIG_HOME"]) / "loom" / "config.toml"
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text('[quilt]\nhistory = "hist"\n')
    ok("init", str(tmp_path / "fresh"), "--prefix", "zz", "--yes")
    assert (tmp_path / "fresh" / "hist" / "ledger.jsonl").is_file()
    assert not (tmp_path / "fresh" / ".loom" / "records" / "history").exists()


def test_every_path_under_loom_is_an_agents_place_or_protected() -> None:
    """Every `.loom/` path `loom.paths` names is either where an agent writes, a file of loom's an agent may edit, or in loom's own table, so a record added later is protected until someone decides otherwise: Claude Code's denies name them one by one, since a deny on `.loom/` would beat the places' allows."""
    from loom.scan.quilt import QuiltConfig

    # a kind's folder holds places of several sorts, each judged below; the folder itself is no place
    named = set(_named().values()) - {paths.RECORDS, paths.AGENTS}
    under = lambda rel, dirs: any(rel == d or rel.startswith(f"{d}/") for d in dirs)  # noqa: E731
    protected = (*LOOM_DIRS, paths.HISTORY)
    loose = sorted(
        p
        for p in named
        if not under(p, AGENT_PLACES) and not under(p, protected) and p not in (*LOOM_FILES, *AGENT_FILES)
    )
    assert not loose, f"neither an agent's place nor protected: {loose}"
    for p in named:
        if p in AGENT_FILES:
            assert denied_by(QuiltConfig(), p) is None, p
        elif p == paths.SESSIONS + "/index.jsonl" or not under(p, AGENT_PLACES):
            assert denied_by(QuiltConfig(), p) is not None, p
