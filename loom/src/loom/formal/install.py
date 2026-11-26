"""What turning formalization on installs: elan where the machine has none, the toolchain the quilt's Lake project names, the project itself where the quilt has none, and Mathlib with its build from Mathlib's own cache.

This is the one part of formalization that uses the network and runs unfenced, and only on the person's act (`formal/switch.py`). So it runs nothing a quilt could have chosen beyond the official Lean and Mathlib: a project is made only with a `lakefile.toml`, never a `lakefile.lean`, which is a program; the toolchain must be one of Lean's own releases; and every package the project requires or its manifest pins must come from the Lean community's or Lean's own repositories on GitHub.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

#: The quilt's Lake project, by path from its root.
LEAN = "lean"
#: The library the agent's modules live in, `lean/Formal/`, and its root module.
LIBRARY = "Formal"
#: The toolchain and Mathlib a new project is made at; a quilt that has a project keeps its own.
TOOLCHAIN = "leanprover/lean4:v4.36.0-rc2"
MATHLIB = "v4.36.0-rc2"
MATHLIB_GIT = "https://github.com/leanprover-community/mathlib4"
#: elan's own installer, which installs elan alone here (`--default-toolchain none`) and edits no shell profile.
ELAN_INSTALLER = "https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh"
#: Where a package may come from: the Lean community's repositories and Lean's own.
TRUSTED = ("https://github.com/leanprover-community/", "https://github.com/leanprover/")
#: A toolchain of Lean's own releases, as `lean-toolchain` names it.
OFFICIAL = re.compile(r"leanprover/lean4:v\d+\.\d+\.\d+(-rc\d+)?")
#: The module that defines the marker `@[loom "NAME"]`, kept by loom in the project as a library of its own.
MARKER_MODULE = "Loom"
MARKER = Path(__file__).parent.parent / "assets" / "lean" / "Loom.lean"


class Refused(Exception):
    """Formalization cannot be installed for this quilt, in a sentence for the person."""


@dataclass
class Installed:
    """What `install` did, each step with the seconds it took."""

    steps: list[tuple[str, float]] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return sum(s for _, s in self.steps)


def elan_home() -> Path:
    """elan's home: `$ELAN_HOME`, else `~/.elan`."""
    return Path(os.environ.get("ELAN_HOME") or Path.home() / ".elan")


def toolchain_folder(name: str) -> Path:
    """The folder elan keeps the toolchain `name` in (`leanprover/lean4:v4.36.0` is `leanprover--lean4---v4.36.0`)."""
    return elan_home() / "toolchains" / name.replace(":", "---").replace("/", "--")


def find_elan() -> str | None:
    """The elan on `PATH`, else the one in elan's home, else None."""
    on_path = shutil.which("elan")
    if on_path:
        return on_path
    own = elan_home() / "bin" / "elan"
    return str(own) if os.access(own, os.X_OK) else None


def project(root: Path) -> Path:
    """The quilt's Lake project."""
    return root / LEAN


def toolchain_of(proj: Path) -> str:
    """The toolchain the project's `lean-toolchain` names, refused unless it is one of Lean's own releases."""
    try:
        name = (proj / "lean-toolchain").read_text(encoding="utf-8").strip()
    except OSError as e:
        raise Refused(f"the Lean project has no readable lean-toolchain ({e.strerror})") from None
    if not OFFICIAL.fullmatch(name):
        raise Refused(f"the Lean project names the toolchain {name!r}, which is not one of Lean's own releases")
    return name


