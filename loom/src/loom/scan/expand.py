"""Master expansion with a span map.

\\input, \\include, and \\nest are resolved as TeX does: the path as written, then with .tex appended; a braceless \\input name is accepted; a name kpsewhich finds is a system file and ignored; a non-.tex file is an opaque inclusion whose text is never scanned. The expanded text keeps every reached file's text exactly once, each child spliced right after its inclusion command, so a section that starts in one file and continues in another is one unit. Cycles and second inclusions of a file in one master are reported and not expanded.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from loom.paths import document_dir, under
from loom.scan.model import Diagnostic, Location, SourceFile
from loom.scan.tokenize import commands, read_mandatory

INCLUDE_CMDS = {"input", "include", "nest"}


@dataclass
class Segment:
    file: str
    file_start: int
    length: int
    exp_start: int
    shift: int

    @property
    def exp_end(self) -> int:
        return self.exp_start + self.length


@dataclass
class Inclusion:
    parent: str
    site_start: int
    site_end: int
    name: str
    kind: str
    child: str | None
    shift: int
    problem: str | None = None  # missing | cycle | double | system | opaque


@dataclass
class Expansion:
    master: str
    text: str = ""
    segments: list[Segment] = field(default_factory=list)
    inclusions: list[Inclusion] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    reached: dict[str, int] = field(default_factory=dict)

    def locate(self, exp_offset: int) -> tuple[str, int, int]:
        """(file, offset in file, level shift) for an expanded offset."""
        lo, hi = 0, len(self.segments) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.segments[mid].exp_start <= exp_offset:
                lo = mid
            else:
                hi = mid - 1
        seg = self.segments[lo]
        return seg.file, seg.file_start + (exp_offset - seg.exp_start), seg.shift

    def exp_offset(self, file: str, offset: int) -> int | None:
        for seg in self.segments:
            if seg.file == file and seg.file_start <= offset < seg.file_start + seg.length:
                return seg.exp_start + (offset - seg.file_start)
        return None


def _kpsewhich(name: str, cwd: Path) -> bool:
    """Whether the distribution resolves `name`, asked of the `kpsewhich` on PATH now from `cwd`, the document's directory, as a compile there would ask.

    Memoised, since a subprocess per unresolved inclusion was 86 ms of a 166 ms scan on the Manolache import; keyed by executable, TEXINPUTS and directory as well as name, so a run under another installation is never answered from this one's memo. A name found is believed while the file `kpsewhich` named is there, one `stat`; a name not found is asked about again once `AGAIN` seconds have passed, whatever way a file can arrive (`tlmgr`, a copy, a link, a folder `TEXINPUTS` names), so for that long a file that has just arrived can still be called missing.
    """
    exe = shutil.which("kpsewhich")
    key = (exe, os.environ.get("TEXINPUTS", ""), name, str(cwd))
    found = _FOUND.get(key)
    if found is not None:
        if os.path.exists(found):
            return True
        del _FOUND[key]
    else:
        asked = _MISSING.get(key)
        if asked is not None and _clock() - asked < AGAIN:
            return False
    # the time before asking, so a file that arrives while kpsewhich runs is asked about at the next interval
    now = _clock()
    path = _probe(*key)
    if path is not None:
        _FOUND[key] = path
        _MISSING.pop(key, None)
        return True
    _MISSING[key] = now
    return False


#: Seconds a name `kpsewhich` did not find is believed missing before it is asked about again.
AGAIN = 10.0
#: The clock `AGAIN` is counted on; a test gives its own.
_clock = time.monotonic
#: Each name `kpsewhich` found, by `_kpsewhich`'s key, with the file it named; and each it did not, with when it was asked.
_FOUND: dict[tuple[str | None, str, str, str], str] = {}
_MISSING: dict[tuple[str | None, str, str, str], float] = {}


def _probe(exe: str | None, texinputs: str, name: str, cwd: str) -> str | None:
    """One `kpsewhich NAME` in `cwd`: the file it names, read against `cwd`, or None; `texinputs` is only part of the memo's key, since the subprocess inherits the environment it names."""
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, name],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
            cwd=cwd if Path(cwd).is_dir() else None,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    named = proc.stdout.strip().splitlines()[0].strip() if proc.returncode == 0 and proc.stdout.strip() else ""
    return str(Path(cwd) / named) if named else None


