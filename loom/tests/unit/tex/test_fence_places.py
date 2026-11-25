"""What the fence hands its profile, and what loom reads for TeX4ht outside the fence: never a folder that holds the person's files, and xr's external aux only from the quilt."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loom import fence
from loom.tex.tex4ht import external_labels


def _layout(monkeypatch: pytest.MonkeyPatch, kpsewhich: dict[str, str]) -> dict[str, str]:
    """The profile's parameters for a TeX whose kpsewhich names `kpsewhich`."""
    from loom.fence import _TREES

    def ask(argv: list[str], env: dict[str, str]) -> str:
        if argv[0] == "kpsewhich":
            return "\n".join(kpsewhich.get(name, "") for _, name in _TREES) + "\n"
        return ""

    monkeypatch.setattr(fence, "_ask", ask)
    fence._places.cache_clear()
    try:
        return fence._machine()
    finally:
        fence._places.cache_clear()


def test_a_tinytex_in_library_hands_the_profile_its_trees_and_never_library(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A TinyTeX at its default `~/Library/TinyTeX` gives the profile its programs and trees, none of which holds `~/Library`, the home folder or loom's data, where the person's cookies and loom's write tokens are; a TeX whose tree did would make the fence count itself as leaking (R2-34)."""
    home = Path(os.path.realpath(isolated_env))
    tiny = home / "Library/TinyTeX"
    places = _layout(
        monkeypatch,
        {
            "SELFAUTOLOC": str(tiny / "bin/universal-darwin"),
            "SELFAUTOPARENT": str(tiny),
            "TEXMFDIST": str(tiny / "texmf-dist"),
            "TEXMFLOCAL": str(tiny / "texmf-local"),
            "TEXMFSYSVAR": str(tiny / "texmf-var"),
            "TEXMFSYSCONFIG": str(tiny / "texmf-config"),
            "TEXMFHOME": str(home / "Library/texmf"),
        },
    )
    assert places["TEXBIN"] == str(tiny / "bin/universal-darwin") and places["TEXDIST"] == str(tiny / "texmf-dist")
    assert not fence._holds_the_person_s(places), places
    assert fence._holds_the_person_s({**places, "TEXDIST": str(home / "Library")})
    assert fence._holds_the_person_s({**places, "TEXLOCAL": str(home)})


def test_xr_s_external_aux_is_read_only_from_the_quilt(tmp_path: Path) -> None:
    """Loom reads xr's external aux itself, outside the fence, so it reads one only where its real file lies in the quilt: an absolute path or a `../` out of the quilt gives no label (R2-32)."""
    q = tmp_path / "q"
    (q / "a").mkdir(parents=True)
    (q / "a/other.aux").write_text("\\newlabel{inside}{{1}{1}}\n", encoding="utf-8")
    out = tmp_path / "outside"
    out.mkdir()
    (out / "x.aux").write_text("\\newlabel{secret}{{SECRET}{1}}\n", encoding="utf-8")
    text = f"\\externaldocument{{other}}\\externaldocument{{{out}/x}}\\externaldocument{{../../outside/x}}"
    _, lines = external_labels(text, q / "a", q)
    assert any("{inside}" in line for line in lines) and not any("secret" in line for line in lines), lines
