"""The blocks a save changed, as source, for the stream's `drafted` event: the viewer draws each at once with its own mathematics and swaps in TeX's block when the save's build publishes it (`docs/specs/write-api.md` §1).

Read only: the published scan's text against the file as saved, nothing written. A block is a statement's or a proof's body when every change in it lies inside that body, else the paragraph round the change when that paragraph holds no environment but a formula's and no heading; anything else is left to TeX.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.scan.source import read_source

if TYPE_CHECKING:
    from loom.scan.model import Env
    from loom.scan.scan import ScanResult

#: A blank line: where TeX ends a paragraph, and so where a text block's window ends.
_BLANK = re.compile(r"\n[ \t]*\n")
#: Environments a paragraph may hold and still be drawn as one: displayed mathematics.
_MATH_ENVS = r"(?:equation|align|alignat|flalign|gather|multline|eqnarray|displaymath|math|split|cases|array|[pbvBV]?matrix|smallmatrix)\*?"
#: What makes a stretch of text more than one paragraph: a heading, or an environment that is not mathematics.
_NOT_ONE = re.compile(
    r"\\(?:part|chapter|section|subsection|subsubsection|paragraph)\*?\s*[\[{]|\\(?:begin|end)\s*\{(?!"
    + _MATH_ENVS
    + r"\})"
)

#: One change: the stretch `[a, b)` of the published text and the stretch `[c, d)` of the saved text that took its place.
Hunk = tuple[int, int, int, int]


def _starts(lines: list[str]) -> list[int]:
    out = [0]
    for line in lines:
        out.append(out[-1] + len(line))
    return out


def hunks(old: str, new: str) -> list[Hunk]:
    """Where `new` differs from `old`, by lines and then narrowed to the characters that differ, in order."""
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    sa, sb = _starts(a), _starts(b)
    out: list[Hunk] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        s, e, c, d = sa[i1], sa[i2], sb[j1], sb[j2]
        while s < e and c < d and old[s] == new[c]:
            s, c = s + 1, c + 1
        while s < e and c < d and old[e - 1] == new[d - 1]:
            e, d = e - 1, d - 1
        out.append((s, e, c, d))
    return out


def _window(changes: list[Hunk], s: int, e: int) -> tuple[int, int] | None:
    """The saved text's stretch that `[s, e)` of the published text became; None where a change crosses either end."""
    if any(a < s < b or a < e < b for a, b, _c, _d in changes):
        return None
    inside = [h for h in changes if s <= h[0] and h[1] <= e]
    before = sum((d - c) - (b - a) for a, b, c, d in changes if b <= s and (a, b, c, d) not in inside)
    within = sum((d - c) - (b - a) for a, b, c, d in inside)
    return s + before, e + before + within


def _innermost(envs: Iterable[Env], a: int, b: int) -> Env | None:
    """The innermost statement or proof whose body holds `[a, b)`."""
    best: Env | None = None
    for env in envs:
        if (env.theorem_like or env.is_proof) and env.body_start <= a and b <= env.body_end:
            if best is None or env.body_end - env.body_start < best.body_end - best.body_start:
                best = env
    return best


def _paragraph(text: str, a: int, b: int) -> tuple[int, int]:
    """The blank-line-bounded stretch of `text` round `[a, b)`."""
    s = 0
    for m in _BLANK.finditer(text, 0, a):
        s = m.end()
    after = _BLANK.search(text, b)
    return s, (after.start() if after else len(text))


def drafted(result: ScanResult, root: Path, changed: Iterable[Path]) -> list[dict[str, Any]]:
    """The blocks a save changed, each as the viewer is to draw it until TeX's arrives.

    Each is `{"src", "kind", "body"}`: `src` is `FILE:START:END` in the published text, as the page's `data-src` names it; `kind` is `env`, a statement's or proof's element whose `src` is exactly that, its `body` the text between its head and its `\\end`, or `text`, a paragraph whose `src` is the blank lines round it, its `body` the paragraph now. Comments are blanked. A file the last publication did not read, or a change that crosses a block's edge, gives nothing.
    """
    out: list[dict[str, Any]] = []
    for path in changed:
        if path.suffix != ".tex":
            continue
        rel = path.relative_to(root).as_posix()
        was = result.files.get(rel)
        if was is None or was.ignored or not path.is_file():
            continue
        now = read_source(root, rel)
        if now.text == was.text:
            continue
        changes = hunks(was.text, now.text)
        envs = result.assembly.envs.get(rel)
        all_envs = envs.all_envs() if envs is not None else []
        windows: dict[tuple[int, int], str] = {}
        for a, b, _c, _d in changes:
            env = _innermost(all_envs, a, b)
            if env is not None:
                windows[(env.start, env.end)] = "env"
                continue
            s, e = _paragraph(was.text, a, b)
            # a paragraph that grew into a neighbour is one window, the two read as one
            for (ws, we), kind in list(windows.items()):
                if kind == "text" and ws <= e and s <= we:
                    del windows[(ws, we)]
                    s, e = min(s, ws), max(e, we)
            windows[(s, e)] = "text"
        for (s, e), kind in sorted(windows.items()):
            if kind == "env":
                env = next(x for x in all_envs if (x.start, x.end) == (s, e))
                span = _window(changes, env.body_start, env.body_end)
                if span is None:
                    continue
                body = now.clean[span[0] : span[1]]
                if body == was.clean[env.body_start : env.body_end]:
                    continue
            else:
                span = _window(changes, s, e)
                if span is None:
                    continue
                body = now.clean[span[0] : span[1]]
                if _NOT_ONE.search(body) or _NOT_ONE.search(was.clean[s:e]) or body == was.clean[s:e]:
                    continue
                body = body.strip()
            out.append({"src": f"{rel}:{s}:{e}", "kind": kind, "body": body})
    return out
