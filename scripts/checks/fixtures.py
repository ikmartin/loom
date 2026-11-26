#!/usr/bin/env python3
"""Every copy of a fixture equals its source (plan 0.14.1 phase 4; docs/specs/fixture.md §3, demos/README.md).

Usage:
    scripts/checks/fixtures.py

Compared byte for byte, over the files git would commit (tracked, or untracked and not ignored):

- `docs/specs/fixture/` and its vendored copies `loom/tests/fixture/` and `viewer/tests/fixture/`, less `views/`: the samples of the views' reads and writes, which `scripts/regen views` and `views-library` write into the source alone and the viewer's tests read from there, so no copy carries them;
- `demos/demo/`, `demos/synthetic/` and `demos/showcase/` and the quilts under `loom/tests/quilts/` that `demos/build.py` copies them from, less the `EXPECTED-LINT.txt` it drops from demo and showcase, and less `.loom/records/review-observations.json`, which loom rewrites whenever it scans a quilt, so serving a demo would change it under the check.

Exit 0 when every copy agrees, 1 otherwise.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFRESH = "sh docs/specs/tools/refresh-fixture.sh"
DEMOS = "python demos/build.py --skip-papers"
#: runtime state loom rewrites on every scan; a served demo changes it without anyone editing anything
STATE = (".loom/records/review-observations.json",)
#: the views' samples, generated into the fixture's source alone (`scripts/regen views`, `views-library`) and read from there by the viewer's tests; no copy carries them
VIEWS = ("views/",)

# (source, copy, files the copy leaves out (a name ending in `/` a folder), the command that makes the copy again)
PAIRS = [
    ("docs/specs/fixture", "loom/tests/fixture", VIEWS, REFRESH),
    ("docs/specs/fixture", "viewer/tests/fixture", VIEWS, REFRESH),
    ("loom/tests/quilts/demo", "demos/demo", ("EXPECTED-LINT.txt", *STATE), DEMOS),
    ("loom/tests/quilts/synthetic", "demos/synthetic", STATE, DEMOS),
    ("loom/tests/quilts/showcase", "demos/showcase", ("EXPECTED-LINT.txt", *STATE), DEMOS),
]


def committable(rel: str) -> set[str]:
    """The files under `rel` a commit would carry, relative to it; every file on disk where git is unavailable."""
    base = ROOT / rel
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", rel],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        names = {Path(p).relative_to(rel).as_posix() for p in out.split("\0") if p}
        return {n for n in names if (base / n).is_file()}
    except (OSError, subprocess.CalledProcessError):
        return {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}


def kept(names: set[str], left_out: tuple[str, ...]) -> set[str]:
    """`names` less those `left_out` names, a name ending in `/` leaving out the folder."""
    return {n for n in names if n not in left_out and not any(n.startswith(o) for o in left_out if o.endswith("/"))}


def compare(source: str, copy: str, left_out: tuple[str, ...]) -> list[str]:
    want = kept(committable(source), left_out)
    have = kept(committable(copy), left_out)
    out = [f"{copy}/{n} is missing (it is in {source}/)" for n in sorted(want - have)]
    out += [f"{copy}/{n} is extra (it is not in {source}/)" for n in sorted(have - want)]
    out += [
        f"{copy}/{n} differs from {source}/{n}"
        for n in sorted(want & have)
        if (ROOT / source / n).read_bytes() != (ROOT / copy / n).read_bytes()
    ]
    return out


def main() -> int:
    fixes: list[str] = []
    for source, copy, left_out, fix in PAIRS:
        if not (ROOT / copy).is_dir():
            print(f"{copy}/ is missing")
            problems = ["missing"]
        else:
            problems = compare(source, copy, left_out)
            for line in problems[:10]:
                print(line)
            if len(problems) > 10:
                print(f"... and {len(problems) - 10} more under {copy}/")
        if problems and fix not in fixes:
            fixes.append(fix)
    if fixes:
        print("\n".join(f"fix: {f}" for f in fixes))
        return 1
    print(f"fixtures: ok ({len(PAIRS)} copies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
