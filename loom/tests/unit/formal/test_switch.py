"""The switch that turns formalization on: kept on this machine and never in the quilt, the person's alone, and what installing it trusts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from loom.formal import install, switch
from tests.helpers import ok, refused
from tests.unit._quilts import showcase


def _files(q: Path) -> dict[str, bytes]:
    return {p.relative_to(q).as_posix(): p.read_bytes() for p in sorted(q.rglob("*")) if p.is_file()}


def test_the_switch_is_kept_on_the_machine_and_a_copy_of_the_quilt_is_off(tmp_path: Path, home: Path) -> None:
    """Turning it on writes nothing in the quilt, only a file in loom's data folder for this quilt's place; a copy of the quilt elsewhere, as a co-author's clone is, reads off."""
    q = showcase(tmp_path)
    before = _files(q)
    switch.turn_on(q)
    assert switch.is_on(q)
    assert _files(q) == before
    assert switch.switch_file(q).is_relative_to(home)
    copy = tmp_path / "copy"
    shutil.copytree(q, copy)
    assert not switch.is_on(copy)
    switch.turn_off(q)
    assert not switch.is_on(q)


def test_a_switch_file_naming_another_quilt_is_off(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    switch.turn_on(q)
    f = switch.switch_file(q)
    f.write_text(json.dumps({"root": str(tmp_path / "elsewhere"), "on": True}), encoding="utf-8")
    assert not switch.is_on(q)


@pytest.mark.parametrize("words", [["formal", "on"], ["formal", "off"]])
def test_turning_it_on_or_off_is_the_person_s(tmp_path: Path, words: list[str]) -> None:
    """Under an agent's shell `loom formal on` and `off` refuse before anything is installed or kept, so an agent never turns on what runs code on the person's machine."""
    q = showcase(tmp_path)
    if words[1] == "off":
        switch.turn_on(q)
    refused(*words, "--quilt", str(q), code=2, match="an agent is running this shell", env={"AI_AGENT": "1"})
    assert switch.is_on(q) is (words[1] == "off")
    assert not (q / install.LEAN).exists()


def test_off_is_kept_and_reads_off(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    switch.turn_on(q)
    ok("formal", "off", "--quilt", str(q))
    assert not switch.is_on(q)
    assert "formalization is off" in ok("formal", "--quilt", str(q)).output


def test_a_new_project_trusts_only_lean_s_and_the_community_s_repositories(tmp_path: Path) -> None:
    """The project loom makes requires Mathlib from the community's repository at loom's pin, with loom's marker module beside its library."""
    proj = tmp_path / "lean"
    install.make_project(proj)
    assert install.untrusted(proj) == []
    assert install.toolchain_of(proj) == install.TOOLCHAIN
    assert (proj / "Loom.lean").read_bytes() == install.MARKER.read_bytes()
    assert (proj / ".gitignore").read_text(encoding="utf-8") == "/.lake\n"


@pytest.mark.parametrize(
    "lakefile, manifest, says",
    [
        ('name = "x"\n[[require]]\nname = "mathlib"\ngit = "https://github.com/someone/mathlib4"\n', None, "someone"),
        ('name = "x"\n[[require]]\nname = "local"\npath = "../elsewhere"\n', None, "local"),
        ('name = "x"\n[[require]]\nname = "thing"\nscope = "someone"\n', None, "thing"),
        (
            'name = "x"\n',
            {"packages": [{"name": "batteries", "type": "git", "url": "https://evil.example/batteries"}]},
            "evil.example",
        ),
        ('name = "x"\n', {"packages": [{"name": "near", "type": "path", "dir": "../near"}]}, "near"),
    ],
)
def test_a_project_requiring_anything_else_is_refused(
    tmp_path: Path, lakefile: str, manifest: dict | None, says: str
) -> None:  # type: ignore[type-arg]
    """A co-author's project that requires a package from another repository, a folder, or a scope loom does not trust is named, so turning formalization on runs none of its code unfenced."""
    proj = tmp_path / "lean"
    proj.mkdir()
    (proj / "lakefile.toml").write_text(lakefile, encoding="utf-8")
    if manifest is not None:
        (proj / "lake-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    found = install.untrusted(proj)
    assert found and says in " ".join(found)


def test_a_lakefile_that_is_a_program_is_refused(tmp_path: Path) -> None:
    proj = tmp_path / "lean"
    install.make_project(proj)
    (proj / "lakefile.lean").write_text("import Lake\n", encoding="utf-8")
    assert any("lakefile.lean" in p for p in install.untrusted(proj))


@pytest.mark.parametrize(
    "name", ["someone/lean4:v4.36.0", "leanprover/lean4:nightly", "leanprover/lean4:v4.36.0; rm -rf ~"]
)
def test_a_toolchain_not_of_lean_s_own_releases_is_refused(tmp_path: Path, name: str) -> None:
    proj = tmp_path / "lean"
    install.make_project(proj)
    (proj / "lean-toolchain").write_text(name + "\n", encoding="utf-8")
    with pytest.raises(install.Refused, match="not one of Lean's own releases"):
        install.toolchain_of(proj)


def test_install_refuses_an_untrusted_project_before_running_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With elan present and a co-author's project requiring a foreign package, install refuses and runs no step."""
    ran: list[list[str]] = []
    monkeypatch.setattr(install, "find_elan", lambda: "/bin/true")
    monkeypatch.setattr(install, "_run", lambda argv, *a, **k: ran.append(argv))
    q = tmp_path / "q"
    proj = q / install.LEAN
    proj.mkdir(parents=True)
    (proj / "lean-toolchain").write_text(install.TOOLCHAIN + "\n", encoding="utf-8")
    (proj / "lakefile.toml").write_text(
        'name = "x"\n[[require]]\nname = "m"\ngit = "https://example.org/m"\n', encoding="utf-8"
    )
    with pytest.raises(install.Refused, match="example.org"):
        install.install(q)
    assert ran == []


def test_install_makes_the_project_and_fetches_through_the_toolchain_s_own_lake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no project in the quilt, install makes one, installs the toolchain it names through elan, and runs that toolchain's own `lake update`."""
    ran: list[list[str]] = []
    monkeypatch.setenv("ELAN_HOME", str(tmp_path / "elan"))
    monkeypatch.setattr(install, "find_elan", lambda: "/usr/bin/elan")

    def fake(argv: list[str], cwd: Path, what: str, toolchain: str | None = None) -> None:
        ran.append(argv)
        if argv[1:3] == ["toolchain", "install"]:
            lake = install.toolchain_folder(argv[3]) / "bin" / "lake"
            lake.parent.mkdir(parents=True)
            lake.write_text("", encoding="utf-8")
        if argv[1:] == ["update"]:
            (cwd / "lake-manifest.json").write_text(json.dumps({"packages": []}), encoding="utf-8")

    monkeypatch.setattr(install, "_run", fake)
    q = tmp_path / "q"
    q.mkdir()
    done = install.install(q)
    lake = str(install.toolchain_folder(install.TOOLCHAIN) / "bin" / "lake")
    assert ran == [["/usr/bin/elan", "toolchain", "install", install.TOOLCHAIN], [lake, "update"]]
    assert [s for s, _ in done.steps] == ["toolchain", "mathlib"]
    assert (q / install.LEAN / "lakefile.toml").is_file()
