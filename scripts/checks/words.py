#!/usr/bin/env python3
"""A component writes none of the viewer's words: every sentence the viewer says is in arras/src/lib/words/ (docs/design/README.md, "The viewer's words in one place").

Usage:
    scripts/checks/words.py [--base REF] [--all] [--file PATH ...]

Every `.svelte` file under `arras/src/` is read, except those on `LEGACY` below: the components that predate the words folder, each taken off the list when its words move. The list only shrinks, and the check holds it so: a path on `LEGACY` that the list at `--base` (default `$WORDS_BASE`, else `$HARDWRAP_BASE`, else HEAD) does not hold fails, as does a path on it that no longer exists or whose component now holds no words. In a component read, once its `<script>`, `<style>` and `<!-- -->` comments are dropped, these are words:

- text between tags that holds a letter once its HTML entities are decoded; glyphs, digits and punctuation alone (`×`, `›`, `·`, `…`, `2`) are not words;
- the static part, holding a letter, of a `title`, `aria-label`, `aria-description`, `aria-roledescription`, `aria-valuetext`, `aria-placeholder`, `placeholder`, `alt` or `label` attribute, or of `value` on an `<input>` of type `button`, `submit` or `reset`, quoted or not (`title="Open {name}"` is words; `title={words.x}` and `title="{words.x}"` are not);
- a string literal, or a template literal's fixed part, that holds a word, a space with a letter or a leading capital, inside an expression in text (`{ok ? 'Saved.' : 'Saving…'}`), inside `{@html …}` or `{@const …}`, or inside such an attribute's expression (``title={`Opened ${n} minutes ago`}``); a literal such as `'docs'` or `' ↑'` is not words.

What it does not see: a string written in `<script>` and used by name (`title={tip}`), a string passed to a component's prop other than `label`, and words in CSS (`content:`). Those are held by review, not by this check.

Each is printed as `path:line: words`. `--all` reads every component, those on `LEGACY` too, and reports only a count of words per file, for measuring what is left. `--file PATH` reads the files named, on `LEGACY` or not, as when a component's words are being moved.

Exit 0 when no component read holds words and `LEGACY` has only shrunk, 1 otherwise; `--all` always exits 0.
"""

from __future__ import annotations

import argparse
import ast
import html
import os
import re
import subprocess
import sys
from bisect import bisect_right
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "arras" / "src"
WORDS = "arras/src/lib/words/"
FIX = f"move the words into {WORDS} (the file for the component's view, or frame.ts), as an entry named for the place it shows with a one-line comment saying where, and use the entry; a component that predates the folder and is not being changed stays on LEGACY in scripts/checks/words.py"

#: Attributes whose value a person sees or hears.
SEEN = {"title", "aria-label", "aria-description", "aria-roledescription", "aria-valuetext", "aria-placeholder", "placeholder", "alt", "label"}
#: The `<input>` types whose `value` is the button's words.
BUTTONS = {"button", "submit", "reset"}
#: The character before a `/` that makes it open a regular expression rather than divide.
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
#: What follows `{` in a block tag, before its name: `{#if}`, `{:else}`, `{/if}`, `{@html}`.
BLOCK = "#:/@"

