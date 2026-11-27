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


def test_a_link_to_another_quilt_never_becomes_the_anchor(tmp_path: Path) -> None:
    """A history outside `.loom/` whose folder is a link to another quilt: the anchor is the outermost quilt, so the link is refused rather than taken for the other quilt's root."""
    root, other = tmp_path / "q", tmp_path / "other"
    (root / ".loom").mkdir(parents=True)
    (other / ".loom").mkdir(parents=True)
    (root / "hist").symlink_to(other)
    with pytest.raises(own.Planted):
        own.write_text(root / "hist/x.md", "x")
    with pytest.raises(own.Planted):
        own.mkdir(root / "hist/texts")
    assert sorted(p.name for p in other.iterdir()) == [".loom"]


@pytest.mark.parametrize("make", [False, True])
def test_a_folder_renamed_over_while_a_write_walks_is_walked_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make: bool) -> None:  # fmt: skip
    """A concurrent maker renames a folder of its own over the one the write opened (`layout.stamp` does so with `.loom/`): the write walks again by name and makes its file in the folder now there, never in the one gone."""
    root = tmp_path / "q"
    (root / ".loom").mkdir(parents=True)
    real, done = os.open, [False]

    def racing(p: object, flags: int, *args: object, **kw: object) -> int:
        if p == "x.lock" and not done[0]:
            done[0] = True
            (tmp_path / "fresh").mkdir()
            os.rename(tmp_path / "fresh", root / ".loom")
        return real(p, flags, *args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", racing)
    os.close(own.os_open(root / ".loom/x.lock", os.O_RDONLY | os.O_CREAT, 0o666, make=make))
    monkeypatch.undo()
    assert done[0] and (root / ".loom/x.lock").is_file()


def test_two_makers_of_one_folder_at_once_both_write_in_it(tmp_path: Path) -> None:
    """Locks taken at once by many threads in a quilt whose `.loom/local/` is not there yet: each makes its folder or finds the other's, and every lock file is made there."""
    import threading

    from loom.locks import locked

    root = tmp_path / "q"
    errors: list[BaseException] = []

    def take(i: int) -> None:
        try:
            with locked(root / f".loom/local/deep/{i}.lock"):
                pass
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=take, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(list((root / ".loom/local/deep").iterdir())) == 16
