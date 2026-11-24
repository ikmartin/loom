"""Diagnostics as report groups (plan 0.18.3): one group per code with its count and class.

Every command that reports diagnostics (`lint`, `build`, `check`, `history verify`) builds its groups here, so a diagnostic reads the same wherever it is printed: its location, its message, the keys it names, and the commands that would resolve it as `fix:` lines. A heading says the code's class in brackets after it (`scan.diagnostics`): `latex`, `model` or `internal`.
"""

from __future__ import annotations

import re

from loom.cli.report import Group, Item, counted
from loom.scan.model import Diagnostic
from loom.scan.scan import ScanResult

SEVERITY = {"error": 0, "warning": 1, "info": 2}


def item(d: Diagnostic, said: str | None = None) -> Item:
    """One diagnostic as an item: its location first, then its message (or `said`, the part of it its heading does not already say), the keys it names last unless the text names them, its fixes beneath; the JSON carries the diagnostic whole."""
    where = ", ".join(f"{loc.file}:{loc.line}" for loc in d.locations)
    message = d.message if said is None else said
    text = f"{where}  {message}" if where else message
    named = set(re.findall(r"[^\s,;:()]+", message))
    return Item(
        text,
        key=" ".join(k for k in d.keys if k not in named) or None,
        fixes=[f.command for f in d.fixes],
        data={"diagnostic": d.to_dict()},
    )


#: A sentence its diagnostics share is said once in their heading when it has at least `SHARED` words and each says no more than `VARIES` of its own: one sentence about different things, not different sentences that begin alike.
SHARED, VARIES = 4, 4


def _shared(messages: list[str]) -> tuple[int, int]:
    """How many leading and trailing words every message shares, word-aligned and never overlapping; (0, 0) when the messages are not one sentence (`SHARED`, `VARIES`)."""
    words = [m.split() for m in messages]
    shortest = min(len(w) for w in words)
    head = 0
    while head < shortest and len({w[head] for w in words}) == 1:
        head += 1
    tail = 0
    while tail < shortest - head and len({w[-1 - tail] for w in words}) == 1:
        tail += 1
    own = [len(w) - head - tail for w in words]
    return (head, tail) if head + tail >= SHARED and all(0 < n <= VARIES for n in own) else (0, 0)


def _code_group(severity: str, code: str, cls: str, ds: list[Diagnostic]) -> Group:
    """One code's diagnostics of one class: when they all say one sentence about different things, the sentence is the heading's, once, and each line says only what varies (T2)."""
    head, tail = _shared([d.message for d in ds]) if len(ds) > 1 else (0, 0)
    if not head and not tail:
        return Group(f"{severity} {code} ({cls})", [item(d) for d in ds], problem=severity == "error", limit=20)
    first = ds[0].message.split()
    gist = " ".join([*first[:head], "…", *(first[len(first) - tail :] if tail else [])])
    # what varies, without the comma that joined it to the shared words
    items = [item(d, " ".join(d.message.split()[head : len(d.message.split()) - tail]).rstrip(",;:")) for d in ds]
    return Group(f"{severity} {code} ({cls}): {gist}", items, problem=severity == "error", limit=20)


def groups(diags: list[Diagnostic], result: ScanResult | None) -> list[Group]:
    """The diagnostics as one group per code, most severe first, each said once."""
    out: list[Group] = []
    by_code: dict[tuple[int, str, str, str], list[Diagnostic]] = {}
    for d in _once(diags):
        by_code.setdefault((SEVERITY.get(d.severity, 3), d.code, d.severity, d.class_), []).append(d)
    for (_, code, severity, cls), ds in sorted(by_code.items()):
        ds.sort(key=lambda d: (d.locations[0].file, d.locations[0].line) if d.locations else ("", 0))
        out.append(_code_group(severity, code, cls, ds))
    return out


def _once(diags: list[Diagnostic]) -> list[Diagnostic]:
    """`diags` with each one said once: two passes can report the same diagnostic at the same place."""
    seen: set[tuple[str, str, str, tuple[tuple[str, int], ...], tuple[str, ...]]] = set()
    out = []
    for d in diags:
        mark = (d.severity, d.code, d.message, tuple((loc.file, loc.line) for loc in d.locations), tuple(d.keys))
        if mark not in seen:
            seen.add(mark)
            out.append(d)
    return out


def tally(diags: list[Diagnostic], result: ScanResult | None) -> str:
    """`2 errors, 1 warning in your documents`, or `no problems`: the count a verdict carries."""
    own = _once(diags)
    parts = [
        counted(sum(1 for d in own if d.severity == s), s)
        for s in ("error", "warning", "info")
        if any(d.severity == s for d in own)
    ]
    return f"{', '.join(parts)} in your documents" if parts else "no problems"


def has_errors(diags: list[Diagnostic], result: ScanResult | None) -> bool:
    """Whether any diagnostic is an error."""
    return any(d.severity == "error" for d in diags)
