"""A quilt's library as an earlier loom left it, in layout format 1, written by hand: what the carry-over (`library.carry`), `loom upgrade` and `library-upgrade` read. No generated quilt is in format 1, so every test of the carry builds its own."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from loom.library.carry import BIBLIOGRAPHY, STORAGE
from loom.paths import FORMAT, LIBRARY

#: A work stating an arXiv number, with its PDF in the old store under that number, and a book stating nothing.
SMI24 = """@article{Smi24,
  author = {Smith, Jane},
  title  = {Widgets},
  year   = {2024},
  eprint = {2401.01234v1},
  archiveprefix = {arXiv},
  loom-source = {smith-widgets.pdf},
}"""
HAR77 = """@book{Har77,
  author    = {Hartshorne, Robin},
  title     = {Algebraic Geometry},
  publisher = {Springer},
  year      = {1977},
}"""
PDF_A = b"%PDF-1.4\n% the arXiv preprint\n"


def old_library(root: Path, bib: str, stored: Mapping[str, bytes] | None = None) -> Path:
    """Make `root`'s library format 1's: the format stamped 1, `bib` as `.loom/library/bibliography.bib` under the head the earlier loom wrote, and each of `stored`, a path under the old store to its bytes; returns `root`."""
    (root / FORMAT).parent.mkdir(parents=True, exist_ok=True)
    (root / FORMAT).write_text("1\n", encoding="utf-8")
    (root / LIBRARY).mkdir(parents=True, exist_ok=True)
    head = "% The quilt's bibliography, gathered by `loom library update` from the landmarks.\n\n"
    (root / BIBLIOGRAPHY).write_text(head + bib + "\n", encoding="utf-8")
    for rel, data in (stored or {}).items():
        path = root / STORAGE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def older_quilt(tmp_path: Path) -> Path:
    """A quilt `loom init` made, its library then written as format 1's: `SMI24` with its PDF stored, and `HAR77`."""
    from tests.helpers import ok

    ok("init", str(tmp_path / "q"), cwd=tmp_path)
    return old_library(tmp_path / "q", f"{SMI24}\n\n{HAR77}", {"arxiv/2401.01234v1/paper.pdf": PDF_A})
