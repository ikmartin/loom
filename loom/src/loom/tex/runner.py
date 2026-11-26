"""Run latexmk from a document's own directory into a build subdirectory.

The engine is the master's `% !TEX program` if present, else `[quilt] engine`. The environment names no search path: a document's local styles, inputs and figures sit in its directory and below, as LaTeX and Overleaf expect, which is what makes it compile on Overleaf too (P12). It does carry what limits a TeX program's writes and commands (`tex_env`). Tests isolate HOME and the TeX trees through the environment they run in.
"""

from __future__ import annotations

import atexit
import contextlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from loom import fence
from loom.clock import tex_date
from loom.tex import missing, private

ENGINE_FLAGS = {
    "pdflatex": ["-pdf"],
    "lualatex": ["-lualatex"],
    "xelatex": ["-xelatex"],
    "latex": ["-dvi"],
}


#: What kpathsea holds every TeX program loom starts to, whatever the distribution's configuration, the person's own or their shell says: it writes only in or below the directory it runs in, and runs no command but the few TeX Live lists as safe, which is how pdflatex converts an EPS figure. Nothing limits what a document reads: `openin_any` has no effect from TeX Live 2026 on, and before that refused the documents loom keeps under `.loom/`, so it is not set.
LIMITS = {"openout_any": "p", "shell_escape": "p"}
#: What a source nobody at loom wrote is compiled under: as `LIMITS`, and no command at all is started for it, a figure TeX would convert among them.
FOREIGN = {**LIMITS, "shell_escape": "f"}
#: Seconds of CPU each program a foreign compile starts may spend (`ulimit -t`): a TeX left running when loom is killed dies by itself.
FOREIGN_CPU = 600
#: The foreign compiles running now, ended with their process groups when loom exits.
_LIVE: set[subprocess.Popen[str]] = set()


def tex_env(*, foreign: bool = False) -> dict[str, str]:
    """The environment of a TeX program loom starts: latexmk, make4ht, and whatever they run in turn.

    Parameters
    ----------
    foreign : bool, default False
        For a source nobody at loom wrote, a work's in the library: `FOREIGN` in place of `LIMITS`.

    Returns
    -------
    dict of str to str
        `os.environ` with what the TeX in use takes (`private.tex_vars`), `tex_date`, `LIMITS`, and `PAR_GLOBAL_TMPDIR`, the machine's one folder for `biber` to unpack into (`machine.unpacked`), whatever `TMPDIR` says: TeX Live's `biber` unpacks about 200 MB into its temporary folder on its first run there.
    """
    from loom.machine import unpacked

    limits = FOREIGN if foreign else LIMITS
    return {**os.environ, **private.tex_vars(), **tex_date(), **limits, "PAR_GLOBAL_TMPDIR": str(unpacked())}


#: A line of the context TeX prints after every error it reports: the line it stopped at (`l.12 …`), or what it was reading instead (`<*> main.tex`, `<argument> …`).
_CONTEXT = re.compile(
    r"^(l\.\d+ |<(\*|insert|read [*\d]+|argument|template|recently read|to be read again|inserted text|output|every\w+|mark|write)> )"
)
#: How many lines after an error's own line TeX's context may begin: a LaTeX error's message runs over several.
_CONTEXT_WITHIN = 15


def tex_errors(text: str) -> list[str]:
    """The errors a TeX log reports, in order: each line beginning `!` that TeX follows with its context, which it prints after every error, and pdfTeX's closing `!  ==> Fatal error occurred`; a line a document writes that only begins with `!` (`\\typeout{! …}`) is no error."""
    lines = text.splitlines()
    return [
        ln
        for i, ln in enumerate(lines)
        if ln.startswith("!")
        and (
            ln.startswith("!  ==> Fatal error")
            or any(_CONTEXT.match(x) for x in lines[i + 1 : i + 1 + _CONTEXT_WITHIN])
        )
    ]


