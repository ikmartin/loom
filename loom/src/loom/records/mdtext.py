"""A Markdown file the viewer draws, as the target of an annotation or a suggested edit: named by its path with its suffix, its words found in the file's own text.

A reader's selection is the page's words, with each formula as its TeX between dollars (the viewer's `quoteOf`); an agent quotes the file as written. Both are found here: as written first, whitespace compared normalised, else as the page prints the Markdown (`printed`), with each character mapped back to the source it came from.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loom.records.selectors import CONTEXT, Selector, _common_prefix_len, _common_suffix_len, find_written

SUFFIXES = (".md", ".markdown")


def is_markdown(path: str) -> bool:
    """Whether `path` names a Markdown file by its suffix, as `files.SUFFIX_KINDS` reads it."""
    return path.lower().endswith(SUFFIXES)


def markdown_file(result: Any, target: str) -> str | None:
    """`target` as the quilt-relative path of a Markdown file the viewer shows; None for anything else."""
    from loom.files import Shown

    rel = target.strip().strip("/")
    if not is_markdown(rel) or not (result.quilt.root / rel).is_file():
        return None
    return rel if Shown.of(result.quilt).is_shown(rel) else None


def text_of(root: Path, rel: str) -> str | None:
    """The file's text as the publisher reads it, or None when it is gone."""
    try:
        return (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


#: What opens a line and prints nothing: its indent, a quote's `>`, a list's marker with its box, a heading's hashes.
_LINE_HEAD = re.compile(r"[ \t]{0,3}(?:>[ \t]?)*[ \t]*(?:(?:[-*+]|\d{1,9}[.)])[ \t]+(?:\[[ xX]\][ \t]+)?|#{1,6}(?=[ \t]|$)[ \t]*)?")
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|<!--[\s\S]*?-->")
_AUTOLINK = re.compile(r"<((?:https?|mailto|quilt|cited):[^<>\s]*)>")
_ESCAPABLE = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")


def _spans(text: str) -> list[tuple[int, int, str]]:
    """The stretches of `text` read as written, `(start, end, kind)`: code (`code`) and mathematics (`math`), as the publisher lifts them before Markdown reads the rest."""
    from loom.records.store import _CODE, _MATH

    out: list[tuple[int, int, str]] = []
    pos = 0
    for i, part in enumerate(_CODE.split(text)):
        if i % 2:
            out.append((pos, pos + len(part), "code"))
        else:
            out += [(pos + m.start(), pos + m.end(), "math") for m in _MATH.finditer(part)]
        pos += len(part)
    return out


def printed(text: str) -> tuple[str, list[tuple[int, int]]]:
    """`text` as the page prints it, each character mapped to the source range it came from.

    Each line's block markers (a heading's hashes, a quote's `>`, a list's marker and its box) are left out; inline, so are emphasis's `*` and `_`, a code span's backticks, a link's brackets and address, an image whole, raw HTML's tags and an escape's backslash. Code and mathematics read as written, a formula with its dollars, as the viewer quotes one. Whitespace collapses to one space. Blind to what is rarer (a reference link's label, an entity): such words are found as written or not at all.
    """
    out: list[str] = []
    where: list[tuple[int, int]] = []
    held = _spans(text)

    def put(ch: str, a: int, b: int) -> None:
        if ch.isspace():
            if out and out[-1] == " ":
                where[-1] = (where[-1][0], b)
                return
            ch = " "
        out.append(ch)
        where.append((a, b))

    i, n, k = 0, len(text), 0
    line_start = True
    while i < n:
        while k < len(held) and held[k][1] <= i:
            k += 1
        if k < len(held) and held[k][0] <= i < held[k][1]:
            a, b, kind = held[k]
            # a code span's backticks are not printed, its words are; a formula is quoted whole, dollars and all
            body = re.match(r"`*", text[a:b]).end() if kind == "code" else 0  # type: ignore[union-attr]
            tail = len(text[a:b]) - len(text[a:b].rstrip("`")) if kind == "code" else 0
            for j in range(a + body, b - tail):
                put(text[j], j, j + 1)
            i = b
            line_start = False
            continue
        if line_start:
            m = _LINE_HEAD.match(text, i)
            line_start = False
            if m and m.end() > i:
                i = m.end()
                continue
        ch = text[i]
        if ch == "\n":
            put(" ", i, i + 1)
            i += 1
            line_start = True
            continue
        if ch == "\\" and i + 1 < n and text[i + 1] in _ESCAPABLE:
            put(text[i + 1], i, i + 2)
            i += 2
            continue
        if ch == "!" and text.startswith("[", i + 1) and (end := _link_end(text, i + 1)) is not None:
            i = end  # an image prints no words
            continue
        if ch == "[" and (close := _bracket_close(text, i)) is not None and text.startswith("(", close + 1):
            end = _paren_end(text, close + 1)
            if end is not None:
                for j in range(i + 1, close):
                    put(text[j], j, j + 1)
                i = end
                continue
        if ch == "<":
            if m := _AUTOLINK.match(text, i):
                for j in range(m.start(1), m.end(1)):
                    put(text[j], j, j + 1)
                i = m.end()
                continue
            if m := _TAG.match(text, i):
                i = m.end()
                continue
        if ch in "*_":
            j = i
            while j < n and text[j] == ch:
                j += 1
            before = text[i - 1] if i else " "
            after = text[j] if j < n else " "
            # a run with space on both sides prints as itself, and so does `_` inside a word (snake_case)
            if (before.isspace() and after.isspace()) or (ch == "_" and before.isalnum() and after.isalnum()):
                for x in range(i, j):
                    put(text[x], x, x + 1)
            i = j
            continue
        put(ch, i, i + 1)
        i += 1
    while out and out[-1] == " ":
        out.pop()
        where.pop()
    return "".join(out), where


def _bracket_close(text: str, at: int) -> int | None:
    """The `]` matching the `[` at `at`, on the same paragraph; None when there is none."""
    depth = 0
    for j in range(at, len(text)):
        c = text[j]
        if c == "\\":
            continue
        if c == "[" and (j == at or text[j - 1] != "\\"):
            depth += 1
        elif c == "]" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return j
        elif c == "\n" and text.startswith("\n", j + 1):
            return None
    return None


def _paren_end(text: str, at: int) -> int | None:
    """Just past the `)` closing the link address opened at `at`; None when it does not close on its line."""
    depth = 0
    for j in range(at, len(text)):
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        elif c == "\n":
            return None
    return None


def _link_end(text: str, at: int) -> int | None:
    """Just past an inline link or image whose `[` is at `at`; None when it is not one."""
    close = _bracket_close(text, at)
    if close is None or not text.startswith("(", close + 1):
        return None
    return _paren_end(text, close + 1)


def find(text: str, quote: str) -> list[tuple[int, int]]:
    """Every occurrence of `quote` in the Markdown `text`, as source spans: as written, whitespace normalised, else as the page prints the text (`printed`), the quote being the page's words already."""
    spans = find_written(text, quote)
    if spans:
        return spans
    pt, where = printed(text)
    pq = " ".join(quote.split())
    if not pq:
        return []
    out: list[tuple[int, int]] = []
    k = pt.find(pq)
    while k >= 0:
        out.append((where[k][0], where[k + len(pq) - 1][1]))
        k = pt.find(pq, k + 1)
    return out


def make_selector(text: str, quote: str) -> Selector:
    """The selector for `quote`, which stands once in `text` (`find`): the file's own words there, with the words either side."""
    spans = find(text, quote)
    if len(spans) != 1:
        raise ValueError("quote must occur exactly once")
    a, b = spans[0]
    return Selector(text[a:b], text[max(0, a - CONTEXT) : a], text[b : b + CONTEXT])


def resolve(text: str, sel: Selector) -> tuple[int, int] | None:
    """Where a selector stands in the file now: its words once, else the occurrence whose words either side match best; None when they are gone (detached)."""
    spans = find(text, sel.exact) if sel.exact else []
    if not spans:
        return None
    if len(spans) == 1:
        return spans[0]

    def score(span: tuple[int, int]) -> int:
        a, b = span
        return _common_suffix_len(text[max(0, a - CONTEXT) : a], sel.prefix) + _common_prefix_len(
            text[b : b + CONTEXT], sel.suffix
        )

    return max(spans, key=score)
