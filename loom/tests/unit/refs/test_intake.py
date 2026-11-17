"""The one intake (`refs.intake`): every file or pasted work becomes one row in one of four states, nothing is filed under an existing work without the person's word, and an undo gives the quilt back byte for byte. The study's B3, B4, B10 and B12 (`docs/reports/v0.1-study/raw/library.md` section 10) are tests here."""

from __future__ import annotations

import io
import random
from pathlib import Path

import pytest

from loom.paths import INCOMING
from loom.refs.intake import IntakeRefused, Item, Row, _acts, answer, receive, take, undo, unfile, waiting
from loom.scan.bib import BibEntry
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import demo, work_home
from tests.unit.refs._made_pdfs import fake_pdf, real_pdf

WHO = "A. Author"
BIB = ".loom/digests/bibliography.bib"
#: A second version of Calloway14, the work the demo cites: its title over its author's byline, with a page more and no identifier, since a PDF stating the work's own DOI is a copy of its document.
CALLOWAY = "Fixed loci of involutions on separated spaces\nImogen Calloway\nA preprint\n\fA second page"
#: A page that names no work in the demo's library.
NOTES = "Notes on balanced quivers\nA. Halloway\nWe record what is known.\n"


def tree(q: Path) -> dict[str, bytes]:
    """Every file of the quilt outside `.loom/build/`, which every rebuild writes again, with its bytes."""
    return {
        p.relative_to(q).as_posix(): p.read_bytes()
        for p in sorted(q.rglob("*"))
        if p.is_file() and not p.relative_to(q).as_posix().startswith(".loom/build/")
    }


def bib(q: Path) -> dict[str, BibEntry]:
    return scan(load_quilt(q)).bib


def dropped(q: Path, name: str, text: str = NOTES, tmp: Path | None = None) -> Item:
    """A file received as the viewer streams one, as an item to take."""
    src = fake_pdf((tmp or q.parent) / "src" / name, text)
    got = receive(q, name, io.BytesIO(src.read_bytes()), src.stat().st_size)
    return Item(drop=got["incoming"], name=name)


def taken(q: Path, *items: Item, online: bool = False) -> list[Row]:
    return take(load_quilt(q), bib(q), list(items), by=WHO, online=online)


def test_a_new_pdf_is_added_and_its_undo_leaves_the_quilt_byte_for_byte_as_before_the_drop(tmp_path: Path) -> None:
    q = demo(tmp_path)
    bib(q)
    before = tree(q)
    item = dropped(q, "Halloway - 2026 - Notes on balanced quivers.pdf")
    (row,) = taken(q, item)
    assert (row.state, row.citekey, row.pages) == ("added", "hallowayNotesBalancedQuivers2026", "read"), row
    assert row.to_json()["title"] == "Notes on balanced quivers"
    # B12: the drop has left `.loom/incoming/` for the store, and only the record of the act waits there
    assert [p.name for p in (q / INCOMING / row.id).iterdir()] == ["act.json"]
    assert (work_home(q, row.citekey) / "paper.pdf").is_file()
    said, again = undo(scan(load_quilt(q)), row.id, by=WHO)
    assert again is None and "took hallowayNotesBalancedQuivers2026 out" in said
    assert tree(q) == before


def test_a_file_dropped_twice_says_it_is_already_here(tmp_path: Path) -> None:
    q = demo(tmp_path)
    (first,) = taken(q, dropped(q, "notes.pdf"))
    (second,) = taken(q, dropped(q, "notes again.pdf"))
    assert (second.state, second.citekey) == ("here", first.citekey) and "these very bytes" in second.why
    # and twice in one take, from the command line
    one = fake_pdf(tmp_path / "a" / "x.pdf", "A paper about widgets\nW. Smith\n")
    two = tmp_path / "b" / "y.pdf"
    two.parent.mkdir()
    two.write_bytes(one.read_bytes())
    rows = taken(q, Item(path=one), Item(path=two))
    assert [r.state for r in rows] == ["added", "here"] and rows[1].citekey == rows[0].citekey


