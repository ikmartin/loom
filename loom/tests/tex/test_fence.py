"""TeX tier: the fence around a TeX compile on macOS (`loom.fence`). A file loom compiles reads nothing outside its own folder however it asks, writes nothing outside its run even with TeX's own limit opened, the fence's state is found by trying, and an honest document compiles to the same output fenced and unfenced. Each read and write is tried unfenced too, so a test that holds is one the fence made hold. Skipped where the fence is not up."""

from __future__ import annotations

import os
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


def test_a_link_to_a_file_outside_the_quilt_is_neither_read_nor_written_by_loom_s_own_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link in the document's folder to a file outside the quilt is left out of a fenced stage, and copied, never kept as a link, into an unfenced one: loom's own HTML steps, which run outside the fence, then neither read the file into what they keep nor write through the link, as the repair of an unbalanced display once wrote the person's outside file (R2-31)."""
    from loom.tex.tex4ht import compile_html

    outside = _outside(tmp_path)
    part = outside / "part.tex"
    part.write_text(f"{SECRET}\n\\[ x = {{ \\]\n", encoding="utf-8")
    was = part.read_bytes()
    q = tmp_path / "q"
    (q / "drafting").mkdir(parents=True)
    (q / "drafting/part.tex").symlink_to(part)
    (q / "drafting/main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{part}\\end{document}\n", encoding="utf-8"
    )
    compile_html(q, "drafting", "drafting/main.tex", tmp_path / "fenced", envs=[])
    kept = b"".join(p.read_bytes() for p in (tmp_path / "fenced").rglob("*") if p.is_file())
    assert SECRET.encode() not in kept
    assert part.read_bytes() == was
    monkeypatch.setenv(fence.OFF, "off")
    compile_html(q, "drafting", "drafting/main.tex", tmp_path / "unfenced", envs=[])
    assert part.read_bytes() == was


def test_a_file_the_fence_kept_out_is_said_as_that_by_a_fenced_compile(tmp_path: Path) -> None:
    """A link in the document's folder to a file outside the quilt fails a fenced compile, PDF and HTML alike, with the fence named as the reason and not with TeX's "not found"."""
    from loom.tex.tex4ht import compile_html

    outside = _outside(tmp_path)
    q = tmp_path / "q"
    (q / "drafting").mkdir(parents=True)
    (q / "drafting/part.tex").symlink_to(outside / "secret.tex")
    (q / "drafting/main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{part}\\end{document}\n", encoding="utf-8"
    )
    said = "the fence kept TeX from reading part.tex, which is outside the quilt; put a copy of it in the document's folder"
    res = compile_document(q, "drafting", "drafting/main.tex", tmp_path / "pdf")
    assert not res.ok and "not found" in res.errors[0] and res.first_error == said
    page = compile_html(q, "drafting", "drafting/main.tex", tmp_path / "html", envs=[])
    assert page.first_error == said


@pytest.mark.parametrize("where", [".git/config", ".loom/records/kept.txt"])
def test_a_link_into_a_dot_named_folder_of_the_quilt_is_left_out_of_a_fenced_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    """A link in the document's folder into `.git` or `.loom` reaches a file of the quilt that no document is: a fenced stage leaves it out, so a remote's credentials never reach the log; unfenced it is copied, as before the fence (R2-35)."""
    q = tmp_path / "q"
    (q / "drafting").mkdir(parents=True)
    target = q / where
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"url = https://someone:{SECRET}@example.org/repo\n", encoding="utf-8")
    (q / "drafting/leak.txt").symlink_to(os.path.relpath(target, q / "drafting"))
    body = "\\newread\\r\\openin\\r=leak.txt \\ifeof\\r\\else\\read\\r to\\x\\typeout{GOT[\\x]}\\closein\\r\\fi"
    (q / "drafting/main.tex").write_text(
        f"\\documentclass{{article}}\\begin{{document}}x{body}\\end{{document}}\n", encoding="utf-8"
    )

    def log(out: Path) -> str:
        res = compile_document(q, "drafting", "drafting/main.tex", out, halt_on_error=False)
        return (res.log.read_text(encoding="utf-8", errors="replace") if res.log else "") + res.stdout

    assert SECRET not in log(tmp_path / "fenced")
    monkeypatch.setenv(fence.OFF, "off")
    assert SECRET in log(tmp_path / "unfenced"), "unfenced, the link is copied as before, or the test proves nothing"


def test_a_lualatex_document_compiles_fenced_with_a_cache_of_loom_s_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LuaTeX's font loader needs a cache it can write: a fenced run is given one of its own, cloned from loom's seed, whose font database loom made first (`fence.run_var`), apart from the person's TeX cache, and a lualatex document compiles to the same aux fenced and unfenced (R2-33)."""
    q = tmp_path / "q"
    q.mkdir()
    (q / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\section{One}\\label{s}See \\ref{s}.\\end{document}\n",
        encoding="utf-8",
    )

    def aux(out: Path) -> bytes:
        res = compile_document(q, "", "main.tex", out, engine="lualatex", halt_on_error=False)
        assert res.pdf is not None and res.aux is not None, res.first_error
        return res.aux.read_bytes()

    fenced = aux(tmp_path / "fenced")
    assert (fence.texmf_var() / fence.NAMES).is_file(), "loom made the seed's font database before the fenced run"
    monkeypatch.setenv(fence.OFF, "off")
    assert aux(tmp_path / "unfenced") == fenced


def test_what_a_fenced_run_writes_in_its_tex_cache_reaches_neither_loom_s_seed_nor_a_later_run(tmp_path: Path) -> None:
    """A fenced run's TeX cache is a clone of loom's seed in the run's own folder (`fence.run_var`), so a file a document plants there, as compiled Lua a later LuaTeX would load, goes with the run: the seed, which only loom writes, never holds it, and the next fenced run does not find it (R2-33's remark)."""
    q = tmp_path / "q"
    q.mkdir()
    planted = "os.getenv('TEXMFVAR') .. '/luatex-cache/planted.lua'"
    plant = f"local f = io.open({planted}, 'w') if f then f:write('return 1') f:close() texio.write_nl('PLANTED') end"
    look = f"if io.open({planted}) then texio.write_nl('SEEN') else texio.write_nl('UNSEEN') end"

    def log(name: str, lua: str) -> str:
        (q / f"{name}.tex").write_text(
            f"\\documentclass{{article}}\\begin{{document}}x\\directlua{{{lua}}}\\end{{document}}\n", encoding="utf-8"
        )
        res = compile_document(q, "", f"{name}.tex", tmp_path / name, engine="lualatex", halt_on_error=False)
        assert res.log is not None, res.first_error
        return res.log.read_text(encoding="utf-8", errors="replace")

    assert "PLANTED" in log("plant", plant), "the document could write its own cache, or the test proves nothing"
    assert not [p for p in fence.texmf_var().rglob("planted.lua")]
    assert "UNSEEN" in log("look", look)
