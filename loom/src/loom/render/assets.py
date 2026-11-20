"""Graphics for fragments: PDF figures become SVG (pdftocairo, else dvisvgm --pdf), raster images and the pictures TeX drew are copied; everything lands content-addressed under .loom/cache/site/svg/."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

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
    svg_dir.mkdir(parents=True, exist_ok=True)
    stamp = _digest(src)
    if src.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg"):
        out = svg_dir / f"{stamp}{src.suffix.lower()}"
        if not out.exists():
            shutil.copy(src, out)
        else:
            _named_again(out)
        return f"svg/{out.name}", None
    out = svg_dir / f"{stamp}.svg"
    if out.exists():
        _named_again(out)
        return f"svg/{out.name}", None
    pdftocairo = shutil.which("pdftocairo")
    if pdftocairo:
        proc = subprocess.run(
            [pdftocairo, "-svg", str(src), str(out)], capture_output=True, text=True, errors="replace", check=False
        )
        if proc.returncode == 0 and out.exists():
            return f"svg/{out.name}", None
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
            return f"svg/{out.name}", None
    if pdftocairo or (dvisvgm and private.ghostscript_available()):
        # a converter the machine has failed, and may not fail again; one it lacks is a state of the machine a key names (`converters`)
        passing()
    return None, f"could not convert {name} to SVG (pdftocairo or dvisvgm --pdf needed)"


def converters() -> tuple[str | None, str | None, bool]:
    """What decides whether a PDF figure converts here, for a key to name: where `pdftocairo` and `dvisvgm` are, and whether `dvisvgm` has a Ghostscript, without which it converts no PDF."""
    return shutil.which("pdftocairo"), shutil.which("dvisvgm"), private.ghostscript_available()


def publish_picture(picture: Path, svg_dir: Path) -> str:
    """A picture TeX drew, copied under `.loom/cache/site/svg/` by its content: the path a fragment names it by."""
    svg_dir.mkdir(parents=True, exist_ok=True)
    out = svg_dir / f"{_digest(picture)}{picture.suffix.lower()}"
    if not out.exists():
        shutil.copy(picture, out)
    else:
        _named_again(out)
    return f"svg/{out.name}"


def _named_again(picture: Path) -> None:
    """Touch a picture a page names again, so a sweep that looked at it before leaves it (`lifetimes.Doom`)."""
    try:
        os.utime(picture)
    except OSError:
        pass