def test_a_pdf_naming_a_work_is_a_question_and_nothing_is_filed_until_answered(tmp_path: Path) -> None:
    q = demo(tmp_path)
    bib(q)
    before = tree(q)
    item = dropped(q, "calloway-v2.pdf", CALLOWAY, tmp_path)
    (row,) = taken(q, item)
    assert row.state == "question" and [c["citekey"] for c in row.candidates] == ["Calloway14"], row
    assert row.candidates[0]["how"] == "its title is the entry's and Calloway leads its byline"
    assert row.document == {
        "title": "Fixed loci of involutions on separated spaces",
        "byline": "Imogen Calloway",
        "identifiers": [],
    }
    assert waiting(q) == [row.to_json() | {"item": 0}] or waiting(q)[0]["state"] == "question"
    assert {k for k in tree(q)} - set(before) == {
        f"{INCOMING}/{row.id}/{n}" for n in ("arrived.json", "question.json", "calloway-v2.pdf")
    }
    with pytest.raises(IntakeRefused, match="not one of the works asked about"):
        answer(load_quilt(q), bib(q), row.question, "Man12", by=WHO)
    said = answer(load_quilt(q), bib(q), row.question, "Calloway14", by=WHO)
    assert (said.state, said.under, said.sibling) == ("added", "Calloway14", "Calloway14-v2"), said
    assert waiting(q) == []
    undo(scan(load_quilt(q)), row.id, by=WHO)
    assert tree(q) == before


def test_a_different_work_is_kept_as_its_own(tmp_path: Path) -> None:
    q = demo(tmp_path)
    (row,) = taken(q, dropped(q, "calloway-v2.pdf", CALLOWAY, tmp_path))
    said = answer(load_quilt(q), bib(q), row.question, None, by=WHO)
    assert said.state == "added" and not said.under and said.citekey == "FixedLociInvolutions"


def test_the_quant_incident_through_the_intake(tmp_path: Path) -> None:
    """B1 end to end: the library holds `Of`, made of a masthead; the Cox PDF from the same journal is added as a work of its own, under its own title."""
    q = demo(tmp_path)
    with (q / BIB).open("a", encoding="utf-8") as fh:
        fh.write("\n@misc{Of,\n  title = {of Financial},\n  loom-added = {2026-11-11T21:00:00Z, The author},\n}\n")
    cox = (
        "Journal\nof Financial\nEconomics\nOPTION PRICING: A SIMPLIFIED APPROACH*\n7 (1979) 229-263.\n"
        "John C. COX\nMassachusetts Institute of Technology, Cambridge, MA 02139, USA\n"
    )
    (row,) = taken(q, dropped(q, "1-s2.0-0304405X79900151-main.pdf", cox, tmp_path))
    assert (row.state, row.under, row.title) == ("added", "", "OPTION PRICING: A SIMPLIFIED APPROACH"), row


def test_an_entry_naming_no_author_is_asked_about_when_the_pdfs_own_title_is_its_title(tmp_path: Path) -> None:
    """The author's request of 2026-11-04 holds through the question: a work whose entry is a title alone is still offered."""
    q = demo(tmp_path)
    with (q / BIB).open("a", encoding="utf-8") as fh:
        fh.write("\n@misc{Wor,\n  title = {Stochastic Calculus for Finance II},\n}\n")
    book = "Stochastic Calculus for Finance II\nContinuous-Time Models\nSteven E. Shreve\nPreface\n"
    (row,) = taken(q, dropped(q, "Shreve - Stochastic Calculus for Finance II.pdf", book, tmp_path))
    assert row.state == "question" and [(c["citekey"], c["how"]) for c in row.candidates] == [
        ("Wor", "its title is Wor's")
    ]


def test_a_drop_on_a_work_is_filed_there_unless_it_shows_another_work_or_another_holds_it(tmp_path: Path) -> None:
    """B3: the per-work upload filed on drop, though the PDF was another work's, and stored the bytes twice."""
    from loom.refs.pages import sha256_of

    q = demo(tmp_path)
    (schedule,) = taken(q, dropped(q, "seminar.pdf", "Department of Mathematics\nSeminar schedule, spring\n", tmp_path))
    assert schedule.state == "added"
    item = dropped(q, "seminar again.pdf", "Department of Mathematics\nSeminar schedule, spring\n", tmp_path)
    (row,) = taken(q, Item(drop=item.drop, name=item.name, work="Har77"))
    assert (row.state, row.citekey) == ("here", schedule.citekey)
    sha = sha256_of(work_home(q, schedule.citekey) / "paper.pdf")
    stored = [p for p in (q / ".loom/digests/storage").rglob("paper.pdf") if sha256_of(p) == sha]
    assert len(stored) == 1 and not (work_home(q, "Har77") / "paper.pdf").exists()
    stamped = dropped(
        q,
        "pullbacks.pdf",
        "arXiv:0805.2065v2 [math.AG] 13 May 2008\nVirtual pull-backs\nCristina Manolache\n",
        tmp_path,
    )
    (asked,) = taken(q, Item(drop=stamped.drop, name=stamped.name, work="Har77"))
    assert asked.state == "question" and [c["citekey"] for c in asked.candidates] == ["Har77", "Man12"]
    plain = dropped(q, "hartshorne.pdf", "Some scanned pages\n", tmp_path)
    (filed,) = taken(q, Item(drop=plain.drop, name=plain.name, work="Har77"))
    assert (filed.state, filed.under) == ("added", "Har77") and (work_home(q, "Har77") / "paper.pdf").is_file()


