"""Loom's own check of the quilt's Lean, with the fenced steps standing in: when it refuses and runs nothing, what it records from what the build states, and how its records stop standing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from loom import fence
from loom.evidence.log import replay
from loom.evidence.status import files_unchanged, status
from loom.evidence.web import DraftWeb, Joined, LibraryWeb
from loom.formal import check, install, switch
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import showcase

SATURATION = "Formal/Saturation.lean"
STANDARD = ["Classical.choice", "Quot.sound", "propext"]


def _decl(name: str, kind: str, statement: str, uses: list[str], *, axioms: list[str] | None = None, marker: str | None = None, internal: bool = False, module: str = "Formal.Saturation") -> dict[str, Any]:  # fmt: skip
    return {"name": name, "module": module, "kind": kind, "statement": statement, "axioms": STANDARD if axioms is None else axioms, "uses": uses, "marker": marker, "internal": internal}  # fmt: skip


def _marker(decl: str, names: str) -> dict[str, Any]:
    return _decl(f"{decl}._loom", "abbrev", "", [], axioms=[], marker=names, internal=True)


def _probe(*, sorry: bool = False, extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """What the probe says of a project stating sh-0003, sh-0004 and sh-0007 of the showcase, as the real one said of the trial's Lean."""
    saturated = ["sorryAx", *STANDARD] if sorry else STANDARD
    return {
        "replay": {"exit": 0, "output": ""},
        "modules": {"Loom": [], "Formal": ["Loom", "Formal.Saturation"], "Formal.Saturation": ["Loom"]},
        "declarations": [
            _decl(
                "Formal.divergence",
                "def",
                "def divergence := incoming - outgoing",
                ["Formal.divergence._proof_1"],
                axioms=[],
            ),
            _decl("Formal.divergence._proof_1", "theorem", "", [], axioms=[], internal=True),
            _marker("Formal.divergence", "sh-0003"),
            _decl("Formal.cycleLattice", "def", "def cycleLattice := ker divergence", ["Formal.divergence"]),
            _marker("Formal.cycleLattice", "sh-0004"),
            _decl("Formal.helper", "theorem", "theorem helper", ["Formal.cycleLattice", "Formal.divergence"]),
            _decl(
                "Formal.cycleLattice_saturated",
                "theorem",
                "theorem saturated",
                ["Formal.helper", "Formal.cycleLattice", "Formal.cycleLattice_saturated._simp_1"],
                axioms=saturated,
            ),  # fmt: skip
            _decl("Formal.cycleLattice_saturated._simp_1", "theorem", "", [], axioms=[], internal=True),
            _marker("Formal.cycleLattice_saturated", "sh-0007"),
            *(extra or []),
        ],
    }


@pytest.fixture
def quilt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The showcase with formalization on, a Lean project as loom makes it holding one module, and a toolchain folder standing in."""
    q = showcase(tmp_path)
    switch.turn_on(q)
    proj = install.project(q)
    install.make_project(q)
    (proj / "lake-manifest.json").write_text(json.dumps({"packages": []}), encoding="utf-8")
    (proj / "Formal").mkdir()
    (proj / SATURATION).write_text("import Loom\n-- the trial's Lean\n", encoding="utf-8")
    monkeypatch.setenv("ELAN_HOME", str(tmp_path / "elan"))
    lake = install.toolchain_folder(install.TOOLCHAIN) / "bin" / "lake"
    lake.parent.mkdir(parents=True)
    lake.write_text("", encoding="utf-8")
    monkeypatch.setattr(fence, "lean_state", lambda: None)
    return q


def _steps(monkeypatch: pytest.MonkeyPatch, probe: dict[str, Any], *, build_out: str = "", during: Any = None) -> list[list[str]]:  # fmt: skip
    """Stand in for the fenced steps: the build makes every module's .olean and the probe answers `probe`; each step's command kept."""
    ran: list[list[str]] = []

    def fenced(
        argv: list[str], places: dict[str, str], cwd: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        ran.append(argv)
        out = ""
        if argv[1] == "build" and argv[2] != "--no-build":
            for m in check.modules(cwd).values():
                o = cwd / ".lake" / "build" / "lib" / "lean" / Path(m).with_suffix(".olean")
                o.parent.mkdir(parents=True, exist_ok=True)
                o.write_bytes(b"")
            out = build_out
        if "--run" in argv:
            out = json.dumps(probe)
            if during is not None:
                during()
        return subprocess.CompletedProcess(argv, 1 if "error:" in out else 0, out, "")

    monkeypatch.setattr(check, "_fenced", fenced)
    return ran


def _status(q: Path, label: str) -> Any:
    drafts = DraftWeb(scan(load_quilt(q)))
    [here] = drafts.heres(label)
    return status(replay(q), Joined(drafts, LibraryWeb(q)), here, lean_now=files_unchanged(q))


def test_off_on_this_machine_it_refuses_and_runs_nothing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _steps(monkeypatch, _probe())
    switch.turn_off(quilt)
    with pytest.raises(check.Refused, match="formalization is off"):
        check.check(quilt)
    assert ran == [] and replay(quilt).of_kind("lean") == []


@pytest.mark.parametrize("why", ["absent", "nested", "leaks"])
def test_with_the_fence_down_it_refuses_and_runs_nothing(
    quilt: Path, monkeypatch: pytest.MonkeyPatch, why: str
) -> None:
    """The check runs fenced or not at all: with the fence not up, as in an agent's sandboxed shell, nothing runs and nothing is recorded."""
    ran = _steps(monkeypatch, _probe())
    monkeypatch.setattr(fence, "lean_state", lambda: why)
    with pytest.raises(check.Refused, match=f"the fence is not up \\({why}\\)"):
        check.check(quilt)
    assert ran == [] and replay(quilt).of_kind("lean") == []


