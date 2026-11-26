"""The compiles `loom serve` runs in the background: each document whose files changed, the one being read first, as many at once as there are workers; and what a document's last compile says, read from its log.

A document asked for while it compiles runs once more afterwards, however often it was asked; one asked for while it waits keeps its place and waits `delay` again, so a burst of saves is one run. How each stands is what the stream and `loom status` report. A compile that stopped on an error or finished with errors is a problem on its document (`compile_problems`), in the manifest and in `loom lint`, whichever compile left the log, the server's or `loom compile`'s.
"""

from __future__ import annotations

import functools
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from loom.scan.model import Diagnostic, Location
from loom.tex.runner import CompileResult, fence_refused, stop_run, tex_errors

#: The line of the log that says where TeX was when it stopped: `l.12 \hlind{...}`.
_AT = re.compile(r"^l\.\d+ .*$", re.M)
#: A file TeX opens, as its log shows it: `(` then a path with an extension.
_OPENED = re.compile(r"\(([^\s()]+\.[A-Za-z]+)")
#: The line TeX stopped at, after an error: `l.12 <the text up to the point>`.
_STOPPED = re.compile(r"^l\.(\d+) (.*)$", re.M)
_MACRO = re.compile(r"\\(?:[A-Za-z@]+|.)")
#: What TeX writes when it made a PDF or DVI, whatever went wrong before it.
_WRITTEN = re.compile(r"^Output written on ", re.M)
#: The codes `compile_problems` reports.
COMPILE_CODES = frozenset({"loom:compile-failed", "loom:compile-errors"})


@dataclass
class Last:
    """How a document's last compile ended: `ok`; `errors`, a PDF made though LaTeX reported errors; or `failed`, no PDF, so the last good one stays."""

    result: str
    ended: str
    error: str | None = None
    at: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"result": self.result, "ended": self.ended, "error": self.error, "at": self.at}


def last_of(res: CompileResult, ended: str) -> Last:
    """What a compile's result says to a reader: whether it made a PDF, and the first error with the line TeX stopped at."""
    if res.pdf is not None and not res.errors:
        return Last("ok", ended)
    at = None
    if res.log is not None and res.errors:
        text = res.log.read_text(encoding="utf-8", errors="replace")
        cut = text.find(res.errors[0])
        found = _AT.search(text, cut if cut >= 0 else 0)
        at = found.group(0).strip()[:200] if found else None
    return Last("errors" if res.pdf is not None else "failed", ended, res.first_error[:300], at)


def _unwrapped(text: str) -> str:
    """The log with the lines TeX broke at its 79th byte joined again, so that a long path reads whole."""
    out: list[str] = []
    held = ""
    for line in text.split("\n"):
        held += line
        if len(line.encode("utf-8")) != WRAP:
            out.append(held)
            held = ""
    return "\n".join([*out, held] if held else out)


#: Where TeX breaks a log line, `max_print_line`.
WRAP = 79


def error_place(res: CompileResult, root: Path) -> dict[str, Any] | None:
    """Where the log's first error is: the file TeX was reading, the line of that file it stopped at, and for an undefined control sequence the macro.

    The file is the innermost one the log's `(file` and `)` leave open, whatever its kind, a package's or the bibliography's as much as an input's: TeX's line is a line of that file. A file is quilt-relative where it lies in the quilt, else absolute; where the log leaves an opening it cannot read innermost, neither the file nor a line is said. A log that says less gives None, or the fields it does say.
    """
    if res.log is None or not res.errors:
        return None
    try:
        text = res.log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    at = text.find(res.errors[0])
    whole = _unwrapped(text)
    upto = whole.find(res.errors[0])
    if at < 0 or upto < 0:
        return None
    stack: list[str | None] = []
    for i in range(upto):
        c = whole[i]
        if c == "(":
            m = _OPENED.match(whole, i)
            stack.append(m.group(1) if m else None)
        elif c == ")" and stack:
            stack.pop()
    reading = stack[-1] if stack else None
    out: dict[str, Any] = {"file": None, "line": None, "macro": None}
    if reading:
        # the log names files from where latexmk ran, the document's own directory (P12)
        p = Path(reading) if Path(reading).is_absolute() or res.cwd is None else res.cwd / reading
        rel = (
            p.resolve().relative_to(root.resolve())
            if p.is_absolute() and p.resolve().is_relative_to(root.resolve())
            else p
        )
        out["file"] = rel.as_posix().removeprefix("./")
    stopped = _STOPPED.search(text, at)
    if stopped is not None and text.count("\n", at, stopped.start()) <= 8:
        if reading:
            out["line"] = int(stopped.group(1))
        if "Undefined control sequence" in res.errors[0]:
            macros = _MACRO.findall(stopped.group(2))
            out["macro"] = macros[-1] if macros else None
    return out if any(out.values()) else None


