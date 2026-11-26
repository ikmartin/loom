"""An agent's commands on the library's web (`cli/library/web.py`): what it reads, and what it writes only through the library's checks and the evidence lane's acts."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence import acts
from loom.evidence.log import replay
from loom.evidence.subjects import Who
from loom.library.digest import digest, of_work
from loom.library.node import node_bytes, node_hash
from loom.library.store import read
from tests.helpers import json_of, ok, refused
from tests.unit.library.test_digest import PDF, quilt, stub, surveyed

AGENT = "Claude Agent"
#: Lemma 1.2 of the digest tests' source, as an agent reads it there.
LEMMA = "Every widget $W$ satisfies $|x| \\le 1$."
ME = Who("person", "A. Author")


@pytest.fixture
def pdf_text(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The digest tests' PDF text, read as the stored PDF's."""
    from loom.library import survey

    pages = list(PDF)
    monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls(pages)))
    return pages


def digested(tmp_path: Path) -> tuple[Path, str]:
    """The digest tests' quilt with Smith 2024 digested whole: its root and Smith's reference."""
    result, smith = quilt(tmp_path)
    s = surveyed(result, smith)
    digest(result, smith, [i.item for i in s.items], s)
    return result.quilt.root, smith


def test_an_agent_reads_a_node_its_neighbours_a_search_and_what_a_draft_rests_on(
    tmp_path: Path, pdf_text: list[str]
) -> None:
    root, smith = digested(tmp_path)
    lemma = stub(root, smith, "1.2")
    node = json_of("library", "node", lemma, "--json", cwd=root)
    assert (node["name"], node["digested"]["how"], node["found"]) == ("Lemma 1.2", "extracted", "words")
    hits = json_of("library", "search", "widget", "satisfies", "--json", cwd=root)["hits"]
    assert lemma in [h["node"] for h in hits]
    uses = json_of("library", "uses", lemma, "--json", cwd=root)
    assert uses["uses"] == [stub(root, smith, "1.1")] and stub(root, smith, "2.1") in uses["used_by"]
    rests = json_of("library", "rests-on", "main.tex", "--json", cwd=root)["rests_on"]
    assert {r["node"] for r in rests} >= {lemma, stub(root, smith, "2.1"), stub(root, smith, "1.1")}, (
        "through what they use"
    )
    work = json_of("library", "work", smith, "--json", cwd=root)
    assert [i["item"] for i in work["outline"]["items"]][:2] == ["def:widget", "lem:bound"]
    assert json_of("library", "stubs", "--json", cwd=root)["stubs"], "the other work's stub, from a proof"


def test_an_agent_fills_a_stub_from_the_source_whose_words_stand_there(tmp_path: Path, pdf_text: list[str]) -> None:
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    refused("library", "fill", lemma, "--from", "tex", "--body", "Every gadget is unbounded.", "--as", AGENT, cwd=root, code=1, match="not all on its source")  # fmt: skip
    refused("library", "fill", lemma, "--from", "tex", "--body", LEMMA, "--as", "A. Author", cwd=root, code=2, match="not an agent's name")  # fmt: skip
    ok("library", "fill", lemma, "--from", "tex", "--body", LEMMA, "--as", AGENT, cwd=root)
    node = read(root, lemma)
    assert node is not None and node.body.startswith("Every widget")
    made = [r for r in replay(root).about("node", lemma, of="digested")]
    assert [(r.get("how"), r.by.name) for r in made] == [("read", AGENT)], "how it was made, and by whom"
    refused("library", "fill", lemma, "--from", "tex", "--body", LEMMA, "--as", AGENT, cwd=root, code=1, match="has its text already")  # fmt: skip


def test_a_correction_of_a_compared_node_waits_and_is_never_a_dependency(tmp_path: Path, pdf_text: list[str]) -> None:
    """The guard for "A proposal is never a dependency": the compared text stands, and is what anything resting on the node rests on, until the person takes the correction."""
    from loom.evidence.status import files_unchanged, status
    from loom.evidence.web import Here, LibraryWeb

    root, smith = digested(tmp_path)
    widget = stub(root, smith, "1.1")
    said = json_of("library", "correct", widget, "--body", "A \\emph{widget} is a closed set.", "--why", "closed, not compact", "--as", AGENT, "--json", cwd=root)  # fmt: skip
    assert said["outcome"] == "written", "nobody had compared it"
    node = read(root, widget)
    assert node is not None
    shown = node_hash(node_bytes(node))
    with pytest.raises(acts.ActRefused, match="only a person"):
        acts.check(root, widget, shown, Who("agent", AGENT))
    acts.check(root, widget, shown, ME)
    said = json_of("library", "correct", widget, "--body", "A \\emph{widget} is an open set.", "--why", "open", "--as", AGENT, "--json", cwd=root)  # fmt: skip
    assert said["outcome"] == "proposed"
    assert read(root, widget) == node, "the compared text stands"
    found = status(replay(root), LibraryWeb(root), Here("node", widget), lean_now=files_unchanged(root))
    assert (found.reading, found.subject.hash, bool(found.proposal)) == ("matches", shown, True)  # type: ignore[union-attr]
    refused("library", "check", widget, cwd=root, code=2, match="No such command")


def test_an_agent_has_loom_digest_a_work_and_never_compiles(
    tmp_path: Path, pdf_text: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.library import survey

    def compiled(*_a: object, **_k: object) -> None:
        raise AssertionError("an agent's call compiles nothing")

    monkeypatch.setattr(survey, "compile_marks", compiled)
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    said = json_of("library", "digest", smith, "--scope", "all", "--json", cwd=root)
    assert list(said["waiting"]) == ["lem:far"], (
        "only the result pointing at a display outside every result, which waits for the person's compile"
    )
    assert [n for n in of_work(root, smith) if not n.empty]
    ok("library", "fill", "--help", cwd=root)


def test_a_source_with_no_pdf_waits_for_the_person_s_compile(tmp_path: Path, pdf_text: list[str]) -> None:
    from loom.library.references import attach

    result, smith = quilt(tmp_path)
    root = result.quilt.root
    attach(root, smith, "pdf", None, by="A. Author", kind="person")
    refused("library", "digest", smith, cwd=root, code=1, match="an agent's call compiles nothing")


@pytest.mark.poppler
def test_a_transcription_not_on_its_pages_is_refused(tmp_path: Path) -> None:
    from loom.library.node import Node
    from loom.library.store import write_node
    from tests.unit._quilts import showcase

    root = showcase(tmp_path)
    bellamy = "sh-0403-ref"
    write_node(root, Node(id="sh-0Z01", taxon="lemma", number="2.2", source=bellamy), new=True)
    words = "Let $\\prec$ be a median order and let $u$ and $v$ be consecutive in $\\prec$, with $u$ immediately preceding $v$."
    wrong = "Every gadget tower of a median order is finite."
    refused("library", "fill", "sh-0Z01", "--pages", "1-2", "--body", wrong, "--as", AGENT, cwd=root, code=1, match="not all on its pages")  # fmt: skip
    ok("library", "fill", "sh-0Z01", "--pages", "1-2", "--body", words, "--as", AGENT, cwd=root)
    assert [r.get("how") for r in replay(root).about("node", "sh-0Z01", of="digested")] == ["transcribed"]
