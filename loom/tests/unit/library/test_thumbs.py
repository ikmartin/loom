"""A stored PDF's first page as a picture (`library.thumbs`): made by poppler once, kept by the PDF's hash, and served at `/_api/library/thumb/<hex>.png`."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library import documents
from loom.library.thumbs import thumb
from loom.paths import LIBRARY_THUMBS
from tests.unit._quilts import showcase

pytestmark = pytest.mark.poppler

PNG = b"\x89PNG\r\n\x1a\n"


def stored_pdf(root: Path) -> str:
    """The hash of a PDF the showcase's store holds."""
    pdf = next((root / ".loom/library/documents").glob("*.pdf"))
    return f"sha256:{pdf.stem}"


def test_a_stored_pdfs_first_page_is_drawn_once_and_kept_by_its_hash(tmp_path: Path) -> None:
    root = showcase(tmp_path)
    digest = stored_pdf(root)
    made = thumb(root, digest)
    assert made == root / LIBRARY_THUMBS / f"{documents.hex_of(digest)}.png"
    assert made.read_bytes().startswith(PNG)
    assert [p.name for p in made.parent.iterdir()] == [made.name]  # no temporary file left beside it
    stamp = made.stat().st_mtime_ns
    assert thumb(root, digest) == made and made.stat().st_mtime_ns == stamp  # kept, not drawn again
    assert thumb(root, f"sha256:{'0' * 64}") is None  # a PDF the store lacks has no picture


def test_the_server_answers_a_thumbnail_by_the_pdfs_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.render import serve as serve_mod
    from loom.render.serve import ServeSession
    from loom.scan.quilt import load_quilt
    from tests.unit.render._serve import QuickServer, fake_bundle, get

    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    root = showcase(tmp_path)
    digits = documents.hex_of(stored_pdf(root))
    s = ServeSession(load_quilt(root), fake_bundle(tmp_path), port=0, compile_masters=False, interval=0.2)
    s.listen()
    try:
        status, headers, body = get(s.url + f"_api/library/thumb/{digits}.png")
        assert status == 200 and headers["Content-Type"] == "image/png" and body.startswith(PNG)
        assert get(s.url + f"_api/library/thumb/{'0' * 64}.png")[0] == 404
    finally:
        s.stop()
