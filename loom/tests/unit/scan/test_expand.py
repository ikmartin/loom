import os
import subprocess
from pathlib import Path

import pytest

from loom.scan.expand import expand_master, resolve_inclusion
from loom.scan.sections import find_sections, heading_labels
from loom.scan.source import read_source


def _files(tmp_path: Path, files: dict[str, str]):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return {rel: read_source(tmp_path, rel) for rel in files if rel.endswith(".tex")}


def test_inclusion_input_include_nest_and_span_map(tmp_path: Path) -> None:
    srcs = _files(
        tmp_path,
        {
            "drafting/main.tex": "\\begin{document}\n\\section{A}\n\\input{nodes/x}\n\\nest{nodes/sec}\n\\subsection{B}\nend\n\\end{document}\n",
            "drafting/nodes/x.tex": "\\begin{lemma}\\label{q-0001}\nX\n\\end{lemma}\n",
            "drafting/nodes/sec.tex": "\\section{Nested}\ninner\n\\input{nodes/y.tex}\n",
            "drafting/nodes/y.tex": "deep\n",
        },
    )
    exp = expand_master(srcs["drafting/main.tex"], tmp_path, srcs)
    assert exp.diagnostics == []
    assert set(exp.reached) == {
        "drafting/main.tex",
        "drafting/nodes/x.tex",
        "drafting/nodes/sec.tex",
        "drafting/nodes/y.tex",
    }
    assert [i.child for i in exp.inclusions] == [
        "drafting/nodes/x.tex",
        "drafting/nodes/sec.tex",
        "drafting/nodes/y.tex",
    ]
    assert [i.shift for i in exp.inclusions] == [0, 1, 1]
    for rel, src in srcs.items():
        assert "".join(exp.text[s.exp_start : s.exp_end] for s in exp.segments if s.file == rel) == src.clean
    off = exp.text.index("deep")
    assert exp.locate(off) == ("drafting/nodes/y.tex", 0, 1)
    assert exp.exp_offset("drafting/nodes/y.tex", 0) == off
    units = find_sections(exp, srcs)
    assert [(u.name, u.level, u.title) for u in units] == [
        ("section", 1, "A"),
        ("section", 2, "Nested"),
        ("subsection", 2, "B"),
    ]
    assert units[1].parent is units[0] and units[2].parent is units[0]
    assert units[1].exp_end == units[2].exp_start
    assert units[1].file_end == len(srcs["drafting/nodes/sec.tex"].clean)


def test_inclusion_exact_extension_braceless_and_system(tmp_path: Path) -> None:
    srcs = _files(
        tmp_path,
        {
            "drafting/main.tex": "\\input xy\n\\input{fig.pspdftex}\n\\input{missing-file}\n\\begin{document}\n\\end{document}\n",
        },
    )
    (tmp_path / "drafting" / "fig.pspdftex").write_text("\\begin{picture}(1,1)\\end{picture}\n", encoding="utf-8")
    exp = expand_master(srcs["drafting/main.tex"], tmp_path, srcs)
    problems = {i.name: i.problem for i in exp.inclusions}
    assert problems == {"xy": "system", "fig.pspdftex": "opaque", "missing-file": "missing"}
    assert [d.code for d in exp.diagnostics] == ["missing-include"]
    assert "picture" not in exp.text


def test_inclusion_double_and_cycle(tmp_path: Path) -> None:
    srcs = _files(
        tmp_path,
        {
            "drafting/main.tex": "\\begin{document}\n\\input{a}\n\\input{a}\n\\input{b}\n\\end{document}\n",
            "drafting/a.tex": "A\n",
            "drafting/b.tex": "B\\input{c}\n",
            "drafting/c.tex": "C\\input{b}\n",
        },
    )
    exp = expand_master(srcs["drafting/main.tex"], tmp_path, srcs)
    codes = sorted(d.code for d in exp.diagnostics)
    assert codes == ["double-inclusion", "inclusion-cycle"]
    assert exp.text.count("A\n") == 1


def test_section_label_not_stolen_and_same_line(tmp_path: Path) -> None:
    clean = "\\subsection{Facts}\n\n\n\\begin{proposition}\\label{prop:x}\nP\n\\end{proposition}\n\\section{S}\\label{sec:s}\\label{alias}\n\\section{T}\n  \\label{sec:t}\ntext\n\\section{U}\n\\subsection{V}\\label{sec:v}\n"
    assert heading_labels(clean, clean.index("{Facts}") + 7) == []
    assert heading_labels(clean, clean.index("{S}") + 3) == ["sec:s", "alias"]
    assert heading_labels(clean, clean.index("{T}") + 3) == ["sec:t"]
    assert heading_labels(clean, clean.index("{U}") + 3) == []