@dataclass
class CompileResult:
    ok: bool
    engine: str
    outdir: Path
    returncode: int
    stdout: str = ""
    errors: list[str] = field(default_factory=list)
    pdf: Path | None = None
    aux: Path | None = None
    log: Path | None = None
    warnings: list[str] = field(default_factory=list)
    cwd: Path | None = None  # where latexmk ran, which the log's relative paths are relative to
    fetched: list[str] = field(default_factory=list)
    needed: list[str] = field(default_factory=list)
    note: str = ""  # what loom fetched for this compile and what it still needs, for the person
    stopped: bool = False  # ended by `stop_run` or a signal before it finished: it says nothing of the document, and left nothing in `outdir`

    @property
    def first_error(self) -> str:
        """The first `!` line of the log, which is what TeX calls an error; latexmk's closing advice is not one. A package loom could not fetch comes first, since it is the cause."""
        if self.needed:
            return self.note
        if self.errors:
            return self.errors[0]
        summary = latexmk_summary(self.stdout)
        if summary:
            return f"latexmk exited {self.returncode}: {summary[0]}"
        if self.log is not None:
            return f"latexmk exited {self.returncode} with no error line in {self.log.name}"
        return (self.stdout.strip().splitlines() or ["latexmk failed"])[-1]

    @property
    def usable(self) -> str:
        """`ok`, `warnings` when a PDF was produced and the log holds no error, or `failed`.

        latexmk exits nonzero on an undefined reference, which produces a perfectly readable PDF. Reporting that as a failure is the difference between a check a reader can act on and one they must ignore, so the middle case is named rather than collapsed into either end.
        """
        if self.ok:
            return "ok"
        return "warnings" if self.pdf is not None and not self.errors else "failed"


def latexmk_summary(stdout: str) -> list[str]:
    """The lines under latexmk's "Collected error summary", which name a failing tool (biber, bibtex, makeindex) that leaves no `! ` line in the log."""
    lines = stdout.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Collected error summary"):
            out = []
            for ln in lines[i + 1 :]:
                if not ln[:1].isspace() or not ln.strip():
                    break
                out.append(ln.strip())
            return out
    return []


BUILD_PRODUCTS = (
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".dvi",
    ".fdb_latexmk",
    ".fls",
    ".idx",
    ".ilg",
    ".ind",
    ".lof",
    ".log",
    ".lot",
    ".nav",
    ".out",
    ".run.xml",
    ".snm",
    ".synctex.gz",
    ".toc",
    ".xdv",
)


def stage_sources(
    paper_dir: Path, dest: Path, outside: list[str] | tuple[str, ...] = (), *, regular_only: bool = False
) -> Path:
    """Copy a paper directory into `dest` without its build products; returns the copy of `paper_dir`, the root to compile.

    latexmk reads and rewrites a .bbl or .fdb_latexmk in its working directory even under -outdir, so compiling the author's directory in place both depends on their editor's leftovers and writes into it. Hidden directories are skipped; a .bbl is kept when the tree has no .bib, since an arXiv-style source ships only that. Files the paper reaches outside its directory (`outside`, as `closure_of` lists them) land at the same relative position, so `../macros` still resolves; a cited paper's source is given none. A link the directory holds is copied as what it reaches where that lies under the copy's root and no dot-named folder, and otherwise left out where the fence is up and copied where it is not (`_links`). With `regular_only`, for a source nobody at loom wrote, only folders and regular files with no other name are copied, judged by `lstat` alone: a link is never followed, and a device or a FIFO never opened.
    """
    paper_dir = paper_dir.resolve()
    reached = [Path(o).resolve() for o in outside if Path(o).is_file()]
    anchor = Path(os.path.commonpath([paper_dir, *reached])) if reached else paper_dir
    root = dest / paper_dir.relative_to(anchor)
    has_bib = any(paper_dir.rglob("*.bib"))

    def ignore(folder: str, names: list[str]) -> set[str]:
        skip = set()
        for n in names:
            if regular_only and not _plain(Path(folder) / n):
                skip.add(n)
            elif n.startswith(".") and (Path(folder) / n).is_dir():
                skip.add(n)
            elif n.endswith(BUILD_PRODUCTS) and not (n.endswith(".bbl") and not has_bib):
                skip.add(n)
        return skip

    shutil.copytree(paper_dir, root, ignore=ignore, symlinks=True)
    _links(root, paper_dir, anchor)
    for f in reached:
        target = dest / f.relative_to(anchor)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, target)
    return root


