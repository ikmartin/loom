"""Replay one seed of the seeded write-safety test outside pytest, printing every act and the first problem found.

Usage: uv run python tests/tools/trace_write_safety.py SEED WORK

WORK is a scratch directory, emptied first; the quilt is copied into it, and the person's name is kept under it, never in the real configuration.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
import test_write_safety as t  # noqa: E402

seed, work = int(sys.argv[1]), Path(sys.argv[2])
shutil.rmtree(work, ignore_errors=True)
work.mkdir(parents=True)
patch = pytest.MonkeyPatch()
# the fixture's own function, which pytest wraps
prepare = getattr(t.q, "_get_wrapped_function", lambda: t.q._fixture_function)()
q = prepare(work, patch)
run = t.Run(q, seed)
for i in range(16):
    t.step(run)
    print(i, run.trail[-1][:300])
    if run.problems:
        print("PROBLEMS", run.problems)
        break
patch.undo()