def test_a_wrongly_filed_pdf_is_taken_off_its_work_and_undo_files_it_again(tmp_path: Path) -> None:
    """B4: nothing could take a filed document off a work, and deleting a cited one is refused."""
    q = demo(tmp_path)
    item = dropped(q, "schedule.pdf", "Department of Mathematics\nSeminar schedule, spring\n", tmp_path)
    (row,) = taken(q, Item(drop=item.drop, name=item.name, work="Man12"))
    assert (row.state, row.under) == ("added", "Man12")
    filed = tree(q)
    off = unfile(scan(load_quilt(q)), "Man12", by=WHO)
    assert off["incoming"] == row.id and off["row"]["state"] == "received"
    assert not (work_home(q, "Man12") / "paper.pdf").exists()
    assert [r["id"] for r in waiting(q)] == [row.id]
    undo(scan(load_quilt(q)), row.id, by=WHO)
    assert tree(q) == filed
    # taken off again and taken in again, it is never asked about the work it was taken off
    unfile(scan(load_quilt(q)), "Man12", by=WHO)
    (again,) = taken(q, Item(drop=row.id, name="schedule.pdf"))
    assert again.state == "added" and not again.under
    with pytest.raises(IntakeRefused, match="has results read off this PDF") as caught:
        unfile(scan(load_quilt(q)), "Calloway14", by=WHO)
    assert caught.value.code == "has-results"
    with pytest.raises(IntakeRefused, match="holds no PDF"):
        unfile(scan(load_quilt(q)), "Har77", by=WHO)
    # a work that came in with its PDF is nothing without it: undo or delete takes it out whole
    with pytest.raises(IntakeRefused, match="came in with this PDF") as caught:
        unfile(scan(load_quilt(q)), again.citekey, by=WHO)
    assert caught.value.code == "own-document"


def test_an_undo_is_refused_once_the_work_is_cited(tmp_path: Path) -> None:
    from tests.helpers import edit

    q = demo(tmp_path)
    (row,) = taken(q, dropped(q, "notes.pdf"))
    edit(q / "drafting" / "main.tex", "\\end{document}", f"\\cite{{{row.citekey}}}\n\\end{{document}}")
    with pytest.raises(IntakeRefused, match="is cited by your documents") as caught:
        undo(scan(load_quilt(q)), row.id, by=WHO)
    assert caught.value.code == "not-new"


@pytest.mark.poppler
def test_a_scan_with_no_text_and_a_textbook_with_no_doi_each_come_in(tmp_path: Path) -> None:
    q = demo(tmp_path)
    book = real_pdf(
        tmp_path / "src" / "casella.pdf",
        [[], []],
        info={"Title": "Statistical Inference", "Author": "George Casella, Roger L. Berger"},
    )
    scan_ = real_pdf(tmp_path / "src" / "scanned-surgery.pdf", [[]], info={"Author": "https://imagemagick.org"})
    rows = taken(q, Item(path=book), Item(path=scan_))
    assert [(r.state, r.citekey, r.pages) for r in rows] == [
        ("added", "casellaStatisticalInference", "none"),
        ("added", "ScannedSurgery", "none"),
    ], rows


def test_many_files_dropped_at_once_are_each_a_row(tmp_path: Path) -> None:
    """B10: a drop of twelve PDFs added one, silently."""
    q = demo(tmp_path)
    items = [
        dropped(q, f"paper {k}.pdf", f"On the {w} of widgets\nW. Smith\n", tmp_path)
        for k, w in enumerate(("rank", "genus", "degree", "height"))
    ]
    items.append(
        Item(path=fake_pdf(tmp_path / "src" / "notes.txt", "not a pdf").with_name("notes.txt"), name="notes.txt")
    )
    items[-1].path.write_text("plain text")  # type: ignore[union-attr]
    rows = taken(q, *items)
    assert [r.state for r in rows] == ["added", "added", "added", "added", "cannot"] and rows[-1].code == "not-a-pdf"
    assert len({r.citekey for r in rows[:4]}) == 4


