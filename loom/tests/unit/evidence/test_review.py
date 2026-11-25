"""Review's lists, each a rule over the evidence, the asks, the scan and the manifest: what puts a row in, what takes it out, how a kind's rows are ordered and narrowed to one draft, and that the counts are the rows'."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from loom.evidence import review
from loom.evidence.asks import ask, say
from loom.evidence.log import replay, write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import DraftWeb, Here
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok
from tests.unit._quilts import opened

PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Probe Agent")
LOOM = Who("loom")
MAIN = r"""\documentclass{article}
\usepackage{amsmath}
\newtheorem{lemma}{Lemma}
\newtheorem{definition}{Definition}
\newcommand{\Zcyc}{\mathcal{Z}}
\begin{document}
\begin{definition}\label{def:connected}
A quiver is connected if its underlying graph is connected.
\end{definition}
\begin{definition}\label{def:cycle}
For a connected quiver (Definition~\ref{def:connected}), $\Zcyc$ is the kernel.
\end{definition}
\begin{lemma}\label{lem:balanced}
Every $w \in \Zcyc$ on a tree vanishes, as in Definition~\ref{def:cycle}.
\end{lemma}
\end{document}
"""
DOC = "drafting/main.tex"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    root = tmp_path / "q"
    ok("init", str(root), "--demo", cwd=tmp_path)
    # the demo ships a suggested edit of its own
    (root / ".loom/records/edits/log.jsonl").unlink()
    (root / DOC).write_text(MAIN, encoding="utf-8")
    (root / "lean").mkdir()
    (root / "lean" / "A.lean").write_text("theorem a : True := trivial\n", encoding="utf-8")
    return root


def _gather(root: Path, manifest: dict | None = None) -> review.Gathered:
    return review.gather(root, scan(load_quilt(root)), manifest or {})


def _key(root: Path, label: str, doc: str | None = None) -> str:
    [node] = [n for n in DraftWeb(scan(load_quilt(root))).bearing[label] if doc is None or doc in n.reached_by]
    return node.key


def _lean(root: Path, label: str, doc: str | None = None) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    subject = web.subject(Here("block", _key(root, label, doc)))
    assert subject is not None
    digest = "sha256:" + hashlib.sha256((root / "lean" / "A.lean").read_bytes()).hexdigest()
    write(
        root,
        "lean",
        LOOM,
        on=subject,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": digest},
        files={"lean/A.lean": digest},
        declarations=[
            {
                "name": label,
                "kind": "theorem",
                "role": "states",
                "names": {"label": label},
                "statement": digest,
                "axioms": [],
                "sorry": False,
            }
        ],
        assumed=[],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=True,
    )


def _attest(root: Path, label: str, doc: str | None = None) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    here = Here("block", _key(root, label, doc))
    subject = web.subject(here)
    assert subject is not None
    lean = [r for r in replay(root).about("label", label, of="lean") if r.on and r.on.hash == subject.hash][-1]
    closure = [{k[0]: k[1], "hash": h} for k, h in sorted(web.closure(here).items())]
    statements = {d["name"]: d["statement"] for d in lean.get("declarations")}
    write(root, "attested", PERSON, on=subject, lean=lean.id, statements=statements, closure=closure, rulings=[])
    for name, digest in web.notation(here).items():
        write(root, "attested", PERSON, on=Subject("macro", name, digest))


def _edit(root: Path, old: str, new: str, doc: str = DOC) -> None:
    text = (root / doc).read_text(encoding="utf-8")
    assert old in text
    (root / doc).write_text(text.replace(old, new), encoding="utf-8")


def _rows(g: review.Gathered, kind: str) -> list[dict]:
    return [r.to_dict() for r in g.of(kind)]


def test_an_agents_question_waits_until_answered_and_names_its_choices(root: Path) -> None:
    q = ask(
        root,
        AGENT,
        "question",
        "person",
        {"label": "lem:balanced"},
        origin=[DOC],
        text="Both?",
        choices=["both", "one"],
    )
    [row] = _rows(_gather(root), "questions")
    assert row["row"] == f"questions:{q.id}" and row["choices"] == ["both", "one"] and row["docs"] == [DOC]
    say(root, PERSON, "answered", q.id, words="", choice=0)
    assert _rows(_gather(root), "questions") == []


def test_a_paper_waits_until_withdrawn_or_held_and_a_task_until_it_produces_or_is_withdrawn(root: Path) -> None:
    paper = ask(
        root,
        AGENT,
        "paper",
        "person",
        {"ref": "dm-00B1-ref"},
        ref="dm-00B1-ref",
        link="https://doi.org/10.1000/x.17",
        want="pdf",
    )
    task = ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    g = _gather(root)
    assert [r["link"] for r in _rows(g, "fetch")] == ["https://doi.org/10.1000/x.17"]
    [waiting] = _rows(g, review.AGENTS)
    assert waiting["task"] == task.id and waiting["what"] == "read" and waiting["working"] is None
    say(root, AGENT, "withdrawn", paper.id)
    say(root, PERSON, "withdrawn", task.id)
    g = _gather(root)
    assert _rows(g, "fetch") == [] and _rows(g, review.AGENTS) == []


def test_lean_accepted_is_to_attest_until_attested(root: Path) -> None:
    _lean(root, "lem:balanced")
    [row] = _rows(_gather(root), "attest")
    assert row["result"] == _key(root, "lem:balanced") and row["what"] == "statement and proof"
    _attest(root, "lem:balanced")
    assert _rows(_gather(root), "attest") == []


def test_results_resting_on_a_changed_definition_are_nested_under_it(root: Path) -> None:
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _lean(root, label)
        _attest(root, label)
    assert _rows(_gather(root), "attested-changed") == []
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "def:connected") and row["changed"] == "statement"
    assert sorted(r["result"] for r in row["resting"]) == sorted(
        _key(root, label) for label in ("def:cycle", "lem:balanced")
    )


def test_a_result_changed_through_a_definition_nobody_attested_is_a_row_of_its_own(root: Path) -> None:
    _lean(root, "lem:balanced")
    _attest(root, "lem:balanced")
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "lem:balanced") and row["changed"] == "used"
    assert [c["changed"] for c in row["causes"]] == [{"label": "def:connected"}]


BOUNDS = "drafting/bounds.tex"
TWIN = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\begin{lemma}\label{lem:balanced}
A twin of the lemma, in other words.
\end{lemma}
\begin{lemma}\label{lem:twinned}
By Lemma~\ref{lem:balanced}, every twin is balanced.
\end{lemma}
\end{document}
"""


