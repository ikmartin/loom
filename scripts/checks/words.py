#!/usr/bin/env python3
"""A component writes none of the viewer's words: every sentence the viewer says is in viewer/src/lib/words/ (docs/design/README.md, "The viewer's words in one place").

Usage:
    scripts/checks/words.py [--base REF] [--all] [--file PATH ...]

Every `.svelte` file under `viewer/src/` is read, except those on `LEGACY` below: the components that predate the words folder, each taken off the list when its words move. The list only shrinks, and the check holds it so: a path on `LEGACY` that the list at `--base` (default `$WORDS_BASE`, else `$HARDWRAP_BASE`, else HEAD) does not hold fails, a component moved since keeping its place (git's rename, or a copy whose source left the list; a copy made to start a new component leaves its source listed), as does a path on it that no longer exists or whose component now holds no words. A base that names no commit fails; a base whose `words.py` holds no list is said in the output, and then nothing is compared. In a component read, once its `<script>`, `<style>` and `<!-- -->` comments are dropped, these are words:

- text between tags that holds a letter once its HTML entities are decoded; glyphs, digits and punctuation alone (`×`, `›`, `·`, `…`, `2`) are not words;
- the static part, holding a letter, of a `title`, `aria-label`, `aria-description`, `aria-roledescription`, `aria-valuetext`, `aria-placeholder`, `placeholder`, `alt` or `label` attribute, or of `value` on an `<input>` of type `button`, `submit` or `reset`, quoted or not (`title="Open {name}"` is words; `title={words.x}` and `title="{words.x}"` are not);
- in an expression in text, in such an attribute's expression, or in `{@html …}`: a string literal, or a template literal's fixed part, that holds a word, a space with a letter or a leading capital (`{ok ? 'Saved.' : 'Saving…'}`, ``title={`Opened ${n} minutes ago`}``), and, at the expression's top level, where it can be the value shown, one that holds any letter (`{busy ? 'undoing' : 'undo'}`); markup in a literal is not words, the text between its tags is;
- in the expression of an event handler (`onclick={…}`), an action (`use:hovercard={{ text: … }}`) or `data-tip`, in an attachment or a spread inside a tag (`{@attach tip("…")}`), and in every block tag (`{@render row(…)}`, `{@const …}`, `{#each [...]}`, `{#if …}`, `{:else if …}`, `{#key …}`, `{#await …}`): a literal that holds a word by the same rule, a space with a letter or a leading capital.

Never words, anywhere: a value tested, the operand of `===`, `!==`, `==` or `!=`, a `case` label, or a key tested with `in` (`e.key === 'Escape'`, `'short' in source`).

What it does not read: a string written in `<script>` and used by name (`title={tip}`); a string in a `.ts` module, beside a component or anywhere outside `words/`; a component's prop other than `label`, static or in an expression (`<Empty hint="…">`, `hint={'…'}`); any other attribute's expression (`class={…}`, `href={…}`); a lone lower-case word with no space anywhere but at the top level of text, a seen attribute or `{@html}` (`message.post('undone')`, `{#each ['open', 'shut'] as w}`); a literal inside brackets in such an expression that holds neither a space nor a capital (`{fmt('undo')}`); and words in CSS (`content:`). Those are held by review.

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
SRC = ROOT / "viewer" / "src"
WORDS = "viewer/src/lib/words/"
FIX = f"move the words into {WORDS} (the file for the component's view, or frame.ts), as an entry named for the place it shows with a one-line comment saying where, and use the entry; a component that predates the folder and is not being changed stays on LEGACY in scripts/checks/words.py"

#: Attributes whose value a person sees or hears.
SEEN = {"title", "aria-label", "aria-description", "aria-roledescription", "aria-valuetext", "aria-placeholder", "placeholder", "alt", "label"}
#: Attributes whose expression may hold words shown elsewhere: a hover card's text given to an action (`use:hovercard={{ text: … }}`), a message posted from a handler (`onclick={() => message.post(…)}`), a tip. Their expressions are read; a static value is a name, not words.
CARRIERS = ("use:", "on", "data-tip")
#: The `<input>` types whose `value` is the button's words.
BUTTONS = {"button", "submit", "reset"}
#: The character before a `/` that makes it open a regular expression rather than divide.
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
#: What follows `{` in a block tag, before its name: `{#if}`, `{:else}`, `{/if}`, `{@html}`.
BLOCK = "#:/@"

#: The components that predate `viewer/src/lib/words/` and still write their own words. A path comes off when its words move, and none is ever added (the check compares the list with its base's).
LEGACY = (
    "viewer/src/lib/components/Diagnostics.svelte",
    "viewer/src/lib/components/DiffView.svelte",
    "viewer/src/lib/components/DraftActions.svelte",
    "viewer/src/lib/components/LinkPreview.svelte",
    "viewer/src/lib/components/NoDrafts.svelte",
    "viewer/src/lib/components/Palette.svelte",
    "viewer/src/lib/fragments/Fragment.svelte",
    "viewer/src/lib/fragments/FragmentNotes.svelte",
    "viewer/src/lib/graph/LocalBoxGraph.svelte",
    "viewer/src/lib/graph/LocalGraph.svelte",
    "viewer/src/lib/graph/LocalGraphPanel.svelte",
    "viewer/src/lib/pdf/DrawTools.svelte",
    "viewer/src/lib/pdf/MarkedDoc.svelte",
    "viewer/src/lib/pdf/PageMarks.svelte",
    "viewer/src/lib/pdf/PagesEditor.svelte",
    "viewer/src/lib/pdf/PdfMenu.svelte",
    "viewer/src/lib/pdf/PdfPage.svelte",
    "viewer/src/lib/pdf/PdfTools.svelte",
    "viewer/src/lib/pdf/Swatches.svelte",
    "viewer/src/lib/review/AnnotateBar.svelte",
    "viewer/src/lib/review/AnnotationPopup.svelte",
    "viewer/src/lib/review/ChangeCard.svelte",
    "viewer/src/lib/review/ChangeList.svelte",
    "viewer/src/lib/review/ChangePopup.svelte",
    "viewer/src/lib/review/Changed.svelte",
    "viewer/src/lib/review/ChangesMenu.svelte",
    "viewer/src/lib/review/ClosurePanel.svelte",
    "viewer/src/lib/review/DeletedBar.svelte",
    "viewer/src/lib/review/LookControls.svelte",
    "viewer/src/lib/review/ReviewPanel.svelte",
    "viewer/src/lib/review/SideList.svelte",
    "viewer/src/lib/review/TypeList.svelte",
    "viewer/src/lib/review/VersionView.svelte",
    "viewer/src/lib/review/YourChanges.svelte",
    "viewer/src/lib/shell/AgentMark.svelte",
    "viewer/src/lib/shell/Contents.svelte",
    "viewer/src/lib/shell/Settings.svelte",
    "viewer/src/lib/shell/column/DocumentList.svelte",
    "viewer/src/lib/shell/settings/Agents.svelte",
    "viewer/src/lib/shell/settings/Annotations.svelte",
    "viewer/src/lib/shell/settings/Appearance.svelte",
    "viewer/src/lib/shell/settings/Chips.svelte",
    "viewer/src/lib/shell/settings/Documents.svelte",
    "viewer/src/lib/shell/settings/Files.svelte",
    "viewer/src/lib/shell/settings/General.svelte",
    "viewer/src/lib/shell/settings/Library.svelte",
    "viewer/src/lib/workspace/CompareControls.svelte",
    "viewer/src/lib/workspace/ItemToolbar.svelte",
    "viewer/src/lib/workspace/Pane.svelte",
    "viewer/src/lib/workspace/PaneViews.svelte",
    "viewer/src/lib/workspace/VersionControls.svelte",
    "viewer/src/lib/workspace/Workspace.svelte",
    "viewer/src/lib/workspace/items/ChatView.svelte",
    "viewer/src/lib/workspace/items/CompiledControls.svelte",
    "viewer/src/lib/workspace/items/CompiledItem.svelte",
    "viewer/src/lib/workspace/items/DocumentControls.svelte",
    "viewer/src/lib/workspace/items/DocumentItem.svelte",
    "viewer/src/lib/workspace/items/FileControls.svelte",
    "viewer/src/lib/workspace/items/FileItem.svelte",
    "viewer/src/lib/workspace/items/NodeControls.svelte",
    "viewer/src/lib/workspace/items/PageMeta.svelte",
    "viewer/src/lib/workspace/items/WorkControls.svelte",
    "viewer/src/routes/graph/+page.svelte",
    "viewer/src/routes/loose/+page.svelte",
    "viewer/src/routes/review/problems/+page.svelte",
    "viewer/src/routes/review/proposed/+page.svelte",
    "viewer/src/routes/review/record/+layout.svelte",
    "viewer/src/routes/review/record/+page.svelte",
    "viewer/src/routes/review/record/acts/+page.svelte",
    "viewer/src/routes/review/record/sessions/+page.svelte",
    "viewer/src/routes/tag/[tag]/+page.svelte",
    "viewer/src/routes/tags/+page.svelte",
    "viewer/src/routes/taxa/+page.svelte",
    "viewer/src/routes/taxon/[slug]/+page.svelte",
    "viewer/src/routes/threads/+page.svelte",
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


def literals(src: str, i: int, end: int, depth: int = 0) -> list[tuple[int, str, int, bool]]:
    """The string literals, and the fixed parts of template literals, in the expression `src[i:end]`, as (offset, text, depth, compared).

    `depth` is how many brackets enclose the literal within the expression, a template literal's `${...}` counting as none, so a literal at depth 0 can be what the expression gives; `compared` says it is an operand of `===`, `!==`, `==` or `!=`, or a `case` label: a value tested, never shown. Comments are stepped over; a template literal's `${...}` is read for literals of its own.
    """
    out: list[tuple[int, str, int, bool]] = []
    j, level = i, depth
    while j < end:
        c = src[j]
        if c in "\"'":
            k = close_quote(src, j)
            out.append((j, src[j + 1 : max(j + 1, k - 1)], level, compared(src, i, j, k, end)))
            j = k
        elif c == "`":
            k = close_template(src, j)
            seg, m = j + 1, j + 1
            tested = compared(src, i, j, k, end)
            while m < k - 1:
                if src[m] == "\\":
                    m += 2
                elif src[m] == "$" and src.startswith("{", m + 1):
                    out.append((seg, src[seg:m], level, tested))
                    close = close_brace(src, m + 1)
                    out.extend(literals(src, m + 2, close - 1, level))
                    m = seg = close
                else:
                    m += 1
            out.append((seg, src[seg : max(seg, k - 1)], level, tested))
            j = k
        elif c in "([{":
            level += 1
            j += 1
        elif c in ")]}":
            level = max(depth, level - 1)
            j += 1
        elif c == "/" and src.startswith("/", j + 1):
            nl = src.find("\n", j)
            j = end if nl < 0 else nl
        elif c == "/" and src.startswith("*", j + 1):
            close = src.find("*/", j + 2)
            j = end if close < 0 else close + 2
        else:
            j += 1
    return out


COMPARE = ("===", "!==", "==", "!=")


def compared(src: str, i: int, at: int, stop: int, end: int) -> bool:
    """Whether the literal `src[at:stop]` is a value tested in the expression `src[i:end]`: an operand of a comparison, a `case` label, or a key tested with `in`."""
    before, after = src[i:at].rstrip(), src[stop:end].lstrip()
    return before.endswith(COMPARE) or after.startswith(COMPARE) or re.search(r"\bcase$", before) is not None or re.match(r"in\b", after) is not None


def spoken(src: str, i: int, end: int, shown_as_is: bool = False) -> list[tuple[int, str]]:
    """The literals in `src[i:end]` that read as words, as (offset, words), a value compared never among them.

    With `shown_as_is`, for an expression whose value is what a person sees (text, a seen attribute, `{@html}`), a literal at its top level is words when it holds any letter (`{busy ? 'undoing' : 'undo'}`), since it can be the value shown.
    """
    return [
        (at, shown(text))
        for at, text, depth, tested in literals(src, i, end)
        if not tested and (is_words(untagged(text)) or (shown_as_is and depth == 0 and has_letter(untagged(text))))
    ]


def untagged(text: str) -> str:
    """A literal's text with its HTML tags taken out, so markup given to `{@html}` (`'<style>'`) is not read as words, and the words between its tags are."""
    return re.sub(r"<[^>]*>", "", text)


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
            if a.startswith(CARRIERS) and not (a in SEEN):
                for x, y in exprs:
                    found.extend((at, f"{a}={{…{words}…}}") for at, words in spoken(src, x + 1, y - 1))
                continue
            if not (a in SEEN or (a == "value" and name == "input" and kind in BUTTONS)):
                continue
            raw = src[v0:v1]
            if has_letter("".join(src[x:y] for x, y in static)):
                found.append((v0 + len(raw) - len(raw.lstrip()), f'{a}="{shown(raw)}"'))
                continue
            for x, y in exprs:
                found.extend((at, f"{a}={{…{words}…}}") for at, words in spoken(src, x + 1, y - 1, shown_as_is=True))

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
            # an attachment or a spread in the tag (`{@attach tip("…")}`, `{...props}`): read by the words rule
            end = close_brace(src, k)
            found.extend((at, f"{{…{words}…}}") for at, words in spoken(src, k + 1, end - 1))
            k = end
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
                # every block tag's literals: `{@html}`'s are shown as they are; `{@const}`, `{@render row(…)}`, `{#each [...]}`, `{#if}`, `{:else if}`, `{#key}` and `{#await}` hold words only by the rule
                head = re.match(r"[#:/@]\s*(?:else\s+if|[a-z]+)", src[i + 1 : end])
                found.extend(spoken(src, i + 1 + (head.end() if head else 1), end - 1, shown_as_is=src.startswith("@html", i + 1)))
            else:
                if run is None:
                    run = i
                exprs.append((i, end))
                found.extend(spoken(src, i + 1, end - 1, shown_as_is=True))
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
    return any(is_words(text) for m in SCRIPT.finditer(src) for _, text, _, _ in literals(m.group(1), 0, len(m.group(1))))


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


