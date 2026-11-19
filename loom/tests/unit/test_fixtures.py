"""Fixture quilts: expected diagnostics, the demo equals `loom init --demo`, edge cases, and the author-file invariance property."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from loom.scan.diagnostics import all_codes
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import describe, ok, run, same_tree

REPO = Path(__file__).resolve().parents[2]
QUILTS_DIR = REPO / "tests" / "quilts"
QUILTS = sorted(p for p in [*QUILTS_DIR.iterdir(), *(QUILTS_DIR / "edge").iterdir()] if (p / "config.toml").is_file())


def _copy(quilt: Path, tmp_path: Path) -> Path:
    dest = tmp_path / quilt.name
    shutil.copytree(quilt, dest)
    return dest


REGENERATE = "cd loom && uv run python scripts/gen_quilts.py"


def _tree(root: Path, skip: set[str]) -> dict[str, bytes]:
    """Every file under `root` by relative path, but those `skip` names by name or by path."""
    out = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file() and p.name not in skip}
    return {rel: p.read_bytes() for rel, p in out.items() if rel not in skip}


#: The quilts the generator writes, expected lint and agent permission files included: what lint says of one is compared with a generated file, so it is a `tree` check; the edge quilts are written by hand and checked in the everyday lane.
GENERATED = ("demo", "showcase", "synthetic")
#: The showcase's marks on its PDFs are found again on a changed file by their words, which want the real pdftotext; without it they read as detached.
LINTED = [
    pytest.param(
        q,
        marks=[
            *([pytest.mark.tree] if q.parent == QUILTS_DIR and q.name in GENERATED else []),
            *([pytest.mark.poppler] if q.name == "showcase" else []),
        ],
    )
    for q in QUILTS
]


@pytest.mark.parametrize("quilt", LINTED, ids=[q.name for q in QUILTS])
def test_lint_fixture_expected_codes(quilt: Path, tmp_path: Path) -> None:
    q = _copy(quilt, tmp_path)
    from loom.scan.quilt import save_author

    names = {"synthetic": "The synthetic quilt", "demo": "The loom demo", "showcase": "The loom showcase"}
    if quilt.name in names:
        save_author(names[quilt.name])
    expected_lines = sorted(
        " ".join(line.split())
        for line in (quilt / "EXPECTED-LINT.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    r = run("lint", "--json", cwd=q)
    got = sorted(f"{d['severity']} {d['code']} {d['class']}" for d in json.loads(r.stdout)["diagnostics"])
    assert got == expected_lines
    code = 1 if any(line.startswith("error") for line in got) else 0
    assert r.exit_code == code, f"expected exit {code}" + describe(("lint", "--json"), r)


def test_all_emitted_codes_are_known() -> None:
    known = set(all_codes())
    for quilt in QUILTS:
        for line in (quilt / "EXPECTED-LINT.txt").read_text(encoding="utf-8").splitlines():
            assert line.split()[1] in known, line


#: The reserved cross-publisher codes of `specs/diagnostics.md` §2, the only codes without `loom:`.
RESERVED_CODES = {
    "duplicate-id",
    "dangling-link",
    "missing-include",
    "inclusion-cycle",
    "double-inclusion",
    "unreachable",
}


def _literals(expr: object) -> list[str]:
    """The string codes an expression can evaluate to: a literal, or either arm of a conditional; a computed code is read where it was made."""
    import ast

    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [expr.value]
    if isinstance(expr, ast.IfExp):
        return _literals(expr.body) + _literals(expr.orelse)
    return []


def test_every_code_loom_can_emit_is_reserved_or_namespaced() -> None:
    """Every code in the table, and every one a `Diagnostic(...)` in loom's source names, is a reserved code or starts with `loom:`; each one named is in the table; and each emitted with a literal severity is emitted at the table's, unless its instances differ (`VARIES`)."""
    import ast

    from loom.scan.diagnostics import RESERVED, VARIES, registered

    assert set(RESERVED) == RESERVED_CODES
    known = set(all_codes())
    named: dict[str, str] = {}
    graded: list[str] = []
    src = Path(__file__).resolve().parents[2] / "src" / "loom"
    for path in sorted(src.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            func = node.func if isinstance(node, ast.Call) else None
            if getattr(func, "id", getattr(func, "attr", None)) != "Diagnostic":
                continue
            assert isinstance(node, ast.Call)
            code = (
                node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "code"), None)
            )
            severity = node.args[0] if node.args else None
            for c in _literals(code):
                named[c] = where = f"{path.relative_to(src)}:{node.lineno}"
                entry = registered(c)
                if entry is not None and c not in VARIES:
                    graded += [f"{c} {s} ({where})" for s in _literals(severity) if s != entry.severity]
    assert len(named) > 40, "the walk found too few codes to be reading the source"
    assert sorted(f"{c} ({w})" for c, w in named.items() if c not in known) == [], "codes missing from the table"
    stray = sorted(c for c in known | set(named) if c not in RESERVED_CODES and not c.startswith("loom:"))
    assert stray == [], "codes that are neither reserved nor loom:"
    assert sorted(graded) == [], "codes emitted at another severity than the table's"


def test_every_code_has_a_class(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry gives every code one of the three classes, and the check finds a code given none."""
    from loom.scan import diagnostics
    from loom.scan.diagnostics import CLASSES, LOOM, Code, unclassed

    assert unclassed() == []
    assert {LOOM[c].cls for c in LOOM} <= set(CLASSES)
    monkeypatch.setitem(LOOM, "loom:made-up", Code("warning", ""))
    assert diagnostics.unclassed() == ["loom:made-up"]


