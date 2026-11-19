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
    """The server's own compile of a document fails: the manifest names the document as one that did not compile, in the person's LaTeX; once a save compiles it, the problem is gone. The quilt holds that one document, so no other compile's rebuild publishes the failure in its stead."""
    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    monkeypatch.setenv("FAKE_TEX_FAIL_MATCH", "main.tex")
    q = demo(tmp_path)
    (q / "drafting" / "outline.tex").unlink()
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


#: A latexmk that writes the start of a log where it is told to write and then runs on, as a long compile does: what a run cut short leaves behind.
SLOW = """import sys, time
from pathlib import Path
out = next(a.split("=", 1)[1] for a in sys.argv if a.startswith("-outdir="))
Path(out, Path(sys.argv[-1]).stem + ".log").write_text("This is a run cut short\\n", encoding="utf-8")
time.sleep(60)
"""


def _slow_latexmk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    import sys

    bin_dir = tmp_path / "slow-bin"
    bin_dir.mkdir()
    (bin_dir / "latexmk").write_text(f"#!{sys.executable}\n{SLOW}", encoding="utf-8")
    (bin_dir / "latexmk").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_a_run_stopped_mid_compile_leaves_the_last_whole_compile_s_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document that did not compile, and the server stopped while it compiles again: its log is the last whole compile's still, so lint still says it did not compile, and nothing is published once the server is stopping."""
    from loom.render.compiles import compile_problems
    from loom.scan.scan import scan

    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    q = demo(tmp_path)
    (q / "drafting" / "outline.tex").unlink()
    out = q / document_build(DOC)
    out.mkdir(parents=True)
    failed = "(./main.tex\n! Undefined control sequence.\nl.9 \\slowerror\n"
    (out / "main.log").write_text(failed, encoding="utf-8")
    _slow_latexmk(tmp_path, monkeypatch)
    s = ServeSession(load_quilt(q), fake_bundle(tmp_path), port=0, compile_masters=True, interval=0.2)
    s.start()
    try:
        assert s.compiles is not None
        _until(lambda: any(p is not None for p in s.compiles._running.values()))
        _until(lambda: any(out.parent.glob(".main-*.run-*/main.log")))  # the run has written the start of its log
    finally:
        s.stop()
    stopped = time.time()
    time.sleep(1)
    assert (out / "main.log").read_text(encoding="utf-8") == failed
    assert [d.code for d in compile_problems(scan(load_quilt(q)))] == ["loom:compile-failed"]
    assert (q / MANIFEST).stat().st_mtime < stopped, "published after the server was stopped"
    assert DOC not in s.compiles.state()  # the run cut short is no verdict


def test_a_compile_stopped_by_hand_moves_nothing_into_its_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`stop_run` on a compile in flight: the run is said to be stopped, and the compile folder keeps what it held."""
    import threading

    from loom.tex.runner import compile_document, stop_run

    q = demo(tmp_path)
    out = q / document_build(DOC)
    out.mkdir(parents=True)
    (out / "main.log").write_text("the last whole compile\n", encoding="utf-8")
    _slow_latexmk(tmp_path, monkeypatch)
    procs: list = []  # type: ignore[type-arg]
    results: list[CompileResult] = []
    t = threading.Thread(target=lambda: results.append(compile_document(q, "drafting", DOC, out, started=procs.append)))
    t.start()
    _until(lambda: bool(procs) and any(out.parent.glob(".main-*.run-*/main.log")))
    stop_run(procs[0])
    t.join(PATIENCE)
    (res,) = results
    assert res.stopped and res.pdf is None and res.log is None
    assert (out / "main.log").read_text(encoding="utf-8") == "the last whole compile\n"
