"""Graphics for fragments: PDF figures become SVG (pdftocairo, else dvisvgm --pdf), raster images and the pictures TeX drew are copied; everything lands content-addressed under .loom/cache/site/svg/."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from loom import own
from loom.paths import under
from loom.render.uses import passing
from loom.tex import private
from loom.tex.runner import tex_env


def _digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:16]


def resolve_graphic(root: Path, name: str, base: str = "") -> Path | None:
    """The file `\\includegraphics{name}` shows, read against `base`, the directory its document compiles from; None for a name that resolves to nothing, or names an absolute path or `..`."""
    name = name.strip()
    if not name or name.startswith("/") or ".." in Path(name).parts:
        return None
    for cand in (name, name + ".pdf", name + ".png", name + ".jpg", name + ".jpeg", name + ".svg"):
        p = root / under(base, cand)
        if p.is_file():
            return p
    return None


def publish_graphic(root: Path, name: str, svg_dir: Path, base: str = "") -> tuple[str | None, str | None]:
    """Return (relative asset path under the site, `.loom/cache/site/`, error). PDF -> SVG conversion, PNG/JPEG/SVG copied; `name` is read against `base`."""
    src = resolve_graphic(root, name, base)
    if src is None:
        return None, f"graphic {name} not found"
    own.mkdir(svg_dir)
    stamp = _digest(src)
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg"):
        out = svg_dir / f"{stamp}{src.suffix.lower()}"
        if not out.exists():
            own.copyfile(src, out, mode=True)
        else:
            _named_again(out)
        return f"svg/{out.name}", None
    out = svg_dir / f"{stamp}.svg"
    if out.exists():
        _named_again(out)
        return f"svg/{out.name}", None
    made, readable = pdf_to_svg(src, out)
    if made:
        return f"svg/{out.name}", None
    if readable:
        # a converter that can read a PDF here failed, and may not fail again; one that cannot is a state of the machine a key names (`converters`)
        passing()
    return None, f"could not convert {name} to SVG (pdftocairo or dvisvgm --pdf needed)"


def pdf_to_svg(src: Path, out: Path) -> tuple[bool, bool]:
    """Convert the PDF `src` to the SVG `out`: poppler's `pdftocairo -svg`, else `dvisvgm --pdf`.

    Returns whether `out` was made, and, where it was not, whether a converter that can read a PDF here failed (`_reads_pdf`), which a figure's key does not name.
    """
    pdftocairo = shutil.which("pdftocairo")
    if pdftocairo:
        proc = subprocess.run(
            [pdftocairo, "-svg", str(src), str(out)], capture_output=True, text=True, errors="replace", check=False
        )
        if proc.returncode == 0 and out.exists():
            return True, False
    said = ""
    dvisvgm = shutil.which("dvisvgm")
    if dvisvgm:
        proc = subprocess.run(
            [dvisvgm, "--pdf", "--no-fonts", f"--output={out}", str(src)],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            env=tex_env(),
        )
        if proc.returncode == 0 and out.exists():
            return True, False
        said = proc.stdout + proc.stderr
    return False, bool(pdftocairo or (dvisvgm and _reads_pdf(said)))


def converters() -> tuple[str | None, str | None, str | None, tuple[str, int, int] | None]:
    """What decides whether a PDF figure converts here, for a key to name: where `pdftocairo`, `dvisvgm` and `mutool` are, and the Ghostscript `dvisvgm` is given (`_ghostscript`). `dvisvgm` reads a PDF with `mutool`, or with a Ghostscript older than 10.01, whose version is its file's."""
    return shutil.which("pdftocairo"), shutil.which("dvisvgm"), shutil.which("mutool"), _ghostscript()


def _ghostscript() -> tuple[str, int, int] | None:
    """The Ghostscript library `dvisvgm` is given, loom's or else the one `LIBGS` names (`tex_env`), by its path, size and modification time; None where none is."""
    named = private.ghostscript_library()
    if named is None and os.environ.get("LIBGS"):
        named = Path(os.environ["LIBGS"])
    try:
        st = named.stat() if named is not None else None
    except OSError:
        return None
    return (str(named), st.st_size, st.st_mtime_ns) if st is not None else None


def _reads_pdf(said: str) -> bool:
    """Whether the `dvisvgm` here could have read the PDF, as `converters` names the machine and as it said failing: with `mutool` or a Ghostscript, unless it said it can use neither ("mutool is required"), which it says of a Ghostscript too new, whatever `mutool` is beside it. With no Ghostscript it says only that it could not count the pages, so there a `mutool` it cannot run counts as one it can, and the draft is rendered again at every build."""
    return "mutool is required" not in said and (shutil.which("mutool") is not None or _ghostscript() is not None)


def publish_picture(picture: Path, svg_dir: Path) -> str:
    """A picture TeX drew, copied under `.loom/cache/site/svg/` by its content: the path a fragment names it by."""
    own.mkdir(svg_dir)
    out = svg_dir / f"{_digest(picture)}{picture.suffix.lower()}"
    if not out.exists():
        own.copyfile(picture, out, mode=True)
    else:
        _named_again(out)
    return f"svg/{out.name}"


def _named_again(picture: Path) -> None:
    """Touch a picture a page names again, so a sweep that looked at it before leaves it (`lifetimes.Doom`)."""
    try:
        os.utime(picture)
    except OSError:
        pass