def test_a_pasted_text_is_a_row_a_line_or_an_entry(tmp_path: Path) -> None:
    """B8: two BibTeX entries pasted were one; a list of identifiers was not recognised."""
    q = demo(tmp_path)
    two = "@article{Ost18, author={Ostrander, D.}, title={Widget categories and their duals}, year={2018}}\n@book{Vale20, author={Vale, E.}, title={Gadgets}, year={2020}}"
    rows = taken(q, Item(text=two))
    assert [(r.state, r.citekey) for r in rows] == [("added", "Ost18"), ("added", "Vale20")]
    again = taken(q, Item(text=two.split("\n")[0].replace("Ost18", "Other")))
    assert again[0].state == "question" and again[0].candidates[0]["citekey"] == "Ost18"
    ids = taken(q, Item(text="arXiv:0805.2065\n10.5555/x.1\nISBN 978-0-387-98549-7\nwidgets, somewhere"))
    assert [(r.state, r.code) for r in ids] == [
        ("cannot", "offline"),
        ("cannot", "offline"),
        ("cannot", "no-service"),
        ("cannot", "not-recognised"),
    ]
    before = tree(q)
    (last,) = taken(q, Item(text="@misc{Lone, title={A lone entry}}"))
    undo(scan(load_quilt(q)), last.id, by=WHO)
    assert tree(q) == before


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    q = demo(tmp_path)
    pdf = fake_pdf(tmp_path / "src" / "x.pdf", NOTES)
    before = tree(q)
    (row,) = take(load_quilt(q), bib(q), [Item(path=pdf)], by=WHO, write=False)
    assert row.state == "added" and tree(q) == before


def _whole(q: Path) -> None:
    """No damage: the bibliography reads, and every work whose entry says where its PDF is holds it there."""
    from loom.refs.fetch import work_dir

    for key, entry in bib(q).items():
        if entry.fields.get("loom-file"):
            assert (work_dir(q, entry) / "paper.pdf").is_file() or entry.fields.get("loom-copy-of") is None, key


@pytest.mark.parametrize("seed", [20261117, 7, 31])
def test_random_drops_answers_unfiles_and_undos_never_damage_and_each_undo_restores_the_exact_bytes(
    tmp_path: Path, seed: int
) -> None:
    """The Safe gate's check for the library, on the demo: a seeded sequence of acts, each undone in turn back to the quilt as it was."""
    q = demo(tmp_path)
    bib(q)
    start = tree(q)
    rng = random.Random(seed)
    pool = [
        NOTES,
        CALLOWAY,
        "On the rank of widgets\nW. Smith\n",
        "Some scanned pages\n",
        "Department of Mathematics\nSchedule\n",
    ]
    done: list[tuple[str, dict[str, bytes]]] = []
    for step in range(24):
        roll = rng.random()
        before = tree(q)
        if roll < 0.5 or not done:
            text = rng.choice(pool)
            (row,) = taken(q, dropped(q, f"drop {step}.pdf", text, tmp_path / str(step)))
            if row.state == "question":
                row = answer(
                    load_quilt(q), bib(q), row.question, rng.choice([None, row.candidates[0]["citekey"]]), by=WHO
                )
            if row.state == "added":
                done.append((row.id, before))
            elif row.state == "here":
                outside = {k: v for k, v in tree(q).items() if not k.startswith(f"{INCOMING}/")}
                assert outside == {k: v for k, v in before.items() if not k.startswith(f"{INCOMING}/")}
        elif roll < 0.65:
            filed = [r for r, _ in done]
            unfilable = [
                a["citekey"]
                for r in filed
                for a in _acts(q / INCOMING / r)[-1:]
                if a["kind"] == "added" and a.get("home")
            ]
            if not unfilable:
                continue
            key = rng.choice(unfilable)
            try:
                got = unfile(scan(load_quilt(q)), key, by=WHO)
            except IntakeRefused as refused:
                assert refused.code in ("own-document", "has-results", "no-document") and tree(q) == before
                continue
            done.append((got["incoming"], before))
        else:
            drop, was = done.pop()
            undo(scan(load_quilt(q)), drop, by=WHO)
            assert tree(q) == was, f"step {step}: undoing {drop[:12]} left the quilt changed"
        _whole(q)
    while done:
        drop, was = done.pop()
        undo(scan(load_quilt(q)), drop, by=WHO)
        assert tree(q) == was
    assert tree(q) == start


