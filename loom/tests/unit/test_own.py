"""`loom.own`: loom's own writes, made, appended, renamed and removed without following a link planted on the way or at the file, and exactly as `Path` makes them where none is."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest

from loom import own


@pytest.fixture
def q(tmp_path: Path) -> tuple[Path, Path]:
    """A quilt with `.loom/records/`, and a folder outside it holding a canary file."""
    root = tmp_path / "q"
    (root / ".loom/records").mkdir(parents=True)
    out = tmp_path / "outside"
    out.mkdir()
    (out / "canary").write_text("canary\n")
    return root, out


def untouched(out: Path) -> bool:
    """The folder outside holds its canary as it was, and nothing else."""
    return sorted(p.name for p in out.iterdir()) == ["canary"] and (out / "canary").read_text() == "canary\n"


WRITERS: dict[str, Callable[[Path], object]] = {
    "write_text": lambda p: own.write_text(p / "canary", "x"),
    "write_text, a new file": lambda p: own.write_text(p / "new", "x"),
    "write_bytes": lambda p: own.write_bytes(p / "new", b"x", make=True),
    "append": lambda p: own.open(p / "canary", "a", encoding="utf-8").close(),
    "r+": lambda p: own.open(p / "canary", "r+").close(),
    "os_open": lambda p: os.close(own.os_open(p / "lock", os.O_RDONLY | os.O_CREAT, 0o666)),
    "mkdir": lambda p: own.mkdir(p / "a" / "b"),
    "unlink": lambda p: own.unlink(p / "canary"),
    "rmtree": lambda p: own.rmtree(p),
    "rmtree below": lambda p: own.rmtree(p / "sub"),
    "replace into": lambda p: own.replace(p.parent / "x", p / "canary"),
    "replace out of": lambda p: own.replace(p / "canary", p.parent / "taken"),
    "copyfile": lambda p: own.copyfile(p.parent / "x", p / "canary"),
}


@pytest.mark.parametrize("what", sorted(WRITERS))
def test_a_folder_on_the_way_that_is_a_link_carries_no_write(q: tuple[Path, Path], what: str) -> None:
    root, out = q
    (out / "sub").mkdir()
    (out / "sub" / "keep").write_text("k")
    (root / ".loom/records/x").write_text("x")
    (root / ".loom/records/l").symlink_to(out, target_is_directory=True)
    with pytest.raises(OSError):
        WRITERS[what](root / ".loom/records/l")
    (out / "sub" / "keep").unlink()
    (out / "sub").rmdir()
    assert untouched(out)


@pytest.mark.parametrize("dangling", [False, True])
def test_a_file_that_is_a_link_is_written_through_by_no_write(q: tuple[Path, Path], dangling: bool) -> None:
    root, out = q
    p = root / ".loom/records/log.jsonl"
    p.symlink_to(out / ("gone" if dangling else "canary"))
    for mode in ("w", "a", "x", "r+"):
        with pytest.raises(OSError):
            own.open(p, mode).close()
    with pytest.raises(own.Planted):
        own.write_text(p, "x")
    with pytest.raises(OSError):
        os.close(own.os_open(p, os.O_RDONLY | os.O_CREAT, 0o666))
    assert untouched(out)


def test_unlink_takes_a_link_itself_and_never_its_target(q: tuple[Path, Path]) -> None:
    root, out = q
    p = root / ".loom/records/l"
    p.symlink_to(out / "canary")
    own.unlink(p)
    assert not p.is_symlink() and untouched(out)


def test_the_loom_folder_itself_a_link_carries_nothing(tmp_path: Path) -> None:
    root, out = tmp_path / "q", tmp_path / "outside"
    root.mkdir()
    (out / "records").mkdir(parents=True)
    (root / ".loom").symlink_to(out)
    with pytest.raises(own.Planted):
        own.write_text(root / ".loom/records/x", "x")
    assert not (out / "records/x").exists()


def test_a_link_above_the_anchor_is_the_person_s_and_followed(tmp_path: Path) -> None:
    real = tmp_path / "disk/q"
    (real / ".loom").mkdir(parents=True)
    (tmp_path / "q").symlink_to(real)
    own.write_text(tmp_path / "q/.loom/a/x", "x", make=True)
    assert (real / ".loom/a/x").read_text() == "x"


@pytest.mark.parametrize("given", [True, False])
def test_a_history_outside_loom_is_anchored_at_its_quilt(tmp_path: Path, given: bool) -> None:
    """`root` given, or found as the folder above holding `.loom/`."""
    root, out = tmp_path / "q", tmp_path / "outside"
    (root / "history").mkdir(parents=True)
    (root / ".loom").mkdir()
    out.mkdir()
    (root / "history/texts").symlink_to(out)
    with pytest.raises(own.Planted):
        own.write_text(root / "history/texts/a.md", "x", root=root if given else None)
    assert not list(out.iterdir())


def test_with_no_link_each_write_is_what_path_writes(q: tuple[Path, Path]) -> None:
    root, _out = q
    d = root / ".loom/records"
    own.mkdir(d / "a/b")
    own.write_text(d / "a/b/t.txt", "one\r\ntwo\n")
    assert (d / "a/b/t.txt").read_bytes() == b"one\r\ntwo\n"
    (d / "p.txt").write_text("p")
    want = stat.S_IMODE((d / "p.txt").stat().st_mode)
    own.write_text(d / "o.txt", "o")
    assert stat.S_IMODE((d / "o.txt").stat().st_mode) == want
    (d / "p.txt").chmod(0o600)
    own.write_text(d / "p.txt", "q")
    assert (d / "p.txt").read_text() == "q" and stat.S_IMODE((d / "p.txt").stat().st_mode) == 0o600
    with own.open(d / "a/b/t.txt", "a", encoding="utf-8") as fh:
        fh.write("three\n")
    assert (d / "a/b/t.txt").read_bytes() == b"one\r\ntwo\nthree\n"
    with pytest.raises(FileExistsError):
        own.open(d / "o.txt", "x")
    own.replace(d / "o.txt", d / "a/o.txt")
    own.copyfile(d / "a/o.txt", d / "c.txt")
    own.unlink(d / "a/o.txt")
    own.unlink(d / "a/o.txt", missing_ok=True)
    assert (d / "c.txt").read_text() == "o"
    own.rmtree(d / "a")
    own.rmtree(d / "a", ignore_errors=True)
    assert sorted(p.name for p in d.iterdir()) == ["c.txt", "p.txt"]
    with pytest.raises(FileNotFoundError):
        own.write_text(d / "none/x", "x")
