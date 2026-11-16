"""Loom's own TeX: a TinyTeX of one TeX Live year in the person's data directory, first on the path of every program loom starts.

Which TeX a run uses is decided here and nowhere else (`active`). Loom's own is used whenever it is installed, unless `[tex] use = "mine"` in the person's loom configuration; the person's TeX is used when loom's is absent. The person's own tree (`~/Library/texmf`) is read by loom's TeX only under `[tex] home_tree = true`. Packages come from one TeX Live year's repository: the frozen `tlnet-final` once the historic archive has it, else a named live mirror (`repository`), so the year's end needs no release of loom. Every run of `tlmgr` has a deadline, and its process group is killed past it.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

#: The TeX Live year loom's TeX is; a new year is a release of loom with a new archive.
YEAR = 2026

#: TinyTeX-0 bundles of the year, by platform: the base `build` starts from, pinned by checksum.
TINYTEX = {
    "darwin": (
        "https://github.com/rstudio/tinytex-releases/releases/download/v2026.11/TinyTeX-0-darwin-v2026.11.tar.xz",
        "5405651b1399cc827ba51de9e930a0498aa92f42e72e0ca694cf15eb00acd421",
    ),
    "linux-x86_64": (
        "https://github.com/rstudio/tinytex-releases/releases/download/v2026.11/TinyTeX-0-linux-x86_64-v2026.11.tar.xz",
        "ecd8e008385c3c5551df935c11ca76dfedbebda69c5118fe7d15db0ac662e64a",
    ),
    "linux-arm64": (
        "https://github.com/rstudio/tinytex-releases/releases/download/v2026.11/TinyTeX-0-linux-arm64-v2026.11.tar.xz",
        "44e6b7027c0f1fa93bf84680aa2ebbf70f876ca2b69499edb3259ea83dd90292",
    ),
}

#: Loom's released archive of a finished installation, by platform: (url, sha256). Empty until the archive is published; `install` then builds from `TINYTEX`.
ARCHIVE: dict[str, tuple[str, str]] = {}

#: Loom's released archive of Ghostscript and poppler, by machine (`tools_key`): (url, sha256). Empty until published; `LOOM_TOOLS_ARCHIVE` names one meanwhile.
TOOLS_ARCHIVE: dict[str, tuple[str, str]] = {}
#: What the tools archive holds: Ghostscript for dvisvgm, dvipng and EPS figures; poppler for page text, PDF figures and crops.
TOOL_PROGRAMS = ("bin/gs", "lib/libgs.dylib", "bin/pdftotext", "bin/pdfinfo", "bin/pdftocairo")

#: TinyTeX-1's packages, then what loom's programs and common papers need; biber and cm-super come on demand, being two thirds of the download.
SEED = (
    "amscls amsfonts amsmath atbegshi atveryend auxhook babel bibtex bigintcalc bitset bookmark booktabs cm dehyph "
    "dvipdfmx dvips ec epstopdf epstopdf-pkg etex etexcmds etoolbox euenc extractbb fancyvrb filehook firstaid float "
    "fontspec framed geometry gettitlestring glyphlist graphics graphics-cfg graphics-def helvetic hycolor hyperref "
    "hyph-utf8 iftex inconsolata infwarerr intcalc knuth-lib kvdefinekeys kvoptions kvsetkeys l3kernel l3packages latex "
    "latex-bin latex-fonts latexconfig latexmk letltxmacro lm lm-math ltxcmds lua-alt-getopt lua-uni-algos luahbtex "
    "lualatex-math lualibs luaotfload luatex mdwtools metafont mfware nameref natbib pdfescape pdftex pdftexcmds plain "
    "psnfss refcount rerunfilecheck stringenc tex tex-ini-files texlive-scripts-extra times tipa tools unicode-data "
    "unicode-math uniquecounter url xcolor xetex xetexconfig xkeyval xunicode zapfding "
    "make4ht tex4ht luaxml dvisvgm dvipng pgf tikz-cd xypic beamer mathtools enumitem amsrefs"
).split()

#: The year's frozen repository in the historic archive, which exists once the year closes.
FROZEN = (
    f"https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/{YEAR}/tlnet-final",
    f"https://ftp.tu-chemnitz.de/pub/tug/historic/systems/texlive/{YEAR}/tlnet-final",
    f"https://mirrors.tuna.tsinghua.edu.cn/tex-historic-archive/systems/texlive/{YEAR}/tlnet-final",
)
#: Named live mirrors, never a redirector, which can pick a mirror that lags or serves no package database.
LIVE = (
    "https://ctan.math.illinois.edu/systems/texlive/tlnet",
    "https://mirror.math.princeton.edu/pub/CTAN/systems/texlive/tlnet",
    "https://mirrors.rit.edu/CTAN/systems/texlive/tlnet",
    "https://ctan.math.utah.edu/ctan/tex-archive/systems/texlive/tlnet",
    "https://ctan.math.washington.edu/tex-archive/systems/texlive/tlnet",
)

#: Seconds a `tlmgr` run may take: an install, and anything else.
INSTALL_TIMEOUT = 600
TLMGR_TIMEOUT = 120
#: Seconds a repository is given to answer when one is chosen.
PROBE_TIMEOUT = 10

#: Where TeX Live and Homebrew put programs, searched after the path when the person's own TeX is in use.
KNOWN = ("/Library/TeX/texbin", "/opt/homebrew/bin", "/usr/local/bin")

LOOM, MINE, NONE = "loom", "mine", "none"


def data_dir() -> Path:
    """Loom's directory of machine-wide data: `~/Library/Application Support/loom` on a Mac, `$XDG_DATA_HOME/loom` elsewhere."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "loom"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "loom"