def _openable(result: Any, path: str | None) -> str | None:
    """`path` when it is a file of the quilt the viewer shows the person, their own `.tex`, `.sty`, `.cls` or `.bib`; None for TeX's own files, loom's and the compile's."""
    from loom.files import Shown

    if not path or path.startswith("/") or not (result.quilt.root / path).is_file():
        return None
    return path if Shown.of(result.quilt).is_shown(path) else None


def _changed_since(result: Any, doc: str, made: float) -> str | None:
    """The first file `doc` reads, itself, what it inputs and its local styles, that changed after `made`, the time its log was written; None when none did."""
    root = result.quilt.root
    for rel in sorted(_reads(result, doc)):
        try:
            if (root / rel).stat().st_mtime > made:
                return str(rel)
        except OSError:
            continue
    return None


def compile_problems(result: Any) -> list[Diagnostic]:
    """`loom:compile-failed` for each document whose last compile stopped on a TeX error and made no PDF, `loom:compile-errors` for one that made its PDF though TeX reported errors; none where its log reports no error, or where it has none.

    Read from the log in the document's compile folder, which every compile of it leaves, so the problem goes when a compile succeeds. Each is on the document's key; its location is the file TeX was reading and its line where that file is one the person can open, and none otherwise, the message naming the file. It is an error while the log is newer than every file the document reads, and a warning saying so once one has changed since, until the next compile: what it says may be mended already.
    """
    from loom.paths import document_build

    root = result.quilt.root
    out: list[Diagnostic] = []
    for doc in result.masters:
        log = root / document_build(doc) / f"{Path(doc).stem}.log"
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
            made = log.stat().st_mtime
        except OSError:
            continue
        errors = tex_errors(text)
        if not errors:
            continue
        res = CompileResult(False, "", log.parent, 1, errors=errors, log=log, cwd=root / result.base_of(doc))
        place = error_place(res, root) or {}
        said = (
            fence_refused(errors[0], root / result.base_of(doc), root)
            or errors[0].removeprefix("!").strip().rstrip(".").rstrip()
        )
        if place.get("macro"):
            said += f" {place['macro']}"
        reading, line = place.get("file"), place.get("line")
        own = _openable(result, reading)
        if reading and own != doc:
            # TeX's line is a line of the file it was reading, never of the document
            name = own or PurePosixPath(str(reading)).name
            said += f", in {name}" + (f", line {line}" if line and not own else "")
            if name.endswith(".bbl"):
                said += " (the bibliography BibTeX made from the .bib)"
        locations = [Location(own, line)] if own and line else []
        changed = _changed_since(result, doc, made)
        when = f" when last compiled, before {changed} changed" if changed else ""
        if _WRITTEN.search(text):
            n = len(errors)
            code = "loom:compile-errors"
            message = f"{doc} compiled with {n} error{'s' if n != 1 else ''}{when}, the first: {said}"
        else:
            code, message = "loom:compile-failed", f"{doc} did not compile{when}: {said}"
        out.append(Diagnostic("warning" if changed else "error", code, message, locations, [doc]))
    return out


