"""The listing of a person's in-place changes (`pending.cut`) is today's listing (`pending._cut_by_difflib`, kept as its oracle) made fast: the same changes and the same ids, since records hang on the ids.

Compared on the review's 6,000 pairs, the fixtures' documents edited at random, and on texts made to be hard: words that recur on every line, moved and duplicated lines, blank lines, re-spaced tables, CRLF. Every range that is costly to search is searched by window here (`pending._CHEAP` at 0), as a long file's ranges are.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from loom import pending

QUILTS = Path(__file__).resolve().parents[1] / "quilts"
WORDS = "the widget orbit fixed point lemma proof hence clearly map kernel \\eqref{eq:x} $x$ & \\\\ quotient".split()


def _documents() -> list[tuple[str, str]]:
    docs = []
    for p in sorted(QUILTS.rglob("*")):
        if p.is_file() and p.suffix in (".tex", ".md", ".bib", ".sty") and ".loom" not in p.parts:
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if len(text.split()) >= 5:
                docs.append((p.relative_to(QUILTS).as_posix(), text))
    return docs


def _lines(t: str) -> list[str]:
    return t.splitlines(keepends=True)


def _word(r: random.Random, t: str) -> str:
    m = r.choice(list(re.finditer(r"\S+", t)))
    return t[: m.start()] + r.choice(WORDS) + t[m.end() :]


def _insert_word(r: random.Random, t: str) -> str:
    m = r.choice(list(re.finditer(r"\S+", t)))
    return t[: m.end()] + " " + r.choice(WORDS) + t[m.end() :]


def _delete_word(r: random.Random, t: str) -> str:
    m = r.choice(list(re.finditer(r"\S+", t)))
    return t[: m.start()] + t[m.end() :]


def _delete_line(r: random.Random, t: str) -> str:
    ls = _lines(t)
    if len(ls) >= 2:
        del ls[r.randrange(len(ls))]
    return "".join(ls)


def _dup_line(r: random.Random, t: str) -> str:
    ls = _lines(t)
    ls.insert(r.randrange(len(ls) + 1), r.choice(ls) if ls else "x\n")
    return "".join(ls)


def _move_block(r: random.Random, t: str) -> str:
    ls = _lines(t)
    if len(ls) < 4:
        return t
    i = r.randrange(len(ls))
    k = r.randint(1, min(8, len(ls) - i))
    block = ls[i : i + k]
    del ls[i : i + k]
    j = r.randrange(len(ls) + 1)
    ls[j:j] = block
    return "".join(ls)


def _swap_lines(r: random.Random, t: str) -> str:
    ls = _lines(t)
    if len(ls) >= 2:
        i, j = r.sample(range(len(ls)), 2)
        ls[i], ls[j] = ls[j], ls[i]
    return "".join(ls)


def _rewrap(r: random.Random, t: str) -> str:
    paras = t.split("\n\n")
    i = r.randrange(len(paras))
    words = paras[i].split()
    if not words:
        return t
    width = r.choice([20, 40, 60, 80])
    out, line = [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}" if line else w
    out.append(line)
    paras[i] = "\n".join(out)
    return "\n\n".join(paras)


def _table(r: random.Random, t: str) -> str:
    ls = _lines(t)
    rows = [k for k, ln in enumerate(ls) if "\\\\" in ln or "&" in ln]
    if not rows:
        k = r.randrange(len(ls) + 1)
        ls[k:k] = ["a & b \\\\\n"] * r.randint(2, 6)
        return "".join(ls)
    k = r.choice(rows)
    ls[k:k] = [ls[k]] * r.randint(1, 4)
    return "".join(ls)


def _crlf(r: random.Random, t: str) -> str:
    return t.replace("\n", "\r\n")


def _edge(r: random.Random, t: str) -> str:
    return r.choice(
        [
            lambda: "% new first line\n" + t,
            lambda: r.choice(WORDS) + t,
            lambda: t + r.choice(WORDS),
            lambda: t + "\n% a last line\n",
            lambda: t[1:],
            lambda: t[:-1],
        ]
    )()


def _blank_lines(r: random.Random, t: str) -> str:
    ls = _lines(t)
    k = r.randrange(len(ls) + 1)
    ls[k:k] = ["\n"] * r.randint(1, 3)
    return "".join(ls)


#: The review's edits (`c18_cut_equiv.py`), in its order, so its seed draws the same pairs.
EDITS = [
    _word,
    _insert_word,
    _delete_word,
    _delete_line,
    _dup_line,
    _move_block,
    _swap_lines,
    _rewrap,
    _table,
    _crlf,
    _edge,
    _blank_lines,
]


def _respace(r: random.Random, t: str) -> str:
    """Every row of a table set again with other spacing, its words as they were."""
    return re.sub(r"[ \t]*&[ \t]*", lambda m: r.choice([" & ", "&", "  &  ", "\t& "]), t)


def _hard(r: random.Random) -> str:
    """A text made to be hard: lines whose words recur on every line, a table of rows alike, blank lines, in some order."""
    lines: list[str] = []
    ten = r.sample(["the", "map", "is", "a", "widget", "of", "orbit", "fixed", "point", "$x$", "and", "so"], 10)
    for _ in range(r.randint(5, 120)):
        kind = r.random()
        if kind < 0.45:
            lines.append(" ".join(r.choice(ten) for _ in range(r.randint(1, 12))) + "\n")
        elif kind < 0.75:
            lines.append(" & ".join(r.choice(["1", "0", "x", "$a$"]) for _ in range(r.randint(2, 5))) + " \\\\\n")
        elif kind < 0.9:
            lines.append("\n")
        else:
            lines.append(ten[0] + " " + ten[1] + "\n")
    return "".join(lines)


#: Edits aimed at where a faster listing could differ: recurring words, moved lines, blank lines, re-spaced tables, CRLF.
HARD_EDITS = [
    _insert_word,
    _delete_word,
    _word,
    _move_block,
    _dup_line,
    _swap_lines,
    _blank_lines,
    _respace,
    _crlf,
    _table,
    _delete_line,
]


@pytest.fixture
def by_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every range with a word in common searched by window, as a long file's costly ranges are."""
    monkeypatch.setattr(pending, "_CHEAP", 0)