def tex_dir() -> Path:
    """Where loom's TeX is: `LOOM_TEX_DIR`, else `tex` in `data_dir`."""
    named = os.environ.get("LOOM_TEX_DIR")
    return Path(named) if named else data_dir() / "tex"


def tools_dir() -> Path:
    """Where loom's other programs are (Ghostscript, poppler): `tools` beside loom's TeX."""
    return tex_dir().parent / "tools"


def _state_file() -> Path:
    return tex_dir().parent / "tex.json"


def platform_key() -> str:
    """The key of `TINYTEX` and `ARCHIVE` for this machine."""
    if sys.platform == "darwin":
        return "darwin"
    return "linux-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "linux-x86_64"


def loom_bin(root: Path | None = None) -> Path | None:
    """The directory of loom's TeX programs, or None when loom's TeX is not installed there."""
    bins = (root or tex_dir()) / "bin"
    if not bins.is_dir():
        return None
    for d in sorted(bins.iterdir()):
        if (d / "kpsewhich").exists() and (d / "tlmgr").exists():
            return d
    return None


@dataclass(frozen=True)
class Settings:
    """What the person said about TeX in their loom configuration's `[tex]` table."""

    use: str = LOOM
    home_tree: bool = False


def settings() -> Settings:
    """The `[tex]` table of the person's loom configuration; defaults when it has none."""
    from loom.scan.quilt import load_user_config

    table = load_user_config().get("tex", {})
    if not isinstance(table, dict):
        return Settings()
    use = MINE if str(table.get("use", LOOM)).strip().lower() == MINE else LOOM
    return Settings(use, bool(table.get("home_tree", False)))


@dataclass(frozen=True)
class Tex:
    """The TeX a run uses: loom's own, the person's, or none."""

    kind: str
    bin: Path | None = None
    year: int | None = None

    @property
    def label(self) -> str:
        """How doctor and the viewer name it."""
        year = f"TeX Live {self.year}" if self.year else "TeX of an unknown year"
        if self.kind == LOOM:
            return f"loom's TeX ({year})"
        if self.kind == MINE:
            return f"your own TeX ({year})"
        return "no TeX"


def active(environ: os._Environ[str] | dict[str, str] | None = None, *, year: bool = True) -> Tex:
    """The TeX loom's runs use.

    Parameters
    ----------
    environ : mapping, optional
        Whose PATH the person's TeX is looked for on; default `os.environ`.
    year : bool, default True
        Ask the person's TeX its year, which runs a program; loom's own says it without one.

    Returns
    -------
    Tex
        Loom's when it is installed and the person has not chosen theirs; theirs when it is on the path (or in a known place, once chosen); else `NONE`.
    """
    env = os.environ if environ is None else environ
    own = loom_bin()
    if own is not None and settings().use == LOOM:
        return Tex(LOOM, own, _loom_year())
    path = env.get("PATH", "")
    if own is not None:
        path = os.pathsep.join(p for p in path.split(os.pathsep) if Path(p) != own)
    found = shutil.which("pdflatex", path=path) or shutil.which("latexmk", path=path)
    if found is None and settings().use == MINE:
        found = shutil.which("pdflatex", path=os.pathsep.join(KNOWN))
    if found is None:
        return Tex(NONE)
    where = Path(found).parent
    return Tex(MINE, where, _year_of(where) if year else None)