class Compiles:
    """A queue of document compiles served by a fixed number of worker threads, started on first use.

    Parameters
    ----------
    run : callable
        `run(doc, started)` compiles one document and returns its `CompileResult`; `started` is handed latexmk's process so `stop` can end it.
    workers : int, default 2
    delay : float, default 0.4
        Seconds a document waits after the last ask before it compiles.
    first : callable, optional
        The document the reader has open, or None; it is taken before any other that is due.
    told : callable, optional
        Called, outside the lock, after any change to how a compile stands.
    made : callable, optional
        Called with a document whose run made a PDF, from the worker that ran it.
    failed : callable, optional
        Called with a document whose run ended and made none, from the worker that ran it. A run that was stopped is told as neither, and changes nothing of how its document stands.
    """

    def __init__(
        self,
        run: Callable[[str, Callable[[Any], None]], CompileResult],
        *,
        workers: int = 2,
        delay: float = 0.4,
        first: Callable[[], str | None] = lambda: None,
        told: Callable[[], None] = lambda: None,
        made: Callable[[str], None] = lambda doc: None,
        failed: Callable[[str], None] = lambda doc: None,
    ) -> None:
        self._run = run
        self._workers = workers
        self.delay = delay
        self._first = first
        self._told = told
        self._made = made
        self._failed = failed
        self._cond = threading.Condition()
        self._due: dict[str, float] = {}  # waiting, by when it may start
        self._running: dict[str, Any] = {}  # compiling, with latexmk's process once it has one
        self._again: set[str] = set()
        self._last: dict[str, Last] = {}
        self._threads: list[threading.Thread] = []
        self._stopped = False
        self.runs = 0

    def want(self, docs: Iterable[str]) -> None:
        """Ask for each of `docs` to be compiled: queued, its wait restarted, or marked to run again after the run under way."""
        changed = False
        with self._cond:
            if self._stopped:
                return
            for doc in docs:
                if doc in self._running:
                    changed |= doc not in self._again
                    self._again.add(doc)
                else:
                    changed |= doc not in self._due
                    self._due[doc] = time.monotonic() + self.delay
            while len(self._threads) < self._workers:
                t = threading.Thread(target=self._work, name=f"loom-compile-{len(self._threads)}", daemon=True)
                self._threads.append(t)
                t.start()
            self._cond.notify_all()
        if changed:
            self._told()

    def state(self) -> dict[str, Any]:
        """Each document this server has compiled or will: `state` (`queued`, `compiling` or `idle`) and its `last` run, None before one ends."""
        with self._cond:
            docs = set(self._due) | set(self._running) | set(self._last)
            out: dict[str, Any] = {}
            for doc in sorted(docs):
                state = "compiling" if doc in self._running else "queued" if doc in self._due else "idle"
                last = self._last.get(doc)
                out[doc] = {"state": state, "again": doc in self._again, "last": last.to_json() if last else None}
            return out

    def idle(self, timeout: float) -> bool:
        """Wait until nothing is queued or compiling, at most `timeout` seconds; whether it got there."""
        with self._cond:
            return self._cond.wait_for(lambda: not self._due and not self._running, timeout)

    def stop(self) -> None:
        """Take nothing more, and end every compile under way with its whole process group."""
        with self._cond:
            self._stopped = True
            self._due.clear()
            self._again.clear()
            running = [p for p in self._running.values() if p is not None]
            self._cond.notify_all()
        for proc in running:
            stop_run(proc)

    def _next(self) -> tuple[str | None, float | None]:
        """The due document to compile now, the open one before the rest, else how long until one is due."""
        now = time.monotonic()
        due = [d for d, t in self._due.items() if t <= now]
        if not due:
            return None, (min(self._due.values()) - now if self._due else None)
        try:
            first = self._first()
        except Exception:  # noqa: BLE001 -- where the reader is only orders the queue
            first = None
        return (first if first in due else min(due, key=self._due.__getitem__)), None

    def _hold(self, doc: str, proc: Any) -> None:
        with self._cond:
            stopped = self._stopped
            if not stopped:
                self._running[doc] = proc
        if stopped:
            stop_run(proc)

    def _work(self) -> None:
        from loom.clock import stamp

        while True:
            with self._cond:
                while True:
                    if self._stopped:
                        return
                    doc, wait = self._next()
                    if doc is not None:
                        break
                    self._cond.wait(wait)
                del self._due[doc]
                self._running[doc] = None
                self.runs += 1
            self._told()
            res: CompileResult | None
            held = functools.partial(self._hold, doc)
            try:
                res = self._run(doc, held)
                last = last_of(res, stamp())
            except Exception as exc:  # noqa: BLE001 -- one document's compile must not end the server's
                res = None
                last = Last("failed", stamp(), f"{type(exc).__name__}: {exc}"[:300])
            # a run cut short says nothing of the document, and once the queue is stopped nothing more is told
            cut = res is not None and res.stopped
            with self._cond:
                del self._running[doc]
                stopped = self._stopped
                if not cut:
                    self._last[doc] = last
                if doc in self._again and not stopped:
                    self._again.discard(doc)
                    self._due[doc] = time.monotonic() + self.delay
                self._cond.notify_all()
            if stopped:
                return
            self._told()
            if res is None or cut:
                continue
            if res.pdf is not None:
                self._made(doc)
            else:
                self._failed(doc)