def _differ(pairs: list[tuple[str, str, str]]) -> int:
    """How many `(name, old, new)` the listing and today's listing give other changes or other ids for."""
    differ = 0
    for name, old, new in pairs:
        today = pending._cut_by_difflib(old, new)
        ids = [pending.change_id(name, old[o0:o1], new[n0:n1], old[:o0]) for o0, o1, n0, n1 in today]
        if pending.cut(old, new) != today or (old and [c[0] for c in pending.cuts(name, old, new)] != ids):
            differ += 1
    return differ


def test_the_listing_is_todays_on_the_reviews_six_thousand_pairs(by_window: None) -> None:
    """The review's pairs: 3,000 edits of the fixtures' documents, one to three of its twelve kinds each, compared both ways."""
    docs = [(n, t) for n, t in _documents() if len(t) < 400_000]
    r = random.Random(20261120)
    pairs = []
    for _ in range(3000):
        name, base = r.choice(docs)
        edits = r.sample(EDITS, r.choice([1, 1, 2, 3]))
        t = base
        for e in edits:
            t = e(r, t)
        pairs += [(name, base, t), (name, t, base)]
    assert len(pairs) == 6000
    assert _differ(pairs) == 0


def test_the_listing_is_todays_on_texts_made_to_be_hard(by_window: None) -> None:
    r = random.Random(20261121)
    pairs = []
    for n in range(600):
        base = _hard(r)
        t = base
        for e in r.sample(HARD_EDITS, r.choice([1, 2, 3])):
            t = e(r, t) if t.strip() else t
        pairs += [(f"hard-{n}.tex", base, t), (f"hard-{n}.tex", t, base)]
    assert _differ(pairs) == 0


