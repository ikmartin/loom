"""Links in a shown Markdown file that go nowhere: `loom lint` and a build report each on the line that wrote it, read off the page the viewer draws and judged by the resolver every `quilt:` and `cited:` link answers to."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from tests.helpers import edit, json_of, ok
from tests.unit._quilts import demo, showcase

CODES = ("loom:link-target-missing", "loom:link-place-missing", "loom:link-work-unknown")
LESSON = "# Lesson\n\n## Part two\n\nSome words.\n\n{link}\n"


def _linted(q: Path) -> list[dict]:  # type: ignore[type-arg]
    return [d for d in json_of("lint", "--json", cwd=q)["diagnostics"] if d["code"] in CODES]


#: Each fault, the line that writes it, the code and class and words lint reports it with, and the same link written correctly.
FAULTS = {
    "a missing file": ("[the next lesson](lesson-3.md)", "loom:link-target-missing", "latex", "course/lesson-3.md does not exist", "[the next lesson](lesson-2.md)"),
    "a missing anchor": ("[part two](lesson-2.md#part-3)", "loom:link-place-missing", "latex", "course/lesson-2.md has no heading part-3", "[part two](lesson-2.md#part-two)"),
    "an unknown cited work": ("[the book](cited:work:deadbeef?page=4)", "loom:link-work-unknown", "model", "work:… names no work", "[the book](cited:doi:10.4171/demo/14-1?page=4)"),
}  # fmt: skip


@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_a_link_that_goes_nowhere_is_reported_on_the_line_that_wrote_it(tmp_path: Path, fault: str) -> None:
    q = demo(tmp_path)
    wrong, code, cls, words, right = FAULTS[fault]
    (q / "course").mkdir()
    (q / "course" / "lesson-2.md").write_text(LESSON.format(link="Nothing linked."), encoding="utf-8")
    (q / "course" / "lesson-1.md").write_text(LESSON.format(link=wrong), encoding="utf-8")
    (found,) = _linted(q)
    assert (found["code"], found["class"], found["severity"]) == (code, cls, "warning")
    assert found["locations"] == [{"file": "course/lesson-1.md", "line": 7}] and words in found["message"], found
    assert found["owner"] == "person"
    (q / "course" / "lesson-1.md").write_text(LESSON.format(link=right), encoding="utf-8")
    assert _linted(q) == []


def test_a_person_is_shown_a_missing_file_or_place_and_an_agent_a_work_not_held() -> None:
    """A file or a heading that is not there is something a person sees in their own text and puts right by hand, so its class is `latex`, which Problems shows; a `cited:` link naming no work the library holds is mended by an agent with `loom link`, so it is `model`."""
    from loom.scan.diagnostics import registered

    assert [(c, registered(c).cls) for c in CODES] == [  # type: ignore[union-attr]
        ("loom:link-target-missing", "latex"),
        ("loom:link-place-missing", "latex"),
        ("loom:link-work-unknown", "model"),
    ]


#: What a person reads on Problems for each kind of link that goes nowhere, after "a link goes nowhere: ": what is not there, in the file's terms, and never a command or loom's rule for writing a link.
AS_SEEN = [
    ("a relative path", "[t](lesson-9.md)", "course/lesson-9.md does not exist"),
    ("a heading of its own", "[t](#nope)", "course/case-01.md has no heading nope"),
    ("a relative path to a heading", "[t](lesson-2.md#nope)", "course/lesson-2.md has no heading nope"),
    ("a quilt: link to a file", "[t](quilt:course/lesson-9.md)", "course/lesson-9.md does not exist"),
    ("a quilt: link to a heading", "[t](quilt:course/lesson-2.md#nope)", "course/lesson-2.md has no heading nope"),
    ("a quilt: link to a key", "[](quilt:dm-9999)", "nothing in the quilt is named dm-9999"),
    ("a quilt: link to a key in a result", "[](quilt:dm-0003#dm-9999)", "nothing in the quilt is named dm-9999"),
    ("an image", "![f](plot.png)", "course/plot.png does not exist"),
    ("an href in raw HTML", '<a href="lesson-2.md#nope">t</a>', "course/lesson-2.md has no heading nope"),
    ("a src in raw HTML", '<img src="plot.png">', "course/plot.png does not exist"),
    ("a hidden file", "[t](../.hidden.md)", ".hidden.md is hidden from the viewer"),
    ("a folder", "[t](sub)", "course/sub is a folder, which the viewer does not open"),
    ("a path out of the quilt", "[t](../../outside.md)", "../../outside.md leads out of the quilt"),
    ("a LaTeX file by its path", "[t](../drafting/nodes/dm-0001.tex)", "drafting/nodes/dm-0001.tex is a LaTeX file, which the viewer does not open by its path"),
    ("a quilt: link to a LaTeX file", "[t](quilt:drafting/nodes/dm-0001.tex)", "drafting/nodes/dm-0001.tex is a LaTeX file, which the viewer does not open by its path"),
    ("a line past a text file's end", "[t](notes.txt#L9)", "course/notes.txt has 2 lines"),
    ("a place in a text file", "[t](notes.txt#top)", "course/notes.txt has no place top"),
    ("a place in a PDF", "[t](book.pdf#p3)", "course/book.pdf has no place p3"),
    ("a place in the research state", "[](quilt:state#goals)", "the research state has no place goals"),
    ("a page of a cited work", "[](cited:doi:10.4171/demo/14-1?page=0)", "there is no page 0"),
    ("a quilt: link naming nothing", "[t](quilt:#nope)", "it names nothing"),
]  # fmt: skip


def test_what_a_person_is_shown_says_what_is_not_there(tmp_path: Path) -> None:
    q = demo(tmp_path)
    course = q / "course"
    (course / "sub").mkdir(parents=True)
    (course / "lesson-2.md").write_text("# Lesson 2\n", encoding="utf-8")
    (course / "notes.txt").write_text("one\ntwo", encoding="utf-8")
    (course / "book.pdf").write_bytes(b"%PDF-1.4\n")
    (q / ".hidden.md").write_text("hidden\n", encoding="utf-8")
    for n, (_, link, _) in enumerate(AS_SEEN):
        (course / f"case-{n:02d}.md").write_text(f"# Case\n\n{link}\n", encoding="utf-8")
    shown = {d["locations"][0]["file"]: d for d in _linted(q)}
    said = []
    for n, (what, _, _words) in enumerate(AS_SEEN):
        d = shown.get(f"course/case-{n:02d}.md")
        assert d is not None and d["class"] == "latex", what
        said.append((what, d["message"]))
    assert said == [(what, f"a link goes nowhere: {words}") for what, _, words in AS_SEEN]
    assert not any("loom " in m or " key" in m or "id is made" in m for _, m in said)


def test_lint_disable_silences_a_link_code(tmp_path: Path) -> None:
    q = demo(tmp_path)
    (q / "lesson.md").write_text(LESSON.format(link="[gone](gone.md)"), encoding="utf-8")
    assert len(_linted(q)) == 1
    edit(q / "config.toml", "disable = []", 'disable = ["loom:link-target-missing"]')
    assert _linted(q) == []


#: Awkward links, each written alone on line 5 of a file of its own in `notes/`, with whether the page reaches what it names; None where the page draws no link at all (code) or hands it to the browser (another site).
AWKWARD = [
    ("up and down", "[t](../notes/sub/target.md#two-words)", True),
    ("down through a dot", "[t](./sub/target.md)", True),
    ("out of the quilt", "[t](../../elsewhere.md)", False),
    ("an anchor with spaces", "[t](<sub/target.md#Two Words>)", False),
    ("an anchor with capitals", "[t](sub/target.md#Two-Words)", False),
    ("an anchor in other than ASCII", "[t](sub/target.md#größe)", True),
    ("a heading of its own", "[t](#case)", True),
    ("a heading of its own with a capital", "[t](#Case)", False),
    ("a LaTeX result", "[](quilt:dm-0003)", True),
    ("a LaTeX result that is not there", "[](quilt:dm-9999)", False),
    ("a document by its path", "[t](../drafting/main.tex)", True),
    ("a line of a text file", "[t](run.py#L2)", True),
    ("a line past a text file's end", "[t](run.py#L99)", False),
    ("an image", "![f](sub/figure.png)", True),
    ("an image that is not there", "![f](sub/plot.png)", False),
    ("a link in raw HTML", '<a href="sub/target.md#nope">t</a>', False),
    ("a cited work", "[](cited:doi:10.4171/demo/14-1?page=2)", True),
    ("a cited work the library does not hold", "[](cited:doi:10.0/nobody)", False),
    ("an external address", "[t](https://example.org/x#Nope)", None),
    ("a link in a code block", "```\n[t](missing.md)\n```", None),
    ("a link in inline code", "`[t](missing.md)`", None),
    ("a link in mathematics", "$[t](missing.md)$", None),
]


def _ids(body: str) -> set[str]:
    return set(re.findall(r'\sid="([^"]+)"', body))


def _viewer_reaches(m: dict, site: Path, path: str, href: str) -> bool | None:  # type: ignore[type-arg]
    """Whether the viewer reaches what `href`, as drawn on the page of `path`, names, worked out from the published manifest and pages alone; None for another site's address, which the browser opens."""
    from loom.library.entries import matchable
    from loom.library.intake import Library

    files = {f["path"]: f for f in m["files"]}

    def page(p: str) -> str:
        return (site / files[p]["body"]).read_text(encoding="utf-8")

    if href.startswith("/_files/"):
        return unquote(href[len("/_files/") :]) in files
    if href.startswith("#"):
        return unquote(href[1:]) in _ids(page(path))
    if href.startswith("quilt:"):
        key, _, place = href[len("quilt:") :].partition("#")
        key, place = unquote(key), unquote(place)
        f = files.get(key)
        if f is not None and f["kind"] == "document" or key in m["nodes"]:
            return not place
        if f is None:
            return False
        if not place:
            return True
        if f["kind"] == "markdown":
            return place in _ids(page(key))
        lines = (site.parents[2] / key).read_text(encoding="utf-8").split("\n")
        return f["kind"] == "text" and re.fullmatch(r"L(\d+)", place) is not None and int(place[1:]) <= len(lines)
    if href.startswith("cited:"):
        wanted = href[len("cited:") :].split("?", 1)[0]
        return bool(Library.read(site.parents[2]).stating([matchable(wanted)]))
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href):
        return None
    return False  # a relative address the page left as written: the viewer finds no item for it