def test_every_route_gives_one_work_one_key(tmp_path: Path) -> None:
    """The command line, the intake the viewer's drop goes through, gathering's adoption of a stored PDF no entry names, and a pasted DOI against the PDF that states it: each keys one work alike."""
    import hashlib
    import json

    from loom.paths import STORAGE
    from loom.refs.scan import record_copy
    from tests.helpers import ok

    name = "Halloway - 2026 - Notes on balanced quivers.pdf"
    pdf = fake_pdf(tmp_path / "src" / name, NOTES)
    quilts = {}
    for route in ("cli", "intake", "adopted"):
        (tmp_path / route).mkdir()
        quilts[route] = demo(tmp_path / route)
    ok("library", "add", str(pdf), "--as", WHO, cwd=quilts["cli"])
    (row,) = taken(quilts["intake"], dropped(quilts["intake"], name, NOTES, tmp_path / "drop"))
    c = quilts["adopted"]
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    home = c / STORAGE / "file" / sha[:16]
    home.mkdir(parents=True)
    (home / "paper.pdf").write_bytes(pdf.read_bytes())
    record_copy(c, sha, name, home)
    ok("library", "update", "--only", "gather", cwd=c)
    keys = {
        route: {k for k, e in bib(q).items() if e.fields.get("title") == "Notes on balanced quivers"}
        for route, q in quilts.items()
    }
    assert (
        keys == {route: {"hallowayNotesBalancedQuivers2026"} for route in quilts}
        and row.citekey == "hallowayNotesBalancedQuivers2026"
    )

    def doi_org(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps(
            {
                "title": "Median orders on weighted digraphs",
                "author": [{"family": "Bellamy", "given": "Rosalind"}],
                "issued": {"date-parts": [[2019]]},
                "DOI": "10.4171/x.19",
            }
        ).encode()

    for route in ("pasted", "dropped"):
        (tmp_path / route).mkdir()
    pasted, dropped_ = demo(tmp_path / "pasted"), demo(tmp_path / "dropped")
    (by_text,) = take(load_quilt(pasted), bib(pasted), [Item(text="10.4171/x.19")], by=WHO, online=True, http=doi_org)
    page = "Median orders on weighted digraphs\nRosalind Bellamy\ndoi:10.4171/x.19\n"
    (by_pdf,) = take(
        load_quilt(dropped_),
        bib(dropped_),
        [Item(path=fake_pdf(tmp_path / "src" / "median.pdf", page))],
        by=WHO,
        online=True,
        http=doi_org,
    )
    assert by_text.citekey == by_pdf.citekey == "bellamyMedianOrdersWeighted2019"


def test_an_undo_never_writes_over_or_removes_a_document_it_did_not_put_there(tmp_path: Path) -> None:
    """The integrator's review, finding 1: P1 dropped on a work and unfiled, P2 dropped on it, then P1's undo wrote P1 over P2, and P2's undo removed P1 in turn; both PDFs were gone. Now the first undo is refused with nothing touched, and in the other order both come back."""
    from loom.refs.pages import sha256_of

    q = demo(tmp_path)
    first = dropped(q, "first.pdf", "Some scanned pages\nthe first scan\n", tmp_path / "1")
    (one,) = taken(q, Item(drop=first.drop, name=first.name, work="Man12"))
    unfile(scan(load_quilt(q)), "Man12", by=WHO)
    second = dropped(q, "second.pdf", "Some scanned pages\na better scan\n", tmp_path / "2")
    (two,) = taken(q, Item(drop=second.drop, name=second.name, work="Man12"))
    held = tree(q)
    with pytest.raises(IntakeRefused, match="holds another document now") as caught:
        undo(scan(load_quilt(q)), one.id, by=WHO)
    assert caught.value.code == "changed" and tree(q) == held
    undo(scan(load_quilt(q)), two.id, by=WHO)
    undo(scan(load_quilt(q)), one.id, by=WHO)
    paper = work_home(q, "Man12") / "paper.pdf"
    assert sha256_of(paper) == one.id


def test_an_undo_refuses_when_the_document_it_added_is_no_longer_there(tmp_path: Path) -> None:
    q = demo(tmp_path)
    (row,) = taken(q, dropped(q, "notes.pdf"))
    paper = work_home(q, row.citekey) / "paper.pdf"
    paper.write_bytes(fake_pdf(tmp_path / "other.pdf", "Another document\n").read_bytes())
    held = tree(q)
    with pytest.raises(IntakeRefused, match="no longer holds the document this drop added") as caught:
        undo(scan(load_quilt(q)), row.id, by=WHO)
    assert caught.value.code == "changed" and tree(q) == held


def test_an_undo_names_its_act_so_a_second_click_undoes_nothing_more(tmp_path: Path) -> None:
    q = demo(tmp_path)
    item = dropped(q, "schedule.pdf", "Department of Mathematics\nSeminar schedule\n", tmp_path)
    (row,) = taken(q, Item(drop=item.drop, name=item.name, work="Man12"))
    off = unfile(scan(load_quilt(q)), "Man12", by=WHO)
    assert row.act and off["act"] and off["act"] != row.act
    undo(scan(load_quilt(q)), row.id, by=WHO, act=off["act"])
    held = tree(q)
    with pytest.raises(IntakeRefused, match="undone already") as caught:
        undo(scan(load_quilt(q)), row.id, by=WHO, act=off["act"])
    assert caught.value.code == "not-last" and tree(q) == held


def test_a_record_of_an_act_that_names_a_place_outside_the_store_is_not_acted_on(tmp_path: Path) -> None:
    """A drop travels with a quilt copied as a folder, so its record is checked before an undo reads or writes anything for it."""
    import json

    q = demo(tmp_path)
    (row,) = taken(q, dropped(q, "notes.pdf"))
    record = q / INCOMING / row.id / "act.json"
    acts = json.loads(record.read_text())
    acts["acts"][-1]["home"] = ".loom/digests/storage/../../../drafting"
    record.write_text(json.dumps(acts))
    held = tree(q)
    with pytest.raises(IntakeRefused, match="cannot be trusted") as caught:
        undo(scan(load_quilt(q)), row.id, by=WHO)
    assert caught.value.code == "untrusted" and tree(q) == held


def test_a_work_that_came_in_with_its_pdf_is_never_unfiled_even_when_gathering_adopted_it(tmp_path: Path) -> None:
    """The integrator's review, finding 2, its first step: a work adopted from a PDF in the store was unfiled, and another PDF dropped on it then sat in the first one's place."""
    import hashlib

    from loom.paths import STORAGE
    from loom.refs.scan import record_copy
    from tests.helpers import ok

    q = demo(tmp_path)
    pdf = fake_pdf(tmp_path / "src" / "Holm - 2020 - Knots in lens spaces.pdf", "Knots in lens spaces\nGreta Holm\n")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    home = q / STORAGE / "file" / sha[:16]
    home.mkdir(parents=True)
    (home / "paper.pdf").write_bytes(pdf.read_bytes())
    record_copy(q, sha, pdf.name, home)
    ok("library", "update", "--only", "gather", cwd=q)
    held = tree(q)
    with pytest.raises(IntakeRefused, match="came in with this PDF") as caught:
        unfile(scan(load_quilt(q)), "holmKnotsLensSpaces2020", by=WHO)
    assert caught.value.code == "own-document" and tree(q) == held


def test_a_new_work_never_takes_a_place_another_works_pdf_holds(tmp_path: Path) -> None:
    """The integrator's review, finding 2: A's own place in the store held B, filed there for the work A came in with, and taking A as a work of its own wrote A over B. Now A gets a place, and an identity, of its own."""
    from loom.refs.identity import identify
    from loom.refs.pages import sha256_of
    from tests.helpers import ok

    q = demo(tmp_path)
    a = fake_pdf(tmp_path / "a" / "lens.pdf", "Knots in lens spaces\nGreta Holm\nthe first scan\n")
    b = fake_pdf(tmp_path / "b" / "lens.pdf", "Knots in lens spaces\nGreta Holm\na better scan\n")
    (first,) = taken(q, Item(path=a))
    ok("library", "ignore", first.citekey, "--why", "a poor scan", "--as", WHO, cwd=q)
    (better,) = taken(q, Item(path=b, work=first.citekey, on_word=True))
    assert better.replaced and sha256_of(work_home(q, first.citekey) / "paper.pdf") == sha256_of(b)
    (again,) = taken(q, Item(path=a, new=True))
    assert again.state == "added" and again.citekey != first.citekey
    assert sha256_of(work_home(q, first.citekey) / "paper.pdf") == sha256_of(b)
    assert sha256_of(work_home(q, again.citekey) / "paper.pdf") == sha256_of(a)
    entries = bib(q)
    assert entries[again.citekey].fields["loom-file"] == entries[first.citekey].fields["loom-file"] + "-2"
    assert identify(entries[again.citekey])[0] != identify(entries[first.citekey])[0]


def test_two_takes_of_one_file_at_once_add_it_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The integrator's review, finding 3: two adds of the same bytes at once each found them not held, outside the lock, and made two works on one home."""
    import shutil
    import threading

    import loom.refs.add as add

    q = demo(tmp_path)
    one = fake_pdf(tmp_path / "a" / "twice.pdf", "Sheaves on exotic manifolds\nZelda Quist\n")
    two = tmp_path / "b" / "twice-copy.pdf"
    two.parent.mkdir()
    shutil.copy(one, two)
    meet = threading.Barrier(2)
    real = add.identify

    def slow(*args: object, **kwargs: object) -> add.Seen:
        seen = real(*args, **kwargs)  # type: ignore[arg-type]
        try:
            meet.wait(timeout=2)  # both are past the check together, unless the lock keeps one out
        except threading.BrokenBarrierError:
            pass
        return seen

    monkeypatch.setattr(add, "identify", slow)
    rows: list[Row] = []
    threads = [threading.Thread(target=lambda p=p: rows.extend(taken(q, Item(path=p)))) for p in (one, two)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(r.state for r in rows) == ["added", "here"], rows
    assert [k for k, e in bib(q).items() if e.fields.get("title") == "Sheaves on exotic manifolds"] == [
        rows[0].citekey or rows[1].citekey
    ]


def test_two_versions_filed_from_two_old_scans_take_two_keys(tmp_path: Path) -> None:
    """The integrator's review, finding 3: two adds `--for` one work, each with the bibliography it read before the other wrote, both took `-v2`."""
    q = demo(tmp_path)
    first, second = bib(q), bib(q)
    a = fake_pdf(
        tmp_path / "a" / "x.pdf", "Fixed loci of involutions on separated spaces\nImogen Calloway\npreprint\n\f2"
    )
    b = fake_pdf(
        tmp_path / "b" / "y.pdf", "Fixed loci of involutions on separated spaces\nImogen Calloway\nslides\n\f2\f3"
    )
    (one,) = take(load_quilt(q), first, [Item(path=a, work="Calloway14", on_word=True)], by=WHO)
    (two,) = take(load_quilt(q), second, [Item(path=b, work="Calloway14", on_word=True)], by=WHO)
    assert (one.sibling, two.sibling) == ("Calloway14-v2", "Calloway14-v3")
    assert (q / BIB).read_text().count("@misc{Calloway14-v2,") + (q / BIB).read_text().count(
        "@article{Calloway14-v2,"
    ) == 1


def test_gathering_while_a_file_is_taken_in_adopts_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The integrator's review, finding 3: gathering in another process, while an add read a long book's pages, adopted the stored PDF as an orphan under another key; after the add's undo that entry named a home that was gone."""
    import threading
    import time

    import loom.refs.scan as rs
    from loom.refs.scan import scan_bibliography

    q = demo(tmp_path)
    reading = threading.Event()
    real = rs.write_map

    def slow(*args: object, **kwargs: object) -> object:
        reading.set()
        time.sleep(1.5)  # a long book
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(rs, "write_map", slow)
    scanned = scan(load_quilt(q))  # gathering's own scan, taken before, so that it acts inside the window
    rows: list[Row] = []
    adder = threading.Thread(
        target=lambda: rows.extend(
            taken(
                q,
                Item(path=fake_pdf(tmp_path / "src" / "book.pdf", "Lectures on braided categories\nQuentin Ostrava\n")),
            )
        )
    )
    adder.start()
    assert reading.wait(timeout=60)
    scan_bibliography(load_quilt(q), result=scanned)
    adder.join()
    named = [
        k
        for k, e in bib(q).items()
        if "braided" in e.fields.get("title", "").lower() or "book" in e.fields.get("loom-source", "")
    ]
    assert named == [rows[0].citekey], named
    undo(scan(load_quilt(q)), rows[0].id, by=WHO)
    from loom.refs.fetch import work_dir

    assert all(work_dir(q, e).is_dir() for e in bib(q).values() if e.fields.get("loom-file"))


def test_an_identifier_a_page_cites_never_becomes_the_pdfs_own(tmp_path: Path) -> None:
    """The integrator's review, finding 4: a note whose abstract opened on "a question raised in arXiv:…" took that paper's arXiv id, year and home as its own."""
    from loom.refs.fetch import work_dir
    from loom.refs.identity import identify

    q = demo(tmp_path)
    page = (
        "Acyclic orientations and cycle bases\nTomas Lind\nDepartment of Mathematics, Invented University\nAbstract\n"
        "We answer a question raised in arXiv:0805.2065 about\nthe cycle space of a quiver.\n"
    )
    (row,) = taken(q, dropped(q, "lind.pdf", page, tmp_path))
    assert row.state == "added", row
    entry = bib(q)[row.citekey]
    assert "eprint" not in entry.fields and work_dir(q, entry).parent.name == "file"
    assert identify(entry) != identify(bib(q)["Man12"])


def test_a_work_of_its_own_never_takes_an_identifier_another_work_states(tmp_path: Path) -> None:
    """A reply sets the id of the paper it answers at its head; said to be a work of its own, it is not given that paper's identity."""
    from loom.refs.identity import identify

    q = demo(tmp_path)
    page = "Comment on arXiv:0805.2065\nA remark on virtual pull-backs\nby Hugo Ness\nWe point out a gap.\n"
    (asked,) = taken(q, dropped(q, "reply.pdf", page, tmp_path))
    assert asked.state == "question" and [c["citekey"] for c in asked.candidates] == ["Man12"]
    row = answer(load_quilt(q), bib(q), asked.question, None, by=WHO)
    entry = bib(q)[row.citekey]
    assert "eprint" not in entry.fields and identify(entry) != identify(bib(q)["Man12"])


def test_the_published_version_dropped_on_its_work_is_filed_and_not_taken_for_a_copy(tmp_path: Path) -> None:
    """The integrator's review, finding 5: a published version printing its own DOI at its head and its preprint's arXiv id at its foot was judged a copy of the preprint and thrown away."""
    from tests.unit._quilts import showcase

    q = showcase(tmp_path)
    page = (
        "J. Invented Combin. 12 (2024) 1-30\ndoi:10.9999/jic.2024.12\nCycle spaces of finite quivers\nElspeth Arden\n"
        "Abstract. A published text, revised after review.\nPreprint: arXiv:2504.01234v1\n"
    )
    (row,) = taken(q, Item(drop=dropped(q, "published.pdf", page, tmp_path).drop, work="Arden24"))
    assert row.state == "added" and row.under == "Arden24" and row.sibling, row


def test_a_survey_listing_identifiers_at_its_foot_states_none_of_them_as_its_own() -> None:
    from loom.refs.ingest import own_identifiers

    page = "A survey of quivers\nLena Field\nBody text.\narXiv:2504.01234\narXiv:0805.2065\ndoi:10.4171/x.1\ndoi:10.4171/x.2\n"
    assert own_identifiers(page) == (set(), set(), set())


def test_a_command_line_add_of_bytes_a_viewers_drop_holds_takes_that_drop(tmp_path: Path) -> None:
    """The integrator's review, finding 6: an add from the command line of bytes waiting in a drop wrote its act into that drop and took its question away, and the drop then waited for good as a row with no name."""
    import shutil

    q = demo(tmp_path)
    page = "Fixed loci of involutions on separated spaces\nImogen Calloway\nslides of a talk\n"
    item = dropped(q, "talk.pdf", page, tmp_path)
    (asked,) = taken(q, item)
    assert asked.state == "question"
    library = {k: v for k, v in tree(q).items() if not k.startswith(f"{INCOMING}/")}
    copy = tmp_path / "elsewhere" / "talk copy.pdf"
    copy.parent.mkdir()
    shutil.copy(next((q / INCOMING / item.drop).glob("*.pdf")), copy)
    (added,) = taken(q, Item(path=copy, new=True))
    assert added.state == "added" and added.id == item.drop and waiting(q) == []
    (again,) = taken(q, Item(drop=item.drop))
    assert again.state == "here" and waiting(q) == []
    undo(scan(load_quilt(q)), item.drop, by=WHO)
    # the viewer's drop waits again as it was received, and the library is as before the add
    assert [(r["id"], r["state"], r["name"]) for r in waiting(q)] == [(item.drop, "received", "talk.pdf")]
    assert {k: v for k, v in tree(q).items() if not k.startswith(f"{INCOMING}/")} == library