def test_an_input_the_window_search_cannot_answer_exactly_takes_todays_path(
    by_window: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two different runs of words with one window hash: the listing is today's, by today's path."""
    monkeypatch.setattr(pending, "_HASH_MOD", 7)
    took: list[int] = []
    slow = pending._cut_by_difflib
    monkeypatch.setattr(pending, "_cut_by_difflib", lambda old, new: took.append(1) or slow(old, new))
    old = "".join(f"line {i} says the map is a widget\n" for i in range(40))
    new = old.replace("line 20 says", "line 20 surely says")
    assert pending.cut(old, new) == slow(old, new)
    assert took


def test_a_long_file_with_recurring_words_is_listed_without_todays_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """One word added in the middle of 1,000 lines that repeat the same words: the costly ranges are searched by window, and the listing is today's."""
    old = "\n".join(
        "" if i % 5 == 4 else f"Line {i} of the paper says something about \\emph{{widgets}} number {i}."
        for i in range(1000)
    )
    mid = old.index("\n", len(old) // 2) + 1
    new = old[:mid] + "Surely " + old[mid:]
    searched: list[int] = []
    window = pending._longest_by_window
    monkeypatch.setattr(pending, "_longest_by_window", lambda *a: searched.append(1) or window(*a))
    (change,) = pending.cut(old, new)
    assert pending._cut_by_difflib(old, new) == [change] and "Surely" in new[change[2] : change[3]]
    assert searched


def test_the_window_hash_is_drawn_again_in_every_process() -> None:
    """A text written to collide under one process's hash collides under no other's: the base is drawn when loom starts."""
    import subprocess
    import sys

    said = {
        subprocess.run(
            [sys.executable, "-c", "from loom import pending; print(pending._HASH_BASE)"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(said) == 2 and all(int(b) >= 1 << 32 for b in said)


def _one_shape(r: random.Random) -> tuple[str, str]:
    """An edit of one shape on every line: a word renamed on lines alike, a table's rows computed again, words alternating, or lines alike with some words changed."""
    n = r.randint(2, 30)
    kind = r.choice(["rename", "table", "alternating", "alike"])
    if kind == "rename":
        old = "".join(f"a{i % r.randint(1, 5)} \\foo b{i % 3}\n" for i in range(n))
        return old, "".join(
            line.replace("\\foo", "\\bar") if r.random() < 0.9 else line for line in old.splitlines(keepends=True)
        )
    if kind == "table":
        old = "".join(f"{i}.1 & {i}.2 & {i}.3 \\\\ \\hline\n" for i in range(n))
        return old, "".join(f"{i}.7 & {i}.8 & {i}.9 \\\\ \\hline\n" for i in range(n))
    if kind == "alternating":
        return "".join("u\n" if i % 2 == 0 else "w\n" for i in range(n)), "".join(
            "w\n" if i % 2 == 0 else "z\n" for i in range(n)
        )
    words = r.sample(["the", "map", "is", "$x$", "&", "\\\\", "a", "widget"], r.randint(2, 4))
    line = " ".join(r.choice(words) for _ in range(r.randint(1, 5))) + "\n"
    old = line * n
    return old, "".join(
        " ".join(w if r.random() < 0.85 else r.choice([*words, "x"]) for w in ln.split()) + "\n"
        for ln in old.splitlines()
    )


def test_the_listing_is_todays_on_edits_of_one_shape_on_every_line(by_window: None) -> None:
    """Where every longest run is as long as the last, difflib takes them one step at a time and the listing takes them in one pass (`_runs_after`): the same changes and ids."""
    r = random.Random(20261122)
    pairs = []
    for n in range(500):
        old, new = _one_shape(r)
        pairs += [(f"shape-{n}.tex", old, new), (f"shape-{n}.tex", new, old)]
    assert _differ(pairs) == 0


def test_a_table_with_every_row_changed_is_listed_in_one_pass_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A table computed again holds `\\\\ \\hline` on every row and nothing else in common: each run after the first is taken by `_runs_after`, not searched for again, and the listing is today's."""
    old = "".join(f"{i}.1 & {i}.2 & {i}.3 \\\\ \\hline\n" for i in range(120))
    new = "".join(f"{i}.7 & {i}.8 & {i}.9 \\\\ \\hline\n" for i in range(120))
    taken: list[int] = []
    after = pending._runs_after
    monkeypatch.setattr(pending, "_runs_after", lambda *a: (taken.append(1) or x for x in after(*a)))
    assert pending.cut(old, new) == pending._cut_by_difflib(old, new)
    assert len(taken) >= 119


def _merged(blocks: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Blocks with each run that follows another directly joined to it, as difflib joins them."""
    out: list[tuple[int, int, int]] = []
    for i, j, k in blocks:
        if out and out[-1][0] + out[-1][2] == i and out[-1][1] + out[-1][2] == j:
            out[-1] = (out[-1][0], out[-1][1], out[-1][2] + k)
        elif k:
            out.append((i, j, k))
    return out


def test_the_blocks_are_difflibs_on_lists_of_few_words(by_window: None) -> None:
    """`_matching`'s blocks, not only the listing made of them, are difflib's: on word lists over one to ten words, edited, and on edits of one shape on every line, where `_runs_after` takes run after run."""
    import difflib

    r = random.Random(20261123)
    differ = 0
    for n in range(3000):
        if n % 2:
            old, new = _one_shape(r)
            a, b = old.split(), new.split()
        else:
            alphabet = [f"w{x}" for x in range(r.choice([1, 2, 3, 5, 10]))]
            a = [r.choice(alphabet) for _ in range(r.randint(0, r.choice([10, 60, 200])))]
            b = list(a)
            for _ in range(r.randint(0, 8)):
                at = r.randint(0, len(b))
                b[at:at] = [r.choice(alphabet)] if r.random() < 0.5 or not b else []
                if b and r.random() < 0.5:
                    del b[r.randrange(len(b))]
        if r.random() < 0.5:
            a, b = b, a
        want = _merged(
            [(m.a, m.b, m.size) for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()]
        )
        differ += _merged(pending._matching(a, b)) != want
    assert differ == 0