def test_lint_and_the_page_agree_on_what_each_awkward_link_reaches(tmp_path: Path) -> None:
    q = demo(tmp_path)
    notes = q / "notes"
    (notes / "sub").mkdir(parents=True)
    (notes / "sub" / "target.md").write_text("# Target\n\n## Two Words\n\n## Größe\n", encoding="utf-8")
    (notes / "sub" / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (notes / "run.py").write_text("x = 1\nprint(x)\n", encoding="utf-8")
    cases = {f"notes/case-{n:02d}.md": case for n, case in enumerate(AWKWARD)}
    for path, (_, link, _) in cases.items():
        (q / path).write_text(f"# Case\n\nOne link.\n\n{link}\n", encoding="utf-8")
    ok("build", cwd=q)
    site = q / ".loom/cache/site"
    m = json.loads((site / "manifest.json").read_text(encoding="utf-8"))
    built = {(d["locations"][0]["file"], d["locations"][0]["line"]) for d in m["diagnostics"] if d["code"] in CODES}
    linted = {(d["locations"][0]["file"], d["locations"][0]["line"]) for d in _linted(q)}
    assert built == linted
    files = {f["path"]: f for f in m["files"]}
    wrong = []
    for path, (what, _, expected) in cases.items():
        body = (site / files[path]["body"]).read_text(encoding="utf-8")
        drawn = [html.unescape(h) for h in re.findall(r'<(?:a href|img src)="([^"]*)"', body)]
        reached = _viewer_reaches(m, site, path, drawn[0]) if drawn else None
        said = (path, 5) in linted
        if reached != expected or said != (expected is False):
            wrong.append(
                f"{what}: the page draws {drawn} and reaches {reached}; lint {'reports' if said else 'says nothing'}"
            )
    assert wrong == []
    assert {f for f, _ in linted} <= set(cases)  # nothing else in the demo goes nowhere


def test_the_research_state_has_a_row_for_a_result_gone_since_it_was_written(tmp_path: Path) -> None:
    """The author's queue, item 20: a page listed a link whose result is gone among its broken links and no diagnostic said so; lint now says it where the page does."""
    q = showcase(tmp_path)
    node = q / "drafting" / "nodes" / "sh-0009.tex"
    node.write_text(node.read_text().replace("{theorem}", "{undeclared}"))
    ok("build", cwd=q)
    m = json.loads((q / ".loom/cache/site" / "manifest.json").read_text())
    assert [b["href"] for b in m["research_state"]["links"]["broken"]] == ["quilt:sh-0009"]
    rows = [d for d in m["diagnostics"] if d["code"] in CODES]
    assert [(d["code"], d["locations"][0]["file"]) for d in rows] == [("loom:link-target-missing", "research-state.md")]
    assert "sh-0009 was a result when the page was written, and is gone" in rows[0]["message"]
    edit(q / "research-state.md", "[](quilt:sh-000C)", "[](quilt:sh-9999)")
    assert sorted(d["message"].split(": ", 1)[1] for d in _linted(q)) == [
        "nothing in the quilt is named sh-9999",
        "sh-0009 was a result when the page was written, and is gone",
    ]