def _plain(path: Path) -> bool:
    """Whether `path` is a folder, or a regular file with no other name, by `lstat` alone."""
    import stat

    try:
        st = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) or (stat.S_ISREG(st.st_mode) and st.st_nlink == 1)


def which_latexmk() -> str | None:
    return shutil.which("latexmk")


def normalise_engine(engine: str | None, default: str = "pdflatex") -> str:
    e = (engine or default).strip().lower()
    return e if e in ENGINE_FLAGS else default


def compile_document(
    root: Path,
    base: str,
    tex: str | Path,
    outdir: Path,
    engine: str = "pdflatex",
    halt_on_error: bool = True,
    timeout: int = 600,
    started: Callable[[subprocess.Popen[str]], None] | None = None,
    overlay: Mapping[str, bytes] | None = None,
) -> CompileResult:
    """Compile a document from `base`, the quilt-relative directory it compiles from (P12), in a clean copy of that directory (`stage_document`), with `overlay`'s files (quilt-relative) written into the copy: a document not yet written, compiled as it would be.

    A document's directory holds whatever its author's editor left there, and latexmk reads a `.bcf`, `.aux` or `.toc` it finds in its working directory and runs biber there even under `-outdir`; compiling the directory in place both depends on those leftovers and writes into it. The log's relative names are the document's directory's, which `CompileResult.cwd` says.

    Parameters
    ----------
    root : Path
        The quilt root.
    base : str
        The document's directory, `ScanResult.base_of`; '' at the root.
    tex : str or Path
        The file to compile, quilt-relative or absolute; named to latexmk from `base`, so an agent copy compiles as `../.loom/agents/copies/x.tex` from its source's directory.
    outdir : Path
        Where latexmk writes.
    engine : str, default 'pdflatex'
    halt_on_error : bool, default True
    timeout : int, default 600
        Seconds.
    started : callable, optional
        Handed latexmk's process as it starts, for a caller that may end it with `stop_run`.

    Returns
    -------
    CompileResult
        Its `pdf` and `aux` are None when this run made no PDF, though the last good ones stay in `outdir`.
    """
    tex_rel = Path(tex).relative_to(root).as_posix() if Path(tex).is_absolute() else Path(tex).as_posix()
    with tempfile.TemporaryDirectory(prefix="loom-compile-") as tmp:
        stage = stage_document(root, base, [tex_rel], Path(tmp), overlay)
        cwd = stage / base
        res = compile_tex(
            cwd, os.path.relpath(stage / tex_rel, cwd), outdir, engine, halt_on_error, timeout, started, reads=stage
        )
    res.cwd = root / base
    return res


def stage_document(
    root: Path, base: str, extra: list[str], dest: Path, overlay: Mapping[str, bytes] | None = None
) -> Path:
    """A copy of the document directory `base` under `dest`, at its quilt-relative place, for latexmk to run in; returns `dest`.

    Left out: build products (`BUILD_PRODUCTS`; a `.bbl` stays when the directory has no `.bib`, as an arXiv source ships only that), hidden directories, the directories never read as a document's (`scan.source.SKIP_DIRS`), and the sync directory. `extra` (quilt-relative files, the document itself when it sits elsewhere, as an agent copy or a closure does) is copied to its own place. Files are copied, never linked, since a package may rewrite a file in its working directory (a TikZ externalisation, a `filecontents`); a link the directory holds is copied as what it reaches where that lies in the quilt under no dot-named folder, and otherwise left out where the fence is up and copied where it is not (`_links`).
    """
    from loom.scan.source import SKIP_DIRS
    from loom.sync import skipped_directory

    synced = skipped_directory(root)
    top = root / base
    has_bib = any(top.rglob("*.bib"))

    def ignore(folder: str, names: list[str]) -> set[str]:
        rel = Path(folder).relative_to(root).as_posix()
        skip = set()
        for n in names:
            path = Path(folder) / n
            where = f"{rel}/{n}" if rel != "." else n
            if path.is_dir() and (n.startswith(".") or n in SKIP_DIRS or where == synced):
                skip.add(n)
            elif n.endswith(BUILD_PRODUCTS) and not (n.endswith(".bbl") and not has_bib):
                skip.add(n)
        return skip

    if top.is_dir():
        shutil.copytree(top, dest / base, ignore=ignore, dirs_exist_ok=True, symlinks=True)
        _links(dest / base, top, root)
    (dest / base).mkdir(parents=True, exist_ok=True)
    for rel, data in (overlay or {}).items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_bytes(data)
    for rel in extra:
        target, source = dest / rel, root / rel
        if source.is_symlink() and fence.state() is None:
            if not _linkable(Path(os.path.realpath(source)), Path(os.path.realpath(root))):
                continue  # as a link in the document's folder is (`_links`)
        if source.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return dest