def test_one_label_on_two_texts_in_two_documents_is_two_rows_each_with_what_rests_on_it(root: Path) -> None:
    (root / BOUNDS).write_text(TWIN, encoding="utf-8")
    for label, doc in (("lem:balanced", DOC), ("lem:balanced", BOUNDS), ("lem:twinned", BOUNDS)):
        _lean(root, label, doc)
        _attest(root, label, doc)
    assert _rows(_gather(root), "attested-changed") == []
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    _edit(root, "in other words", "in yet other words", BOUNDS)
    rows = {r["result"]: r for r in _rows(_gather(root), "attested-changed")}
    here, there = _key(root, "lem:balanced", DOC), _key(root, "lem:balanced", BOUNDS)
    assert sorted(rows) == sorted([here, there])
    assert rows[here]["resting"] == [] and rows[here]["docs"] == [DOC]
    assert [u["result"] for u in rows[there]["resting"]] == [_key(root, "lem:twinned")]


def test_a_result_rests_under_a_member_whose_own_words_changed_never_under_one_resting_itself(root: Path) -> None:
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _lean(root, label)
        _attest(root, label)
    # the cycle's words change and it is attested again; the lemma, attested on its first words, is not
    _edit(root, "is the kernel.", "is the kernel of the boundary.")
    _lean(root, "def:cycle")
    _attest(root, "def:cycle")
    # then what both rest on changes: the cycle rests on it, and the lemma names the cycle first among its causes
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "def:connected")
    assert sorted(u["result"] for u in row["resting"]) == sorted(_key(root, x) for x in ("def:cycle", "lem:balanced"))


