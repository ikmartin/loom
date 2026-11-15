"""Loom's own TeX: which TeX a run uses, installing it from an archive, the package tool's deadline and repository, and a compile that fetches what it lacks, with no network.

Each case builds a fake installation (`fake_loom_tex.py`) at `LOOM_TEX_DIR`; HOME is the suite's isolated one, so the person's own TeX is the fake toolchain on PATH.
"""

from __future__ import annotations

import os
import sys
import tarfile
import time
from pathlib import Path

import pytest

from loom.tex import missing, private
from loom.tex.runner import compile_tex

FAKE = Path(__file__).with_name("fake_loom_tex.py")
PLATFORM = "universal-darwin"
#: The repository's packages and the files each holds.
REPOSITORY = {
    "latex-bin": ["article.cls", "latexmk", "pdftex"],
    "stmaryrd": ["stmaryrd.sty"],
    "amscls": ["amsart.cls"],
    "spath3": ["tikzlibraryspath3.code.tex"],
    "dvips": ["tex.pro"],
    "ec": ["tcrm1200.tfm"],
    "cm-super": ["sfrm1200.pfb"],
    "biber": ["biber"],
    "tools-dev": ["array.sty"],
    "tools": ["array.sty"],
}


def make_tex(root: Path, *, installed: tuple[str, ...] = ("latex-bin",)) -> Path:
    """A fake installation of loom's TeX at `root`, holding `installed`; returns its bin directory."""
    bin_ = root / "bin" / PLATFORM
    bin_.mkdir(parents=True)
    body = FAKE.read_text(encoding="utf-8")
    for tool in ("tlmgr", "kpsewhich", "latexmk", "pdftex", "pdflatex"):
        (bin_ / tool).write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        (bin_ / tool).chmod(0o755)
    tlpkg = root / "tlpkg"
    tlpkg.mkdir()
    (tlpkg / "texlive.tlpdb.main.fake").write_text(
        "".join(
            f"name {p}\nrunfiles size=1\n" + "".join(f" texmf-dist/x/{f}\n" for f in fs) for p, fs in REPOSITORY.items()
        ),
        encoding="utf-8",
    )
    (tlpkg / "texlive.tlpdb").write_text("".join(f"name {p}\n" for p in installed), encoding="utf-8")
    (root / "have.txt").write_text("\n".join(f for p in installed for f in REPOSITORY[p]) + "\n", encoding="utf-8")
    (root / "release-texlive.txt").write_text("TeX Live 2026 (TinyTeX)\n", encoding="utf-8")
    return bin_


@pytest.fixture
def loomtex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Loom's TeX installed at a fresh `LOOM_TEX_DIR`, a repository that answers, and a cleared index; returns the root."""
    root = tmp_path / "data" / "tex"
    make_tex(root)
    monkeypatch.setenv("LOOM_TEX_DIR", str(root))
    monkeypatch.setattr(private, "_answers", lambda url, timeout=10: True)
    monkeypatch.setattr(missing, "_INDEX", None)
    monkeypatch.setattr(missing, "_PREFLIGHTED", set(), raising=False)
    env = {"PATH": os.environ["PATH"]}
    private.activate(env)  # as the CLI does at start
    monkeypatch.setenv("PATH", env["PATH"])
    return root


def tlmgr_log(root: Path) -> list[str]:
    log = root / "tlmgr.log"
    return log.read_text(encoding="utf-8").splitlines() if log.is_file() else []


def write_doc(d: Path, body: str) -> str:
    d.mkdir(parents=True, exist_ok=True)
    (d / "paper.tex").write_text(
        f"\\documentclass{{article}}\n{body}\n\\begin{{document}}\nHi.\n\\end{{document}}\n", encoding="utf-8"
    )
    return "paper.tex"


# ---- which TeX ------------------------------------------------------------------------


def test_loom_tex_is_used_and_put_first_on_the_path(loomtex: Path) -> None:
    env = {"PATH": "/usr/bin:/bin"}
    tex = private.activate(env)
    assert (tex.kind, tex.year) == (private.LOOM, 2026)
    assert env["PATH"].split(os.pathsep)[0] == str(loomtex / "bin" / PLATFORM)
    assert tex.label == "loom's TeX (TeX Live 2026)"


def test_activating_twice_does_not_grow_the_path(loomtex: Path) -> None:
    env = {"PATH": "/usr/bin:/bin"}
    private.activate(env)
    once = env["PATH"]
    private.activate(env)
    assert env["PATH"] == once


def test_the_person_can_keep_their_own_tex(loomtex: Path, tmp_path: Path) -> None:
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "loom" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[tex]\nuse = "mine"\n', encoding="utf-8")
    tex = private.active()
    assert tex.kind == private.MINE  # the suite's fake toolchain on PATH
    assert not private.can_fetch()  # loom never installs into the person's TeX