def _links(staged: Path, original: Path, inside: Path) -> None:
    """In `staged`, a copy of `original` made keeping its links, each link replaced by a copy of what it reaches where that is in `inside` under no dot-named folder (`_linkable`), as a shared macro file elsewhere in the quilt is; any other link is left out where the fence is up (`loom.fence`), and copied as what it reaches where it is not, as every link was before the fence. So a staged copy holds no link, and nothing loom does to it reads or writes through one.

    A folder copied where the fence is up leaves out every dot-named name in it, as `_linkable` would refuse a link to each. A link to a folder that holds the link itself, the quilt's root among them, is left out fenced or not, since copying it never ends.
    """
    fenced = fence.state() is None
    bound = Path(os.path.realpath(inside))
    for folder, dirs, files in os.walk(staged):
        for name in [*dirs, *files]:
            link = Path(folder) / name
            if not link.is_symlink():
                continue
            place = original / link.relative_to(staged)
            real = Path(os.path.realpath(place))
            link.unlink()
            if fenced and not _linkable(real, bound):
                continue
            if real.is_dir():
                if Path(os.path.realpath(place.parent)).is_relative_to(real):
                    continue  # the folder holds the link: its copy would hold the link again, without end
                shutil.copytree(real, link, symlinks=True, ignore=_dot_named if fenced else None)
            elif real.is_file():
                shutil.copy2(real, link)


def _dot_named(folder: str, names: list[str]) -> set[str]:
    """`shutil.copytree`'s ignore for a folder a link reaches in a fenced stage: every name beginning with a dot."""
    return {n for n in names if n.startswith(".")}


def _linkable(real: Path, bound: Path) -> bool:
    """Whether a link that reaches `real` is copied into a fenced stage: a file or folder in `bound`, the quilt or a paper's folders, under no folder whose name begins with a dot, `.git` and `.loom` among them."""
    return real.is_relative_to(bound) and not any(p.startswith(".") for p in real.relative_to(bound).parts)


def compile_tex(
    root: Path,
    tex_rel: str,
    outdir: Path,
    engine: str = "pdflatex",
    halt_on_error: bool = True,
    timeout: int = 600,
    started: Callable[[subprocess.Popen[str]], None] | None = None,
    *,
    foreign: bool = False,
    online: bool = True,
    reads: Path | None = None,
) -> CompileResult:
    """Compile `tex_rel` (relative to `root`) with latexmk into `outdir`, fetching what it lacks into loom's TeX; return a result even when latexmk is missing.

    Under loom's own TeX the preamble is checked first and what it names that TeX lacks is installed in one go (`missing.preflight`); a run that still fails on a missing file, font or program has it fetched and runs again, up to `missing.ROUNDS` times. A foreign source's compile fetches only what its own text names, never what its log does, since the log is the source's to write and the names asked of the mirror would carry what it read out of the machine. The person's own TeX is never installed into. `fetched`, `needed` and `note` say what happened.

    Parameters
    ----------
    root : Path
        The directory latexmk runs in.
    tex_rel : str
        The document, relative to `root`.
    outdir : Path
        Where latexmk writes.
    engine : str, default 'pdflatex'
    halt_on_error : bool, default True
    timeout : int, default 600
        Seconds for each run.
    started : callable, optional
        Handed latexmk's process as it starts, for a caller that may end it with `stop_run`.
    foreign : bool, default False
        A source nobody at loom wrote: compiled under `FOREIGN` (`tex_env`), each program capped at `FOREIGN_CPU` seconds of CPU, ended when loom exits, and fetched for from its text alone.
    online : bool, default True
        Whether the network may be used to fetch what it lacks.
    reads : Path, optional
        The folder of staged sources the run may read where the fence is up (`loom.fence`), when it holds more than `root`; default `root`.

    Returns
    -------
    CompileResult
    """
    fetching = private.can_fetch() and online
    rounds = missing.Round()
    if fetching:
        rounds.fetch(missing.preflight(root, tex_rel))
    res = _compile_once(root, tex_rel, outdir, engine, halt_on_error, timeout, started, reads or root, foreign=foreign)
    for _ in range(missing.ROUNDS):
        if res.ok or not fetching or foreign or res.returncode == 124 or res.stopped:
            break
        log = res.log.read_text(encoding="utf-8", errors="replace") if res.log is not None else ""
        if not rounds.fetch(missing.from_log(log, res.stdout)):
            break
        res = _compile_once(
            root, tex_rel, outdir, engine, halt_on_error, timeout, started, reads or root, foreign=foreign
        )
    res.fetched, res.needed, res.note = rounds.fetched, rounds.needed, rounds.note
    return res