def test_a_result_citing_a_result_of_a_work_no_node_answers_for_is_not_offered_to_attest(root: Path) -> None:
    cited = "\\begin{lemma}\\label{lem:cited}\nBy \\cite[Theorem 2.1]{Calloway14}, every cog is finite.\n\\end{lemma}\n"
    _edit(root, "\\end{document}", cited + "\\end{document}")
    _lean(root, "lem:cited")
    _lean(root, "lem:balanced")
    assert [r["result"] for r in _rows(_gather(root), "attest")] == [_key(root, "lem:balanced")]


def _served(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[object], list[int]]:
    """The publisher's kept scan offered for `root`, one scan object until the test swaps it, and `gather`'s calls counted."""
    from loom.render.endpoints import base

    held: list[object] = [scan(load_quilt(root))]
    monkeypatch.setitem(base._SCANS, root.resolve(), lambda: held[0])
    calls: list[int] = []
    real = review.gather
    monkeypatch.setattr(review, "gather", lambda *a, **k: calls.append(1) or real(*a, **k))
    return held, calls


def test_a_read_under_the_same_scan_and_files_answers_from_the_last(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.looks import keep_all, take
    from loom.render.endpoints.review import _gathered
    from loom.scan.quilt import save_author

    save_author("A. Author")
    opened(root)  # the paper open to agents, so an edit in it is listed
    take(load_quilt(root), "A. Author")
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    held, calls = _served(root, monkeypatch)
    [change] = _gathered(root)[2].of("edits")
    assert _gathered(root)[2].of("edits") == [change] and len(calls) == 1
    # the person's look takes the change in: the same scan, another look
    keep_all(load_quilt(root), "A. Author")
    assert _gathered(root)[2].of("edits") == [] and len(calls) == 2
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=[DOC], text="Both?")
    assert len(_gathered(root)[2].of("questions")) == 1 and len(calls) == 3
    held[0] = scan(load_quilt(root))
    _gathered(root)
    assert len(calls) == 4