def test_with_no_loom_tex_the_persons_is_used_and_with_neither_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "absent"))
    assert private.active().kind == private.MINE
    assert private.active({"PATH": str(tmp_path)}).kind == private.NONE
    env = {"PATH": "/usr/bin"}
    private.activate(env)
    assert env["PATH"] == "/usr/bin"


def test_the_persons_own_tree_is_read_only_when_they_say(loomtex: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEXMFHOME")
    assert "TEXMFHOME" not in private.tex_vars()
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "loom" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("[tex]\nhome_tree = true\n", encoding="utf-8")
    assert private.tex_vars()["TEXMFHOME"].endswith("texmf")


# ---- installing ----------------------------------------------------------------------


def archive_of(tmp_path: Path, name: str = "tex.tar.xz") -> Path:
    src = tmp_path / "made" / "TinyTeX"
    make_tex(src)
    out = tmp_path / name
    with tarfile.open(out, "w:xz") as tar:
        tar.add(src, arcname="TinyTeX")
    return out


def test_install_unpacks_an_archive_into_loom_tex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "data" / "tex"))
    tex = private.install(str(archive_of(tmp_path)))
    assert tex.kind == private.LOOM and private.works()
    assert private.read_state()["year"] == private.YEAR
    assert private.stamp() == "loom:2026:0"


def test_a_checksum_that_does_not_match_installs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "data" / "tex"))
    archive = archive_of(tmp_path)
    Path(f"{archive}.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
    with pytest.raises(OSError, match="checksum"):
        private.install(str(archive))
    assert private.loom_bin() is None


def test_repair_installs_when_absent_and_reports_nothing_to_do_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "data" / "tex"))
    monkeypatch.setenv("LOOM_TEX_ARCHIVE", str(archive_of(tmp_path)))
    monkeypatch.setattr(private, "SEED", ("latex-bin",))
    first = private.repair()
    assert first.ok and first.steps == ["installed loom's TeX"]
    assert private.repair().steps == ["loom's TeX answers; nothing to repair"]