def resolve_inclusion(
    root: Path, name: str, known: frozenset[str] = frozenset(), base: str = ""
) -> tuple[str | None, str | None]:
    """(quilt-relative path, problem). Problems: 'system' for a kpsewhich-resolvable name, 'missing' otherwise.

    `base` is the quilt-relative directory the document compiles from (P12): `name` is read against it, as TeX reads against its working directory, and `..` is refused, since Overleaf cannot follow it. `known` holds paths that exist only in an editor's buffers, so a file an author has written but not yet saved resolves.
    """
    name = name.strip()
    if not name or name.startswith("/") or ".." in Path(name).parts:
        return None, "missing"
    for cand in (name, name + ".tex"):
        rel = under(base, cand)
        if rel in known or (root / rel).is_file():
            return rel, None
    probe = name if "." in Path(name).name else name + ".tex"
    if _kpsewhich(probe, root / base):
        return None, "system"
    return None, "missing"


def _read_include_arg(text: str, pos: int) -> tuple[str | None, int]:
    """The argument of \\input-like commands: a braced group, or a whitespace-delimited name (the primitive form)."""
    value, _, _, nxt = read_mandatory(text, pos)
    if value is None:
        return None, pos
    if nxt == pos + len(value) or text[pos:nxt].lstrip().startswith("{"):
        return value.strip(), nxt
    m = re.match(r"\s*([^\s{}\\]+)", text[pos:])
    if m:
        return m.group(1), pos + m.end()
    return value.strip(), nxt


def expand_master(master: SourceFile, root: Path, files: dict[str, SourceFile], base: str | None = None) -> Expansion:
    """`files` is the scanner's whole file table, so a path that exists only in an editor's buffer resolves like one on disk.

    Every inclusion, at every depth, resolves against `base`, default the master's own directory: TeX reads a nested `\\input` against its working directory, not the including file's.
    """
    base = document_dir(master.path) if base is None else base
    exp = Expansion(master=master.path)
    parts: list[str] = []
    cursor = [0]

    def emit(file: str, file_start: int, length: int, shift: int) -> None:
        if length <= 0:
            return
        exp.segments.append(Segment(file, file_start, length, cursor[0], shift))
        cursor[0] += length

    def rec(src: SourceFile, shift: int, stack: tuple[str, ...]) -> None:
        exp.reached[src.path] = exp.reached.get(src.path, 0) + 1
        text = src.clean
        pos = 0
        for t in commands(text, INCLUDE_CMDS):
            name, arg_end = _read_include_arg(text, t.end)
            if name is None:
                continue
            emit(src.path, pos, arg_end - pos, shift)
            parts.append(text[pos:arg_end])
            pos = arg_end
            child_shift = shift + 1 if t.value == "nest" else shift
            inc = Inclusion(src.path, t.start, arg_end, name, t.value, None, child_shift)
            exp.inclusions.append(inc)
            rel, problem = resolve_inclusion(root, name, frozenset(files), base)
            loc = [Location(src.path, src.line_of(t.start))]
            if rel is None:
                inc.problem = problem
                if problem == "missing":
                    exp.diagnostics.append(
                        Diagnostic("error", "missing-include", f"\\{t.value}{{{name}}} names no file", loc)
                    )
                continue
            inc.child = rel
            if not rel.endswith(".tex") or rel not in files:
                inc.problem = "opaque"
                continue
            if rel in stack or rel == src.path:
                inc.problem = "cycle"
                chain = " -> ".join([*stack, src.path, rel])
                exp.diagnostics.append(Diagnostic("error", "inclusion-cycle", f"inclusion cycle {chain}", loc))
                continue
            if rel in exp.reached:
                inc.problem = "double"
                exp.diagnostics.append(
                    Diagnostic("error", "double-inclusion", f"{rel} is included twice in {master.path}", loc, [rel])
                )
                continue
            child = files[rel]
            if child.ignored:
                inc.problem = "ignored"
                continue
            rec(child, child_shift, (*stack, src.path))
        emit(src.path, pos, len(text) - pos, shift)
        parts.append(text[pos:])

    rec(master, 0, ())
    exp.text = "".join(parts)
    return exp
