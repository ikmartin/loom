"""Problems by class in `loom serve`: the start line counts an error of loom's model as none and a failed compile as one, a run that makes no PDF is published as a problem on its document, and every diagnostic the manifest carries says its class."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from loom.paths import MANIFEST, document_build
from loom.render import serve as serve_mod
from loom.render.compiles import Compiles
from loom.render.serve import ServeSession
from loom.scan.diagnostics import CLASSES
from loom.scan.quilt import load_quilt
from loom.tex.runner import CompileResult
from tests.helpers import PATIENCE, edit
from tests.unit._quilts import demo
from tests.unit.render._serve import QuickServer, fake_bundle

DOC = "drafting/main.tex"
#: A proof after `\item`, which LaTeX compiles and loom's model attaches to nothing.
UNATTACHED = "\\begin{enumerate}\n\\item One.\n\\begin{proof}\nThe answer is short.\n\\end{proof}\n\\end{enumerate}\n"


def _demo(tmp_path: Path, name: str) -> Path:
    (tmp_path / name).mkdir()
    return demo(tmp_path / name)


def _published(q: Path) -> list[dict]:  # type: ignore[type-arg]
    return list(json.loads((q / MANIFEST).read_text(encoding="utf-8"))["diagnostics"])


def _until(check: Callable[[], bool]) -> None:
    deadline = time.monotonic() + PATIENCE
    while not check():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def test_the_start_line_counts_no_error_of_loom_s_model_and_a_failed_compile_as_one(
    tmp_path: Path, serve: Callable[..., ServeSession], capsys: pytest.CaptureFixture[str]
) -> None:
    """A proof after `\\item` compiles: once an error, it made the start line say so on a quilt with nothing wrong in its LaTeX; a document whose last compile failed is an error there."""
    model = _demo(tmp_path, "model")
    edit(model / DOC, "\\end{document}", UNATTACHED + "\\end{document}")
    serve(model, watch=False)
    line = next(ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("loom serve: built "))
    assert "error" not in line, line
    failed = _demo(tmp_path, "failed")
    out = failed / document_build(DOC)
    out.mkdir(parents=True)
    (out / "main.log").write_text("(./main.tex\n! Emergency stop.\nl.9 \\end{document}\n", encoding="utf-8")
    serve(failed, watch=False)
    line = next(ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("loom serve: built "))
    assert line.endswith("; 1 error in your documents; loom lint lists them"), line
    assert any(d["code"] == "loom:compile-failed" and d["class"] == "latex" for d in _published(failed))
    assert {d["class"] for d in _published(failed)} <= set(CLASSES)


def test_a_run_that_makes_no_pdf_is_told_as_one_that_failed() -> None:
    """The server publishes again when a run made no PDF, so the problem its log names reaches the manifest; a run that made one is told as made."""
    made: list[str] = []
    failed: list[str] = []
    results = {
        "bad.tex": CompileResult(False, "pdflatex", Path("."), 12, errors=["! LaTeX Error: no."]),
        "good.tex": CompileResult(True, "pdflatex", Path("."), 0, pdf=Path("good.pdf")),
    }
    c = Compiles(lambda doc, started: results[doc], delay=0.01, made=made.append, failed=failed.append)
    try:
        c.want(["bad.tex", "good.tex"])
        assert c.idle(PATIENCE)
        _until(lambda: bool(made and failed))
        assert (made, failed) == (["good.tex"], ["bad.tex"])
    finally:
        c.stop()


def test_a_compile_the_server_runs_and_that_fails_is_published_on_its_document_until_it_compiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server's own compile of a document fails: the manifest names the document as one that did not compile, in the person's LaTeX; once a save compiles it, the problem is gone."""
    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    monkeypatch.setenv("FAKE_TEX_FAIL_MATCH", "main.tex")
    q = demo(tmp_path)
    s = ServeSession(load_quilt(q), fake_bundle(tmp_path), port=0, compile_masters=True, interval=0.2)
    try:
        s.start()

        def failed() -> list[dict]:  # type: ignore[type-arg]
            return [d for d in _published(q) if d["code"] == "loom:compile-failed"]

        _until(lambda: bool(failed()))
        (d,) = failed()
        assert (d["class"], d["severity"], d["keys"], d["owner"]) == ("latex", "error", [DOC], "person")
        monkeypatch.delenv("FAKE_TEX_FAIL_MATCH")
        edit(q / DOC, "\\end{document}", "Saved again.\n\\end{document}")
        _until(lambda: not failed())
    finally:
        s.stop()