def resolves(ref: str) -> bool:
    """Whether `ref` names a commit here."""
    return subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=ROOT, capture_output=True).returncode == 0


def legacy_at(base: str) -> set[str] | None:
    """`LEGACY` as this script held it at `base`, or None where the script did not exist there."""
    shown_ = subprocess.run(["git", "show", f"{base}:scripts/checks/words.py"], cwd=ROOT, capture_output=True, text=True)
    if shown_.returncode != 0:
        return None
    for node in ast.parse(shown_.stdout).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "LEGACY" for t in node.targets):
            return set(ast.literal_eval(node.value))
    return None


def moved_since(base: str, legacy: set[str]) -> dict[str, str]:
    """The components on `LEGACY` at `base` that moved since, each old path to its new one, so that a component keeps its place on the list when it moves.

    A rename moves a path. To git a move whose old path now holds something new is a copy, so a copy counts as a move too, but only where its old path has left the list: a component copied to start a new one leaves its source where it was, on the list, and the copy is read like any new component. One `git diff` over every component in the repository answers for every path, so a component whose folder moved keeps its place too.
    """
    shown_ = subprocess.run(["git", "diff", "-C", "-C", "--name-status", base, "--", "*.svelte"], cwd=ROOT, capture_output=True, text=True)
    moved: dict[str, str] = {}
    for line in shown_.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and (parts[0].startswith("R") or (parts[0].startswith("C") and parts[1] not in legacy)):
            moved[parts[1]] = parts[2]
    return moved


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
    if not args.file and not resolves(args.base):
        print(f"words: the base {args.base} names no commit here, so LEGACY cannot be held to it; fix: give --base (or $WORDS_BASE) a commit, branch or tag this checkout has, fetching it first in CI")
        return 1
    gone = [] if args.file else [p for p in LEGACY if not (ROOT / p).is_file()]
    before = None if args.file else legacy_at(args.base)
    moved = {} if before is None else moved_since(args.base, legacy)
    added = [] if before is None else sorted(legacy - {moved.get(p, p) for p in before})
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
    unheld = "" if args.file or before is not None else f"; LEGACY not compared with {args.base}, which holds no list"
    print(f"words: ok ({len(read)} component(s) read hold no words{'' if args.file else f'; {len(LEGACY)} on LEGACY'}{unheld})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