def test_every_step_runs_under_the_lean_profile(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each command the check starts goes through `fence.lean_argv`, so none runs outside the fence."""
    started: list[list[str]] = []

    def popen(argv: list[str], **kw: Any) -> Any:
        started.append(argv)
        raise OSError("stop here")

    monkeypatch.setattr(
        fence, "lean_places", lambda **at: {"PROJECT": str(at["project"].resolve()), "DEVDIR": "/var/empty"}
    )
    monkeypatch.setattr(subprocess, "Popen", popen)
    with pytest.raises(OSError):
        check.check(quilt)
    [argv] = started
    assert argv[:3] == [fence.SANDBOX, "-f", str(fence.LEAN_PROFILE)]
    assert f"PROJECT={install.project(quilt).resolve()}" in argv


def test_it_records_what_the_build_states_for_each_result_a_marker_names(
    quilt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One record for each result: its stating declaration, the marked definitions it reaches as stating theirs and listed in `uses`, a declaration that only supports it, none Lean made for another, and every file it rests on; the result then reads as Lean proved it and the person not yet attested it."""
    _steps(monkeypatch, _probe())
    done = check.check(quilt)
    assert sorted(done.written) == ["sh-0003", "sh-0004", "sh-0007"]
    [record] = replay(quilt).about("label", "sh-0007", of="lean")
    rows = {d["name"]: d for d in record.get("declarations")}
    assert list(rows) == ["Formal.cycleLattice_saturated", "Formal.helper", "Formal.cycleLattice", "Formal.divergence"]
    assert rows["Formal.cycleLattice_saturated"]["names"] == {"label": "sh-0007"}
    assert rows["Formal.helper"]["role"] == "supports" and rows["Formal.helper"]["names"] is None
    assert rows["Formal.divergence"]["names"] == {"label": "sh-0003"}
    assert [u.get("label") for u in record.get("uses")] == ["sh-0004", "sh-0003"]
    assert set(record.get("files")) == {f"lean/{SATURATION}", "lean/Loom.lean", "lean/lakefile.toml", "lean/lean-toolchain", "lean/lake-manifest.json"}  # fmt: skip
    assert record.by.kind == "loom" and record.get("ok") is True and record.get("replay")["exit"] == 0
    found = _status(quilt, "sh-0007")
    assert (found.lean, found.role) == ("unattested", "proved")


def test_a_second_check_saying_the_same_records_nothing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _steps(monkeypatch, _probe())
    check.check(quilt)
    again = check.check(quilt)
    assert again.written == [] and sorted(again.unchanged) == ["sh-0003", "sh-0004", "sh-0007"]
    assert len(replay(quilt).of_kind("lean")) == 3


def test_a_sorry_reads_as_failed(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _steps(monkeypatch, _probe(sorry=True))
    check.check(quilt)
    assert _status(quilt, "sh-0007").lean == "failed"


def test_a_build_error_in_a_module_it_rests_on_is_not_ok(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _steps(monkeypatch, _probe(), build_out=f"error: ./{SATURATION}:12:4: unknown identifier 'foo'\n")
    done = check.check(quilt)
    [record] = replay(quilt).about("label", "sh-0007", of="lean")
    assert record.get("ok") is False and record.get("errors") == [f"{SATURATION}:12:4: unknown identifier 'foo'"]
    assert done.errors and _status(quilt, "sh-0007").lean == "failed"


def test_a_marker_naming_nothing_is_reported_and_recorded_nowhere(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extra = [_decl("Formal.stray", "theorem", "theorem stray", []), _marker("Formal.stray", "thm:nowhere")]
    _steps(monkeypatch, _probe(extra=extra))
    done = check.check(quilt)
    assert done.unknown == ["Formal.stray: thm:nowhere"]
    assert replay(quilt).about("label", "thm:nowhere") == []


def test_a_changed_lean_file_stops_the_record_standing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A change to any Lean file a record names, the proof's or a definition's, makes it stand no more: the result reads `rerun` until loom checks again."""
    _steps(monkeypatch, _probe())
    check.check(quilt)
    (install.project(quilt) / SATURATION).write_text(
        "import Loom\n-- the divergence's sign flipped\n", encoding="utf-8"
    )
    assert _status(quilt, "sh-0007").lean == "rerun"
    assert _status(quilt, "sh-0003").lean == "rerun"


def test_a_changed_statement_leaves_no_current_record(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the paper's statement changes, the record names a text that is gone: the result reads `rerun`, and a check now records on the new text."""
    _steps(monkeypatch, _probe())
    check.check(quilt)
    node = quilt / "drafting" / "nodes" / "sh-0007.tex"
    node.write_text(
        node.read_text(encoding="utf-8").replace("some integer $n \\neq 0$", "some integer $n$"), encoding="utf-8"
    )
    assert _status(quilt, "sh-0007").lean == "rerun"
    again = check.check(quilt)
    assert again.written == ["sh-0007"]
    assert _status(quilt, "sh-0007").lean == "unattested"


def test_a_lean_file_changed_during_the_check_records_nothing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def edit() -> None:
        (install.project(quilt) / SATURATION).write_text("import Loom\n-- edited mid-check\n", encoding="utf-8")

    _steps(monkeypatch, _probe(), during=edit)
    with pytest.raises(check.Refused, match="changed while loom checked it"):
        check.check(quilt)
    assert replay(quilt).of_kind("lean") == []


def test_a_project_whose_folders_hold_the_person_s_files_is_refused(
    quilt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where a folder the Lean profile reads whole holds the home folder, as a toolchain kept at its root would, the check refuses before running anything: the fence would open the person's files to the Lean it runs."""
    ran = _steps(monkeypatch, _probe())
    places = fence.lean_places
    monkeypatch.setattr(fence, "lean_places", lambda **at: {**places(**at), "TOOLCHAIN": str(Path.home().resolve())})
    with pytest.raises(check.Refused, match="holds your own files"):
        check.check(quilt)
    assert ran == []


def test_a_probe_that_does_not_answer_records_nothing(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A probe that fails, as one short of memory does, is no observation: the check refuses and writes no record that Lean rejected anything."""
    _steps(monkeypatch, _probe())
    real = check._fenced

    def failing(argv: list[str], *a: Any) -> subprocess.CompletedProcess[str]:
        if "--run" in argv:
            return subprocess.CompletedProcess(argv, 1, "", "uncaught exception: failed to read file")
        return real(argv, *a)

    monkeypatch.setattr(check, "_fenced", failing)
    with pytest.raises(check.Refused, match="probe of the built project failed"):
        check.check(quilt)
    assert replay(quilt).of_kind("lean") == []


def test_a_marker_module_that_is_not_loom_s_is_refused(quilt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The check writes nothing in the quilt: where the marker module differs from loom's it refuses, runs nothing, and leaves the file for turning formalization on to put back."""
    ran = _steps(monkeypatch, _probe())
    marker = install.project(quilt) / "Loom.lean"
    marker.write_text("import Lean\n-- the marker made to mean something else\n", encoding="utf-8")
    with pytest.raises(check.Refused, match="not loom's marker module"):
        check.check(quilt)
    assert ran == [] and marker.read_text(encoding="utf-8").endswith("something else\n")


@pytest.mark.parametrize("linked", [".lake", ".lake/build", ".lake/loom"])
def test_a_folder_the_check_removes_that_is_a_link_is_refused(quilt: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, linked: str) -> None:  # fmt: skip
    """`.lake`, `.lake/build` or `.lake/loom` made a link to a folder elsewhere is refused before anything is removed, so the clean rebuild removes nothing outside the project."""
    ran = _steps(monkeypatch, _probe())
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "build").mkdir(parents=True)
    (elsewhere / "loom").mkdir()
    (elsewhere / "keep.txt").write_text("keep\n", encoding="utf-8")
    (elsewhere / "build" / "keep.txt").write_text("keep\n", encoding="utf-8")
    lake = install.project(quilt) / ".lake"
    if linked == ".lake":
        lake.symlink_to(elsewhere)
    else:
        lake.mkdir()
        (install.project(quilt) / linked).symlink_to(elsewhere)
    with pytest.raises(check.Refused, match="not a folder of the project's own"):
        check.check(quilt)
    assert ran == [] and (elsewhere / "keep.txt").is_file() and (elsewhere / "build" / "keep.txt").is_file()


def _helped(helper: str, proof: str) -> list[dict[str, Any]]:
    """A theorem marked for sh-0002 whose statement names a definition no marker names, and the proof it uses."""
    return [
        {**_decl("Formal.D", "def", f"def D := {helper}", []), "means": []},
        {**_decl("Formal.t", "theorem", "theorem t : D", ["Formal.D", "Formal.p"]), "means": ["Formal.D"]},
        {**_decl("Formal.p", "theorem", f"theorem p := {proof}", []), "means": []},
        _marker("Formal.t", "sh-0002"),
    ]


def test_a_statement_s_hash_covers_the_unmarked_definitions_it_names(
    quilt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What a person attests is the stating declarations' statements: a definition with no marker that the statement names is part of what it says, so changing what that definition says changes the statement's hash, and changing only a proof does not."""
    from loom.evidence.status import statements_of

    def stated(helper: str, proof: str) -> dict[str, str]:
        _steps(monkeypatch, _probe(extra=_helped(helper, proof)))
        (install.project(quilt) / SATURATION).write_text(f"import Loom\n-- {helper} {proof}\n", encoding="utf-8")
        check.check(quilt)
        return statements_of(replay(quilt).about("label", "sh-0002", of="lean")[-1])

    first = stated("n + 0 = n", "by simp")
    assert stated("n + 0 = n", "by omega") == first
    assert stated("True", "by omega") != first


def test_a_record_keeps_each_declaration_as_lean_printed_it_and_what_its_statement_names(
    quilt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the person reads before attesting is loom's own: each declaration as the probe had Lean print it, null where the printer failed, and the declarations of the project its statement names, followed through one Lean made for another to what that one names."""
    shown = "theorem Formal.t (n : Nat) : Formal.D n"
    extra = [
        {
            **_decl("Formal.D", "def", "def D := E", []),
            "means": ["Formal.D._aux"],
            "shown": "def Formal.D (n : Nat) : Prop :=\n  fun n => Formal.E n",
        },  # fmt: skip
        {**_decl("Formal.D._aux", "def", "", [], internal=True), "means": ["Formal.E"]},
        {**_decl("Formal.E", "def", "def E", []), "means": [], "shown": None},
        {
            **_decl("Formal.t", "theorem", "theorem t : D", ["Formal.D", "Formal.D._aux", "Formal.E", "Formal.p"]),
            "means": ["Formal.D"],
            "shown": shown,
        },  # fmt: skip
        {**_decl("Formal.p", "theorem", "theorem p", []), "means": [], "shown": "theorem Formal.p : True"},
        _marker("Formal.t", "sh-0002"),
    ]
    _steps(monkeypatch, _probe(extra=extra))
    check.check(quilt)
    [record] = replay(quilt).about("label", "sh-0002", of="lean")
    rows = {d["name"]: d for d in record.get("declarations")}
    assert rows["Formal.t"]["shown"] == shown and rows["Formal.t"]["means"] == ["Formal.D"]
    assert rows["Formal.D"]["means"] == ["Formal.E"] and rows["Formal.D"]["shown"].startswith("def Formal.D")
    assert rows["Formal.E"]["shown"] is None and rows["Formal.p"]["means"] == []
