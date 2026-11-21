"""Id allocation: the set of local parts anything can point at, recomputed on every call; nothing is stored."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
from pathlib import Path

from loom.paths import ANNOTATION_LOG, LEDGER, LIBRARY_NODES, TAG_LOG
from loom.scan.labels import LOOMLOCAL
from loom.scan.scan import ScanResult


def visible_locals(result: ScanResult, prefix: str) -> set[str]:
    """Every local part under `prefix` that anything can point at: ids in source, the acceptance ledger's keys, the history ledger's keys and every file name under its steps (an id the history has recorded is never allocated again), annotation targets, the library's nodes and the tags on them, references anywhere (dangling included), and git history. A command that writes the id it draws from these holds the id lock from before its scan (`cli._quilt.draws_ids`); one that mints a library node's stem draws from these too, since the library and the author's sources share the prefix."""
    pat = re.compile(r"\b" + re.escape(prefix) + r"-([0-9A-Z]{4})\b")
    found: set[str] = set()
    for src in result.files.values():
        found.update(pat.findall(src.text))
    root = result.quilt.root
    ledger = root / LEDGER
    if ledger.is_file():
        found.update(pat.findall(ledger.read_text(encoding="utf-8", errors="replace")))
    history = result.quilt.history_dir
    if (history / "ledger.jsonl").is_file():
        found.update(pat.findall((history / "ledger.jsonl").read_text(encoding="utf-8", errors="replace")))
        for step in history.iterdir():
            if step.is_dir() and step.name != "texts":
                found.update(pat.findall(" ".join(p.name for p in step.iterdir())))
    for log in (root / ANNOTATION_LOG, root / TAG_LOG):
        if log.is_file():
            found.update(pat.findall(log.read_text(encoding="utf-8", errors="replace")))
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        found.update(pat.findall(" ".join(os.listdir(root / LIBRARY_NODES))))
    found.update(pat.findall(git_mentions(root, rf"{re.escape(prefix)}-[0-9A-Z]{{4}}")))
    return {x for x in found if LOOMLOCAL.match(x)}


def git_mentions(root: Path, pattern: str) -> str:
    """Every match of the extended regular expression `pattern`, as a whole word, in the files of the quilt's newest 500 commits on any ref, one a line; empty without git or a repository.

    The word is `git grep -w`'s, since `\\b` is a GNU extension Apple's git does not read: a pattern holding one matches nothing there.
    """
    from loom import gitprog

    try:
        if not gitprog.usable():
            return ""
        revs = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--all", "--max-count=500"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
            check=False,
        )
        if revs.returncode != 0 or not revs.stdout.strip():
            return ""
        out = subprocess.run(
            ["git", "-C", str(root), "grep", "-h", "-o", "-w", "-E", pattern, *revs.stdout.split()],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
            check=False,
        )
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return ""
