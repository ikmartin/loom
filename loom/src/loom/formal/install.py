"""What turning formalization on installs: elan where the machine has none, the toolchain the quilt's Lake project names, the project itself where the quilt has none, and Mathlib with its build from Mathlib's own cache.

This is the one part of formalization that uses the network and runs unfenced, and only on the person's act (`formal/switch.py`). So it runs nothing a quilt could have chosen beyond Lean's and Mathlib's own releases: the toolchain must be one of Lean's, the project must have loom's shape (`untrusted`) and require Mathlib at a release tag from its own repository, and the manifest is resolved again from there every time, so a revision a quilt's manifest names is never fetched as it stands.
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
#: A package Mathlib brings: a repository of the Lean community's or of Lean's own, named plainly.
PACKAGE = re.compile(r"https://github\.com/(leanprover-community|leanprover)/[A-Za-z0-9_-][A-Za-z0-9_.-]*")
#: A release tag of Mathlib's, as its maintainers tag one for each Lean release.
RELEASE = re.compile(r"v\d+\.\d+\.\d+(-rc\d+)?")
#: What a project's `lakefile.toml` may set besides its libraries and Mathlib.
LAKEFILE_KEYS = frozenset({"name", "defaultTargets", "leanOptions", "lean_lib", "require", "version"})
#: A toolchain of Lean's own releases, as `lean-toolchain` names it.
OFFICIAL = re.compile(r"leanprover/lean4:v\d+\.\d+\.\d+(-rc\d+)?")
#: The module that defines the marker `@[loom "NAME"]`, kept by loom in the project as a library of its own.
MARKER_MODULE = "Loom"
MARKER = Path(__file__).parent.parent / "assets" / "lean" / "Loom.lean"


#: Each step of the install by the code `install` tells, with the words a terminal says it in; the viewer has its own words for each code.
STEPS = {
    "elan": "installing elan, Lean's toolchain manager",
    "project": f"making the Lean project in {LEAN}/",
    "toolchain": "installing the Lean toolchain",
    "mathlib": "fetching Mathlib and its build, about 1.3 GB the first time",
}


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
    """What the project asks for beyond loom's own shape, in words; [] for none.

    Its `lakefile.toml` names the project, its default targets and Lean's options, loom's two libraries (`MARKER_MODULE`, `LIBRARY`) with nothing but their names, and at most Mathlib, from exactly `MATHLIB_GIT` at one of its release tags; a `lakefile.lean`, a program, is refused. Its manifest pins Mathlib from that repository at a release tag, and each other package from the Lean community's or Lean's own repositories as Mathlib's own manifest brings it (`inherited`). So a module the build makes is one of loom's libraries, and the one unfenced step fetches only what Mathlib's maintainers tagged.
    """
    out: list[str] = []
    if (proj / "lakefile.lean").exists():
        out.append("lakefile.lean, a program loom does not run")
    try:
        config = tomllib.loads((proj / "lakefile.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return [*out, "a lakefile.toml loom can read"]
    out += [f"the setting {k}" for k in sorted(set(config) - LAKEFILE_KEYS)]
    libs = config.get("lean_lib", [])
    if not isinstance(libs, list) or sorted(str(lib.get("name")) if isinstance(lib, dict) else "" for lib in libs) != sorted((MARKER_MODULE, LIBRARY)) or any(set(lib) != {"name"} for lib in libs):  # fmt: skip
        out.append(f"libraries other than {MARKER_MODULE} and {LIBRARY} as loom writes them")
    requires = config.get("require", [])
    for req in requires if isinstance(requires, list) else [requires]:
        if not (
            isinstance(req, dict)
            and set(req) == {"name", "git", "rev"}
            and req["name"] == "mathlib"
            and _repository(req["git"]) == MATHLIB_GIT
            and isinstance(req["rev"], str)
            and RELEASE.fullmatch(req["rev"])
        ):
            out.append(
                f"{req.get('name') if isinstance(req, dict) else req!s}, which is not Mathlib from {MATHLIB_GIT} at a release tag"
            )
    try:
        manifest = json.loads((proj / "lake-manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return out
    except (OSError, ValueError):
        return [*out, "a lake-manifest.json loom can read"]
    for pkg in manifest.get("packages", []) if isinstance(manifest, dict) else []:
        if not isinstance(pkg, dict) or pkg.get("type") != "git":
            out.append(f"{pkg.get('name') if isinstance(pkg, dict) else pkg!s}, which is not a git repository")
            continue
        url, name = _repository(pkg.get("url")), pkg.get("name")
        if name == "mathlib":
            if url != MATHLIB_GIT or not RELEASE.fullmatch(str(pkg.get("inputRev"))):
                out.append(f"mathlib from {pkg.get('url')!s} at {pkg.get('inputRev')!s}")
        elif not (url is not None and PACKAGE.fullmatch(url) and pkg.get("inherited") is True):
            out.append(f"{name!s} from {pkg.get('url')!s}, which Mathlib does not bring")
    return out


def _repository(url: object) -> str | None:
    """A repository's address as compared: without a final `.git` or `/`; None for what is not one."""
    if not isinstance(url, str):
        return None
    return url.removesuffix("/").removesuffix(".git")