#: The components that predate `arras/src/lib/words/` and still write their own words. A path comes off when its words move, and none is ever added (the check compares the list with its base's).
LEGACY = (
    "arras/src/lib/components/AddWork.svelte",
    "arras/src/lib/components/AskAgent.svelte",
    "arras/src/lib/components/Diagnostics.svelte",
    "arras/src/lib/components/DiffView.svelte",
    "arras/src/lib/components/DraftActions.svelte",
    "arras/src/lib/components/HelpDot.svelte",
    "arras/src/lib/components/JobProgress.svelte",
    "arras/src/lib/components/LibraryRun.svelte",
    "arras/src/lib/components/LinkPreview.svelte",
    "arras/src/lib/components/Locator.svelte",
    "arras/src/lib/components/NetworkAsk.svelte",
    "arras/src/lib/components/NoDrafts.svelte",
    "arras/src/lib/components/OutOfStep.svelte",
    "arras/src/lib/components/Palette.svelte",
    "arras/src/lib/components/PdfViewer.svelte",
    "arras/src/lib/components/ResultCard.svelte",
    "arras/src/lib/components/WorkLinks.svelte",
    "arras/src/lib/components/WorkStatus.svelte",
    "arras/src/lib/fragments/Fragment.svelte",
    "arras/src/lib/fragments/FragmentNotes.svelte",
    "arras/src/lib/graph/LocalBoxGraph.svelte",
    "arras/src/lib/graph/LocalGraph.svelte",
    "arras/src/lib/graph/LocalGraphPanel.svelte",
    "arras/src/lib/pdf/DrawTools.svelte",
    "arras/src/lib/pdf/MarkedDoc.svelte",
    "arras/src/lib/pdf/PageMarks.svelte",
    "arras/src/lib/pdf/PagesEditor.svelte",
    "arras/src/lib/pdf/PdfMenu.svelte",
    "arras/src/lib/pdf/PdfPage.svelte",
    "arras/src/lib/pdf/PdfTools.svelte",
    "arras/src/lib/pdf/Reading.svelte",
    "arras/src/lib/pdf/Swatches.svelte",
    "arras/src/lib/review/AnnotateBar.svelte",
    "arras/src/lib/review/AnnotationPopup.svelte",
    "arras/src/lib/review/ChangeCard.svelte",
    "arras/src/lib/review/ChangeList.svelte",
    "arras/src/lib/review/ChangePopup.svelte",
    "arras/src/lib/review/Changed.svelte",
    "arras/src/lib/review/ChangesMenu.svelte",
    "arras/src/lib/review/ClosurePanel.svelte",
    "arras/src/lib/review/ContributionReview.svelte",
    "arras/src/lib/review/DeletedBar.svelte",
    "arras/src/lib/review/IncomingPull.svelte",
    "arras/src/lib/review/LibraryRow.svelte",
    "arras/src/lib/review/LinkList.svelte",
    "arras/src/lib/review/LookControls.svelte",
    "arras/src/lib/review/ProposalCard.svelte",
    "arras/src/lib/review/ProposalQueue.svelte",
    "arras/src/lib/review/QuoteChip.svelte",
    "arras/src/lib/review/ReviewPanel.svelte",
    "arras/src/lib/review/SideList.svelte",
    "arras/src/lib/review/TypeList.svelte",
    "arras/src/lib/review/VersionView.svelte",
    "arras/src/lib/sessions/DeleteSession.svelte",
    "arras/src/lib/sessions/SessionFooter.svelte",
    "arras/src/lib/sessions/SessionPicker.svelte",
    "arras/src/lib/shell/AgentMark.svelte",
    "arras/src/lib/shell/Contents.svelte",
    "arras/src/lib/shell/FileTree.svelte",
    "arras/src/lib/shell/Settings.svelte",
    "arras/src/lib/shell/column/DocumentList.svelte",
    "arras/src/lib/shell/column/FilesShelf.svelte",
    "arras/src/lib/shell/column/LibraryShelf.svelte",
    "arras/src/lib/shell/settings/Agents.svelte",
    "arras/src/lib/shell/settings/Annotations.svelte",
    "arras/src/lib/shell/settings/Appearance.svelte",
    "arras/src/lib/shell/settings/Chips.svelte",
    "arras/src/lib/shell/settings/Documents.svelte",
    "arras/src/lib/shell/settings/Files.svelte",
    "arras/src/lib/shell/settings/General.svelte",
    "arras/src/lib/shell/settings/Library.svelte",
    "arras/src/lib/shell/settings/Overleaf.svelte",
    "arras/src/lib/shell/settings/Profile.svelte",
    "arras/src/lib/workspace/CompareControls.svelte",
    "arras/src/lib/workspace/HistoryMenu.svelte",
    "arras/src/lib/workspace/ItemToolbar.svelte",
    "arras/src/lib/workspace/Pane.svelte",
    "arras/src/lib/workspace/PaneHead.svelte",
    "arras/src/lib/workspace/PaneViews.svelte",
    "arras/src/lib/workspace/VersionControls.svelte",
    "arras/src/lib/workspace/Workspace.svelte",
    "arras/src/lib/workspace/items/ChatView.svelte",
    "arras/src/lib/workspace/items/CompiledControls.svelte",
    "arras/src/lib/workspace/items/CompiledItem.svelte",
    "arras/src/lib/workspace/items/ContextItem.svelte",
    "arras/src/lib/workspace/items/DocumentControls.svelte",
    "arras/src/lib/workspace/items/DocumentItem.svelte",
    "arras/src/lib/workspace/items/FileControls.svelte",
    "arras/src/lib/workspace/items/FileItem.svelte",
    "arras/src/lib/workspace/items/NodeControls.svelte",
    "arras/src/lib/workspace/items/NodeItem.svelte",
    "arras/src/lib/workspace/items/NodePreview.svelte",
    "arras/src/lib/workspace/items/PageItem.svelte",
    "arras/src/lib/workspace/items/PageMeta.svelte",
    "arras/src/lib/workspace/items/SessionDid.svelte",
    "arras/src/lib/workspace/items/WorkControls.svelte",
    "arras/src/lib/workspace/items/WorkItem.svelte",
    "arras/src/routes/+page.svelte",
    "arras/src/routes/graph/+page.svelte",
    "arras/src/routes/loose/+page.svelte",
    "arras/src/routes/review/+page.svelte",
    "arras/src/routes/review/library/+page.svelte",
    "arras/src/routes/review/problems/+page.svelte",
    "arras/src/routes/review/proposed/+page.svelte",
    "arras/src/routes/review/record/+layout.svelte",
    "arras/src/routes/review/record/+page.svelte",
    "arras/src/routes/review/record/acts/+page.svelte",
    "arras/src/routes/review/record/sessions/+page.svelte",
    "arras/src/routes/tag/[tag]/+page.svelte",
    "arras/src/routes/tags/+page.svelte",
    "arras/src/routes/taxa/+page.svelte",
    "arras/src/routes/taxon/[slug]/+page.svelte",
    "arras/src/routes/threads/+page.svelte",
)


