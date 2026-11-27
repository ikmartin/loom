"""Downloading a work's arXiv source or PDF to a folder of the caller's, under the name arXiv gives it, so that the intake reads the arXiv number off the name as it does off a dropped file (`docs/design/library.md`: with the TeX source loom knows every result exactly).

Nothing here writes the library: what comes back is taken in as any dropped document is. Nothing calls it yet.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

from loom import own
from loom.version import __version__

USER_AGENT = f"loom/{__version__} (+https://github.com/ikmartin/loom)"
ARXIV = "https://export.arxiv.org"


class FetchRefused(Exception):
    """The service could not be reached, or answered with an error."""


def get(url: str, attempts: int = 3) -> bytes:
    """GET with loom's User-Agent; a 406 (arXiv's answer to a burst), 429 or 5xx, or an unreachable host, is retried after a pause of 3 s, then 6 s.

    Parameters
    ----------
    url : str
        What to download.
    attempts : int, default 3
        How many times to ask.

    Returns
    -------
    bytes
        The answer's body.

    Raises
    ------
    FetchRefused
        When the last attempt failed.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    last: Exception | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(3.0 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            last = FetchRefused(f"{url}: HTTP {exc.code} {exc.reason}")
            if exc.code not in (406, 429) and not 500 <= exc.code < 600:
                break
        except urllib.error.URLError as exc:
            last = FetchRefused(f"{url}: {exc.reason}")
    assert last is not None
    raise last


def arxiv_source(ident: str, dest: Path, *, attempts: int = 3) -> Path:
    """Download the e-print of the arXiv paper `ident` into the folder `dest`.

    Parameters
    ----------
    ident : str
        The arXiv number, with or without its version (`2401.01234v2`, `math/0601001`).
    dest : Path
        A folder of the caller's, made if missing.
    attempts : int, default 3
        How many times to ask (`get`); 1 for one request and no retry.

    Returns
    -------
    Path
        The file written: `<ident>.gz` as arXiv serves a source (a gzipped tar or a gzipped single file), or `<ident>.pdf` where arXiv holds only a PDF; a `/` in an old-style number is written `_`.

    Raises
    ------
    FetchRefused
        When arXiv could not be asked or has no such paper.
    """
    data = get(f"{ARXIV}/e-print/{ident}", attempts)
    return _written(dest, ident, ".pdf" if data[:4] == b"%PDF" else ".gz", data)


def arxiv_pdf(ident: str, dest: Path, *, attempts: int = 3) -> Path:
    """Download the PDF of the arXiv paper `ident` into the folder `dest`.

    Parameters
    ----------
    ident : str
        The arXiv number, with or without its version.
    dest : Path
        A folder of the caller's, made if missing.
    attempts : int, default 3
        How many times to ask (`get`); 1 for one request and no retry.

    Returns
    -------
    Path
        `<ident>.pdf`.

    Raises
    ------
    FetchRefused
        When arXiv could not be asked, has no such paper, or answered with something other than a PDF.
    """
    data = get(f"{ARXIV}/pdf/{ident}", attempts)
    if data[:4] != b"%PDF":
        raise FetchRefused(f"{ARXIV}/pdf/{ident} did not return a PDF")
    return _written(dest, ident, ".pdf", data)


def _written(dest: Path, ident: str, suffix: str, data: bytes) -> Path:
    """`data` written into `dest` as `<ident><suffix>`, a `/` in the number made `_`."""
    own.mkdir(dest)
    path = dest / f"{ident.replace('/', '_')}{suffix}"
    own.write_bytes(path, data)
    return path
