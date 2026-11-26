"""Lean tier: loom's own check with the real toolchain, fenced, on a project that needs no Mathlib. What Lean said is read from the build and recorded as loom's; a module that reaches outside the project gets nothing and its result reads as Lean did not accept it; a changed Lean file or statement stops the record standing. Skipped where the toolchain loom pins is not installed or the fence is not up."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from loom import fence
from loom.evidence.log import replay
from loom.evidence.status import files_unchanged, status
from loom.evidence.web import DraftWeb, Joined, LibraryWeb
from loom.formal import check, install, switch
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import showcase

pytestmark = [pytest.mark.lean, pytest.mark.skipif(fence.lean_state() is not None, reason="the fence is not up here")]

SECRET = "LEANFENCESECRET4d1e"

PROVED = """import Loom

namespace Formal

@[loom "sh-0003"]
def double (n : Nat) : Nat := n + n

theorem double_eq (n : Nat) : double n = 2 * n := by
  unfold double; omega

@[loom "sh-0007"]
theorem double_even (n : Nat) : double n % 2 = 0 := by
  rw [double_eq]; omega

end Formal
"""

SORRY = """import Loom

@[loom "sh-0004"]
theorem Formal.unfinished : 1 = 2 := by sorry
"""


def _escape(outside: Path) -> str:
    return f"""import Loom

#eval do
  let s ← IO.FS.readFile "{outside / "secret.txt"}"
  IO.println s

#eval IO.FS.writeFile "{outside / "written.txt"}" "{SECRET}"

@[loom "sh-0002"]
theorem Formal.escaped : True := trivial
"""


def _manifest() -> str:
    return (
        json.dumps(
            {"version": "1.3.0", "packagesDir": ".lake/packages", "packages": [], "name": "formal", "lakeDir": ".lake"}
        )
        + "\n"
    )


@pytest.fixture
def quilt(tmp_path: Path) -> Path:
    """The showcase with formalization on and a Lean project of loom's shape that requires nothing."""
    q = showcase(tmp_path)
    switch.turn_on(q)
    proj = install.project(q)
    install.make_project(proj)
    (proj / "lakefile.toml").write_text(
        f'name = "formal"\ndefaultTargets = ["{install.LIBRARY}"]\n\n[[lean_lib]]\nname = "{install.MARKER_MODULE}"\n\n[[lean_lib]]\nname = "{install.LIBRARY}"\n',
        encoding="utf-8",
    )
    (proj / "lake-manifest.json").write_text(_manifest(), encoding="utf-8")
    (proj / "Formal").mkdir()
    (proj / "Formal" / "Double.lean").write_text(PROVED, encoding="utf-8")
    return q


def _lean(q: Path, label: str) -> str:
    drafts = DraftWeb(scan(load_quilt(q)))
    [here] = drafts.heres(label)
    return status(replay(q), Joined(drafts, LibraryWeb(q)), here, lean_now=files_unchanged(q)).lean


def test_loom_checks_the_lean_itself_and_records_what_it_saw(quilt: Path) -> None:
    """The real build, probe and replay, fenced: the theorem marked for sh-0007 is proved on standard axioms, the definition it uses is stated as sh-0003's and listed among its uses, the lemma between them supports it; a second check records nothing new."""
    done = check.check(quilt)
    assert sorted(done.written) == ["sh-0003", "sh-0007"] and done.errors == [] and done.unknown == []
    [record] = replay(quilt).about("label", "sh-0007", of="lean")
    assert record.by.kind == "loom" and record.get("ok") is True and record.get("replay")["exit"] == 0
    rows = {d["name"]: d for d in record.get("declarations")}
    assert rows["Formal.double_even"]["role"] == "states" and rows["Formal.double_even"]["sorry"] is False
    assert rows["Formal.double_eq"]["role"] == "supports"
    assert rows["Formal.double"]["names"] == {"label": "sh-0003"}
    assert set(rows["Formal.double_even"]["axioms"]) <= {"propext", "Classical.choice", "Quot.sound"}
    assert [u.get("label") for u in record.get("uses")] == ["sh-0003"]
    assert _lean(quilt, "sh-0007") == "unattested"
    assert check.check(quilt).written == []


def test_a_changed_lean_file_or_statement_stops_the_record_standing(quilt: Path) -> None:
    check.check(quilt)
    lean = install.project(quilt) / "Formal" / "Double.lean"
    lean.write_text(PROVED.replace("n + n", "n + n + 0"), encoding="utf-8")
    assert _lean(quilt, "sh-0007") == "rerun"
    lean.write_text(PROVED, encoding="utf-8")
    assert _lean(quilt, "sh-0007") == "unattested"
    node = quilt / "drafting" / "nodes" / "sh-0007.tex"
    node.write_text(node.read_text(encoding="utf-8").replace("some integer", "any integer"), encoding="utf-8")
    assert _lean(quilt, "sh-0007") == "rerun"


def test_a_sorry_is_recorded_and_reads_failed(quilt: Path) -> None:
    (install.project(quilt) / "Formal" / "Unfinished.lean").write_text(SORRY, encoding="utf-8")
    check.check(quilt)
    [record] = replay(quilt).about("label", "sh-0004", of="lean")
    assert record.get("declarations")[0]["sorry"] is True
    assert _lean(quilt, "sh-0004") == "failed"


def test_lean_reaching_outside_the_project_gets_nothing(quilt: Path, tmp_path: Path) -> None:
    """A module whose elaboration reads a file outside the project and writes one there gets neither: the fence refuses both, the build fails on that module, the secret is in nothing loom said or kept, and with no build of it loom records nothing of the result it marks, while the rest are recorded."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(SECRET + "\n", encoding="utf-8")
    (install.project(quilt) / "Formal" / "Escape.lean").write_text(_escape(outside), encoding="utf-8")
    done = check.check(quilt)
    assert not (outside / "written.txt").exists()
    assert SECRET not in (quilt / ".loom" / "records" / "evidence" / "log.jsonl").read_text(encoding="utf-8")
    said = [e for e in done.errors if "Escape.lean" in e]
    assert said and all(SECRET not in e for e in said) and any("not permitted" in e for e in said), done.errors
    assert replay(quilt).about("label", "sh-0002", of="lean") == []
    assert sorted(done.written) == ["sh-0003", "sh-0007"]
    # unfenced, the same module reads the secret and writes outside, or the test proves nothing
    lake = install.toolchain_folder(install.TOOLCHAIN) / "bin" / "lake"
    ran = subprocess.run([str(lake), "env", "lean", "Formal/Escape.lean"], cwd=install.project(quilt), capture_output=True, text=True, check=False)  # fmt: skip
    assert SECRET in ran.stdout and (outside / "written.txt").exists()