def block_tag(src: str, i: int) -> bool:
    """Whether the `{` at `src[i]` opens a block tag, whose mark is followed by a name: `{/if}` is one, `{/* note */ x}` is not."""
    return i + 2 < len(src) and src[i + 1] in BLOCK and src[i + 2].isalpha()


def close_quote(src: str, i: int) -> int:
    """Index past the JavaScript string opening at `src[i]`.

    A raw newline ends it, since no JavaScript string holds one; that keeps a stray quote from swallowing the file.
    """
    quote, j, n = src[i], i + 1, len(src)
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
        elif c == quote:
            return j + 1
        elif c == "\n":
            return j
        else:
            j += 1
    return n


def close_template(src: str, i: int) -> int:
    """Index past the template literal opening at `src[i]`, stepping over each `${...}` inside it."""
    j, n = i + 1, len(src)
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
        elif c == "`":
            return j + 1
        elif c == "$" and src.startswith("{", j + 1):
            j = close_brace(src, j + 1)
        else:
            j += 1
    return n


def close_regex(src: str, i: int) -> int:
    """Index past the regular expression opening at `src[i]`, or just past the `/` when none closes on its line."""
    j, n, in_class = i + 1, len(src), False
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == "\n":
            return i + 1
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            return j + 1
        j += 1
    return i + 1


