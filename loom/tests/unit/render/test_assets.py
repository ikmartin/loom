"""Graphics for fragments: a PDF figure becomes SVG by pdftocairo, else `dvisvgm --pdf`; a raster or SVG is copied; everything lands content-addressed under .loom/cache/site/svg/."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from loom.render.assets import publish_graphic, resolve_graphic


def calls() -> list[str]:
    """The tools the fake toolchain was run as, in order."""
    log = Path(os.environ["FAKE_TEX_LOG"])
    return [line.split()[0] for line in log.read_text().splitlines()] if log.exists() else []


def test_a_graphic_is_found_with_or_without_its_extension(tmp_path: Path) -> None:
    (tmp_path / "fig").mkdir()
    (tmp_path / "fig" / "cone.pdf").write_bytes(b"%PDF-1.4\n")
    assert resolve_graphic(tmp_path, " fig/cone ") == tmp_path / "fig" / "cone.pdf"
    assert resolve_graphic(tmp_path, "fig/cone.pdf") == tmp_path / "fig" / "cone.pdf"
    assert resolve_graphic(tmp_path, "fig/none") is None
    assert publish_graphic(tmp_path, "fig/none", tmp_path / "svg") == (None, "graphic fig/none not found")


def test_a_raster_is_copied_under_its_content_hash(tmp_path: Path) -> None:
    (tmp_path / "a.png").write_bytes(b"\x89PNG one")
    (tmp_path / "b.PNG").write_bytes(b"\x89PNG one")
    out = tmp_path / ".loom/cache/site" / "svg"
    rel, err = publish_graphic(tmp_path, "a", out)
    assert err is None and rel is not None and rel.startswith("svg/") and rel.endswith(".png")
    assert (out.parent / rel).read_bytes() == b"\x89PNG one"
    assert publish_graphic(tmp_path, "b.PNG", out) == (rel, None)  # same bytes, same asset, lower-cased suffix
    assert calls() == []  # nothing converted


def test_a_pdf_is_converted_by_pdftocairo_once(tmp_path: Path) -> None:
    (tmp_path / "cone.pdf").write_bytes(b"%PDF-1.4\n%FAKE-LOOM\nx\n")
    out = tmp_path / ".loom/cache/site" / "svg"
    rel, err = publish_graphic(tmp_path, "cone", out)
    assert err is None and rel is not None and rel.endswith(".svg") and "<svg" in (out.parent / rel).read_text()
    assert calls() == ["pdftocairo"]
    assert publish_graphic(tmp_path, "cone", out) == (rel, None)
    assert calls() == ["pdftocairo"]  # already converted: nothing runs again


def test_without_pdftocairo_dvisvgm_converts_and_without_either_it_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "cone.pdf").write_bytes(b"%PDF-1.4\n%FAKE-LOOM\nx\n")
    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda tool: None if tool == "pdftocairo" else real_which(tool))
    rel, err = publish_graphic(tmp_path, "cone", tmp_path / "svg1")
    assert err is None and rel is not None and calls() == ["dvisvgm"]
    monkeypatch.setattr(shutil, "which", lambda tool: None)
    assert publish_graphic(tmp_path, "cone", tmp_path / "svg2") == (
        None,
        "could not convert cone to SVG (pdftocairo or dvisvgm --pdf needed)",
    )


#: Each machine a figure meets, as (the converters here, the Ghostscript `dvisvgm` is given), and whether an unconverted figure is noted passing: only where a converter that can read a PDF here ran and failed, which it may not do again; a converter missing, or a `dvisvgm` with neither `mutool` nor a Ghostscript it accepts, is a state of the machine a key names (`converters`). A tool marked `-failing` exits 1; `-refusing` is `dvisvgm` 3.2's answer to a Ghostscript from 10.01 on.
MACHINES = {
    "a converter that works": (("pdftocairo",), None, False),
    "no converter": ((), None, False),
    "dvisvgm with neither mutool nor a Ghostscript": (("dvisvgm-failing",), None, False),
    "dvisvgm refusing its Ghostscript, no mutool": (("dvisvgm-refusing",), ("/x/libgs.dylib", 1, 2), False),
    "dvisvgm with a Ghostscript it accepts, failing": (("dvisvgm-failing",), ("/x/libgs.dylib", 1, 2), True),
    "dvisvgm with mutool, failing": (("dvisvgm-failing", "mutool"), None, True),
    "pdftocairo, failing": (("pdftocairo-failing",), None, True),
}


@pytest.mark.parametrize("machine", sorted(MACHINES))
def test_an_unconverted_figure_is_passing_only_when_a_converter_that_reads_pdf_here_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, machine: str
) -> None:
    from loom.render import assets
    from loom.render.uses import PASSING, noting

    (tmp_path / "cone.pdf").write_bytes(b"%PDF-1.4\n%FAKE-LOOM\nx\n")
    scripts = {
        "failing": "#!/bin/sh\necho 'ERROR: something went wrong' >&2\nexit 1\n",
        "refusing": "#!/bin/sh\necho 'ERROR: To process PDF files, either Ghostscript < 10.01.0 or mutool is required.' >&2\nexit 252\n",
    }
    for how, body in scripts.items():
        (tmp_path / how).write_text(body)
        (tmp_path / how).chmod(0o755)
    tools, ghostscript, passing = MACHINES[machine]
    real = shutil.which
    here = {}
    for t in tools:
        tool, _, how = t.partition("-")
        here[tool] = str(tmp_path / how) if how else (real(tool) or str(tmp_path / "failing"))
    monkeypatch.setattr(shutil, "which", lambda tool: here.get(tool))
    monkeypatch.setattr(assets, "_ghostscript", lambda: ghostscript)
    with noting() as noted:
        rel, _ = publish_graphic(tmp_path, "cone", tmp_path / "svg")
    assert (rel is not None) == (machine == "a converter that works")
    assert (PASSING in noted) == passing


def test_the_converters_name_the_ghostscript_dvisvgm_is_given_by_its_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Ghostscript of another version is another file: the key changes when loom's, or the one `LIBGS` names, is replaced."""
    from loom.render import assets
    from loom.tex import private

    monkeypatch.setattr(private, "ghostscript_library", lambda: None)
    monkeypatch.delenv("LIBGS", raising=False)
    assert assets._ghostscript() is None
    lib = tmp_path / "libgs.dylib"
    lib.write_bytes(b"10.06")
    monkeypatch.setenv("LIBGS", str(lib))
    first = assets._ghostscript()
    assert first is not None and first[0] == str(lib)
    lib.write_bytes(b"10.00.0")
    assert assets._ghostscript() != first
    shipped = tmp_path / "loom-libgs.dylib"
    shipped.write_bytes(b"10.05")
    monkeypatch.setattr(private, "ghostscript_library", lambda: shipped)
    assert assets._ghostscript() is not None and assets._ghostscript()[0] == str(shipped)


def test_a_graphic_the_quilt_does_not_hold_is_not_passing(tmp_path: Path) -> None:
    from loom.render.uses import PASSING, noting

    with noting() as noted:
        assert publish_graphic(tmp_path, "nothing", tmp_path / "svg")[0] is None
    assert PASSING not in noted
