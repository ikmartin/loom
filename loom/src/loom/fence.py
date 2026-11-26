"""The fence around what loom runs on macOS: Apple's `sandbox-exec` with a profile loom ships for each kind of run, so a file loom runs, one the person did not write among them, reads and writes only the places its profile names and reaches no network.

A TeX compile (`assets/fence/tex.sb`) reads only its run's folders, the TeX in use and what TeX's own scripts need, and writes only its run's folders and TeX's font cache; where the fence is not up (`state`) it runs as it would without it. Lean's certifying check (`assets/fence/lean.sb`) reads the quilt's Lake project, its one toolchain, the developer tools' git and loom's probe, and writes only the project; it runs fenced or not at all (`lean_state`). A fenced run that fails is never tried again unfenced, since a file could fail on purpose to get the unfenced run.
"""

from __future__ import annotations

import functools
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

#: Apple's program that runs a command under a profile; macOS ships it, and no other system has it.
SANDBOX = "/usr/bin/sandbox-exec"
#: The one profile every fenced TeX compile runs under.
PROFILE = Path(__file__).parent / "assets" / "fence" / "tex.sb"
#: The profile Lean's certifying check runs under.
LEAN_PROFILE = Path(__file__).parent / "assets" / "fence" / "lean.sb"
#: The environment variable that turns the fence off, set to `off`: for a person whose honest paper it breaks.
OFF = "LOOM_FENCE"
#: `sandbox-exec`'s exit when it may not apply a profile, as inside another sandbox.
_NESTED = 71
#: What a parameter is given when the machine has no such place, so the profile names nothing real.
_NOWHERE = "/var/empty"


def state() -> str | None:
    """Whether a TeX compile loom starts is fenced on this machine.

    Returns
    -------
    str or None
        None when it is; otherwise why not, in a word: `off`, the person turned it off (`OFF`); `absent`, this system has no `sandbox-exec` or its profile does not run, as on Linux; `nested`, loom runs inside another sandbox, which may not hold a second; `leaks`, the fence let a program read outside its run, or a TeX folder it would read holds the person's files (`_holds_the_person_s`). Found once in a process by trying (`_tried`), but for `off`, read each time.
    """
    if os.environ.get(OFF, "").strip().lower() == "off":
        return "off"
    return _tried()


@functools.cache
def _tried() -> str | None:
    """`state` but `off`, found by trying the real profile once (`_trial`)."""
    if not os.access(SANDBOX, os.X_OK) or not PROFILE.is_file():
        return "absent"
    if _holds_the_person_s(_machine()):
        return "leaks"
    return _trial(lambda a, argv: _argv(argv, a, a))


def lean_state() -> str | None:
    """Whether Lean's certifying check can run fenced on this machine.

    Returns
    -------
    str or None
        None when it can; otherwise why not, as `state` words it: `absent`, `nested` or `leaks`. Never `off`: the check runs fenced or not at all, so the switch that turns the TeX fence off does not reach it.
    """
    return _lean_tried()


@functools.cache
def _lean_tried() -> str | None:
    """`lean_state`, found once in a process by trying the Lean profile (`_trial`)."""
    if not LEAN_PROFILE.is_file():
        return "absent"
    return _trial(lambda a, argv: lean_argv(argv, lean_places(project=a, toolchain=Path(_NOWHERE), probe=a)))


def _trial(argv_in: Callable[[Path, list[str]], list[str]]) -> str | None:
    """Try a profile once: `/bin/cat` run as `argv_in(folder, argv)` must read a file in `folder` and fail to read one outside it; None when it does, else `absent`, `nested` or `leaks`."""
    if not os.access(SANDBOX, os.X_OK):
        return "absent"
    with tempfile.TemporaryDirectory(prefix="loom-fence-") as a, tempfile.TemporaryDirectory(prefix="loom-fence-") as b:
        inside, outside = Path(a) / "inside", Path(b) / "outside"
        inside.write_text("inside\n", encoding="utf-8")
        outside.write_text("outside\n", encoding="utf-8")

        def cat(p: Path) -> subprocess.CompletedProcess[bytes] | None:
            try:
                return subprocess.run(
                    argv_in(Path(a), ["/bin/cat", str(p)]), capture_output=True, timeout=30, check=False
                )
            except (OSError, subprocess.SubprocessError):
                return None

        read = cat(inside)
        if read is None:
            return "absent"
        if read.returncode == _NESTED:
            return "nested"
        if read.returncode != 0 or read.stdout != b"inside\n":
            return "absent"
        leaked = cat(outside)
        if leaked is None or leaked.returncode == 0 or b"outside" in leaked.stdout:
            return "leaks"
    return None