def _loom_year() -> int | None:
    """The year loom's installation says, from its state file or TeX Live's release file."""
    year = read_state().get("year")
    if isinstance(year, int):
        return year
    release = tex_dir() / "release-texlive.txt"
    if release.is_file():
        m = re.search(r"TeX Live.*?(\d{4})", release.read_text(encoding="utf-8", errors="replace"))
        if m:
            return int(m.group(1))
    return None


_YEARS: dict[Path, int | None] = {}


def _year_of(where: Path) -> int | None:
    """The TeX Live year of the TeX in `where`, from `pdftex --version`; None when it does not say."""
    if where not in _YEARS:
        year = None
        exe = where / "pdftex"
        if exe.exists():
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=20).stdout
                m = re.search(r"TeX Live (\d{4})", out)
                year = int(m.group(1)) if m else None
        _YEARS[where] = year
    return _YEARS[where]


def activate(environ: os._Environ[str] | dict[str, str] | None = None) -> Tex:
    """Put the active TeX, and loom's own programs, first on this process's PATH, so that every program loom starts and every lookup it makes finds them.

    Parameters
    ----------
    environ : mapping, optional
        The environment changed; default `os.environ`.

    Returns
    -------
    Tex
        What `active` chose.
    """
    env = os.environ if environ is None else environ
    tex = active(env, year=False)
    parts = [p for p in env.get("PATH", "").split(os.pathsep) if p]
    first: list[str] = []
    if tex.kind == LOOM and tex.bin is not None:
        first.append(str(tex.bin))
    if (tools_dir() / "bin").is_dir():
        first.append(str(tools_dir() / "bin"))
    last = [k for k in KNOWN if tex.kind == MINE and settings().use == MINE and k not in parts]
    env["PATH"] = os.pathsep.join([*first, *(p for p in parts if p not in first), *last])
    fonts = tools_dir() / "etc" / "fonts" / "fonts.conf"
    if fonts.is_file() and "FONTCONFIG_FILE" not in env:
        env["FONTCONFIG_FILE"] = str(fonts)
    return tex


def tex_vars() -> dict[str, str]:
    """What the environment of a TeX program takes from the TeX in use: Ghostscript for dvisvgm when loom ships one, and the person's own tree for loom's TeX when they asked for it."""
    out: dict[str, str] = {}
    gs = ghostscript_library()
    if gs is not None:
        out["LIBGS"] = str(gs)
    if "TEXMFHOME" not in os.environ and loom_bin() is not None and settings().use == LOOM:
        if settings().home_tree:
            out["TEXMFHOME"] = str(Path.home() / ("Library/texmf" if sys.platform == "darwin" else "texmf"))
    return out


def ghostscript_library() -> Path | None:
    """The Ghostscript library loom ships, or None."""
    for name in ("libgs.dylib", "libgs.so"):
        p = tools_dir() / "lib" / name
        if p.exists():
            return p
    return None


def ghostscript_available() -> bool:
    """Whether dvisvgm will find a Ghostscript: loom's, or one `LIBGS` names. Without one it ignores every PostScript special, which is how xy draws arrows unless told otherwise."""
    if ghostscript_library() is not None:
        return True
    named = os.environ.get("LIBGS", "")
    return bool(named) and Path(named).is_file()


def can_fetch() -> bool:
    """Whether loom may install packages: only into its own TeX, never the person's."""
    tex = active(year=False)
    return tex.kind == LOOM and tex.bin is not None and (tex.bin / "tlmgr").exists()


# ---- state ----------------------------------------------------------------------------