def close_brace(src: str, i: int) -> int:
    """Index past the `}` matching the `{` at `src[i]`.

    Strings, template literals, comments and regular expressions inside are stepped over; a block tag's leading `#`, `:`, `/` or `@` is not read as the start of a regular expression.
    """
    n = len(src)
    depth, prev, j = 0, "", i
    if block_tag(src, i):
        depth, prev, j = 1, "a", i + 2
    while j < n:
        c = src[j]
        if c in "\"'":
            j, prev = close_quote(src, j), "a"
            continue
        if c == "`":
            j, prev = close_template(src, j), "a"
            continue
        if c == "/" and src.startswith("/", j + 1):
            end = src.find("\n", j)
            j = n if end < 0 else end
            continue
        if c == "/" and src.startswith("*", j + 1):
            end = src.find("*/", j + 2)
            j = n if end < 0 else end + 2
            continue
        if c == "/" and (prev == "" or prev in REGEX_AFTER):
            j, prev = close_regex(src, j), "a"
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        if not c.isspace():
            prev = c
        j += 1
    return n


def has_letter(static: str) -> bool:
    return any(ch.isalpha() for ch in html.unescape(static))


def is_words(literal: str) -> bool:
    """Whether a string literal's text reads as words a person sees: a space with a letter, or a leading capital."""
    text = html.unescape(literal)
    return (any(ch.isspace() for ch in text) and any(ch.isalpha() for ch in text)) or text[:1].isupper()


def literals(src: str, i: int, end: int) -> list[tuple[int, str]]:
    """The string literals, and the fixed parts of template literals, in the expression `src[i:end]`, as (offset, text).

    Comments are stepped over; a template literal's `${...}` is read for literals of its own.
    """
    out: list[tuple[int, str]] = []
    j = i
    while j < end:
        c = src[j]
        if c in "\"'":
            k = close_quote(src, j)
            out.append((j, src[j + 1 : max(j + 1, k - 1)]))
            j = k
        elif c == "`":
            k = close_template(src, j)
            seg, m = j + 1, j + 1
            while m < k - 1:
                if src[m] == "\\":
                    m += 2
                elif src[m] == "$" and src.startswith("{", m + 1):
                    out.append((seg, src[seg:m]))
                    close = close_brace(src, m + 1)
                    out.extend(literals(src, m + 2, close - 1))
                    m = seg = close
                else:
                    m += 1
            out.append((seg, src[seg : max(seg, k - 1)]))
            j = k
        elif c == "/" and src.startswith("/", j + 1):
            nl = src.find("\n", j)
            j = end if nl < 0 else nl
        elif c == "/" and src.startswith("*", j + 1):
            close = src.find("*/", j + 2)
            j = end if close < 0 else close + 2
        else:
            j += 1
    return out


def spoken(src: str, i: int, end: int) -> list[tuple[int, str]]:
    """The literals in `src[i:end]` that read as words, as (offset, words)."""
    return [(at, shown(text)) for at, text in literals(src, i, end) if is_words(text)]


def shown(raw: str) -> str:
    """The words as a finding prints them: whitespace collapsed, at most 60 characters."""
    text = " ".join(raw.split())
    return text if len(text) <= 60 else text[:59] + "…"