def test_an_ask_reads_working_while_the_session_that_took_it_is_alive_on_a_kept_read_too(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.evidence import asks
    from loom.render.endpoints.review import _gathered

    task = ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    say(root, AGENT, "took", task.id, session="s-2026-11-21-a8k2rx")
    _held, calls = _served(root, monkeypatch)
    alive: list[frozenset[str]] = [frozenset()]
    monkeypatch.setattr(asks, "live_sessions", lambda _root: alive[0])
    [row] = _gathered(root)[2].of(review.AGENTS)
    assert row.fields["working"] is None
    alive[0] = frozenset({"s-2026-11-21-a8k2rx"})
    [row] = _gathered(root)[2].of(review.AGENTS)
    assert row.fields["working"] == {"by": "Probe Agent"} and len(calls) == 1


def test_an_accepted_result_that_changed_is_listed_from_the_published_ledger(root: Path) -> None:
    from loom.cli.review import write_acceptance
    from loom.render.build import build
    from loom.scan.quilt import save_author

    save_author("A. Author")
    key = _key(root, "lem:balanced")
    write_acceptance(scan(load_quilt(root)), [key], "A. Author")
    assert _rows(_gather(root, build(load_quilt(root)).manifest), "accepted-changed") == []
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    manifest = build(load_quilt(root)).manifest
    [row] = _rows(_gather(root, manifest), "accepted-changed")
    # numbered where the compile numbered it (the fake TeX of the unit tier numbers nothing)
    assert row["key"] == key and row["doc"] == DOC and row["name"] in ("Lemma", "Lemma 1")


def test_an_agents_suggested_edit_is_a_proposed_edit(root: Path) -> None:
    key = _key(root, "lem:balanced")
    ok("suggest", key, "--with", "Every balanced weighting", "--quote", "Every", "--as", "Probe Agent", cwd=root)
    [row] = _rows(_gather(root), "edits")
    assert row["type"] == "suggested" and row["key"] == key and row["by"] == "Probe Agent"


def test_the_proposed_edits_are_the_changes_a_publication_lists_and_differ_only_until_the_next(root: Path) -> None:
    """Your Changes lists the publication's `changes`; the column's count for `edits` is the same rows, from the same scan and reviewer, and runs ahead of it only between a write and the publication that follows."""
    from loom.looks import take
    from loom.render.build import build
    from loom.scan.quilt import save_author

    save_author("A. Author")
    opened(root)  # the paper open to agents, so an edit in it is listed
    take(load_quilt(root), "A. Author")
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    ok("suggest", _key(root, "def:connected"), "--with", "Every quiver", "--quote", "A quiver", "--as", "Probe Agent", cwd=root)  # fmt: skip
    report = build(load_quilt(root))
    listed = [c["id"] for c in report.manifest["changes"]]
    assert len(listed) == 2
    assert [r["change"] for r in _rows(review.gather(root, report.result, report.manifest), "edits")] == listed
    # a write the publisher has not published yet: the read scans the files now, the page still has the last publication
    _edit(root, "is the kernel", "is the cokernel")
    assert len(_rows(_gather(root, report.manifest), "edits")) == len(listed) + 1
    report = build(load_quilt(root))
    assert [r["change"] for r in _rows(review.gather(root, report.result, report.manifest), "edits")] == [c["id"] for c in report.manifest["changes"]]  # fmt: skip


def test_the_proposed_edits_list_exactly_what_the_look_lists(root: Path) -> None:
    """On `wave-c`'s look, kept for every quilt and watching only what agents may edit: a save in the demo's paper, denied to agents, is never listed; opened to them, an agent's change there is; the person's keep of an agent's suggestion goes through the door, which follows the look, so the words loom wrote are no change of anyone's; and the rows are the publication's `changes` throughout."""
    from loom.looks import take
    from loom.pending import keep
    from loom.render.build import build
    from loom.scan.quilt import save_author

    save_author("A. Author")
    take(load_quilt(root), "A. Author")

    def both() -> tuple[list[str], list[str]]:
        report = build(load_quilt(root))
        return [r["change"] for r in _rows(review.gather(root, report.result, report.manifest), "edits")], [c["id"] for c in report.manifest["changes"]]  # fmt: skip

    _edit(root, "on a tree vanishes", "on a forest vanishes")
    assert both() == ([], []), "the paper is denied to agents, so a save there is the person's and never listed"
    opened(root)
    take(load_quilt(root), "A. Author")
    _edit(root, "is the kernel", "is the cokernel")
    rows, changes = both()
    assert rows == changes and len(rows) == 1
    ok("suggest", _key(root, "def:connected"), "--with", "Every quiver", "--quote", "A quiver", "--as", "Probe Agent", cwd=root)  # fmt: skip
    rows, changes = both()
    assert rows == changes and len(rows) == 2
    suggestion = rows[1]  # the in-place changes come first, then the suggestions
    keep(scan(load_quilt(root)), "A. Author", [suggestion], ("person", "A. Author"))
    rows, changes = both()
    assert rows == changes and suggestion not in rows and len(rows) == 1, (
        "the kept suggestion is not listed again as an in-place change"
    )


def test_a_rows_kind_is_its_kind_and_no_field_of_its_own_overwrites_it(root: Path) -> None:
    key = _key(root, "lem:balanced")
    ok("suggest", key, "--with", "Every balanced weighting", "--quote", "Every", "--as", "Probe Agent", cwd=root)
    ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    g = _gather(root)
    assert [(r["kind"], r["type"]) for r in _rows(g, "edits")] == [("edits", "suggested")]
    assert [(r["kind"], r["what"]) for r in _rows(g, review.AGENTS)] == [(review.AGENTS, "read")]
    with pytest.raises(ValueError, match="kind"):
        review.Row("edits:e-1", "edits", (DOC,), fields={"kind": "suggested"}).to_dict()


def test_everything_is_in_rank_order_counts_are_the_rows_and_a_draft_narrows_both(root: Path) -> None:
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=["drafting/other.tex"], text="Elsewhere?")
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=[DOC], text="Here?")
    ask(
        root,
        AGENT,
        "paper",
        "person",
        {"ref": "dm-00B1-ref"},
        origin=[DOC],
        ref="dm-00B1-ref",
        link="https://example.org/p",
        want="pdf",
    )
    _lean(root, "lem:balanced")
    g = _gather(root)
    groups = review.listed(g, "all")
    assert [grp["kind"] for grp in groups] == ["questions", "fetch", "attest"]
    counted = review.counts(g, [DOC, "drafting/other.tex"])
    assert counted["everything"] == 4 and counted["kinds"]["questions"] == 2 and counted["agents"] == 0
    assert counted["drafts"] == [{"doc": DOC, "n": 3}, {"doc": "drafting/other.tex", "n": 1}]
    assert [len(grp["rows"]) for grp in review.listed(g, "all", DOC)] == [1, 1, 1]
    assert review.find(g, groups[0]["rows"][0]["row"]) is not None