@pytest.mark.tree
def test_init_demo_matches_fixture(tmp_path: Path) -> None:
    ok("init", str(tmp_path / "demo"), "--demo", cwd=tmp_path)
    fixture = QUILTS_DIR / "demo"
    # `.gitignore` is written from `assets/init/` and never from the demo's own copy: the fixture negates the store's PDF so this repository can commit the invented paper behind the demo's digest, and a quilt an author makes must not inherit that (DR-194, as amended). The MCP client files name this machine's paths, so init writes them and no fixture carries them.
    from loom.ai.clients import PROJECT_FILES

    skip = {"EXPECTED-LINT.txt", ".gitignore", *PROJECT_FILES}
    same_tree(
        _tree(tmp_path / "demo", skip), _tree(fixture, skip), "`loom init --demo` against tests/quilts/demo", REGENERATE
    )


def test_nested_nest_levels() -> None:
    r = scan(load_quilt(QUILTS_DIR / "edge" / "nested-nest"))
    levels = {k: n.level for k, n in r.nodes.items() if n.kind == "section"}
    assert levels == {"ed-0100": 1, "ed-0101": 2, "ed-0102": 3, "ed-0103": 1}
    assert r.nodes["ed-0102"].parent["drafting/main.tex"] == "ed-0101"
    assert r.nodes["ed-0101"].parent["drafting/main.tex"] == "ed-0100"
    assert r.nodes["ed-0001"].reached_by == ["drafting/main.tex"]


def test_begin_not_alone_tolerated() -> None:
    r = scan(load_quilt(QUILTS_DIR / "edge" / "begin-not-alone"))
    assert r.nodes["ed-0001"].proofs == ["ed-0001/proof"]
    assert r.nodes["ed-0002"].proofs == [] and r.nodes["ed-0002"].title == "T"
    unattached = [d for d in r.lint if d.code == "loom:unattached-proof"]
    assert len(unattached) == 1


def test_synthetic_structure() -> None:
    r = scan(load_quilt(QUILTS_DIR / "synthetic"))
    n = r.nodes
    assert n["sy-0300"].level == 2 and n["sy-0300"].parent["drafting/main.tex"] == "sy-0200"
    assert n["sy-0201"].parent["drafting/main.tex"] == "sy-0200"
    assert n["sy-0007"].proofs == ["sy-0007/proof"] and n["sy-0007/proof"].attach_via == "ref"
    assert n["sy-0003"].proofs == ["sy-0004", "sy-0005"]
    assert n["sy-0006"].proofs == ["sy-0006/proof", "sy-0006/proof/2"]
    assert n["sy-0008"].aliases == ["def:gadget", "defn:gadget-old"]
    assert set(n["sy-0002"].reached_by) == {"drafting/main.tex", "drafting/talk.tex"}
    assert n["sy-0009"].reached_by == []
    assert n["sy-000C/proof"].incomplete and n["sy-000C/proof"].directives == {}
    assert (
        n["sy-0202"].directives["author"] == "A Coauthor" and n["sy-0003"].directives["author"] == "The synthetic quilt"
    )
    assert n["sy-000B"].taxon == "Main Theorem"
    assert n["Kre99-thm-2.1"].digest == "Kre99" and n["Kre99-thm-2.1"].external
    assert "drafting/old.tex" not in n and r.files["drafting/old.tex"].ignored
    assert r.taxa["lemma"].style == "plain"


