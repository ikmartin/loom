"""A figure's bounding box is asked of `extractbb` once a process for the same figure: every TeX4ht run stages a fresh copy of the folder, and asking again of every figure cost seconds a save on a paper with many."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loom.tex import tex4ht


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A stand-in `extractbb` that writes an `.xbb` naming the figure's bytes, and the names it was asked about."""
    calls: list[str] = []

    def run(argv: list[str], *, cwd: Path, **_kw: object) -> subprocess.CompletedProcess[bytes]:
        name = argv[1]
        calls.append(name)
        fig = Path(cwd) / name
        if fig.read_bytes() == b"broken":
            return subprocess.CompletedProcess(argv, 1)
        fig.with_suffix(".xbb").write_bytes(b"%%BoundingBox: " + fig.read_bytes() + b"\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(tex4ht, "_XBB", {})
    monkeypatch.setattr(tex4ht.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(tex4ht.subprocess, "run", run)
    monkeypatch.setattr(tex4ht, "tex_env", lambda: {})
    return calls


def stage(root: Path, figures: dict[str, bytes]) -> Path:
    root.mkdir()
    for name, data in figures.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data)
    return root


def test_a_figure_seen_before_is_not_asked_again_and_gets_the_same_box(tmp_path: Path, asked: list[str]) -> None:
    first = stage(tmp_path / "one", {"a.pdf": b"A", "figs/b.png": b"B", "notes.txt": b"x"})
    tex4ht._bounding_boxes(first)
    assert sorted(asked) == ["a.pdf", "b.png"]
    second = stage(tmp_path / "two", {"a.pdf": b"A", "figs/b.png": b"B"})
    tex4ht._bounding_boxes(second)
    assert sorted(asked) == ["a.pdf", "b.png"]
    assert (second / "a.xbb").read_bytes() == (first / "a.xbb").read_bytes()
    assert (second / "figs" / "b.xbb").read_bytes() == b"%%BoundingBox: B\n"


def test_a_changed_figure_is_asked_again(tmp_path: Path, asked: list[str]) -> None:
    tex4ht._bounding_boxes(stage(tmp_path / "one", {"a.pdf": b"A"}))
    again = stage(tmp_path / "two", {"a.pdf": b"A, redrawn"})
    tex4ht._bounding_boxes(again)
    assert asked == ["a.pdf", "a.pdf"]
    assert (again / "a.xbb").read_bytes() == b"%%BoundingBox: A, redrawn\n"


def test_a_figure_of_another_name_is_asked_about_itself(tmp_path: Path, asked: list[str]) -> None:
    tex4ht._bounding_boxes(stage(tmp_path / "one", {"a.pdf": b"A"}))
    other = stage(tmp_path / "two", {"c.pdf": b"A"})
    tex4ht._bounding_boxes(other)
    assert asked == ["a.pdf", "c.pdf"]
    assert (other / "c.xbb").is_file()


def test_a_figure_extractbb_failed_on_leaves_the_folder_as_a_failing_run_does(tmp_path: Path, asked: list[str]) -> None:
    tex4ht._bounding_boxes(stage(tmp_path / "one", {"a.pdf": b"broken"}))
    again = stage(tmp_path / "two", {"a.pdf": b"broken"})
    tex4ht._bounding_boxes(again)
    assert asked == ["a.pdf"]
    assert not (again / "a.xbb").exists()


def test_with_no_extractbb_nothing_is_asked(tmp_path: Path, asked: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tex4ht.shutil, "which", lambda name: None)
    tex4ht._bounding_boxes(stage(tmp_path / "one", {"a.pdf": b"A"}))
    assert asked == []
