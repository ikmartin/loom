"""The layout's number: a quilt made by `loom init` carries it, one whose `.loom/` lacks it or holds another is refused by every command and reported by `loom doctor`, and a quilt loom has not written into yet is stamped when it is first read."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.layout import NUMBER
from loom.paths import FORMAT
from tests.helpers import ok, refused, run
from tests.unit._quilts import demo


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