def test_a_result_is_named_by_its_taxon_and_the_number_the_build_published() -> None:
    manifest = {
        "nodes": {
            "k": {
                "taxon": "Lemma",
                "numbers": {"a.tex": {"number": "3.3", "page": 2}, "b.tex": {"number": "1", "page": 1}},
            }
        }
    }
    assert review._name(manifest, "k", "b.tex") == "Lemma 1" and review._name(manifest, "k", "c.tex") == "Lemma 3.3"
    assert review._name({"nodes": {"k": {"taxon": "Remark", "numbers": {}}}}, "k", "a.tex") == "Remark"


def test_a_row_about_a_result_carries_how_it_stands_and_one_attested_when_it_was(root: Path) -> None:
    _lean(root, "lem:balanced")
    [row] = _rows(_gather(root), "attest")
    record = replay(root).about("label", "lem:balanced", of="lean")[-1]
    assert row["record"] == record.id and row["reading"] is None
    assert row["lean"] == {"lean": "unattested", "role": "proved", "waiting_on": []}
    for label in ("def:connected", "def:cycle"):
        _lean(root, label)
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _attest(root, label)
    _edit(root, "is connected.", "is connected after its loops are removed.")
    g = _gather(root)
    [changed] = _rows(g, "attested-changed")
    attestation = replay(root).by_id(changed["attestation"])
    assert attestation is not None and changed["attested_at"] == attestation.at
    # its text changed, so no Lean record is on it now and it has no role
    assert changed["lean"] == {"lean": "changed", "role": None, "waiting_on": []}
    found = review.find(g, changed["row"])
    assert found is not None and review.body_of(found, {}) == {"at": attestation.at}


def test_a_question_names_the_task_its_session_was_working_on(tmp_path: Path) -> None:
    from loom.evidence.asks import replay as replay_asks
    from loom.evidence.asks import working_on
    from tests.helpers import json_of
    from tests.unit._quilts import demo, new_session

    q = demo(tmp_path)
    session = new_session(q, "digesting", AGENT.name)
    task = ask(q, PERSON, "digest", "agent", {"ref": "dm-00B1-ref"}, origin=[DOC], ref="dm-00B1-ref", scope="all")
    say(q, AGENT, "took", task.id, session=session)
    assert working_on(q, session) == task.id and working_on(q, "s-2026-11-21-zzzzzz") is None
    asked = json_of("ask", "Remark 2.5 too?", "--on", "dm-0003", "--as", AGENT.name, "--json", cwd=q, env={"LOOM_MCP_SESSION": session})["task"]  # fmt: skip
    assert replay_asks(q).asks[asked].get("under") == task.id
    [row] = _rows(review.gather(q, scan(load_quilt(q)), {}), "questions")
    assert row["under"] == {"task": task.id, "what": "digest", "on": {"ref": "dm-00B1-ref"}, "ref": "dm-00B1-ref"}
    # a task said done, or withdrawn, is no longer what the session works on
    say(q, AGENT, "done", task.id, made=["dm-00B7"])
    assert working_on(q, session) is None


