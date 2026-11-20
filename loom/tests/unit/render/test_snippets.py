"""What the snippet cache remembers of a text TeX did not make: TeX's refusal of the text, kept; a failure of the machine's (a run that stopped saying nothing, one out of time, no TeX to run), kept nowhere and noted `uses.PASSING`, so that nothing made from it outlives the build."""

from __future__ import annotations

from pathlib import Path

import pytest

import loom.render.snippets as snippets
from loom.render.snippets import Snippet, _Run, render_snippets
from loom.render.uses import PASSING, noting

PREAMBLE = "\\documentclass{article}"


def made(*args: object) -> _Run:
    """A run of a working TeX4ht: each text made, but one that says `\\oops`, refused as TeX refuses it."""
    texts: list[tuple[int, str]] = args[3]  # type: ignore[assignment]
    return _Run(
        {i: Snippet(None, "Undefined control sequence") if "oops" in t else Snippet(f"<p>{t}</p>") for i, t in texts},
        None,
        True,
    )


@pytest.mark.parametrize("stopped", ["TeX4ht made no page: it said nothing", "make4ht timed out after 600 seconds"])
def test_a_run_stopped_for_the_machines_sake_is_kept_nowhere_and_passing(
    tmp_path: Path, stopped: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snippets, "_one_run", lambda *args: _Run({}, None, False, stopped))
    cache = tmp_path / "snippets"
    with noting() as noted:
        out = render_snippets(tmp_path, "", PREAMBLE, ["Some words."], cache)
    assert out.made[0].html is None and not cache.exists() and PASSING in noted


def test_a_text_tex_refused_is_kept_and_nothing_is_passing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snippets, "_one_run", made)
    cache = tmp_path / "snippets"
    with noting() as noted:
        out = render_snippets(tmp_path, "", PREAMBLE, ["Some words.", "\\oops"], cache)
    assert [s.html for s in out.made] == ["<p>Some words.</p>", None]
    assert len(list(cache.glob("*.failed"))) == 1 and PASSING not in noted


def test_without_tex_a_text_not_made_before_is_passing_and_one_made_before_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snippets, "_one_run", made)
    cache = tmp_path / "snippets"
    render_snippets(tmp_path, "", PREAMBLE, ["Some words."], cache)
    with noting() as before:
        assert render_snippets(tmp_path, "", PREAMBLE, ["Some words."], cache, tex=False).made[0].cached
    with noting() as new:
        assert render_snippets(tmp_path, "", PREAMBLE, ["Other words."], cache, tex=False).made[0].html is None
    assert PASSING not in before and PASSING in new
