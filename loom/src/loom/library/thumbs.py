"""A stored PDF's first page as a picture, for a works list drawn as thumbnails (`library-views.md` §3.1): 360 pixels wide, made by poppler the first time it is asked for and kept by the PDF's hash under `.loom/cache/library/thumbs/`, which the sweep keeps while the store holds the PDF."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from loom.library import documents
from loom.paths import LIBRARY_THUMBS

#: The picture's width in pixels: twice a card's, for a screen of double density.
WIDTH = 360


def thumb(root: Path, digest: str) -> Path | None:
    """The first page of the stored PDF `digest` as a PNG, made once; None when the store lacks the PDF or poppler cannot draw it.

    Parameters
    ----------
    root : Path
        The quilt.
    digest : str
        The PDF's hash.

    Returns
    -------
    Path or None
        The picture.
    """
    pdf = documents.path_of(root, digest, "pdf")
    out = root / LIBRARY_THUMBS / f"{documents.hex_of(digest)}.png"
    if out.is_file():
        return out
    tool = shutil.which("pdftoppm")
    if not pdf.is_file() or tool is None:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.with_name(f".{out.stem}.{os.getpid()}")
    try:
        made = subprocess.run(
            [
                tool,
                "-png",
                "-f",
                "1",
                "-l",
                "1",
                "-singlefile",
                "-scale-to-x",
                str(WIDTH),
                "-scale-to-y",
                "-1",
                str(pdf),
                str(stem),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        drawn = stem.with_suffix(".png")
        if made.returncode != 0 or not drawn.is_file():
            return None
        os.replace(drawn, out)
        return out
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        stem.with_suffix(".png").unlink(missing_ok=True)
