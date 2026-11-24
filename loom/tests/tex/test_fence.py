"""TeX tier: the fence around a TeX compile on macOS (`loom.fence`). A file loom compiles reads nothing outside its own folder however it asks, writes nothing outside its run even with TeX's own limit opened, the fence's state is found by trying, and an honest document compiles to the same output fenced and unfenced. Each read and write is tried unfenced too, so a test that holds is one the fence made hold. Skipped where the fence is not up."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from loom import fence
from loom.tex import runner
from loom.tex.runner import compile_document

pytestmark = [pytest.mark.tex, pytest.mark.skipif(fence.state() is not None, reason="the fence is not up here")]

SECRET = "FENCESECRET7f3a9c"
#: Enough `../` to climb from any staged folder to the root, after which more stay there.
UP = "../" * 24
REPO = Path(__file__).resolve().parents[3]


def _outside(tmp_path: Path) -> Path:
    """A folder outside every quilt and run, holding the secret as a TeX file that prints it and as plain text."""
    out = tmp_path / "outside"
    out.mkdir(exist_ok=True)
    (out / "secret.tex").write_text(f"\\typeout{{{SECRET}}}\n", encoding="utf-8")
    (out / "secret.txt").write_text(f"{SECRET}\n", encoding="utf-8")
    return out


def _compile(q: Path, body: str) -> str:
    """Compile a document in the folder `q`, whose body is `body`, as loom compiles a quilt's document; its log and what latexmk printed."""
    q.mkdir(parents=True, exist_ok=True)
    (q / "main.tex").write_text(
        f"\\documentclass{{article}}\\begin{{document}}x{body}\\end{{document}}\n", encoding="utf-8"
    )
    res = compile_document(q, "", "main.tex", q / ".loom/cache/tex/main", halt_on_error=False)
    return (res.log.read_text(encoding="utf-8", errors="replace") if res.log else "") + res.stdout


def _reads(outside: Path) -> dict[str, str]:
    """Each way a document asks for a file outside its folder, as its body."""
    return {
        "openin and read": f"\\newread\\r\\openin\\r={outside}/secret.txt \\ifeof\\r\\else\\read\\r to\\x\\typeout{{GOT[\\x]}}\\closein\\r\\fi",
        "input of an absolute path": f"\\input{{{outside}/secret.tex}}",
        "input of ../": f"\\input{{{UP}{str(outside / 'secret.tex').lstrip('/')}}}",
        "input through a link in its folder": "\\input{link.tex}",
    }


@pytest.mark.parametrize(
    "which", ["openin and read", "input of an absolute path", "input of ../", "input through a link in its folder"]
)
def test_a_document_gets_nothing_of_a_file_outside_its_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    """A document that reads a file outside its folder, by `\\openin` and `\\read`, by `\\input` of an absolute path or of `../`, or through a link its folder holds, gets nothing of it fenced; unfenced the same document reads it, so the fence is what held."""
    outside = _outside(tmp_path)
    q = tmp_path / "q"
    q.mkdir()
    (q / "link.tex").symlink_to(outside / "secret.tex")
    body = _reads(outside)[which]
    assert SECRET not in _compile(q, body)
    monkeypatch.setenv(fence.OFF, "off")
    assert SECRET in _compile(q, body), "unfenced, the document reads the file, or the test proves nothing"


def test_a_write_outside_the_run_fails_with_tex_s_own_limit_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With kpathsea's `openout_any` opened, a document's `\\openout` to a path outside its run writes nothing fenced, and writes unfenced: the fence holds where TeX's own limit does not."""
    outside = _outside(tmp_path)
    monkeypatch.setattr(runner, "LIMITS", {"openout_any": "a", "shell_escape": "p"})
    body = f"\\newwrite\\w\\immediate\\openout\\w={outside}/written.txt\\immediate\\write\\w{{{SECRET}}}\\immediate\\closeout\\w"
    _compile(tmp_path / "q", body)
    assert not (outside / "written.txt").exists()
    monkeypatch.setenv(fence.OFF, "off")
    _compile(tmp_path / "q", body)
    assert (outside / "written.txt").exists(), "unfenced and opened, TeX writes it, or the test proves nothing"