def test_repair_puts_back_a_seed_package_that_went_missing(loomtex: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(private, "SEED", ("latex-bin", "stmaryrd"))
    done = private.repair()
    assert done.ok and done.steps == ["installed 1 missing packages"]
    assert any(line.endswith("install stmaryrd") for line in tlmgr_log(loomtex))


# ---- the package tool -------------------------------------------------------------------


def test_tlmgr_is_killed_past_its_deadline(loomtex: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_TLMGR_HANG", "1")
    began = time.monotonic()
    run = private.tlmgr(["install", "stmaryrd"], timeout=1)
    assert run.code == 124 and time.monotonic() - began < 10


def test_the_frozen_repository_wins_once_it_answers_and_the_choice_is_kept_a_day(
    loomtex: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    def live_only(url: str) -> bool:
        asked.append(url)
        return "tlnet-final" not in url

    assert private.repository(live_only) == private.LIVE[0]
    assert private.repository(lambda url: True) == private.LIVE[0]  # kept for the day
    private._write_state(repository={})
    assert private.repository(lambda url: True) == private.FROZEN[0]
    private._write_state(repository={})
    assert private.repository(lambda url: False) is None


# ---- fetching what a document lacks -----------------------------------------------------


def test_the_preamble_is_read_and_its_packages_fetched_before_the_compile(loomtex: Path, tmp_path: Path) -> None:
    d = tmp_path / "doc"
    res = compile_tex(d, write_doc(d, "\\usepackage{stmaryrd}"), tmp_path / "out")
    assert res.ok and res.fetched == ["stmaryrd"]
    installs = [ln for ln in tlmgr_log(loomtex) if " install " in f" {ln} "]
    assert len(installs) == 1, installs  # one install, before the one compile


def test_a_file_the_log_names_is_fetched_and_the_compile_run_again(
    loomtex: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(missing, "preflight", lambda cwd, tex_rel: missing.Needs())  # what the preamble does not show
    d = tmp_path / "doc"
    res = compile_tex(d, write_doc(d, "\\usepackage{stmaryrd}"), tmp_path / "out")
    assert res.ok and res.fetched == ["stmaryrd"]


def test_offline_the_compile_says_which_package_it_needs(
    loomtex: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(private, "_answers", lambda url, timeout=10: False)
    d = tmp_path / "doc"
    res = compile_tex(d, write_doc(d, "\\usepackage{stmaryrd}"), tmp_path / "out")
    assert not res.ok and res.needed == ["stmaryrd"]
    assert "needs stmaryrd" in res.first_error and "offline" in res.first_error
    assert tlmgr_log(loomtex) == []


def test_the_persons_own_tex_is_never_installed_into(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "absent"))
    got = private.install_packages(["stmaryrd"])
    assert got.installed == [] and got.failed == ["stmaryrd"] and "only into its own" in got.reason


# ---- reading names ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "said,package",
    [
        ("! LaTeX Error: File `stmaryrd.sty' not found.", "stmaryrd"),
        ("Package `amsart' not installed, or version too old?", None),
        ("I did not find the tikz library 'spath3'. I looked for files named tikzlibraryspath3.code.tex", "spath3"),
        ("! Font OT1/ptm/m/n/12=tcrm1200 at 12.0pt not loadable: Metric (TFM) file not found.", "ec"),
        ("WARNING: PostScript header file tex.pro not found", "dvips"),
        ("!pdfTeX error: pdflatex (file tcrm1200): Font tcrm1200 at 600 not found", "metafont"),
        ("! pdfTeX error (font expansion): auto expansion is only possible with scalable fonts.", "cm-super"),
        ("sh: biber: command not found", "biber"),
    ],
)
def test_each_form_a_missing_file_takes_names_its_package(said: str, package: str | None) -> None:
    files = {f: p for p, fs in REPOSITORY.items() for f in fs}
    needs = missing.from_log(said, files=files)
    assert (package in needs.packages) if package else not needs.packages, needs


def test_the_database_maps_files_to_packages_preferring_the_released_one() -> None:
    text = (
        "name tools-dev\nrunfiles size=1\n texmf-dist/tex/latex/tools/array.sty\n\n"
        "name tools\nrunfiles size=1\n texmf-dist/tex/latex/tools/array.sty\n\n"
        "name biber.universal-darwin\nbinfiles arch=universal-darwin size=1\n bin/universal-darwin/biber\n\n"
        "name texlive.infra\nrunfiles size=1\n tlpkg/TeXLive/TLUtils.pm\n"
    )
    files = missing.parse_database(text)
    assert files == {"array.sty": "tools", "biber": "biber", "TLUtils.pm": "texlive.infra"}


def test_the_preamble_names_class_packages_libraries_style_and_biber(tmp_path: Path) -> None:
    (tmp_path / "local.sty").write_text("\\RequirePackage{stmaryrd}\n", encoding="utf-8")
    (tmp_path / "pre.tex").write_text("\\usetikzlibrary{spath3, arrows.meta}\n", encoding="utf-8")
    (tmp_path / "paper.tex").write_text(
        "\\documentclass[11pt]{amsart}\n\\usepackage{local}\n\\input{pre}\n% \\usepackage{commented}\n"
        "\\usepackage[backend=biber]{biblatex}\n\\begin{document}\n\\usepackage{late}\\bibliographystyle{alpha}\n\\end{document}\n",
        encoding="utf-8",
    )
    got = missing.wanted(tmp_path, "paper.tex")
    assert got == {
        "amsart.cls",
        "stmaryrd.sty",
        "tikzlibraryspath3.code.tex",
        "tikzlibraryarrows.meta.code.tex",
        "biblatex.sty",
        "biber",
        "alpha.bst",
    }


def test_doctor_repair_installs_loom_tex_and_the_report_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from tests.helpers import run

    monkeypatch.setenv("LOOM_TEX_DIR", str(tmp_path / "data" / "tex"))
    monkeypatch.setenv("LOOM_TEX_ARCHIVE", str(archive_of(tmp_path)))
    monkeypatch.setattr(private, "SEED", ("latex-bin",))
    away = tmp_path / "away"
    away.mkdir()
    r = run("doctor", "--repair", "--json", cwd=away)
    tex = next(i for i in json.loads(r.stdout)["items"] if i["name"] == "tex")
    assert (tex["status"], tex["kind"]) == ("ok", "loom"), r.output
    assert "installed loom's TeX" in r.stderr


def test_a_package_that_failed_is_not_tried_again_within_the_hour(loomtex: Path) -> None:
    first = private.install_packages(["no-such-package"])
    assert first.failed == ["no-such-package"]
    runs = len(tlmgr_log(loomtex))
    again = private.install_packages(["no-such-package"])
    assert again.failed == ["no-such-package"] and "within the last hour" in again.reason
    assert len(tlmgr_log(loomtex)) == runs  # no second run of the package tool


def test_a_package_another_run_installed_meanwhile_counts_as_installed(loomtex: Path) -> None:
    private.install_packages(["stmaryrd"])
    runs = len(tlmgr_log(loomtex))
    got = private.install_packages(["stmaryrd"])
    assert got.installed == ["stmaryrd"] and len(tlmgr_log(loomtex)) == runs
