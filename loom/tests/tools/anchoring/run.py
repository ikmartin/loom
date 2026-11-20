"""Run the anchoring harness over papers and print, for each scenario of co-author edits, where the records filed on the paper ended up.

Usage: uv run python tests/tools/anchoring/run.py OUT [PAPER ...] [--only SCENARIO ...]

With `--pretwin`, each statement targeted has a verbatim twin at the end of its file before any record is filed. With `--old`, every record is filed as a loom before `context` filed it, and read by the rules for such records. With `--verify`, records are read as the Safe gate reads them: a record on a stable key (an id) keeps its block only while that block still reads as the record was written, and is detached otherwise (`records.locate.VERIFY`); without it, as loom reads them.

OUT is a scratch directory; each paper's copies and its results (`<name>.json`, which `aggregate.py` sums) go under it. With no PAPER, the papers are the two quilt sources the repository commits (`tests/quilts/sources/showcase` and `synthetic`) and, when `LOOM_PAPER_FIXTURES` is set, every directory under it.

A PAPER that holds a `config.toml` is a quilt and is used as it is. Any other is a paper's source tree, as its author wrote it, and is made the smallest quilt there is, a `config.toml` naming its main file, which is what a mirror of someone's Overleaf project would be. The main file is the one `.tex` at the top with a `\\documentclass`; where there are several, name it as `DIR:MAIN.tex`.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import harness  # noqa: E402

SOURCES = Path(__file__).resolve().parents[2] / "quilts" / "sources"
COMMITTED = (SOURCES / "showcase", SOURCES / "synthetic")


def main_file(paper: Path) -> str:
    """The paper's main file: the one top-level `.tex` that declares a document class."""
    found = sorted(
        p.name for p in paper.glob("*.tex") if "\\documentclass" in p.read_text(encoding="utf-8", errors="replace")
    )
    if len(found) != 1:
        raise SystemExit(
            f"{paper}: {len(found)} top-level .tex files declare a document class ({', '.join(found) or 'none'}); name the main one as {paper}:MAIN.tex"
        )
    return found[0]


def as_quilt(given: str, out: Path) -> Path:
    """The quilt to run on: `given` itself when it is one, else a copy under `out` with a `config.toml` naming its main file."""
    where, _, named = given.partition(":")
    paper = Path(where).resolve()
    if (paper / "config.toml").is_file():
        return paper
    main = named or main_file(paper)
    quilt = out / "quilts" / paper.name
    if quilt.exists():
        shutil.rmtree(quilt)
    shutil.copytree(paper, quilt, ignore=shutil.ignore_patterns("*.gz", "*.zip", "*.pdf", ".git"))
    (quilt / "config.toml").write_text(f'[quilt]\nname = "{paper.name}"\nmain = "{main}"\n', encoding="utf-8")
    return quilt


def papers(named: list[str]) -> list[str]:
    """The papers asked for, or the committed ones and every directory of `LOOM_PAPER_FIXTURES`."""
    if named:
        return named
    out = [str(p) for p in COMMITTED]
    fixtures = os.environ.get("LOOM_PAPER_FIXTURES")
    if fixtures:
        out += sorted(str(p) for p in Path(fixtures).iterdir() if p.is_dir() and not p.name.startswith("."))
    return out


def run(out: Path, named: list[str], only: list[str] | None = None) -> dict[str, Path]:
    """Run every paper; the results file of each, by the paper's name."""
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for given in papers(named):
        quilt = as_quilt(given, out)
        name = Path(given.partition(":")[0]).name
        results = out / f"{name}.json"
        harness.main(quilt, out / name, results, only)
        written[name] = results
    return written


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--pretwin" in args:
        args.remove("--pretwin")
        harness.PRETWIN = True
    if "--old" in args:
        args.remove("--old")
        harness.OLD = True
    if "--verify" in args:
        args.remove("--verify")
        from loom.records import locate

        locate.VERIFY = True
    only: list[str] | None = None
    if "--only" in args:
        at = args.index("--only")
        args, only = args[:at], args[at + 1 :]
    if not args:
        raise SystemExit((__doc__ or "").split("\n\n")[1])
    run(Path(args[0]), args[1:], only)