def test_the_fence_s_state_is_found_by_trying(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`state` is None here; `off` when the person sets `LOOM_FENCE=off`; `absent` with no `sandbox-exec`; `leaks` when the profile lets the canary read outside; and `nested` inside another sandbox, which holds no second."""
    assert fence.state() is None
    monkeypatch.setenv(fence.OFF, "off")
    assert fence.state() == "off"
    monkeypatch.delenv(fence.OFF)
    try:
        monkeypatch.setattr(fence, "SANDBOX", str(tmp_path / "no-sandbox-exec"))
        fence._tried.cache_clear()
        assert fence.state() == "absent"
        monkeypatch.setattr(fence, "SANDBOX", "/usr/bin/sandbox-exec")
        wide = tmp_path / "wide.sb"
        wide.write_text("(version 1)\n(allow default)\n", encoding="utf-8")
        monkeypatch.setattr(fence, "PROFILE", wide)
        fence._tried.cache_clear()
        assert fence.state() == "leaks"
    finally:
        monkeypatch.undo()
        fence._tried.cache_clear()
    outer = '(version 1)(allow default)(deny file-write* (literal "/var/empty/loom-fence-outer"))'
    inside = subprocess.run(
        [fence.SANDBOX, "-p", outer, sys.executable, "-c", "from loom import fence; print(fence.state())"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert inside.stdout.strip() == "nested", inside.stdout + inside.stderr


def test_a_folder_whose_path_holds_a_space_a_quote_and_a_parenthesis_compiles_fenced(tmp_path: Path) -> None:
    """A run folder whose path holds a space, a quote and a parenthesis is given to the profile as a parameter, never as its text: an honest document compiles, and a read outside it still gets nothing."""
    outside = _outside(tmp_path)
    q = tmp_path / "a b'c(d)"
    _compile(q, "")
    assert (q / ".loom/cache/tex/main/main.pdf").is_file()
    assert SECRET not in _compile(q, _reads(outside)["input of an absolute path"])


def test_a_fenced_compile_that_fails_is_not_run_again_unfenced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fenced compile that fails is run once, inside the fence, and never again without it, since a file could fail on purpose to get the unfenced run."""
    seen: list[list[str]] = []
    real = subprocess.Popen

    def popen(cmd: list[str], *args: object, **kwargs: object) -> subprocess.Popen[str]:
        seen.append(list(cmd))
        return real(cmd, *args, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    _compile(tmp_path / "q", "\\undefinedcommand")
    latexmk = [cmd for cmd in seen if any(Path(part).name == "latexmk" for part in cmd)]
    assert [cmd[0] for cmd in latexmk] == [fence.SANDBOX], seen


def _kept(root: Path, doc: str, out: Path) -> dict[str, bytes]:
    """Compile `doc` of the quilt at `root` for its PDF, as loom does; what the compile keeps that says what TeX made of it, its aux and its bbl."""
    res = compile_document(root, str(Path(doc).parent), doc, out, halt_on_error=False)
    assert res.aux is not None, res.first_error
    return {p.name: p.read_bytes() for p in sorted(out.iterdir()) if p.suffix in (".aux", ".bbl")}


@pytest.mark.parametrize(
    "doc", ["drafting/main.tex", "drafting/main-atomic.tex", "drafting/sketch.tex", "drafting/talk.tex"]
)
def test_the_showcase_compiles_to_the_same_output_fenced_and_unfenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: str
) -> None:
    """The honest side: each of the showcase's documents compiles fenced to the same aux and bbl as unfenced."""
    q = tmp_path / "q"
    shutil.copytree(REPO / "loom/tests/quilts/showcase", q)
    fenced = _kept(q, doc, tmp_path / "fenced")
    monkeypatch.setenv(fence.OFF, "off")
    assert _kept(q, doc, tmp_path / "unfenced") == fenced


def test_the_showcase_s_html_is_the_same_fenced_and_unfenced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The honest side for the HTML the viewer shows: make4ht makes the same page of the showcase's main document fenced and unfenced."""
    from loom.tex.tex4ht import compile_html

    q = tmp_path / "q"
    shutil.copytree(REPO / "loom/tests/quilts/showcase", q)

    def page(out: Path) -> bytes:
        res = compile_html(q, "drafting", "drafting/main.tex", out, envs=[])
        assert res.html is not None, res.errors
        return res.html.read_bytes()

    fenced = page(tmp_path / "fenced")
    monkeypatch.setenv(fence.OFF, "off")
    assert page(tmp_path / "unfenced") == fenced


def test_a_biblatex_document_compiles_to_the_same_output_fenced_and_unfenced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document that cites with biblatex runs biber, which the fence lets neither write nor read the machine's unpacked copy: the run is given its own clone, and the same aux and bbl come out fenced and unfenced."""
    q = tmp_path / "q"
    q.mkdir()
    (q / "refs.bib").write_text(
        "@book{knuth84, author={Donald Knuth}, title={The TeXbook}, year={1984}}\n", encoding="utf-8"
    )
    (q / "main.tex").write_text(
        "\\documentclass{article}\\usepackage[backend=biber]{biblatex}\\addbibresource{refs.bib}"
        "\\begin{document}See \\cite{knuth84}.\\printbibliography\\end{document}\n",
        encoding="utf-8",
    )
    fenced = _kept(q, "main.tex", tmp_path / "fenced")
    assert "main.bbl" in fenced and b"knuth84" in fenced["main.bbl"]
    monkeypatch.setenv(fence.OFF, "off")
    assert _kept(q, "main.tex", tmp_path / "unfenced") == fenced
