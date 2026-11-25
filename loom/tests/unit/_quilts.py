"""Quilts the unit tests share: the demo, the demo with its deny list set or its paper opened to agents, a fresh session in one, and a copy of the showcase."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.helpers import ok

REPO = Path(__file__).resolve().parents[2]
SHOWCASE = REPO / "tests" / "quilts" / "showcase"


def demo(tmp_path: Path) -> Path:
    """`loom init --demo` into `tmp_path/q`, shipped ledger, sessions and annotation log included."""
    ok("init", str(tmp_path / "q"), "--demo", cwd=tmp_path)
    return tmp_path / "q"


def denying(q: Path, *entries: str) -> Path:
    """`q` with its `[agents] deny` list set to `entries`, through the config's own writer, whatever table its config holds already."""
    from loom.config_edit import set_values
    from loom.scan.quilt import load_quilt

    set_values(load_quilt(q), {"agents.deny": list(entries)})
    return q


def opened(q: Path) -> Path:
    """`q` with its `[agents] deny` list emptied, as a person who opens their paper to agents' edits in place does.

    The demo denies its paper to agents, as a quilt made from a paper does, so its look does not watch it; a test of an in-place change in the paper opens it before the look is taken.
    """
    return denying(q)


def new_session(q: Path, title: str = "a sitting", author: str = "A. Author") -> str:
    """A fresh session made by `loom session new`, returning its id; the demo's own sessions are left as they are."""
    return ok("session", "new", "--name", title, "--as", author, cwd=q).stdout.split()[0]


def open_session(root: Path) -> str:
    """An open session to write into, made if there is none; every write over the API names one."""
    from loom.sessions import create, sessions

    have = [s for s in sessions(root).values() if s.state == "open"]
    return have[0].id if have else create(root, "test sitting", "tester").id


def showcase(tmp_path: Path) -> Path:
    """A copy of the showcase, the one test quilt whose works hold real PDFs; a copy because reading a page caches its text and word boxes inside it."""
    q = tmp_path / "showcase"
    shutil.copytree(SHOWCASE, q)
    return q
