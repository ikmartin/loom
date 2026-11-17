#!/usr/bin/env python3
"""Measure what a served quilt holds across saves, on a copy of a quilt: the process's memory and the scanner's live tokens after the first build and after each save.

Each build runs in this process as `loom serve` runs it after a change (`build(quilt, tex=...)`, the last report kept and nothing older), so the numbers are this checkout's code. Each save writes a word never written before into one file, so no cache holds its text. Memory is read after a full collection, and on macOS after the allocator has handed back the pages it holds free, so a number is what the process keeps rather than what it has yet to free or give back. The copy is a clone where the file system makes one (APFS), and is removed at the end unless `--keep` is given; HOME and the XDG directories point into it, so nothing of the person running it is read or written but their TeX tree (`TEXMFHOME`, kept for `--tex`).

    uv run python scripts/memory.py PATH [--saves N] [--file REL] [--tex] [--keep]

`--tex` builds as a server with compiles on does, letting TeX make the text no compile makes; the compiles themselves are separate processes and are not counted.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import os
import random
import resource
import shutil
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MB = 1024 * 1024


def clone(source: Path, into: Path) -> Path:
    q = into / "q"
    if sys.platform == "darwin":
        subprocess.run(["cp", "-cR", str(source), str(q)], check=True)
    else:
        shutil.copytree(source, q, symlinks=True)
    return q


def isolate(home: Path) -> None:
    """HOME and XDG inside the scratch directory, TeX's personal tree kept where it was."""
    texmfhome = subprocess.run(["kpsewhich", "-var-value", "TEXMFHOME"], capture_output=True, text=True).stdout.strip()
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        (home / name).mkdir()
        os.environ[name] = str(home / name)
    if texmfhome:
        os.environ["TEXMFHOME"] = texmfhome
    os.environ["LOOM_PROGRESS"] = "off"
    for marker in ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        os.environ.pop(marker, None)


class _RusageInfoV0(ctypes.Structure):
    _fields_ = [("uuid", ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64)
        for name in (
            "user_time",
            "system_time",
            "pkg_idle_wkups",
            "interrupt_wkups",
            "pageins",
            "wired_size",
            "resident_size",
            "phys_footprint",
            "proc_start_abstime",
            "proc_exit_abstime",
        )
    ]


def memory() -> tuple[float, float]:
    """(footprint, resident) in MB, after a full collection: the footprint is what macOS's Activity Monitor shows as the process's memory, compressed pages included; elsewhere both are the resident size.

    On macOS the allocator is first asked to hand back the pages it holds free, which otherwise stay resident until the system needs them and make the resident size climb with what was freed.
    """
    gc.collect()
    if sys.platform == "darwin":
        info = _RusageInfoV0()
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
        libc.malloc_zone_pressure_relief(None, ctypes.c_size_t(0))
        if libc.proc_pid_rusage(os.getpid(), 0, ctypes.byref(info)) == 0:
            return info.phys_footprint / MB, info.resident_size / MB
    status = Path("/proc/self/status")
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith("VmRSS:"):
                rss = int(line.split()[1]) / 1024
                return rss, rss
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / MB, peak / MB


def peak() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / MB if sys.platform == "darwin" else rss / 1024


def live_tokens() -> int:
    from loom.scan.tokenize import Tok

    return sum(1 for o in gc.get_objects() if type(o) is Tok)


def the_largest_reached(result) -> str:  # type: ignore[no-untyped-def]
    """The largest `.tex` file of the person's that a document reaches: the save that remakes the most."""
    from loom.paths import LOOM

    reached = {f for exp in result.expansions.values() for f in exp.reached}
    own = [f for f in reached if f.endswith(".tex") and not f.startswith(f"{LOOM}/")]
    return max(own, key=lambda f: len(result.files[f].text))


def save(q: Path, rel: str) -> None:
    """Write a word never written before at the end of the file's last environment, or its end."""
    p = q / rel
    text = p.read_text(encoding="utf-8")
    word = "".join(random.choices(string.ascii_lowercase, k=9))
    at = text.rfind("\\end{")
    at = len(text) if at < 0 else at
    p.write_text(f"{text[:at]} Memory {word}.\n{text[at:]}", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("quilt", type=Path, help="the quilt to copy")
    parser.add_argument("--saves", type=int, default=20, help="how many saves after the first build; default 20")
    parser.add_argument("--file", help="the quilt-relative file each save writes; default the largest one reached")
    parser.add_argument("--tex", action="store_true", help="let TeX make what no compile makes, as when serving")
    parser.add_argument("--keep", action="store_true", help="keep the copy and print where it is")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    home = Path(tempfile.mkdtemp(prefix="loom-memory-"))
    try:
        q = clone(args.quilt.resolve(), home)
        isolate(home)
        from loom.paths import SERVE_JSON
        from loom.render.build import build
        from loom.scan.quilt import load_quilt

        (q / SERVE_JSON).unlink(missing_ok=True)  # the original's server, if one runs, is never told of the copy

        quilt = load_quilt(q)
        print(f"{'build':>7}  {'seconds':>7}  {'footprint MB':>12}  {'resident MB':>11}  {'peak MB':>7}  {'tokens':>9}")
        rel = args.file
        for n in range(args.saves + 1):
            if n:
                save(q, rel)
            started = time.perf_counter()
            # the last report is kept during the build and replaced after it, as the server keeps it
            report = build(quilt, tex=args.tex)
            took = time.perf_counter() - started
            rel = rel or the_largest_reached(report.result)
            footprint, resident = memory()
            if not n:
                first = (footprint, resident)
            label = "first" if not n else f"save {n}"
            print(f"{label:>7}  {took:7.2f}  {footprint:12.0f}  {resident:11.0f}  {peak():7.0f}  {live_tokens():9,}")
        print(
            f"saved {args.saves} times to {rel}: footprint {footprint - first[0]:+.0f} MB, resident {resident - first[1]:+.0f} MB since the first build"
        )
    finally:
        if args.keep:
            print(f"copy kept at {home / 'q'}")
        else:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    main()
