#!/usr/bin/env python3
"""No file git would commit names a person's machine or holds a secret: the repository is public.

Usage:
    scripts/checks/machine_paths.py [--base REF]

Every file git would commit (tracked, or untracked and not ignored) is read as bytes, text and binary alike, and so is the text a PDF's streams, a zip's members, a gzip and a PNG's text chunks keep compressed; a PNG's pixels are not read, since no text is kept there. Found:

- a home folder: `/Users/<name>` or `/home/<name>`, `C:\\Users\\<name>`, or `-Users-<name>-`, the spelling Claude Code gives one in a folder's name;
- a per-user temporary folder: macOS's `/var/folders/XX/…` with its per-user part spelled out, `/tmp/claude-<uid>`, `/tmp/pytest-of-<name>`, `/run/user/<uid>`;
- a token: a GitHub, Anthropic, OpenAI, AWS, Slack, Google, GitLab, npm, PyPI, Hugging Face or Stripe key, a JSON web token, a private key's armour, or a loom server's write token written out;
- an email address, in a UTF-8 file with no NUL byte, outside the example domains (`example.org`, `example.com`, `example.net`, `*.test`, `*.example`, `*.invalid`, `*.localhost`) and the `git@HOST` of an SSH remote.

`ALLOWED` names the placeholders that look like one of these and are not. `PENDING` names the files whose home and temporary folders wait on the author, each with its reason; an email or a token fails wherever it is. `PENDING` only shrinks, and the check holds it so: a path on it that the list at `--base` (default `$MACHINE_PATHS_BASE`, else `$HARDWRAP_BASE`, else HEAD) does not hold fails, as does one that no longer exists or names no folder.

Each finding is printed as `path:line: what`, with the name or the secret left out, since CI's log of a public repository is public too.

Exit 0 when nothing is found outside `PENDING` and `PENDING` has only shrunk, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import io
import os
import re
import subprocess
import sys
import zipfile
import zlib
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = "write a placeholder that keeps the sentence or the test true (`~/…`, `/Users/someone/…`, `<scratch>/…`, `$TMPDIR`, a path in the repository, an address at example.org); a real token is revoked first, then removed, and stays in git's history until that is rewritten"

#: Strings shaped like a finding that are placeholders, each with what it is.
ALLOWED = {
    "someone": "the documents' and tests' placeholder for a person's home folder",
    "web_user": "the home folder in the virtual file system Emscripten gives the vendored pdf.js",
    "sk-ant-local-fake-not-a-key": "the fake key the v0.1 study's live harness hands a local client",
}

#: Files whose home and temporary folders wait on the author, each with its reason. A path comes off when its folders go, and none is ever added (the check compares the list with its base's).
PENDING = {
    "docs/plans/0.1-implementation-plan.md": "a plan that is history; the author's home folder in the two commands that run the paper tier",
    "docs/plans/0.16.1-graph-readability.md": "a plan that is history; a collaborator's home folder as the checkout the plan inspected",
    "docs/plans/review-panel-and-precise-dependencies.md": "a plan that is history; a collaborator's home folder where the plan's reference mock-ups were kept",
    "docs/plans/section-drafts-and-responsive-adoption.md": "a plan that is history; a collaborator's home folder holding the paper the plan was tried on",
}

WORD = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_")
HOME, TEMP, TOKEN = "a home folder", "a per-user temporary folder", "a token"
#: (what is found, its pattern, the bytes that may not come just before it). Every pattern starts with a literal, which `re` finds fast, so the word boundary is tested here instead of by a lookbehind; `who` is the part `ALLOWED` is asked about, the whole match where there is none.
KINDS = [
    (HOME, rb"/(?:Users|home)/(?P<who>[A-Za-z0-9._-]+)", WORD | {ord("."), ord("-")}),
    (HOME, rb":\\{1,2}Users\\{1,2}(?P<who>[A-Za-z0-9._-]+)", frozenset()),
    (HOME, rb"-Users-(?P<who>[A-Za-z0-9._]+)-", WORD - {ord("_")}),
    (TEMP, rb"/var/folders/[A-Za-z0-9_+-]{2}/(?P<who>[A-Za-z0-9_+-]{8,})", frozenset()),
    (TEMP, rb"/tmp/claude-[0-9]+", frozenset()),
    (TEMP, rb"/tmp/pytest-of-(?P<who>[A-Za-z0-9._-]+)", frozenset()),
    (TEMP, rb"/run/user/[0-9]+", frozenset()),
    *(
        (TOKEN, pattern, WORD | {ord("-")})
        for pattern in (
            rb"gh[pousr]_[A-Za-z0-9]{30,}",
            rb"github_pat_[A-Za-z0-9_]{30,}",
            rb"sk-ant-[A-Za-z0-9_-]{20,}",
            rb"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{40,}",
            rb"AKIA[0-9A-Z]{16}",
            rb"ASIA[0-9A-Z]{16}",
            rb"xox[abposr]-[A-Za-z0-9-]{10,}",
            rb"AIza[0-9A-Za-z_-]{35}",
            rb"glpat-[A-Za-z0-9_-]{20,}",
            rb"npm_[A-Za-z0-9]{36}",
            rb"pypi-AgE[A-Za-z0-9_-]{20,}",
            rb"hf_[A-Za-z0-9]{30,}",
            rb"sk_live_[A-Za-z0-9]{20,}",
            rb"rk_live_[A-Za-z0-9]{20,}",
            rb"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
            rb"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            rb"hooks\.slack\.com/services/[A-Za-z0-9/]+",
            rb"""X-Loom-Token["']?\s*[:=]\s*["']?[A-Za-z0-9_-]{24,}""",
            rb"""x-loom-token["']?\s*[:=]\s*["']?[A-Za-z0-9_-]{24,}""",
            rb""""token"\s*:\s*"[A-Za-z0-9_-]{24,}\"""",
        )
    ),
]
PATTERNS = [(what, re.compile(pattern), before) for what, pattern, before in KINDS]
#: An address's `@` and domain; its local part is read backwards from the `@`.
EMAIL = re.compile(rb"@(?P<domain>(?:[a-z0-9-]+\.)+[a-z]{2,24})(?![A-Za-z0-9-])")
LOCAL = WORD | frozenset(b".%+-")
EXAMPLE = re.compile(rb"(?:^|\.)(?:example\.(?:org|com|net)|[a-z0-9-]+\.(?:test|example|invalid|localhost))$")
PNG = b"\x89PNG\r\n\x1a\n"
NL = b"\n"