def test_kpsewhich_is_probed_once_per_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe is a subprocess run once per unresolved inclusion, and a paper's unresolved names repeat; on the Manolache import it was 86 ms of a 166 ms scan."""
    from loom.scan import expand as expand_mod

    installed = tmp_path / "texmf" / "amsmath.sty"
    installed.parent.mkdir()
    installed.write_text("% amsmath\n")
    calls: list[str] = []

    def fake(cmd, **kw):  # type: ignore[no-untyped-def]
        calls.append(cmd[1])
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{installed}\n", stderr="")

    monkeypatch.setattr(expand_mod.shutil, "which", lambda _n: "/usr/bin/kpsewhich")
    monkeypatch.setattr(expand_mod.subprocess, "run", fake)
    for _ in range(5):
        assert expand_mod._kpsewhich("amsmath.sty", tmp_path) is True
    assert calls == ["amsmath.sty"]
    # another installation on PATH is asked afresh, never answered from the first one's memo
    monkeypatch.setattr(expand_mod.shutil, "which", lambda _n: "/opt/other/kpsewhich")
    assert expand_mod._kpsewhich("amsmath.sty", tmp_path) is True
    assert calls == ["amsmath.sty", "amsmath.sty"]
    monkeypatch.setattr(expand_mod.shutil, "which", lambda _n: None)
    assert expand_mod._kpsewhich("amsmath.sty", tmp_path) is False


class _Kpsewhich:
    """A `kpsewhich` over a person's trees, called through `subprocess.run`: TEXMFHOME searched on disk through any link, a distribution through its `ls-R`, and a folder `TEXINPUTS` names; with a clock `AGAIN` is counted on."""

    def __init__(self, root: Path) -> None:
        self.home, self.dist, self.inputs = root / "texmf", root / "texmf-dist", root / "inputs"
        for folder in (self.home, self.dist, self.inputs):
            folder.mkdir()
        (self.dist / "ls-R").write_text("% ls-R\n")
        self.calls: list[str] = []
        self.now = 0.0

    def run(self, cmd, **kw):  # type: ignore[no-untyped-def]
        self.calls.append(cmd[1])
        name = cmd[1]
        found = [
            *(Path(d) / f for d, _, fs in os.walk(self.home, followlinks=True) for f in fs if f == name),
            *([self.dist / name] if name in (self.dist / "ls-R").read_text().split() else []),
            *([self.inputs / name] if (self.inputs / name).is_file() else []),
        ]
        return subprocess.CompletedProcess(cmd, 0 if found else 1, stdout="".join(f"{f}\n" for f in found), stderr="")


@pytest.fixture
def kpsewhich(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Kpsewhich:
    from loom.scan import expand as expand_mod

    fake = _Kpsewhich(tmp_path)
    monkeypatch.setattr(expand_mod.shutil, "which", lambda _n: "/usr/bin/kpsewhich")
    monkeypatch.setattr(expand_mod.subprocess, "run", fake.run)
    monkeypatch.setattr(expand_mod, "_clock", lambda: fake.now)
    return fake


@pytest.mark.parametrize(
    "how",
    [
        "copied into TEXMFHOME by hand",
        "installed, its ls-R written again",
        "put in a folder TEXMFHOME reaches by a link",
        "put in a folder TEXINPUTS names",
    ],
)
def test_a_file_not_found_is_asked_about_again_after_the_interval(
    tmp_path: Path, kpsewhich: _Kpsewhich, how: str
) -> None:
    """A server goes on scanning after a package arrives, by whatever way: a name `kpsewhich` did not find is asked about again once `AGAIN` seconds have passed, and not before, so a scan between costs no subprocess and walks no tree."""
    from loom.scan.expand import AGAIN

    root = tmp_path / "quilt"
    root.mkdir()
    assert resolve_inclusion(root, "reviewextra") == (None, "missing")
    if how == "copied into TEXMFHOME by hand":
        (kpsewhich.home / "tex" / "latex" / "reviewextra").mkdir(parents=True)
        (kpsewhich.home / "tex" / "latex" / "reviewextra" / "reviewextra.tex").write_text("Words.\n")
    elif how == "installed, its ls-R written again":
        (kpsewhich.dist / "reviewextra.tex").write_text("Words.\n")
        (kpsewhich.dist / "ls-R").write_text("% ls-R\nreviewextra.tex\n")
    elif how == "put in a folder TEXMFHOME reaches by a link":
        mine = tmp_path / "my-styles"
        mine.mkdir()
        (kpsewhich.home / "mine").symlink_to(mine, target_is_directory=True)
        (mine / "reviewextra.tex").write_text("Words.\n")
    else:
        (kpsewhich.inputs / "reviewextra.tex").write_text("Words.\n")
    kpsewhich.now += AGAIN - 1
    assert resolve_inclusion(root, "reviewextra") == (None, "missing")
    assert kpsewhich.calls == ["reviewextra.tex"]
    kpsewhich.now += 1
    assert resolve_inclusion(root, "reviewextra") == (None, "system")
    assert resolve_inclusion(root, "reviewextra") == (None, "system")
    assert kpsewhich.calls == ["reviewextra.tex", "reviewextra.tex"]


def test_a_file_found_is_believed_only_while_it_is_there(tmp_path: Path, kpsewhich: _Kpsewhich) -> None:
    """A package deleted, or removed by `tlmgr`, is missing at the next scan: the file `kpsewhich` named is looked at, and it is asked again when the file has gone."""
    root = tmp_path / "quilt"
    root.mkdir()
    installed = kpsewhich.home / "reviewextra.tex"
    installed.write_text("Words.\n")
    assert resolve_inclusion(root, "reviewextra") == (None, "system")
    assert resolve_inclusion(root, "reviewextra") == (None, "system")
    assert kpsewhich.calls == ["reviewextra.tex"]
    installed.unlink()
    assert resolve_inclusion(root, "reviewextra") == (None, "missing")
    assert kpsewhich.calls == ["reviewextra.tex", "reviewextra.tex"]
