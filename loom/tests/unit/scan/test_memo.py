"""What the scanner remembers of a whole text is what the quilt now holds: a rebuild after a change lets the old text go, and one with no change makes nothing again."""

from __future__ import annotations

import gc
from pathlib import Path

import pytest

from loom.render.build import build
from loom.scan import memo, tokenize
from loom.scan.memo import Memo, reading
from loom.scan.quilt import load_quilt
from tests.unit.scan.helpers import PREAMBLE


def chapter(word: str) -> str:
    """A file long enough that its tokens and blanked text are remembered."""
    body = "".join(
        f"\\begin{{lemma}}\\label{{lem:{i}}}\nLemma {i}, about {word}: $x_{i} = \\alpha^{i}$ by \\cite{{X}}. % a comment\n\\end{{lemma}}\n\\begin{{equation}}\\label{{eq:{i}}}\ny_{i} = 1\n\\end{{equation}}\n"
        for i in range(60)
    )
    assert len(body) > tokenize.CACHED_FROM
    return f"\\section{{Long}}\n{body}"


def a_quilt(tmp_path: Path, word: str = "widgets") -> Path:
    root = tmp_path / "quilt"
    (root / "drafting").mkdir(parents=True)
    (root / "config.toml").write_text('[quilt]\nmain = "drafting/main.tex"\nprefix = "ab"\n', encoding="utf-8")
    (root / "drafting" / "main.tex").write_text(
        PREAMBLE + "\\begin{document}\n\\input{chapter}\n\\end{document}\n", encoding="utf-8"
    )
    (root / "drafting" / "chapter.tex").write_text(chapter(word), encoding="utf-8")
    return root


def remembered(text: str) -> list[Memo]:  # type: ignore[type-arg]
    """Every memo holding an entry for `text`, or for a text derived from it by blanking its comments."""
    from loom.scan.source import _blank_comments

    return [m for m in memo._memos if text in m or _blank_comments(text) in m]


def live_tokens() -> int:
    gc.collect()
    return sum(1 for o in gc.get_objects() if type(o) is tokenize.Tok)


def test_a_rebuild_after_a_change_keeps_nothing_of_the_old_text(tmp_path: Path) -> None:
    root = a_quilt(tmp_path)
    quilt = load_quilt(root)
    build(quilt, tex=False)
    old = (root / "drafting" / "chapter.tex").read_text(encoding="utf-8")
    assert remembered(old), "the long file is remembered while it is current"
    held = live_tokens()
    new = chapter("gadgets")  # one word for another: as many tokens as before
    (root / "drafting" / "chapter.tex").write_text(new, encoding="utf-8")
    build(quilt, tex=False)
    assert remembered(old) == []
    assert remembered(new)
    assert live_tokens() == held


def test_a_rebuild_with_nothing_changed_tokenizes_no_long_text_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quilt = load_quilt(a_quilt(tmp_path))
    build(quilt, tex=False)
    made: list[int] = []
    tokens = tokenize._tokenize

    def counted(text: str) -> list[tokenize.Tok]:
        if len(text) >= tokenize.CACHED_FROM:
            made.append(len(text))
        return tokens(text)

    monkeypatch.setattr(tokenize, "_tokenize", counted)
    build(quilt, tex=False)
    assert made == []


def test_a_scan_inside_a_build_from_a_held_scan_leaves_the_next_build_nothing_to_tokenize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build from `reuse` scans other texts (a pinned version, a temporary copy): those scans must not take the quilt's own entries with them."""
    from loom.render import build as built
    from loom.scan.scan import scan

    quilt = load_quilt(a_quilt(tmp_path / "served"))
    other = load_quilt(a_quilt(tmp_path / "other", "gadgets"))
    writes = built._write_source

    def and_another_scan(*args: object) -> None:
        writes(*args)  # type: ignore[arg-type]
        scan(other)

    monkeypatch.setattr(built, "_write_source", and_another_scan)
    report = build(quilt, tex=False)
    build(quilt, tex=False, reuse=report.result)
    made: list[int] = []
    tokens = tokenize._tokenize
    monkeypatch.setattr(tokenize, "_tokenize", lambda text: made.append(len(text)) or tokens(text))
    build(quilt, tex=False)
    assert [n for n in made if n >= tokenize.CACHED_FROM] == []


def test_a_scan_of_a_copy_outside_a_build_leaves_the_next_build_nothing_to_tokenize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An adoption's comparison, which a Review decision runs outside any build, scans a temporary copy; the quilt's own entries must outlive it."""
    from loom.adopt import _flat_shape

    quilt = load_quilt(a_quilt(tmp_path))
    report = build(quilt, tex=False)
    other = PREAMBLE + "\\begin{document}\n" + chapter("gadgets") + "\\end{document}\n"
    _flat_shape(report.result, other, "drafting")
    made: list[int] = []
    tokens = tokenize._tokenize
    monkeypatch.setattr(tokenize, "_tokenize", lambda text: made.append(len(text)) or tokens(text))
    build(quilt, tex=False)
    assert [n for n in made if n >= tokenize.CACHED_FROM] == []


def test_a_reading_that_outlives_an_older_one_keeps_what_the_older_one_asked_for() -> None:
    """A request's scan that begins during a rebuild and ends after it: when it ends, what the rebuild read is still there."""
    m = Memo(str.upper)
    build_reading, request_reading = reading(), reading()
    build_reading.__enter__()
    m("the build's")
    request_reading.__enter__()
    m("the request's")
    build_reading.__exit__(None, None, None)
    request_reading.__exit__(None, None, None)
    assert "the build's" in m and "the request's" in m


def test_a_keeping_reading_that_outlives_an_older_one_keeps_what_the_older_one_made() -> None:
    m = Memo(str.upper)
    build_reading, copy_reading = reading(), reading(keep=True)
    build_reading.__enter__()
    copy_reading.__enter__()
    m("made by the build while the copy was read")
    build_reading.__exit__(None, None, None)
    m("made by the copy alone")
    copy_reading.__exit__(None, None, None)
    assert "made by the build while the copy was read" in m and "made by the copy alone" not in m


def test_a_keeping_reading_lets_go_only_what_it_made() -> None:
    m = Memo(str.upper)
    m("before")
    with reading(keep=True):
        m("made inside")
        with reading():
            pass  # an inner reading forgets nothing
        assert "before" in m
    assert "before" in m and "made inside" not in m


def test_an_entry_lives_while_a_reading_asks_for_it() -> None:
    made: list[str] = []
    m = Memo(lambda text: made.append(text) or text.upper())
    with reading():
        assert m("kept") == "KEPT"
        m("dropped")
    with reading():
        with reading():
            m("kept")
        # an inner reading forgets nothing: the outer one may still ask for what came before it
        assert "dropped" in m
    assert "kept" in m and "dropped" not in m
    assert m("kept") == "KEPT" and made == ["kept", "dropped"]
    m("outside")
    assert "outside" in m
    with reading():
        pass
    assert "outside" not in m and "kept" not in m


def test_a_reading_that_ends_before_an_older_one_forgets_nothing() -> None:
    m = Memo(str.upper)
    m("before")
    older = reading()
    older.__enter__()
    with reading():
        pass
    assert "before" in m
    older.__exit__(None, None, None)
    assert "before" not in m