def fenced(argv: list[str], *, stage: Path, out: Path, var: Path | None = None) -> list[str]:
    """`argv` run inside the fence where it is up (`state`), and `argv` itself where it is not.

    Parameters
    ----------
    argv : list of str
        The command, its program an absolute path.
    stage : Path
        The folder of staged sources the run reads, and may write.
    out : Path
        The folder the run writes its output into.
    var : Path, optional
        The run's own TeX cache (`run_var`), which it reads and writes; default loom's seed (`texmf_var`), for a run of loom's own.

    Returns
    -------
    list of str
        The command to start: `sandbox-exec` with the profile and its parameters, then `argv`; or `argv` unchanged.
    """
    return argv if state() is not None else _argv(argv, stage, out, var)


def lean_places(*, project: Path, toolchain: Path, probe: Path) -> dict[str, str]:
    """The Lean profile's parameters for one check, each resolved: the Lake project, the toolchain's folder, the developer tools' folder (`xcode-select -p`) and the folder of loom's probe."""
    dev = _ask(["/usr/bin/xcode-select", "-p"], {"PATH": "/usr/bin:/bin"}).strip()
    at = {"PROJECT": str(project), "TOOLCHAIN": str(toolchain), "DEVDIR": dev, "PROBE": str(probe)}
    return {name: os.path.realpath(place).rstrip("/") if place else _NOWHERE for name, place in at.items()}


def lean_leaks(places: dict[str, str]) -> bool:
    """Whether a folder the Lean profile would read whole holds the home folder, `~/Library` or loom's own data folder, as a project at the root of the home folder would."""
    return _holds_the_person_s(places)


def lean_argv(argv: list[str], places: dict[str, str]) -> list[str]:
    """`sandbox-exec` running `argv` under the Lean profile with `places` (`lean_places`) as its parameters; never `argv` alone, since the check runs fenced or not at all."""
    return [
        SANDBOX,
        "-f",
        str(LEAN_PROFILE),
        *(x for name, at in places.items() for x in ("-D", f"{name}={at}")),
        *argv,
    ]


def _argv(argv: list[str], stage: Path, out: Path, var: Path | None = None) -> list[str]:
    """`sandbox-exec` running `argv` under the profile, each place a `-D` parameter, resolved: a path is never written into the profile's text."""
    places = {"STAGE": os.path.realpath(stage), "OUT": os.path.realpath(out), **_machine()}
    if var is not None:
        places["TEXMFVAR"] = os.path.realpath(var)
    return [SANDBOX, "-f", str(PROFILE), *(x for name, at in places.items() for x in ("-D", f"{name}={at}")), *argv]


def texmf_var() -> Path:
    """Loom's own seed of the TeX cache fenced runs start from, kept between runs and apart from the person's own cache: LuaTeX's font database, which only loom writes (`_fill`). A document's run is given a clone of it (`run_var`) and never writes it, so no compile leaves anything here for another to read."""
    from loom.machine import data_dir

    p = data_dir() / "fenced-texmf-var"
    p.mkdir(parents=True, exist_ok=True)
    return p


#: LuaTeX's font database in a TeX cache, by which a run's rescan of the fonts is seen (`after_run`).
NAMES = "luatex-cache/generic/names/luaotfload-names.luc.gz"


def run_var(folder: Path, *, lua: bool) -> Path:
    """A TeX cache of a fenced run's own, `folder`/texmf-var, for its `TEXMFVAR`: a copy-on-write clone of loom's seed (`texmf_var`), so what the run writes there goes with it.

    For a LuaTeX run the seed's font database is made first where it has none (`_fill`), about 10 s once, which an empty cache would cost every run; with it, a font the seed lacks costs a run a fraction of a second. Where no clone can be made the seed is copied, and where no copy either the cache starts empty, and the run is only slower; a later pass of the same run in the same `folder` keeps its own.
    """
    from loom.locks import locked

    seed, clone = texmf_var(), folder / "texmf-var"
    if clone.is_dir():
        return clone  # a later pass of the same run keeps the cache it began with
    with locked(seed.parent / "fenced-texmf-var.lock"):
        if lua and not (seed / NAMES).is_file():
            _fill(seed)
        cloned = subprocess.run(["/bin/cp", "-c", "-R", str(seed), str(clone)], capture_output=True, check=False)
        if cloned.returncode != 0:
            # a folder on another volume takes no clone: a plain copy of the seed, which is small
            try:
                shutil.copytree(seed, clone, dirs_exist_ok=True)
            except OSError:
                clone.mkdir(parents=True, exist_ok=True)
    return clone