def untrusted(proj: Path) -> list[str]:
    """Each package the project's `lakefile.toml` requires or its `lake-manifest.json` pins that does not come from a repository in `TRUSTED`, in words; a `lakefile.lean` is one by itself."""
    out: list[str] = []
    if (proj / "lakefile.lean").exists():
        out.append("lakefile.lean, a program loom does not run")
    try:
        config = tomllib.loads((proj / "lakefile.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return [*out, "a lakefile.toml loom can read"]
    for req in config.get("require", []):
        git, scope = req.get("git"), req.get("scope")
        if git is not None:
            if not isinstance(git, str) or not git.startswith(TRUSTED):
                out.append(f"{req.get('name')!s} from {git!s}")
        elif scope not in ("leanprover-community", "leanprover") or "path" in req:
            out.append(f"{req.get('name')!s}, from no repository loom trusts")
    try:
        manifest = json.loads((proj / "lake-manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return out
    except (OSError, ValueError):
        return [*out, "a lake-manifest.json loom can read"]
    for pkg in manifest.get("packages", []) if isinstance(manifest, dict) else []:
        url = pkg.get("url") if isinstance(pkg, dict) else None
        if not (
            isinstance(pkg, dict) and pkg.get("type") == "git" and isinstance(url, str) and url.startswith(TRUSTED)
        ):
            out.append(f"{pkg.get('name') if isinstance(pkg, dict) else pkg!s} from {url!s}")
    return out


def make_project(proj: Path) -> None:
    """Write a new Lake project requiring Mathlib at `MATHLIB`: its `lakefile.toml`, `lean-toolchain`, the library's root module, loom's marker module and a `.gitignore` keeping `.lake` out."""
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "lean-toolchain").write_text(TOOLCHAIN + "\n", encoding="utf-8")
    (proj / "lakefile.toml").write_text(
        f'name = "formal"\ndefaultTargets = ["{LIBRARY}"]\n\n'
        f'[[require]]\nname = "mathlib"\ngit = "{MATHLIB_GIT}"\nrev = "{MATHLIB}"\n\n'
        f'[[lean_lib]]\nname = "{MARKER_MODULE}"\n\n[[lean_lib]]\nname = "{LIBRARY}"\n',
        encoding="utf-8",
    )
    (proj / f"{LIBRARY}.lean").write_text(f"import {MARKER_MODULE}\n", encoding="utf-8")
    (proj / ".gitignore").write_text("/.lake\n", encoding="utf-8")
    write_marker(proj)


def write_marker(proj: Path) -> None:
    """Put loom's marker module in the project, as loom ships it, where it is missing or differs."""
    want = MARKER.read_bytes()
    target = proj / f"{MARKER_MODULE}.lean"
    try:
        if target.read_bytes() == want:
            return
    except OSError:
        pass
    target.write_bytes(want)


def install(root: Path, say: Callable[[str], None] = lambda _: None) -> Installed:
    """Install what formalization needs for the quilt at `root` on this machine.

    Parameters
    ----------
    root : Path
        The quilt's root.
    say : callable, optional
        Told each step as it starts, in words.

    Returns
    -------
    Installed
        The steps taken, each with its seconds.

    Raises
    ------
    Refused
        When the project is one loom does not install for (`untrusted`, `toolchain_of`), or a step fails.
    """
    done = Installed()
    proj = project(root)
    elan = find_elan()
    if elan is None:
        say("installing elan, Lean's toolchain manager")
        t = time.monotonic()
        elan = _install_elan()
        done.steps.append(("elan", time.monotonic() - t))
    if not (proj / "lakefile.toml").exists() and not (proj / "lakefile.lean").exists():
        say(f"making the Lean project in {LEAN}/")
        make_project(proj)
    problems = untrusted(proj)
    if problems:
        raise Refused("the Lean project requires what loom does not install: " + "; ".join(problems))
    name = toolchain_of(proj)
    if not (toolchain_folder(name) / "bin" / "lake").exists():
        say(f"installing the Lean toolchain {name}")
        t = time.monotonic()
        _run([elan, "toolchain", "install", name], proj, "installing the toolchain")
        done.steps.append(("toolchain", time.monotonic() - t))
    lake = str(toolchain_folder(name) / "bin" / "lake")
    if not (proj / "lake-manifest.json").exists():
        say("fetching Mathlib and its build, about 1.3 GB the first time")
        t = time.monotonic()
        _run([lake, "update"], proj, "fetching Mathlib", name)
        done.steps.append(("mathlib", time.monotonic() - t))
        problems = untrusted(proj)
        if problems:
            raise Refused("Mathlib pinned what loom does not install: " + "; ".join(problems))
    else:
        say("fetching Mathlib's build")
        t = time.monotonic()
        _run([lake, "exe", "cache", "get"], proj, "fetching Mathlib's build", name)
        done.steps.append(("mathlib", time.monotonic() - t))
    write_marker(proj)
    return done


def _install_elan() -> str:
    """Run elan's own installer for elan alone, into elan's home, with no shell profile edited; the path of the elan it installed."""
    with tempfile.TemporaryDirectory(prefix="loom-elan-") as tmp:
        script = Path(tmp) / "elan-init.sh"
        try:
            with urllib.request.urlopen(ELAN_INSTALLER, timeout=60) as r:  # noqa: S310 -- a fixed https address
                script.write_bytes(r.read())
        except OSError as e:
            raise Refused(f"could not download elan's installer: {e}") from None
        _run(
            ["/bin/sh", str(script), "-y", "--no-modify-path", "--default-toolchain", "none"],
            Path(tmp),
            "installing elan",
        )
    elan = elan_home() / "bin" / "elan"
    if not os.access(elan, os.X_OK):
        raise Refused("elan's installer finished and left no elan")
    return str(elan)


def _run(argv: list[str], cwd: Path, what: str, toolchain: str | None = None) -> None:
    """Run one step of the install in `cwd`, its output kept for the refusal when it fails; with `toolchain`, that toolchain's programs first on `PATH`."""
    env = dict(os.environ)
    if toolchain is not None:
        env["PATH"] = f"{toolchain_folder(toolchain) / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    try:
        done = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, errors="replace", check=False)
    except OSError as e:
        raise Refused(f"{what} failed: {e}") from None
    if done.returncode != 0:
        tail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-12:])
        raise Refused(f"{what} failed (exit {done.returncode}):\n{tail}")