def scan_tag(src: str, i: int, found: list[tuple[int, str]]) -> int:
    """Read the tag opening at `src[i]`, add its seen attributes' words to `found`, and return the index past it.

    Quoted values and `{...}` are stepped over whole, so `onclick={() => a > b}` does not end the tag; a `<script>` or `<style>` is skipped to its closing tag. Positions in `found` are offsets, made lines by the caller.
    """
    n = len(src)
    if src.startswith("!", i + 1):
        end = src.find(">", i)
        return n if end < 0 else end + 1
    k = i + 1
    closing = src.startswith("/", k)
    if closing:
        k += 1
    start = k
    while k < n and not (src[k].isspace() or src[k] in "/>"):
        k += 1
    name = src[start:k].lower()
    attrs: list[tuple[str, int, int, list[tuple[int, int]], list[tuple[int, int]]]] = []

    def judge() -> None:
        kind = next((src[v0:v1].strip("\"' ").lower() for a, v0, v1, _, _ in attrs if a == "type"), "")
        for a, v0, v1, static, exprs in attrs:
            if not (a in SEEN or (a == "value" and name == "input" and kind in BUTTONS)):
                continue
            raw = src[v0:v1]
            if has_letter("".join(src[x:y] for x, y in static)):
                found.append((v0 + len(raw) - len(raw.lstrip()), f'{a}="{shown(raw)}"'))
                continue
            for x, y in exprs:
                found.extend((at, f"{a}={{…{words}…}}") for at, words in spoken(src, x + 1, y - 1))

    while k < n:
        c = src[k]
        if c.isspace():
            k += 1
            continue
        if c == ">" or src.startswith("/>", k):
            k += 1 if c == ">" else 2
            judge()
            if name in ("script", "style") and not closing and c == ">":
                end = src.lower().find(f"</{name}", k)
                if end < 0:
                    return n
                end = src.find(">", end)
                return n if end < 0 else end + 1
            return k
        if c == "{":
            k = close_brace(src, k)
            continue
        a = k
        while k < n and not (src[k].isspace() or src[k] in "=>" or src.startswith("/>", k)):
            k += 1
        if k == a:
            k += 1
            continue
        attr = src[a:k].lower()
        while k < n and src[k].isspace():
            k += 1
        if not src.startswith("=", k):
            continue
        k += 1
        while k < n and src[k].isspace():
            k += 1
        # the value's static parts and its expressions, as (start, end) spans, and the span of the whole value
        static: list[tuple[int, int]] = []
        exprs: list[tuple[int, int]] = []
        if k < n and src[k] in "\"'":
            quote, k = src[k], k + 1
            v0 = seg = k
            while k < n and src[k] != quote:
                if src[k] == "{":
                    static.append((seg, k))
                    end = close_brace(src, k)
                    exprs.append((k, end))
                    k = seg = end
                else:
                    k += 1
            static.append((seg, k))
            v1, k = k, min(k + 1, n)
        elif k < n and src[k] == "{":
            v0, k = k, close_brace(src, k)
            exprs.append((v0, k))
            v1 = k
        else:
            v0 = seg = k
            while k < n and not (src[k].isspace() or src[k] == ">" or src.startswith("/>", k)):
                if src[k] == "{":
                    static.append((seg, k))
                    end = close_brace(src, k)
                    exprs.append((k, end))
                    k = seg = end
                else:
                    k += 1
            static.append((seg, k))
            v1 = k
        attrs.append((attr, v0, v1, static, exprs))
    judge()
    return n


def findings(src: str) -> list[tuple[int, str]]:
    """The words written in a component's source, as (1-based line, words) in source order.

    A run of text and `{expression}`s between tags is one finding when its text holds a letter; a block tag ends a run, as a tag does.
    """
    found: list[tuple[int, str]] = []
    n = len(src)
    run: int | None = None
    exprs: list[tuple[int, int]] = []

    def flush(end: int) -> None:
        nonlocal run, exprs
        if run is not None:
            text, at = [], run
            for s, e in exprs:
                text.append(src[at:s])
                at = e
            text.append(src[at:end])
            raw = src[run:end]
            if has_letter("".join(text)):
                found.append((run + len(raw) - len(raw.lstrip()), shown(raw)))
        run, exprs = None, []

    i = 0
    while i < n:
        c = src[i]
        if src.startswith("<!--", i):
            flush(i)
            end = src.find("-->", i + 4)
            i = n if end < 0 else end + 3
        elif c == "<" and i + 1 < n and (src[i + 1].isalpha() or src[i + 1] in "/!"):
            flush(i)
            i = scan_tag(src, i, found)
        elif c == "{":
            end = close_brace(src, i)
            if block_tag(src, i):
                flush(i)
                if src.startswith("@html", i + 1) or src.startswith("@const", i + 1):
                    found.extend(spoken(src, i + 1, end - 1))
            else:
                if run is None:
                    run = i
                exprs.append((i, end))
                found.extend(spoken(src, i + 1, end - 1))
            i = end
        else:
            if run is None:
                run = i
            i += 1
    flush(n)
    newlines = [j for j, ch in enumerate(src) if ch == "\n"]
    return [(bisect_right(newlines, at - 1) + 1, words) for at, words in sorted(found, key=lambda f: f[0])]


SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)


def holds_words(src: str) -> bool:
    """Whether a component holds words anywhere, its script's strings included: what keeps a component on `LEGACY`, which is read more widely than a component off it, since a string in `<script>` is words the check cannot otherwise see."""
    if findings(src):
        return True
    return any(is_words(text) for m in SCRIPT.finditer(src) for _, text in literals(m.group(1), 0, len(m.group(1))))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def report(paths: list[Path]) -> list[str]:
    """Each component's words as `path:line: words` lines."""
    out = []
    for path in paths:
        for line, words in findings(path.read_text(encoding="utf-8")):
            out.append(f"{rel(path)}:{line}: {words}")
    return out


def legacy_at(base: str) -> set[str] | None:
    """`LEGACY` as this script held it at `base`, or None where the script did not exist there."""
    shown_ = subprocess.run(["git", "show", f"{base}:scripts/checks/words.py"], cwd=ROOT, capture_output=True, text=True)
    if shown_.returncode != 0:
        return None
    for node in ast.parse(shown_.stdout).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LEGACY" for t in node.targets):
            return set(ast.literal_eval(node.value))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    # CI sets HARDWRAP_BASE to the push's or pull request's base, and this check takes it too, since a clean checkout has nothing added since HEAD
    base = os.environ.get("WORDS_BASE") or os.environ.get("HARDWRAP_BASE") or "HEAD"
    parser.add_argument("--base", default=base, help="the commit whose LEGACY this one may only shrink from (default $WORDS_BASE, else $HARDWRAP_BASE, else HEAD)")
    parser.add_argument(
        "--all", action="store_true", help="count the words in every component, those on LEGACY too, and exit 0"
    )
    parser.add_argument("--file", nargs="+", type=Path, metavar="PATH", help="read these files, on LEGACY or not")
    args = parser.parse_args()
    components = sorted(SRC.rglob("*.svelte"))
    legacy = set(LEGACY)
    if args.all:
        total = files = 0
        for path in components:
            n = len(findings(path.read_text(encoding="utf-8")))
            if n:
                total, files = total + n, files + 1
                print(f"{n:4d}  {rel(path)}{'  (legacy)' if rel(path) in legacy else ''}")
        print(
            f"{total} word finding(s) in {files} of {len(components)} components; the check reads only those off LEGACY ({len(LEGACY)} on it)"
        )
        return 0
    gone = [] if args.file else [p for p in LEGACY if not (ROOT / p).is_file()]
    before = None if args.file else legacy_at(args.base)
    added = [] if before is None else sorted(legacy - before)
    clean = [] if args.file else [p for p in LEGACY if (ROOT / p).is_file() and not holds_words((ROOT / p).read_text(encoding="utf-8"))]
    read = args.file or [p for p in components if rel(p) not in legacy]
    bad = report(read)
    for p in gone:
        print(f"words: {p} is on LEGACY and no longer exists; fix: remove it from LEGACY in scripts/checks/words.py")
    for p in added:
        print(f"words: {p} was added to LEGACY since {args.base}; the list only shrinks; fix: move the component's words into {WORDS} and take it off LEGACY")
    for p in clean:
        print(f"words: {p} is on LEGACY and holds no words now; fix: take it off LEGACY in scripts/checks/words.py")
    if bad:
        print(f"words written in a component, not in {WORDS}:")
        print("\n".join(bad))
        print(f"fix: {FIX}")
    if bad or gone or added or clean:
        return 1
    print(f"words: ok ({len(read)} component(s) read hold no words{'' if args.file else f'; {len(LEGACY)} on LEGACY'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