def _compile_once(
    root: Path,
    tex_rel: str,
    outdir: Path,
    engine: str,
    halt_on_error: bool,
    timeout: int,
    started: Callable[[subprocess.Popen[str]], None] | None,
    reads: Path,
    *,
    foreign: bool = False,
) -> CompileResult:
    """One latexmk run of `tex_rel` into `outdir`.

    latexmk reads no rc file (`-norc`): one in a quilt is a Perl program, and one at home may turn on shell escape. The run writes into a scratch directory beside `outdir`, seeded with `outdir`'s files so latexmk still runs only the passes it needs, and its output replaces `outdir`'s only when it made a PDF: a failed run leaves the last good PDF and aux in place, and only its log is kept. The run is a process group of its own, killed whole on timeout or by `stop_run` on the process `started` is handed; a run that times out, is stopped or dies of a signal keeps nothing, so the last whole compile's log stays.

    Where the fence is up (`loom.fence`) latexmk runs inside it, reading `reads` and writing the run's folder, its temporary folder there and, for a document that uses biblatex, biber's unpacked folder cloned there (`_fenced_env`); a fenced run that fails is never run again unfenced.
    """
    engine = normalise_engine(engine)
    exe = which_latexmk()
    outdir.mkdir(parents=True, exist_ok=True)
    if exe is None:
        return CompileResult(False, engine, outdir, 127, errors=["latexmk is not installed"])
    stem = Path(tex_rel).stem
    made = {f"{stem}.pdf", f"{stem}.dvi"}
    run = Path(tempfile.mkdtemp(prefix=f".{outdir.name}.run-", dir=outdir.parent))
    try:
        # what tells this run's success is a PDF of its own making, and its log must be its own
        shutil.copytree(
            outdir,
            run,
            dirs_exist_ok=True,
            ignore=lambda d, names: {n for n in names if Path(d) == outdir and (n in made or n == f"{stem}.log")},
        )
        cmd = [exe, "-norc", *ENGINE_FLAGS[engine], "-interaction=nonstopmode", f"-outdir={run}"]
        if halt_on_error:
            cmd.append("-halt-on-error")
        cmd.append(tex_rel)
        if foreign:
            # `ulimit -t` holds in every program latexmk starts, so a TeX outlives a killed loom by its CPU cap at most
            cmd = ["/bin/sh", "-c", f'ulimit -t {FOREIGN_CPU} && exec "$@"', "sh", *cmd]
        env = tex_env(foreign=foreign)
        lua = engine == "lualatex"
        if fence.state() is None:
            env = {**_fenced_env(env, reads, run, lua=lua), "PWD": str(root)}
            cmd = fence.fenced(cmd, stage=reads, out=run, var=Path(env["TEXMFVAR"]))
        proc = subprocess.Popen(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=env,
            start_new_session=True,
        )
        if started is not None:
            started(proc)
        if foreign:
            _LIVE.add(proc)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_run(proc)
            proc.communicate()
            return CompileResult(False, engine, outdir, 124, errors=[f"latexmk timed out after {timeout}s"])
        finally:
            _LIVE.discard(proc)
        if proc.returncode < 0 or getattr(proc, "loom_stopped", False):
            # cut short, its log is part of a run: what the last whole compile left stays
            return CompileResult(
                False, engine, outdir, proc.returncode, out + err, ["the compile was stopped"], stopped=True
            )
        if lua and fence.state() is None:
            fence.after_run(run / FENCED / "texmf-var")
        made_one = any((run / n).is_file() for n in made)
        for f in sorted(run.rglob("*")) if made_one else [run / f"{stem}.log"]:
            if f.is_file() and f.relative_to(run).parts[0] != FENCED:
                target = outdir / f.relative_to(run)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(f, target)
    finally:
        shutil.rmtree(run, ignore_errors=True)
    log = outdir / f"{stem}.log"
    errors: list[str] = []
    warnings: list[str] = []
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        errors = tex_errors(text)
        warnings = re.findall(r"^(?:LaTeX|Package \w+|Class \w+) Warning: .*$", text, re.M)
    pdf = outdir / f"{stem}.pdf"
    aux = outdir / f"{stem}.aux"
    return CompileResult(
        proc.returncode == 0 and made_one and pdf.exists(),
        engine,
        outdir,
        proc.returncode,
        out + err,
        errors,
        pdf if made_one and pdf.exists() else None,
        aux if made_one and aux.exists() else None,
        log if log.exists() else None,
        warnings,
        root,
    )