def committable() -> list[str]:
    """The files a commit would carry: tracked, or untracked and not ignored."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return sorted({p.decode() for p in out.stdout.split(b"\0") if p})


def png_chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Each chunk of a PNG as (type, body)."""
    pos = 8
    while pos + 8 <= len(data):
        size, kind = int.from_bytes(data[pos : pos + 4], "big"), data[pos + 4 : pos + 8]
        yield kind, data[pos + 8 : pos + 8 + size]
        pos += 12 + size


def inside(data: bytes, depth: int = 0) -> Iterator[tuple[str, bytes]]:
    """The text a PDF, PNG, zip or gzip keeps compressed, as (where, bytes); nothing for any other file."""
    if depth > 2:
        return
    if data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    inner = z.read(info)
                    yield f"its member {info.filename}", inner
                    yield from ((f"its member {info.filename}, {where}", b) for where, b in inside(inner, depth + 1))
        except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, zlib.error):
            pass
    elif data[:2] == b"\x1f\x8b":
        try:
            yield "its gzip content", gzip.decompress(data)
        except (OSError, EOFError, zlib.error):
            pass
    elif data[:5] == b"%PDF-":
        for m in re.finditer(rb"stream\r?\n", data):
            end = data.find(b"endstream", m.end())
            try:
                text = zlib.decompressobj().decompress(data[m.end() : end if end > 0 else None])
            except zlib.error:
                continue
            if text:
                yield f"a stream at byte {m.start()}", text
    elif data[:8] == PNG:
        for kind, body in png_chunks(data):
            _, _, rest = body.partition(b"\0")
            try:
                if kind == b"zTXt":
                    yield "its zTXt chunk", zlib.decompress(rest[1:])
                elif kind == b"iTXt" and rest[:1] == b"\1":
                    yield "its iTXt chunk", zlib.decompress(rest[2:].split(b"\0", 2)[-1])
            except zlib.error:
                pass


