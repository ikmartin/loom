"""The words check's ratchet (`scripts/checks/words.py`): a component on its list keeps its place when it moves, and a copy made to start a new component leaves its source where it was."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

WORDS = Path(__file__).resolve().parents[2] / "scripts" / "checks" / "words.py"


@pytest.fixture
def words(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("words_check", WORDS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    git("init", "-q")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "t")
    old = tmp_path / "viewer" / "src" / "Old.svelte"
    old.parent.mkdir(parents=True)
    old.write_text("<p>Some words a person reads here, and more of them.</p>\n" * 20)
    git("add", "-A")
    git("commit", "-qm", "base")
    return module, git, old


def test_a_rename_moves_a_listed_component(words):
    module, git, old = words
    git("mv", "viewer/src/Old.svelte", "viewer/src/New.svelte")
    assert module.moved_since("HEAD", {"viewer/src/New.svelte"}) == {"viewer/src/Old.svelte": "viewer/src/New.svelte"}


def test_a_component_whose_folder_moved_keeps_its_place(words):
    module, git, old = words
    git("mv", "viewer", "client")
    assert module.moved_since("HEAD", {"client/src/Old.svelte"}) == {"viewer/src/Old.svelte": "client/src/Old.svelte"}


def test_a_copy_leaves_its_listed_source_in_place(words):
    module, git, old = words
    (old.parent / "Copy.svelte").write_text(old.read_text())
    git("add", "-A")
    assert module.moved_since("HEAD", {"viewer/src/Old.svelte"}) == {}


def test_a_copy_whose_source_left_the_list_is_a_move(words):
    module, git, old = words
    (old.parent / "Moved.svelte").write_text(old.read_text())
    old.write_text("<script>\n\timport X from './Moved.svelte';\n</script>\n\n<X />\n")
    git("add", "-A")
    assert module.moved_since("HEAD", {"viewer/src/Moved.svelte"}) == {"viewer/src/Old.svelte": "viewer/src/Moved.svelte"}


def test_an_attachment_in_a_tag_is_read(words):
    module, _git, _old = words
    found = module.findings('<div {@attach tip("Every result and what it rests on.")}>x</div>\n')
    assert any("Every result" in w for _, w in found)