def test_a_text_never_attested_beside_an_attested_one_is_not_an_attested_result_that_changed(root: Path) -> None:
    other = "drafting/b.tex"
    (root / other).write_text(MAIN.replace("vanishes, as in", "is zero, as in"), encoding="utf-8")
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _lean(root, label, DOC)
        _attest(root, label, DOC)
    assert _rows(_gather(root), "attested-changed") == []


def test_a_row_to_attest_opens_on_the_lean_its_notation_and_what_it_uses_that_was_attested(root: Path) -> None:
    _lean(root, "def:cycle")
    _attest(root, "def:cycle")
    _lean(root, "lem:balanced")
    gathered = _gather(root)
    [row] = [r for r in gathered.of("attest") if r.fields["result"] == _key(root, "lem:balanced")]
    body = review.body_of(row, {})
    lean = replay(root).about("label", "lem:balanced", of="lean")[-1]
    assert body["observation"] == lean.id and body["parts"] is None and body["difference"] is None
    assert body["notation"] == [{"part": "Zcyc", "from": "preamble", "attested": True}]
    assert [u["result"] for u in body["uses_attested"]] == [_key(root, "def:cycle")]
    assert body["supporting"] == [] and "body" not in row.to_dict()


def test_digested_results_to_check_are_a_row_a_work_and_a_correction_a_row_with_its_word_diff(root: Path) -> None:
    """`check`: the statements with a text not compared on their text now, by work, a stub never; one compared leaves; an agent's correction of a compared text is a row of its own, its body the word diff, gone once taken."""
    from loom.evidence import acts
    from loom.evidence.web import LibraryWeb
    from loom.library.store import folder
    from tests.unit.library._examples import fixtures

    folder(root).mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (folder(root) / name).write_bytes(data)
    rows = lambda: [r.to_dict() for r in _gather(root).of("check")]  # noqa: E731
    [work] = rows()
    assert (work["ref"], work["short"], work["pdf"]) == ("tq-00A1-ref", "Smith 2024", "sha256:41b7c0a9e3f2d5681c94ab07e6d3f81290ce5b47a8d1036f2e9c7b54a0d8e163")  # fmt: skip
    assert [(n["node"], n["number"], n["title"], n["rests"]) for n in work["nodes"]][:2] == [("tq-00A4", "2.1", "Widget", {"docs": []}), ("tq-00K3", "3.2", "Test lemma", {"docs": []})]  # fmt: skip
    assert "tq-00B7" not in [n["node"] for n in work["nodes"]], "a stub is read before it is checked"
    shown = LibraryWeb(root).subject(Here("node", "tq-00A4"))
    assert shown is not None
    acts.check(root, "tq-00A4", shown.hash, PERSON)
    [work] = rows()
    assert "tq-00A4" not in [n["node"] for n in work["nodes"]]
    data = (folder(root) / "tq-00A4.node").read_bytes()
    _said, proposal = acts.propose(root, "tq-00A4", data.replace(b"compact set", b"closed set", 1), AGENT, "page 4")
    [_, correction] = [r for r in _gather(root).of("check")]
    said = correction.to_dict()
    assert (said["correction"], said["node"], said["short"], said["by"]) == (proposal.id, "tq-00A4", "Smith 2024", "Probe Agent")  # fmt: skip
    body = review.body_of(correction, {})
    assert body["compared_at"] is not None and ["-", "compact"] in [[k, w.strip()] for k, w in body["runs"]] and ["+", "closed"] in [[k, w.strip()] for k, w in body["runs"]]  # fmt: skip
    assert "".join(w for k, w in body["runs"] if k != "+") == data.decode().split("+++")[2].lstrip("\n")
    assert said["refusal"] is None, "the take is offered"
    acts.take(root, proposal.id, PERSON)
    assert [r["kind"] for r in rows() if "correction" in r] == []