def is_text(data: bytes) -> bool:
    """Whether `data` is UTF-8 with no NUL: the files an email address is looked for in, since a binary's bytes spell one by chance."""
    if b"\0" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def scan(data: bytes, text: bool) -> list[tuple[int, str]]:
    """Each finding in `data` as (offset, what); an email address only when `text`."""
    found = []
    for what, pattern, before in PATTERNS:
        for m in pattern.finditer(data):
            if m.start() and data[m.start() - 1] in before:
                continue
            who = m.groupdict().get("who") or m.group(0)
            if who.decode("latin-1") not in ALLOWED:
                found.append((m.start(), what))
    if text:
        for m in EMAIL.finditer(data):
            i = m.start()
            while i and data[i - 1] in LOCAL:
                i -= 1
            if (
                i < m.start()
                and data[i] in WORD
                and data[i] != ord("_")
                and not EXAMPLE.search(m.group("domain"))
                and data[i : m.start()] != b"git"
            ):
                found.append((i, "an email address"))
    return sorted(found)


def findings(path: str) -> list[tuple[str, str]]:
    """What `path` holds, as (`path:where: what`, what), in file order."""
    try:
        data = (ROOT / path).read_bytes()
    except (IsADirectoryError, FileNotFoundError):
        return []
    out = []
    if data[:8] == PNG:
        # the pixels are compressed and hold no text; every other chunk is read as it stands
        meta = NL.join(body for kind, body in png_chunks(data) if kind != b"IDAT")
        out += [(f"{path}: {what} in its metadata", what) for _, what in scan(meta, False)]
    else:
        text = is_text(data)
        for at, what in scan(data, text):
            where = str(data.count(NL, 0, at) + 1) if text else f"byte {at}"
            out.append((f"{path}:{where}: {what}", what))
    for where, inner in inside(data):
        out += [(f"{path}: {what} in {where}", what) for _, what in scan(inner, False)]
    return out


def pending_at(base: str) -> set[str] | None:
    """`PENDING` as this script held it at `base`, or None where the script did not exist there."""
    shown = subprocess.run(
        ["git", "show", f"{base}:scripts/checks/machine_paths.py"], cwd=ROOT, capture_output=True, text=True
    )
    if shown.returncode != 0:
        return None
    for node in ast.parse(shown.stdout).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PENDING" for t in node.targets):
            return set(ast.literal_eval(node.value))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    # CI sets HARDWRAP_BASE to the push's or pull request's base, and this check takes it too, since a clean checkout has nothing added since HEAD
    base = os.environ.get("MACHINE_PATHS_BASE") or os.environ.get("HARDWRAP_BASE") or "HEAD"
    parser.add_argument(
        "--base",
        default=base,
        help="the commit whose PENDING this one may only shrink from (default $MACHINE_PATHS_BASE, else $HARDWRAP_BASE, else HEAD)",
    )
    args = parser.parse_args()
    files = committable()
    bad: list[str] = []
    named: set[str] = set()
    for path in files:
        for line, what in findings(path):
            if path in PENDING and what in (HOME, TEMP):
                named.add(path)
            else:
                bad.append(line)
    before = pending_at(args.base)
    added = [] if before is None else sorted(set(PENDING) - before)
    gone = sorted(p for p in PENDING if not (ROOT / p).is_file())
    clean = sorted(p for p in PENDING if (ROOT / p).is_file() and p not in named)
    for p in added:
        print(
            f"machine paths: {p} was added to PENDING since {args.base}; the list only shrinks; fix: replace what it names and leave it off PENDING"
        )
    for p in gone:
        print(
            f"machine paths: {p} is on PENDING and no longer exists; fix: remove it from PENDING in scripts/checks/machine_paths.py"
        )
    for p in clean:
        print(
            f"machine paths: {p} is on PENDING and names no home or temporary folder now; fix: take it off PENDING in scripts/checks/machine_paths.py"
        )
    if bad:
        print("a home folder, a temporary folder, an email address or a token, in a file git would commit:")
        print("\n".join(bad))
        print(f"fix: {FIX}")
    if bad or added or gone or clean:
        return 1
    print(f"machine paths: ok ({len(files)} files read; {len(PENDING)} on PENDING)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
