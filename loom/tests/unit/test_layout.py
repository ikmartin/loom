"""The layout's number: a quilt made by `loom init` carries it, one whose `.loom/` lacks it or holds another is refused by every command and reported by `loom doctor`, and a quilt loom has not written into yet is stamped when it is first read."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.layout import NUMBER
from loom.paths import FORMAT
from tests.helpers import ok, refused, run
from tests.unit._quilts import demo


def test_the_shipped_demo_carries_this_looms_number() -> None:
    """`loom init --demo` copies the demo with its own number and stamps nothing, so a demo left in another layout is refused rather than read as this one."""
    import loom

    assert (Path(loom.__file__).parent / "assets" / "demo" / FORMAT).read_text(encoding="utf-8") == f"{NUMBER}\n"


def test_init_and_the_demo_write_the_number(tmp_path: Path) -> None:
    ok("init", str(tmp_path / "fresh"), "--prefix", "zz", "--yes")
    assert (tmp_path / "fresh" / FORMAT).read_text(encoding="utf-8") == f"{NUMBER}\n"
    assert (demo(tmp_path) / FORMAT).read_text(encoding="utf-8") == f"{NUMBER}\n"


@pytest.mark.parametrize(
    ("number", "said"),
    [
        (
            None,
            f"this quilt's .loom/ has no format number, so an older loom made it, and this loom reads format {NUMBER}",
        ),
        ("2\n", f"this quilt's {FORMAT} says 2, and this loom reads format {NUMBER}"),
    ],
)
def test_a_quilt_in_another_layout_is_refused_and_doctor_says_so(tmp_path: Path, number: str | None, said: str) -> None:
    """Read with this layout's names, an older quilt's records would look absent and a second tree would be written beside them, so every command refuses it in one sentence; `loom doctor` reports the same and still checks the machine."""
    q = demo(tmp_path)
    (q / FORMAT).unlink()
    if number is not None:
        (q / FORMAT).write_text(number, encoding="utf-8")
    before = sorted(p.relative_to(q).as_posix() for p in q.rglob("*"))
    refused("status", cwd=q, code=2, match=said)
    refused("build", cwd=q, code=2, match=said)
    assert sorted(p.relative_to(q).as_posix() for p in q.rglob("*")) == before, "nothing is written beside the old tree"
    r = run("doctor", "--json", cwd=q)
    report = json.loads(r.stdout)
    assert r.exit_code == 2
    items = {i["name"]: i for i in report["items"]}
    assert items["format"]["status"] == "fail" and items["format"]["detail"] == said
    assert "python" in report and "author" in items, "the machine is still checked"


def test_a_quilt_loom_has_not_written_into_is_stamped_when_first_read(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text('[quilt]\nname = "q"\nprefix = "qq"\n', encoding="utf-8")
    ok("status", cwd=tmp_path)
    assert (tmp_path / FORMAT).read_text(encoding="utf-8") == f"{NUMBER}\n"


def _load_at(root: str, start: float) -> str:
    """Load the quilt at `root` as soon after `start` as this process can: '' when it opened, else why not."""
    import time

    from loom.scan.quilt import LayoutError, load_quilt

    time.sleep(max(0.0, start - time.time()))
    try:
        load_quilt(Path(root))
    except LayoutError as exc:
        return str(exc)
    return ""


def test_quilts_loaded_at_once_for_the_first_time_all_open(tmp_path: Path) -> None:
    """A server and an agent's server starting together on a new quilt each stamp it; neither ever sees a `.loom/` without its number, or with part of it."""
    import time
    from concurrent.futures import ProcessPoolExecutor

    for n in range(5):
        root = tmp_path / f"q{n}"
        root.mkdir()
        (root / "config.toml").write_text('[quilt]\nname = "q"\nprefix = "qq"\n', encoding="utf-8")
        start = time.time() + 0.5
        with ProcessPoolExecutor(6) as pool:
            said = list(pool.map(_load_at, [str(root)] * 6, [start] * 6))
        assert said == [""] * 6
        assert (root / FORMAT).read_text(encoding="utf-8") == f"{NUMBER}\n"
        assert [p.name for p in root.iterdir() if p.name.startswith(".loom-")] == []


def test_a_stamp_that_loses_the_race_leaves_what_won(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from loom import layout

    real = os.rename

    def first_another(src: str, dst: str) -> None:
        Path(dst).mkdir()
        (Path(dst) / "format").write_text("1\n", encoding="utf-8")
        (Path(dst) / "theirs").write_text("", encoding="utf-8")
        real(src, dst)

    q = tmp_path / "q"
    q.mkdir()
    monkeypatch.setattr(layout.os, "rename", first_another)
    layout.stamp(q)
    assert sorted(p.name for p in (q / ".loom").iterdir()) == ["format", "theirs"]
    assert [p.name for p in q.iterdir()] == [".loom"]