@atexit.register
def _end_live() -> None:
    """End every foreign compile still running when loom exits, with what it started."""
    for proc in list(_LIVE):
        stop_run(proc)


#: The folder in a fenced run's folder for its temporary files and biber's clone, never kept with the output.
FENCED = ".loom-fenced"


def _fenced_env(env: dict[str, str], reads: Path, run: Path, *, lua: bool = False) -> dict[str, str]:
    """`env` for a run inside the fence, whose caller also sets `PWD` to where it runs, as a shell does, since Perl asks `/bin/pwd`, which may not look at a folder outside the fence: a TeX cache of the run's own, cloned from loom's (`fence.run_var`, with LuaTeX's font database where `lua`), its temporary folder in the run's folder, and biber's own (`PAR_GLOBAL_TMPDIR`, and `PAR_GLOBAL_TEMP` where set) there too. Where the sources use biblatex each is a copy-on-write clone of the folder it named, made there, since the fence lets a run neither write nor read the machine's unpacked biber, and an empty one would have biber unpack 200 MB on every run."""
    own = run / FENCED
    (own / "tmp").mkdir(parents=True, exist_ok=True)
    env = {**env, "TMPDIR": str(own / "tmp"), "TEXMFVAR": str(fence.run_var(own, lua=lua))}
    biblatex = _uses_biblatex(reads)
    for var in ("PAR_GLOBAL_TMPDIR", "PAR_GLOBAL_TEMP"):
        if var not in env:
            continue
        unpacked, clone = Path(env[var]), own / var.lower()
        made = (
            biblatex
            and unpacked.is_dir()
            and subprocess.run(
                ["/bin/cp", "-c", "-R", str(unpacked), str(clone)], capture_output=True, check=False
            ).returncode
            == 0
        )
        env[var] = str(clone if made else own / "tmp")
    return env


def _uses_biblatex(folder: Path) -> bool:
    """Whether a TeX source in `folder` names biblatex, whose biber the run may start."""
    for f in folder.rglob("*"):
        if f.suffix in (".tex", ".sty", ".cls", ".ltx") and f.is_file():
            try:
                if b"biblatex" in f.read_bytes():
                    return True
            except OSError:
                continue
    return False


def stop_run(proc: subprocess.Popen[str]) -> None:
    """End a compile `compile_tex` started, with every program latexmk ran: TERM to its process group, then KILL to what is left after two seconds. The run is marked, so it moves nothing into its compile folder, whatever latexmk exits with."""
    setattr(proc, "loom_stopped", True)  # noqa: B010 -- a mark on the process object, read where the run ends
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)