def _snapshot(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts:
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@pytest.mark.parametrize("quilt", QUILTS, ids=[q.name for q in QUILTS])
def test_never_modifies_author_files(quilt: Path, tmp_path: Path) -> None:
    q = _copy(quilt, tmp_path)
    before = _snapshot(q)
    r = scan(load_quilt(q))
    key = next((k for k, n in r.nodes.items() if n.kind == "environment"), None)
    env = next(iter(r.taxa), None)
    master = r.default_master
    landmark = next(iter(r.canon_files), None)
    # written beside the default document, where a person's new document would go
    drafting = str(Path(master).parent) if master else "drafting"
    commands: list[list[str]] = [
        ["lint"],
        ["lint", "--json"],
        ["lint", "--nodes"],
        ["search", "a"],
        ["search", "a", "--json"],
        ["delete", "x"],
        ["doctor"],
        ["history"],
        ["history", "verify"],
        ["stamp", "-m", "written by the invariance test"],
    ]
    if key:
        commands += [
            ["deps", key],
            ["deps", key, "--closure", "--json"],
            ["downstream", key],
            ["downstream", key, "--json"],
            ["history", key],
            ["revert", f"{key}@1"],
            ["fork", key, "--in", master or "nothing.tex"],
        ]
    if env:
        commands += [["new", env, "--print"], ["new", env, "Written by the invariance test"]]
    if master:
        commands += [
            ["stamp", master, "-m", "written by the invariance test on a document"],
            ["linearize", master, "--to", f"{drafting}/invariance-flat.tex", "--no-check"],
            ["live", master],
        ]
    if landmark:
        commands += [["history", "restore", Path(landmark).stem, "--to", f"{drafting}/invariance-draft.tex"]]
    for cmd in commands:
        # the verdict is not this test's subject, only what the command leaves on disk; it differs by quilt and command (a lint with errors exits 1, `live` on a live master 2), and a crash raises out of `run`
        run(*cmd, cwd=q)
    after = _snapshot(q)
    for rel, digest in before.items():
        if rel == "config.toml" or rel.startswith(".loom/"):
            continue  # loom's own files, checked below: [quilt] main may move, and the ledgers are appended to
        assert after.get(rel) == digest, f"{rel} was modified or deleted by a command"
    was = (quilt / "config.toml").read_text(encoding="utf-8").splitlines()
    now = (q / "config.toml").read_text(encoding="utf-8").splitlines()
    assert [ln for ln in was if not ln.startswith("main")] == [ln for ln in now if not ln.startswith("main")], (
        "config.toml changed in something other than [quilt] main"
    )
    ledger = ".loom/records/history/ledger.jsonl"
    if ledger in before:
        old = (quilt / ledger).read_text(encoding="utf-8")
        assert (q / ledger).read_text(encoding="utf-8").startswith(old), "the history ledger is append-only"
    new_files = set(after) - set(before)
    # everything loom writes goes into nodes/, the drafting directory it was told to write in, or its own record, where a landmark's text is kept
    allowed = ("drafting/nodes/", f"{drafting}/", ".loom/")
    assert all(rel.startswith(allowed) for rel in new_files), new_files


SPEC = REPO.parent / "docs" / "specs" / "diagnostics.md"


def test_the_specification_gives_every_code_the_registry_s_grade_and_class() -> None:
    """`docs/specs/diagnostics.md` says each code's severity and class as `scan/diagnostics.py` holds them, so a wrong class or grade on any code fails here: a reserved code in its table's row, a loom code in its entry's parentheses, `fixed` there exactly when the registry has it; a code whose instances differ names its registry grade and class among what it says."""
    import re

    from loom.scan.diagnostics import LOOM, RESERVED, VARIES

    text = SPEC.read_text(encoding="utf-8")
    wrong: list[str] = []
    for code, entry in RESERVED.items():
        row = re.search(rf"^\| `{re.escape(code)}` \| ([^|]+) \| ([^|]+) \|", text, re.M)
        if row is None:
            wrong.append(f"{code}: no row")
            continue
        severity, cls = (x.strip() for x in row.groups())
        if code in VARIES:
            ok_ = entry.severity in severity and entry.cls in cls
        else:
            ok_ = (severity, cls) == (entry.severity, entry.cls)
        if not ok_:
            wrong.append(f"{code}: says {severity}, {cls}; the registry {entry.severity}, {entry.cls}")
    said = {m.group(1): m.group(0) for m in re.finditer(r"`(loom:[a-z0-9-]+)` \(([^)]*)\)[^\n]*", text)}
    for code, entry in LOOM.items():
        line = next((ln for ln in text.splitlines() if ln.startswith(f"- `{code}`")), None)
        if line is None:
            line = said.get(code)
        if line is None:
            wrong.append(f"{code}: no entry")
            continue
        paren = re.match(r"[^(]*\(([^)]*)\)", line)
        parts = [p.strip() for p in paren.group(1).split(",")] if paren else []
        if code in VARIES:
            if not (entry.severity in line and entry.cls in line):
                wrong.append(f"{code}: says neither {entry.severity} nor {entry.cls}")
        elif parts[:2] != [entry.severity, entry.cls] or ("fixed" in parts) != entry.fixed:
            wrong.append(f"{code}: says ({', '.join(parts)}); the registry {entry}")
    assert wrong == []