def make_project(root: Path) -> None:
    """Make the quilt's Lake project, requiring Mathlib at `MATHLIB`, through the door: its `lakefile.toml`, `lean-toolchain`, the library's root module and a `.gitignore` keeping `.lake` out, each only where none is, and loom's marker module (`write_marker`)."""
    files = {
        "lean-toolchain": TOOLCHAIN + "\n",
        "lakefile.toml": f'name = "formal"\ndefaultTargets = ["{LIBRARY}"]\n\n'
        f'[[require]]\nname = "mathlib"\ngit = "{MATHLIB_GIT}"\nrev = "{MATHLIB}"\n\n'
        f'[[lean_lib]]\nname = "{MARKER_MODULE}"\n\n[[lean_lib]]\nname = "{LIBRARY}"\n',
        f"{LIBRARY}.lean": f"import {MARKER_MODULE}\n",
        ".gitignore": "/.lake\n",
    }
    for name, text in files.items():
        if not (project(root) / name).exists():
            _put(root, name, text.encode("utf-8"), None)
    write_marker(root)


def write_marker(root: Path) -> None:
    """Put loom's marker module in the quilt's project as loom ships it, through the door, where it is missing or differs; refused (`changed`) where it changed since loom read it."""
    want = MARKER.read_bytes()
    try:
        now: bytes | None = (project(root) / f"{MARKER_MODULE}.lean").read_bytes()
    except FileNotFoundError:
        now = None
    if now != want:
        _put(root, f"{MARKER_MODULE}.lean", want, now)


def marker_is_loom_s(root: Path) -> bool:
    """Whether the project's marker module is loom's as it ships it."""
    try:
        return (project(root) / f"{MARKER_MODULE}.lean").read_bytes() == MARKER.read_bytes()
    except OSError:
        return False


def _put(root: Path, name: str, data: bytes, expect: bytes | None) -> None:
    """Write one file of the quilt's project through the door, as part of turning formalization on: a file of the quilt like any other, so its history keeps what it replaces."""
    from loom.writes import put

    put(root, None, f"{LEAN}/{name}", data, kind="formal", expect=expect)


def install(root: Path, say: Callable[[str], None] = lambda _: None) -> Installed:
    """Install what formalization needs for the quilt at `root` on this machine.

    Parameters
    ----------
    root : Path
        The quilt's root.
    say : callable, optional
        Told each step as it starts, by its code in `STEPS`.

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
        say("elan")
        t = time.monotonic()
        elan = _install_elan()
        done.steps.append(("elan", time.monotonic() - t))
    if not (proj / "lakefile.toml").exists() and not (proj / "lakefile.lean").exists():
        say("project")
        make_project(root)
    problems = untrusted(proj)
    if problems:
        raise Refused("the Lean project requires what loom does not install: " + "; ".join(problems))
    name = toolchain_of(proj)
    if not (toolchain_folder(name) / "bin" / "lake").exists():
        say("toolchain")
        t = time.monotonic()
        _run([elan, "toolchain", "install", name], proj, "installing the toolchain")
        done.steps.append(("toolchain", time.monotonic() - t))
    lake = str(toolchain_folder(name) / "bin" / "lake")
    # always resolved again from Mathlib's own repository, so a manifest a quilt carries chooses no revision
    say("mathlib")
    t = time.monotonic()
    _run([lake, "update"], proj, "fetching Mathlib", name)
    done.steps.append(("mathlib", time.monotonic() - t))
    problems = untrusted(proj)
    if problems:
        raise Refused("Mathlib pinned what loom does not install: " + "; ".join(problems))
    write_marker(root)
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