def test_a_citation_of_a_library_work_naming_no_result_is_listed_until_the_person_calls_it_a_mention(
    root: Path,
) -> None:
    """`cited`: `\\cite{Smi24}` in a lemma names no result of Smith 2024, so it is a row; `\\cite[Theorem 2]{Jon19}` names one and a key no work has is no row; the person's `mention` lets it go, and taking it back lists it again."""
    from loom.evidence import acts
    from loom.library.store import folder
    from tests.unit.library._examples import fixtures

    folder(root).mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (folder(root) / name).write_bytes(data)
    _edit(
        root,
        "on a tree vanishes",
        "on a tree vanishes \\cite{Smi24}, as in \\cite[Theorem 2]{Jon19} and \\cite{Nobody99}",
    )
    key = _key(root, "lem:balanced")
    rows = lambda: [r.to_dict() for r in _gather(root).of("cited")]  # noqa: E731
    [row] = rows()
    assert (row["ref"], row["short"], row["citekey"], row["key"], row["doc"]) == ("tq-00A1-ref", "Smith 2024", "Smi24", key, DOC)  # fmt: skip
    assert row["citation"] == f"tq-00A1-ref@{key}"
    [cited] = _gather(root).of("cited")
    assert review.body_of(cited, {})["cite"]["nth"] == 0
    acts.mention(root, scan(load_quilt(root)), key, "tq-00A1-ref", PERSON)
    assert rows() == []
    acts.mention(root, scan(load_quilt(root)), key, "tq-00A1-ref", PERSON, undo=True)
    assert [r["citekey"] for r in rows()] == ["Smi24"]
    with pytest.raises(acts.ActRefused, match="does not cite"):
        acts.mention(root, scan(load_quilt(root)), key, "tq-00B1-ref", PERSON)


def test_a_library_node_is_to_attest_once_it_and_all_it_uses_match_their_paper(root: Path) -> None:
    from loom.evidence import acts
    from loom.evidence.web import LibraryWeb
    from loom.library.store import folder
    from tests.unit.library._examples import fixtures

    folder(root).mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (folder(root) / name).write_bytes(data)
    on = LibraryWeb(root).subject(Here("node", "tq-00K3"))
    assert on is not None
    declaration = {"name": "Smith.lem32", "kind": "theorem", "role": "states", "names": {"node": "tq-00K3"}, "statement": "sha256:" + "5" * 64, "axioms": [], "sorry": False}  # fmt: skip
    lean = write(root, "lean", LOOM, on=on, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64}, files={"lean/A.lean": "sha256:" + hashlib.sha256((root / "lean" / "A.lean").read_bytes()).hexdigest()}, declarations=[declaration], assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    listed = lambda: [r for r in _gather(root).of("attest") if r.fields["result"] == "tq-00K3"]  # noqa: E731
    assert listed() == []
    acts.check(root, "tq-00K3", on.hash, PERSON)
    assert listed() == [], "what it uses is not compared yet"
    definition = LibraryWeb(root).subject(Here("node", "tq-00A4"))
    assert definition is not None
    acts.check(root, "tq-00A4", definition.hash, PERSON)
    [row] = listed()
    said = row.to_dict()
    assert said["what"] == "statement only" and said["paper"] == "matches" and said["docs"] == []
    assert said["name"] == "lemma 3.2" and said["source"] == {"ref": "tq-00A1-ref", "short": "Smith 2024"}
    body = review.body_of(row, {})
    assert body["observation"] == lean.id and body["statement"]["body"].startswith("Let $W$ be a widget")
    # its notation, its work's macros node's rows its text uses, each not yet attested in its definition
    assert [(n["part"], n["from"], n["attested"]) for n in body["notation"]] == [("Wid", "macros", False), ("diam", "macros", False)]  # fmt: skip
    assert body["statement"]["macros"]["node"] == "tq-00A1-macros" and "\\Wid" in body["statement"]["macros"]["body"]
