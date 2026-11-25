"""The fence around a TeX compile on macOS: Apple's `sandbox-exec` with the one profile loom ships (`assets/fence/tex.sb`), so a file loom compiles, one the person did not write among them, reads only its run's folders, the TeX in use and what TeX's own scripts need, writes only its run's folders and TeX's font cache, and reaches no network.

Where the fence is not up (`state`), a compile runs as it would without it. A fenced compile that fails is never tried again unfenced, since a file could fail on purpose to get the unfenced run.
"""

from __future__ import annotations

import functools
import os
import subprocess
import tempfile
from pathlib import Path

#: Apple's program that runs a command under a profile; macOS ships it, and no other system has it.
SANDBOX = "/usr/bin/sandbox-exec"
#: The one profile every fenced TeX compile runs under.
PROFILE = Path(__file__).parent / "assets" / "fence" / "tex.sb"
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
    """`state` but `off`, found by trying the real profile once: `/bin/cat` must read a file in its run and fail to read one outside it."""
    if not os.access(SANDBOX, os.X_OK) or not PROFILE.is_file():
        return "absent"
    if _holds_the_person_s(_machine()):
        return "leaks"
    with tempfile.TemporaryDirectory(prefix="loom-fence-") as a, tempfile.TemporaryDirectory(prefix="loom-fence-") as b:
        inside, outside = Path(a) / "inside", Path(b) / "outside"
        inside.write_text("inside\n", encoding="utf-8")
        outside.write_text("outside\n", encoding="utf-8")

        def cat(p: Path) -> subprocess.CompletedProcess[bytes] | None:
            try:
                return subprocess.run(
                    _argv(["/bin/cat", str(p)], Path(a), Path(a)), capture_output=True, timeout=30, check=False
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


def fenced(argv: list[str], *, stage: Path, out: Path) -> list[str]:
    """`argv` run inside the fence where it is up (`state`), and `argv` itself where it is not.

    Parameters
    ----------
    argv : list of str
        The command, its program an absolute path.
    stage : Path
        The folder of staged sources the run reads, and may write.
    out : Path
        The folder the run writes its output into.

    Returns
    -------
    list of str
        The command to start: `sandbox-exec` with the profile and its parameters, then `argv`; or `argv` unchanged.
    """
    return argv if state() is not None else _argv(argv, stage, out)


def _argv(argv: list[str], stage: Path, out: Path) -> list[str]:
    """`sandbox-exec` running `argv` under the profile, each place a `-D` parameter, resolved: a path is never written into the profile's text."""
    places = {"STAGE": os.path.realpath(stage), "OUT": os.path.realpath(out), **_machine()}
    return [SANDBOX, "-f", str(PROFILE), *(x for name, at in places.items() for x in ("-D", f"{name}={at}")), *argv]


def texmf_var() -> Path:
    """Loom's own TeX cache for fenced runs, which they read and write as their `TEXMFVAR`: the fonts METAFONT draws and LuaTeX's font database, kept between runs and apart from the person's own cache, which a fenced run never writes."""
    from loom.machine import data_dir

    p = data_dir() / "fenced-texmf-var"
    p.mkdir(parents=True, exist_ok=True)
    return p


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
