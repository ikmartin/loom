"""PDFs the library's tests make: one in the fake toolchain's shape, read by the unit tier's `pdftotext`, and real ones of sized lines with a document information dictionary, read by poppler in tests marked `poppler`."""

from __future__ import annotations

from pathlib import Path

#: A page's height in points, and the left edge every line starts at.
HEIGHT, LEFT = 792.0, 72.0


def fake_pdf(path: Path, text: str) -> Path:
    """A PDF in the shape the fake toolchain's pdftotext reads (`tests/fake_latex`): its text is the page, a form feed a page break."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"%PDF-1.4\n%FAKE-LOOM\n%%Pages: {text.count(chr(12)) + 1}\n{text}\n".encode())
    return path


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def real_pdf(path: Path, pages: list[list[tuple[str, float]]], *, info: dict[str, str] | None = None) -> Path:
    """A real PDF of `pages`, each a list of (line, size in points) set in Helvetica from the top down, a page of no lines having no text at all, as a scan has none; `info` is its document information (`Title`, `Author`).

    Each line's baseline stands its size and a third below the last, so a larger line takes more room, as a title does.
    """
    n = len(pages)
    font = 3 + 2 * n
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    kids = []
    for lines in pages:
        y = HEIGHT - 72.0
        rows = []
        for text, size in lines:
            y -= size * 1.35
            rows.append(f"BT /F1 {size:g} Tf 1 0 0 1 {LEFT:g} {y:g} Tm ({_esc(text)}) Tj ET")
        stream = " ".join(rows).encode()
        page_no = len(objs) + 1
        kids.append(f"{page_no} 0 R")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 {HEIGHT:g}] /Contents {page_no + 1} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {n} >>".encode()
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    trailer_info = ""
    if info:
        objs.append(("<< " + " ".join(f"/{k} ({_esc(v)})" for k, v in info.items()) + " >>").encode())
        trailer_info = f" /Info {len(objs)} 0 R"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    start = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R{trailer_info} >>\nstartxref\n{start}\n%%EOF\n".encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))
    return path