def after_run(clone: Path) -> None:
    """Once a fenced LuaTeX run is over: where the font database in its cache differs from the seed's, as when the run rescanned the fonts for one installed since, loom makes the seed's again itself (`_fill`), never taking the run's, so the next run finds the font without rescanning."""
    from loom.locks import locked

    seed = texmf_var()
    theirs, ours = clone / NAMES, seed / NAMES
    try:
        if not theirs.is_file() or (ours.is_file() and ours.read_bytes() == theirs.read_bytes()):
            return
    except OSError:
        return
    with locked(seed.parent / "fenced-texmf-var.lock"):
        _fill(seed)


def _fill(seed: Path) -> None:
    """Make the seed's LuaTeX font database with `luaotfload-tool --update`, loom's own command, which reads the fonts and no document; inside the fence where it is up, with only the seed to write, so it finds the fonts a fenced run can read. Call holding the seed's lock."""
    from loom.tex.runner import tex_env

    env = tex_env()
    tool = shutil.which("luaotfload-tool", path=env.get("PATH"))
    if tool is None:
        return
    with tempfile.TemporaryDirectory(prefix="loom-fill-") as tmp:
        argv = [tool, "--update"]
        if state() is None:
            argv = _argv(argv, Path(tmp), Path(tmp), seed)
        env = {**env, "TEXMFVAR": str(seed), "TMPDIR": tmp, "PWD": tmp}
        try:
            subprocess.run(argv, cwd=tmp, env=env, capture_output=True, timeout=600, check=False)
        except subprocess.TimeoutExpired:
            return


def _machine() -> dict[str, str]:
    """The profile's parameters for this machine's TeX, as the environment a TeX program is started in names it (`tex.runner.tex_env`)."""
    from loom.tex.runner import tex_env

    env = tex_env()
    return dict(_places(tuple(env.get(k, "") for k in ("PATH", "HOME", "TEXMFHOME", "XDG_DATA_HOME"))))


#: The places kpsewhich names that the profile reads, by its own names: the programs, the install's own folder (of which two files are read), and its trees.
_TREES = (
    ("TEXBIN", "SELFAUTOLOC"),
    ("TEXPARENT", "SELFAUTOPARENT"),
    ("TEXDIST", "TEXMFDIST"),
    ("TEXLOCAL", "TEXMFLOCAL"),
    ("TEXSYSVAR", "TEXMFSYSVAR"),
    ("TEXSYSCONFIG", "TEXMFSYSCONFIG"),
    ("TEXMFHOME", "TEXMFHOME"),
)


@functools.cache
def _places(key: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """`_machine` for one environment, `key` the parts of it that move the places; asked once each.

    The TeX in use is given as its trees and its programs, as kpsewhich names them, and never a folder above them, which for loom's own TeX or a TinyTeX in `~/Library` would hold the person's files; TEXMFVAR is loom's own (`texmf_var`); DEVDIR is Xcode's bundle, or the Command Line Tools; USERTMP is the per-user temporary folder, for `xcrun`'s cache.
    """
    from loom.tex.runner import tex_env

    var = texmf_var()
    env = {**tex_env(), "TEXMFVAR": str(var)}
    asked = "\n".join(f"${name}" for _, name in _TREES)
    found = _ask(["kpsewhich", f"-expand-var={asked}"], env).splitlines()
    at = dict(zip((param for param, _ in _TREES), (*found, *[""] * len(_TREES)), strict=False))
    dev = _ask(["/usr/bin/xcode-select", "-p"], env).strip()
    if dev.endswith(".app/Contents/Developer"):
        dev = str(Path(dev).parents[1])
    at |= {
        "TEXMFVAR": str(var),
        "DEVDIR": dev,
        "USERTMP": _ask(["/usr/bin/getconf", "DARWIN_USER_TEMP_DIR"], env).strip(),
    }
    return tuple((name, os.path.realpath(place).rstrip("/") if place else _NOWHERE) for name, place in at.items())


def _holds_the_person_s(places: dict[str, str]) -> bool:
    """Whether a folder the profile reads whole holds the home folder, `~/Library` or loom's own data folder, where the person's files, cookies and loom's write tokens are: a TeX laid out so would leave the fence open to them."""
    from loom.machine import data_dir

    home = Path(os.path.realpath(os.path.expanduser("~")))
    theirs = (home, home / "Library", Path(os.path.realpath(data_dir())))
    whole = (at for name, at in places.items() if name not in ("TEXPARENT", "USERTMP") and at != _NOWHERE)
    return any(p.is_relative_to(at) for at in whole for p in theirs)


def _ask(argv: list[str], env: dict[str, str]) -> str:
    """What `argv` prints, or '' when it cannot be run or fails."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""