def served(root: Path) -> dict[str, Any] | None:
    """How the compiles of the server running on `root` stand, as the stream says it; None when no server runs on this quilt or its record cannot be read.

    A server's record outlives it and travels with a copied quilt, so it counts only while its process lives and it names this quilt (`serve.open_url`).
    """
    import json

    from loom.paths import COMPILES
    from loom.render.serve import open_url

    if not open_url(root):
        return None
    try:
        state = json.loads((root / COMPILES).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) else None


def needs_compiling(
    result: Any, changed: Iterable[Path] | None, built: Callable[[str], Path], *, pages: bool = False
) -> list[str]:
    """The documents a change reaches, or with `changed` None every document whose PDF is missing or older than what it reads, and with `pages` every document with no page beside its PDF.

    A document reaches its master, the files it inputs and its preamble's local styles; any other file it may read sits in its own directory or below (P12), so a changed file there of a kind TeX reads counts too. `built` names a document's compiled PDF; its page is `html/<stem>.html` beside it, which a server asks for when TeX4ht is installed to make one.
    """
    root = result.quilt.root
    reads = {m: _reads(result, m) for m in result.masters}
    if changed is None:
        out = []
        for m, files in reads.items():
            pdf = built(m)
            if not pdf.exists() or (pages and not (pdf.parent / "html" / f"{Path(m).stem}.html").is_file()):
                out.append(m)
                continue
            made = pdf.stat().st_mtime
            if any((root / f).exists() and (root / f).stat().st_mtime > made for f in files):
                out.append(m)
        return out
    rel = [p.relative_to(root).as_posix() for p in changed if p.is_relative_to(root)]
    out = []
    for m, files in reads.items():
        base = result.base_of(m)
        under = [r for r in rel if Path(r).suffix.lower() in TEX_READS and (not base or r.startswith(base + "/"))]
        if any(r in files for r in rel) or under:
            out.append(m)
    return out


#: Kinds of file a document may read without the scan knowing: its bibliography, figures and data. `.tex`, `.sty` and `.cls` are not among them, since the scan knows which documents read a local one.
TEX_READS = frozenset(
    (
        ".bib",
        ".bst",
        ".bbx",
        ".cbx",
        ".def",
        ".cfg",
        ".png",
        ".jpg",
        ".jpeg",
        ".pdf",
        ".eps",
        ".svg",
        ".tikz",
        ".dat",
        ".csv",
        ".txt",
    )
)


def _reads(result: Any, m: str) -> set[str]:
    exp = result.expansions.get(m)
    closure = result.closures.get(m)
    return {m, *(exp.reached if exp else ()), *(closure.files if closure else ())}
