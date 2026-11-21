#!/usr/bin/env python3
"""A component writes none of the viewer's words: every sentence the viewer says is in arras/src/lib/words/ (docs/design/README.md, "The viewer's words in one place").

Usage:
    scripts/checks/words.py [--all] [--file PATH ...]

Every `.svelte` file under `arras/src/` is read, except those on `LEGACY` below: the components that predate the words folder, each taken off the list when its words move, so the list only shrinks. A path on `LEGACY` that no longer exists fails the check. In a component read, once its `<script>`, `<style>` and `<!-- -->` comments are dropped and every `{...}` (an expression, or a block tag such as `{#if}`, `{:else}`, `{@html}`) is stepped over with its strings and template literals, these are words:

- text between tags that holds a letter once its HTML entities are decoded; glyphs, digits and punctuation alone (`×`, `›`, `·`, `…`, `2`) are not words;
- the static part, holding a letter, of a `title`, `aria-label`, `aria-description`, `aria-roledescription`, `placeholder`, `alt` or `label` attribute, quoted or not (`title="Open {name}"` is words; `title={words.x}` and `title="{words.x}"` are not).

Each is printed as `path:line: words`. `--all` reads every component, those on `LEGACY` too, and reports only a count of words per file, for measuring what is left. `--file PATH` reads the files named, on `LEGACY` or not, as when a component's words are being moved.

Exit 0 when no component read holds words, 1 otherwise; `--all` always exits 0.
"""

from __future__ import annotations

import argparse
import html
import sys
from bisect import bisect_right
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "arras" / "src"
WORDS = "arras/src/lib/words/"
FIX = f"move the words into {WORDS} (the file for the component's view, or frame.ts), as an entry named for the place it shows with a one-line comment saying where, and use the entry; a component that predates the folder and is not being changed stays on LEGACY in scripts/checks/words.py"

#: Attributes whose value a person sees or hears.
SEEN = {"title", "aria-label", "aria-description", "aria-roledescription", "placeholder", "alt", "label"}
#: The character before a `/` that makes it open a regular expression rather than divide.
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
#: What follows `{` in a block tag, before its name: `{#if}`, `{:else}`, `{/if}`, `{@html}`.
BLOCK = "#:/@"

#: The components that predate `arras/src/lib/words/` and still write their own words. A path comes off when its words move, and none is ever added.
LEGACY = (
    "arras/src/lib/components/AddWork.svelte",
    "arras/src/lib/components/Diagnostics.svelte",
    "arras/src/lib/components/DiffView.svelte",
    "arras/src/lib/components/DraftActions.svelte",
    "arras/src/lib/components/HelpDot.svelte",
    "arras/src/lib/components/JobProgress.svelte",
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
    "arras/src/lib/pdf/PageMarks.svelte",
    "arras/src/lib/pdf/PagesEditor.svelte",
    "arras/src/lib/pdf/PdfMenu.svelte",
    "arras/src/lib/pdf/PdfPage.svelte",
    "arras/src/lib/pdf/PdfTools.svelte",
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
    while k < n:
        c = src[k]
        if c.isspace():
            k += 1
            continue
        if c == ">" or src.startswith("/>", k):
            k += 1 if c == ">" else 2
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
        # the value's static parts, as (start, end) spans, and the span of the whole value
        static: list[tuple[int, int]] = []
        if k < n and src[k] in "\"'":
            quote, k = src[k], k + 1
            v0 = seg = k
            while k < n and src[k] != quote:
                if src[k] == "{":
                    static.append((seg, k))
                    k = seg = close_brace(src, k)
                else:
                    k += 1
            static.append((seg, k))
            v1, k = k, min(k + 1, n)
        elif k < n and src[k] == "{":
            v0, k = k, close_brace(src, k)
            v1 = k
        else:
            v0 = seg = k
            while k < n and not (src[k].isspace() or src[k] == ">" or src.startswith("/>", k)):
                if src[k] == "{":
                    static.append((seg, k))
                    k = seg = close_brace(src, k)
                else:
                    k += 1
            static.append((seg, k))
            v1 = k
        if attr in SEEN and has_letter("".join(src[s:e] for s, e in static)):
            raw = src[v0:v1]
            found.append((v0 + len(raw) - len(raw.lstrip()), f'{attr}="{shown(raw)}"'))
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
            else:
                if run is None:
                    run = i
                exprs.append((i, end))
            i = end
        else:
            if run is None:
                run = i
            i += 1
    flush(n)
    newlines = [j for j, ch in enumerate(src) if ch == "\n"]
    return [(bisect_right(newlines, at - 1) + 1, words) for at, words in sorted(found, key=lambda f: f[0])]


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
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
    read = args.file or [p for p in components if rel(p) not in legacy]
    bad = report(read)
    for p in gone:
        print(f"words: {p} is on LEGACY and no longer exists; fix: remove it from LEGACY in scripts/checks/words.py")
    if bad:
        print(f"words written in a component, not in {WORDS}:")
        print("\n".join(bad))
        print(f"fix: {FIX}")
    if bad or gone:
        return 1
    print(f"words: ok ({len(read)} component(s) read hold no words{'' if args.file else f'; {len(LEGACY)} on LEGACY'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
