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


def test_a_scan_of_its_own_forgets_nothing_a_build_made() -> None:
    """A request's scan between two builds asks for nothing a build makes from its scan (a version's marks, an agent copy's comparison): what the last build made outlives it, and the next build that does not ask for it lets it go."""
    m = Memo(str.upper, built=True)
    with reading(build=True):
        m("made by the build")
    with reading():
        pass
    assert "made by the build" in m
    with reading(build=True):
        pass
    assert "made by the build" not in m


def test_a_value_that_does_not_hold_is_handed_out_and_not_kept() -> None:
    """A rendering made while TeX failed for the machine's sake serves the build that made it, and the next asks for it again."""
    made: list[str] = []
    m: Memo[str, str] = Memo(built=True)

    def make() -> str:
        made.append("passing")
        return "passing"

    assert m.get("draft", make, lambda v: v != "passing") == "passing"
    assert "draft" not in m
    m.get("draft", make, lambda v: v != "passing")
    assert len(made) == 2


def test_a_kept_value_that_no_longer_holds_is_made_again() -> None:
    """A rendering whose files are gone from disk is made again, and kept again once they are back."""
    there = {"picture"}
    made: list[str] = []
    m: Memo[str, str] = Memo(built=True)

    def make() -> str:
        made.append("picture")
        return "picture"

    def holds(v: str) -> bool:
        return v in there

    m.get("draft", make, holds)
    m.get("draft", make, holds)
    assert len(made) == 1
    there.clear()
    m.get("draft", make, holds)
    assert len(made) == 2 and "draft" not in m
    there.add("picture")
    m.get("draft", make, holds)
    m.get("draft", make, holds)
    assert len(made) == 3 and "draft" in m


def test_a_build_empties_every_memo_when_another_process_built_since(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build in another process, a `loom build --force` in a terminal, shows as a build index this process did not write, or none: the next build here forgets all it remembers, and a build after its own forgets nothing."""
    import os
    import shutil

    import loom.render.build as building
    from loom.paths import BUILD_INDEX

    root = a_quilt(tmp_path)
    quilt = load_quilt(root)
    forgot: list[int] = []
    monkeypatch.setattr(building, "forget", lambda: forgot.append(1))
    build(quilt, tex=False)
    build(quilt, tex=False)
    assert forgot == []
    # written again whole, as another process writes it: the same bytes, a new file
    shutil.copy(root / BUILD_INDEX, root / "index.json")
    os.replace(root / "index.json", root / BUILD_INDEX)
    build(quilt, tex=False)
    assert forgot == [1]
    build(quilt, tex=False)
    assert forgot == [1]
    (root / BUILD_INDEX).unlink()
    build(quilt, tex=False)
    assert forgot == [1, 1]
