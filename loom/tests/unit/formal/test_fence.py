"""The fence's Lean profile: what a check's command is started as, that the TeX fence's own switch never unfences it, and that a place holding the person's files is caught; with the fence up here, what a fenced program may read and write."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loom import fence


def test_a_fenced_command_runs_under_the_lean_profile_with_its_places_as_parameters(tmp_path: Path) -> None:
    places = {"PROJECT": str(tmp_path), "TOOLCHAIN": "/var/empty", "DEVDIR": "/var/empty", "PROBE": str(tmp_path)}
    argv = fence.lean_argv(["/bin/echo", "hi"], places)
    assert argv[:3] == [fence.SANDBOX, "-f", str(fence.LEAN_PROFILE)]
    assert argv[-2:] == ["/bin/echo", "hi"] and f"PROJECT={tmp_path}" in argv
    assert str(tmp_path) not in fence.LEAN_PROFILE.read_text(encoding="utf-8"), (
        "a path is a parameter, never the profile's text"
    )


def test_the_tex_fence_s_switch_does_not_reach_lean(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LOOM_FENCE=off`, for a person whose honest paper the TeX fence breaks, leaves Lean's check fenced or refused: there is no unfenced check."""
    monkeypatch.setenv(fence.OFF, "off")
    assert fence.state() == "off"
    assert fence.lean_state() != "off"


def test_a_place_holding_the_home_folder_leaks(tmp_path: Path) -> None:
    home = str(Path.home().resolve())
    assert fence.lean_leaks({"PROJECT": str(tmp_path), "TOOLCHAIN": home})
    assert not fence.lean_leaks({"PROJECT": str(tmp_path / "q" / "lean"), "TOOLCHAIN": "/var/empty"})


@pytest.mark.skipif(fence.lean_state() is not None, reason="the fence is not up here")
def test_a_fenced_program_reads_and_writes_the_project_and_nothing_outside_it(tmp_path: Path) -> None:
    project, outside = tmp_path / "project", tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret\n", encoding="utf-8")
    (project / "mine.txt").write_text("mine\n", encoding="utf-8")
    places = fence.lean_places(project=project, toolchain=Path("/var/empty"), probe=project)

    def run(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(fence.lean_argv(list(argv), places), capture_output=True, text=True, check=False)

    assert run("/bin/cat", str(project / "mine.txt")).stdout == "mine\n"
    assert run("/bin/cat", str(outside / "secret.txt")).returncode != 0
    assert run("/usr/bin/touch", str(project / "made.txt")).returncode == 0 and (project / "made.txt").is_file()
    assert run("/usr/bin/touch", str(outside / "made.txt")).returncode != 0 and not (outside / "made.txt").exists()
    assert run("/usr/bin/nc", "-z", "-w", "3", "1.1.1.1", "80").returncode != 0