def read_state() -> dict[str, object]:
    """Loom's record of its TeX: the year, where it came from, and how many installs it has made since."""
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(**changes: object) -> None:
    state = {**read_state(), **changes}
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def stamp() -> str:
    """What tells one TeX installation's results from another's: which TeX, its year, and a counter loom bumps on every install into its own, so a cache keyed by it retries what an earlier installation could not make."""
    tex = active()
    if tex.kind == LOOM:
        return f"loom:{tex.year}:{read_state().get('installs', 0)}"
    if tex.kind == MINE:
        return f"mine:{tex.year}:{tex.bin}"
    return "none"


# ---- tlmgr ----------------------------------------------------------------------------


@dataclass
class Run:
    """What one `tlmgr` run did: its exit code (124 past its deadline, 127 when there is no tlmgr) and what it said."""

    code: int
    out: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


def tlmgr(args: list[str], *, timeout: float = TLMGR_TIMEOUT, root: Path | None = None) -> Run:
    """Run loom's `tlmgr` with `args` under a deadline.

    Parameters
    ----------
    args : list of str
    timeout : float, default TLMGR_TIMEOUT
        Seconds; past it the run's process group is killed and the code is 124.
    root : Path, optional
        The installation; default `tex_dir()`.

    Returns
    -------
    Run
    """
    bin_ = loom_bin(root)
    if bin_ is None:
        return Run(127, "loom's TeX is not installed")
    env = {**os.environ, "PATH": os.pathsep.join([str(bin_), os.environ.get("PATH", "")])}
    proc = subprocess.Popen(
        [str(bin_ / "tlmgr"), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        errors="replace",
        env=env,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return Run(124, (out or "") + f"\ntlmgr did not finish within {int(timeout)}s")
    return Run(proc.returncode, out or "")


def _answers(url: str, timeout: float = PROBE_TIMEOUT) -> bool:
    """Whether a TeX Live repository at `url` serves its package database's checksum."""
    try:
        with urllib.request.urlopen(f"{url}/tlpkg/texlive.tlpdb.sha512", timeout=timeout) as r:
            return bool(r.status == 200)
    except (OSError, ValueError):
        return False


def repository(probe: Callable[[str], bool] | None = None) -> str | None:
    """The repository loom's installs come from: the year's frozen one once it answers, else the first named live mirror that does; None when none answers.

    Parameters
    ----------
    probe : callable, optional
        Says whether a repository answers; default `_answers`. The answer is kept for a day.

    Returns
    -------
    str or None
    """
    state = read_state()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    kept = state.get("repository")
    if isinstance(kept, dict) and kept.get("checked") == today and isinstance(kept.get("url"), str):
        return str(kept["url"])
    answers = probe or _answers
    chosen = next((u for u in (*FROZEN, *LIVE) if answers(u)), None)
    if chosen is not None:
        _write_state(repository={"url": chosen, "checked": today})
    return chosen


@dataclass
class Fetched:
    """What an install did: the packages installed, those it could not, and why not."""

    installed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    reason: str = ""


def install_packages(packages: list[str], *, timeout: float = INSTALL_TIMEOUT) -> Fetched:
    """Install `packages` into loom's TeX from `repository`, one install at a time across every loom process.

    A package another run installed while this one waited counts as installed. One that failed, or ran past the deadline, in the last `RETRY_AFTER` seconds is not tried again, so the many runs of one build pay for a failure once; past a deadline the repository is chosen afresh.

    Parameters
    ----------
    packages : list of str
        TeX Live package names.
    timeout : float, default INSTALL_TIMEOUT

    Returns
    -------
    Fetched
        Nothing is installed when loom's TeX is not in use, or no repository answers (offline).
    """
    from loom.errors import EnvError
    from loom.locks import locked

    wanted = sorted(set(packages))
    if not wanted:
        return Fetched()
    if not can_fetch():
        return Fetched([], wanted, "loom installs packages only into its own TeX")
    try:
        with locked(tex_dir().parent / "tex.lock", wait=timeout + 60):
            return _install_held(wanted, timeout)
    except EnvError:
        return Fetched([], wanted, "another loom is installing packages; this one tries again on its next compile")


#: Seconds a package that failed to install is left alone before loom tries it again.
RETRY_AFTER = 3600


def _install_held(wanted: list[str], timeout: float) -> Fetched:
    """`install_packages` under the install lock."""
    have = _installed()
    present = [p for p in wanted if p in have]
    now = time.time()
    failed = read_state().get("failed")
    recent = (
        {k: v for k, v in failed.items() if isinstance(v, int | float) and now - v < RETRY_AFTER}
        if isinstance(failed, dict)
        else {}
    )
    skipped = [p for p in wanted if p not in have and p in recent]
    need = [p for p in wanted if p not in have and p not in recent]
    if not need:
        reason = "it failed to install within the last hour; loom tries again later" if skipped else ""
        return Fetched(present, skipped, reason)
    url = repository()
    if url is None:
        return Fetched(
            present, [*need, *skipped], "no TeX Live repository answers (offline?); loom fetches them when it is online"
        )
    run = tlmgr(["--repository", url, "install", *need], timeout=timeout)
    have = _installed()
    got = [p for p in need if p in have]
    lost = [p for p in need if p not in have]
    changes: dict[str, object] = {"failed": {**recent, **{p: now for p in lost}}}
    if got:
        changes["installs"] = int(str(read_state().get("installs", 0))) + 1
    if run.code == 124:
        changes["repository"] = {}
    _write_state(**changes)
    reason = "" if not lost else (_last_line(run.out) or f"tlmgr exited {run.code}")
    return Fetched(sorted([*present, *got]), sorted([*lost, *skipped]), reason)


def _installed() -> set[str]:
    """The packages loom's TeX holds, from its local package database."""
    db = tex_dir() / "tlpkg" / "texlive.tlpdb"
    try:
        text = db.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(re.findall(r"^name (\S+)$", text, re.M))


def _last_line(out: str) -> str:
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# ---- install, build, repair --------------------------------------------------------------


def _download(url: str, dest: Path, sha256: str | None, say: Callable[[str], None]) -> Path:
    """`url` (or a local path) copied to `dest`, its checksum checked when one is given."""
    if "://" not in url:
        shutil.copyfile(url, dest)
    else:
        say(f"downloading {url.rsplit('/', 1)[-1]}")
        with urllib.request.urlopen(url, timeout=60) as r, dest.open("wb") as out:
            shutil.copyfileobj(r, out, 1 << 20)
    if sha256:
        h = hashlib.sha256()
        with dest.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != sha256.lower():
            raise OSError(f"{url} does not have the checksum loom expects; nothing was installed")
    return dest


def _unpack(archive: Path, into: Path) -> Path:
    """Unpack a TeX archive into `into`; returns the installation's root, the directory holding `bin`."""
    with tarfile.open(archive) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(into, filter="data")
        else:  # pragma: no cover - Python before 3.11.4
            tar.extractall(into)  # noqa: S202
    for candidate in (into, *sorted(p for p in into.iterdir() if p.is_dir())):
        if (candidate / "bin").is_dir():
            return candidate
    raise OSError(f"{archive.name} holds no TeX installation")


def _place(root: Path, dest: Path) -> None:
    """Move a finished installation to `dest`, replacing what was there only once the new one is in place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    old = dest.with_name(f".{dest.name}.old")
    shutil.rmtree(old, ignore_errors=True)
    if dest.exists():
        dest.rename(old)
    root.rename(dest)
    shutil.rmtree(old, ignore_errors=True)


def install(source: str | None = None, *, say: Callable[[str], None] = lambda s: None) -> Tex:
    """Install loom's TeX: from an archive of a finished installation when one is named or released, else built from TinyTeX (`build`).

    Parameters
    ----------
    source : str, optional
        A path or URL of an archive; default `LOOM_TEX_ARCHIVE`, then `ARCHIVE` for this platform.
    say : callable, optional
        Handed a line for the person at each step.

    Returns
    -------
    Tex
        The installed TeX.
    """
    named = source or os.environ.get("LOOM_TEX_ARCHIVE")
    url, sha = (named, None) if named else ARCHIVE.get(platform_key(), (None, None))
    dest = tex_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".loom-tex-", dir=dest.parent) as tmp:
        work = Path(tmp)
        if url is None:
            root = build(work / "tinytex", say=say)
            origin = "built"
        else:
            if sha is None and "://" not in url and Path(f"{url}.sha256").is_file():
                sha = Path(f"{url}.sha256").read_text(encoding="utf-8").split()[0]
            archive = _download(url, work / "tex.tar.xz", sha, say)
            say("unpacking loom's TeX")
            root = _unpack(archive, work / "unpacked")
            origin = url
        _place(root, dest)
    _write_state(year=YEAR, source=origin, installed=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), installs=0)
    _YEARS.clear()
    return active()


def build(dest: Path, *, say: Callable[[str], None] = lambda s: None) -> Path:
    """Build loom's TeX in `dest` from the year's TinyTeX-0 and `SEED`: what `install` does with no archive, and what the release archives.

    Parameters
    ----------
    dest : Path
        An empty or absent directory; the installation's root is `dest/TinyTeX`.
    say : callable, optional

    Returns
    -------
    Path
        The installation's root.
    """
    url, sha = TINYTEX[platform_key()]
    dest.mkdir(parents=True, exist_ok=True)
    bundle = _download(url, dest / "tinytex.tar.xz", sha, say)
    root = _unpack(bundle, dest / "unpacked")
    bundle.unlink()
    say("setting up TeX for reading papers (one time, about 60 MB)")
    repo = repository() or LIVE[0]
    for args, limit in (
        (["--repository", repo, "update", "--self"], TLMGR_TIMEOUT),
        (["option", "repository", repo], TLMGR_TIMEOUT),
        (["--repository", repo, "install", *SEED], INSTALL_TIMEOUT * 2),
    ):
        run = tlmgr(args, timeout=limit, root=root)
        if not run.ok and args[-1] != repo:
            raise OSError(f"tlmgr {' '.join(args[2:4])} failed: {_last_line(run.out)}")
    return root


def tools_key() -> str:
    """The key of `TOOLS_ARCHIVE` for this machine: the tools are built per architecture."""
    machine = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    return f"{'darwin' if sys.platform == 'darwin' else 'linux'}-{machine}"


def tools_work() -> bool:
    """Whether loom's Ghostscript and poppler answer."""
    bin_ = tools_dir() / "bin"
    try:
        for argv in ([bin_ / "gs", "--version"], [bin_ / "pdftotext", "-v"]):
            if subprocess.run([str(a) for a in argv], capture_output=True, timeout=30).returncode != 0:
                return False
    except (OSError, subprocess.SubprocessError):
        return False
    return True


_FONTS_CONF = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>/System/Library/Fonts</dir>
  <dir>/Library/Fonts</dir>
  <cachedir prefix="xdg">loom-fontconfig</cachedir>
</fontconfig>
"""


def install_tools(source: str | None = None, *, say: Callable[[str], None] = lambda s: None) -> bool:
    """Install loom's Ghostscript and poppler beside its TeX, from the tools archive.

    Parameters
    ----------
    source : str, optional
        A path or URL of an archive; default `LOOM_TOOLS_ARCHIVE`, then `TOOLS_ARCHIVE` for this machine.
    say : callable, optional

    Returns
    -------
    bool
        False when there is no archive for this machine; otherwise True once the tools answer.
    """
    named = source or os.environ.get("LOOM_TOOLS_ARCHIVE")
    url, sha = (named, None) if named else TOOLS_ARCHIVE.get(tools_key(), (None, None))
    if url is None:
        return False
    dest = tools_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".loom-tools-", dir=dest.parent) as tmp:
        work = Path(tmp)
        if sha is None and "://" not in url and Path(f"{url}.sha256").is_file():
            sha = Path(f"{url}.sha256").read_text(encoding="utf-8").split()[0]
        archive = _download(url, work / "tools.tar.xz", sha, say)
        say("unpacking Ghostscript and poppler")
        root = _unpack(archive, work / "unpacked")
        fonts = root / "etc" / "fonts"
        fonts.mkdir(parents=True, exist_ok=True)
        (fonts / "fonts.conf").write_text(_FONTS_CONF, encoding="utf-8")
        _place(root, dest)
    _write_state(tools=url)
    return tools_work()


def assemble_tools(prefix: Path, dest: Path) -> Path:
    """Copy `TOOL_PROGRAMS` from a conda prefix, with every library they load from it, into `dest/tools`, and a NOTICE naming each package, its version, licence and home; what the release archives.

    Libraries are followed by `otool -L` through `@rpath`, so this runs on a Mac.
    """
    root = dest / "tools"
    todo = [prefix / rel for rel in TOOL_PROGRAMS]
    seen: set[Path] = set()
    while todo:
        f = todo.pop()
        real = f.resolve()
        if real in seen:
            continue
        seen.add(real)
        for path in {f, real}:
            target = root / path.relative_to(prefix)
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                if not target.exists():
                    target.symlink_to(os.readlink(path))
            elif not target.exists():
                shutil.copy2(path, target)
        listed = subprocess.run(["otool", "-L", str(real)], capture_output=True, text=True, check=True).stdout
        own = subprocess.run(["otool", "-D", str(real)], capture_output=True, text=True, check=True).stdout
        ids = set(own.splitlines()[1:])  # a library lists its own install name first, which is not a dependency
        for line in listed.splitlines()[1:]:
            dep = line.strip().split(" (", 1)[0]
            if dep in ids:
                continue
            if dep.startswith("@rpath/"):
                todo.append(prefix / "lib" / dep.removeprefix("@rpath/"))
            elif dep.startswith(str(prefix)):
                todo.append(Path(dep))
    lines = [
        "loom's tools: unmodified binaries from conda-forge (https://conda-forge.org), each under its own licence.",
        "",
    ]
    for meta in sorted((prefix / "conda-meta").glob("*.json")):
        info = json.loads(meta.read_text(encoding="utf-8"))
        files = {str(Path(x).name) for x in info.get("files", [])}
        if files & {p.name for p in seen}:
            lines.append(f"{info.get('name')} {info.get('version')}: {info.get('license')}, {info.get('url', '')}")
    (root / "NOTICE").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


@dataclass
class Repair:
    """What `repair` did, step by step, and whether loom's TeX works after it."""

    steps: list[str] = field(default_factory=list)
    ok: bool = False


def works(root: Path | None = None) -> bool:
    """Whether loom's TeX answers: kpsewhich finds a class and pdflatex starts."""
    bin_ = loom_bin(root)
    if bin_ is None:
        return False
    try:
        k = subprocess.run([str(bin_ / "kpsewhich"), "article.cls"], capture_output=True, text=True, timeout=30)
        p = subprocess.run([str(bin_ / "pdflatex"), "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return k.returncode == 0 and bool(k.stdout.strip()) and p.returncode == 0


def repair(*, say: Callable[[str], None] = lambda s: None) -> Repair:
    """Repair TeX: install loom's TeX when it is absent, does not answer or is another year, else put back any of `SEED` it lacks; then loom's Ghostscript and poppler when they do not answer.

    Touches nothing but loom's own directory.

    Parameters
    ----------
    say : callable, optional

    Returns
    -------
    Repair
    """
    done = Repair()
    if not works() or _loom_year() != YEAR:
        done.steps.append(
            "installed loom's TeX"
            if loom_bin() is None
            else f"reinstalled loom's TeX, which {'did not answer' if not works() else 'was another year'}"
        )
        install(say=say)
    else:
        lacking = [p for p in SEED if p not in _installed()]
        if lacking:
            got = install_packages(lacking)
            done.steps.append(
                f"installed {len(got.installed)} missing packages" + (f"; {got.reason}" if got.failed else "")
            )
    if not tools_work():
        if install_tools(say=say):
            done.steps.append("installed Ghostscript and poppler")
        elif tools_key() in TOOLS_ARCHIVE or os.environ.get("LOOM_TOOLS_ARCHIVE"):
            done.steps.append("Ghostscript and poppler did not answer after installing them")
    done.ok = works()
    if not done.steps:
        done.steps.append("loom's TeX answers; nothing to repair")
    return done


@contextlib.contextmanager
def _timed(say: Callable[[str], None], what: str) -> Iterator[None]:
    began = time.monotonic()
    yield
    say(f"{what} in {time.monotonic() - began:.0f}s")


def main(argv: list[str] | None = None) -> int:
    """`python -m loom.tex.private build DIR` and `tools PREFIX DIR`: the release's archives of loom's TeX and tools are made from these."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 3 and args[0] == "tools":
        print(assemble_tools(Path(args[1]), Path(args[2])))
        return 0
    if len(args) != 2 or args[0] != "build":
        print("usage: python -m loom.tex.private build DIR | tools PREFIX DIR", file=sys.stderr)
        return 2
    with _timed(lambda s: print(s, file=sys.stderr), "built"):
        root = build(Path(args[1]), say=lambda s: print(s, file=sys.stderr))
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
