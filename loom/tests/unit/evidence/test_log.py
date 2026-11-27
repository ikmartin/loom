"""The evidence log: written only in its kinds' shapes, by the hand each kind allows; read past every line it cannot use."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.evidence import log
from loom.evidence.log import EvidenceRefused, replay, write
from loom.evidence.subjects import Subject, Who

H = "sha256:" + "a" * 64
H2 = "sha256:" + "b" * 64
PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Claude Code")
LOOM = Who("loom")
NODE = Subject("node", "tq-00K3", H)
PAPER = {"ref": "tq-00A1-ref", "pdf": H2, "pages": "12"}


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    return tmp_path


def _lines(root: Path) -> list[dict]:
    return [json.loads(line) for line in log.log_path(root).read_text(encoding="utf-8").splitlines()]


def test_a_record_is_written_whole_and_read_back(root: Path) -> None:
    made = write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    assert made.id.startswith("ev-2026-11-21-") and made.at == "2026-11-21T10:00:00Z"
    [line] = _lines(root)
    assert line == {
        "id": made.id,
        "kind": "compared",
        "at": made.at,
        "by": PERSON.to_dict(),
        "on": NODE.to_dict(),
        "with": PAPER,
    }
    found = replay(root)
    assert [r.id for r in found.records] == [made.id] and found.problems == []
    assert found.about("node", "tq-00K3", of="compared")[0].get("with") == PAPER


def test_two_records_on_one_day_draw_two_ids(root: Path) -> None:
    a = write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    b = write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    assert a.id != b.id
    assert [r.id for r in replay(root).records] == [a.id, b.id]


@pytest.mark.parametrize(
    ("kind", "by", "fields"),
    [
        ("compared", AGENT, {"with": PAPER}),
        ("attested", AGENT, {}),
        ("lean", PERSON, {}),
        ("proposed", PERSON, {"bytes": "+++\n", "why": ""}),
        ("declined", AGENT, {"proposal": "ev-2026-11-21-aaaaaa", "why": ""}),
    ],
)
def test_a_kind_is_refused_from_another_hand(root: Path, kind: str, by: Who, fields: dict) -> None:
    with pytest.raises(EvidenceRefused, match="written by"):
        write(root, kind, by, on=None if kind == "declined" else NODE, **fields)
    assert not log.log_path(root).exists() or log.log_path(root).read_text() == ""


@pytest.mark.parametrize(
    ("how", "by", "ok"),
    [
        ("extracted", LOOM, True),
        ("extracted", AGENT, False),
        ("transcribed", AGENT, True),
        ("written", PERSON, True),
        ("written", AGENT, False),
    ],
)
def test_how_a_node_is_made_says_whose_hand(root: Path, how: str, by: Who, ok: bool) -> None:
    def go() -> None:
        write(root, "digested", by, on=NODE, how=how, **{"from": {"ref": "tq-00A1-ref", "tex": H2}})

    if ok:
        go()
    else:
        with pytest.raises(EvidenceRefused):
            go()


def test_a_person_may_write_a_node_from_no_document(root: Path) -> None:
    write(root, "digested", PERSON, on=NODE, how="written", **{"from": None})
    with pytest.raises(EvidenceRefused):
        write(root, "digested", AGENT, on=NODE, how="transcribed", **{"from": None})


def test_a_field_too_many_or_too_few_is_refused(root: Path) -> None:
    with pytest.raises(EvidenceRefused, match="which this kind does not"):
        write(root, "compared", PERSON, on=NODE, **{"with": PAPER, "verdict": "yes"})
    with pytest.raises(EvidenceRefused, match="lacks with"):
        write(root, "compared", PERSON, on=NODE)


def test_a_reading_names_a_statement_or_a_proof_never_a_work(root: Path) -> None:
    with pytest.raises(EvidenceRefused, match="not a statement or a proof"):
        write(root, "compared", PERSON, on=Subject("node", "tq-00A1-ref", H), **{"with": PAPER})
    write(root, "compared", PERSON, on=Subject("node", "tq-00K3-proof00", H), **{"with": PAPER})


def test_a_draft_result_is_attested_by_its_label_and_a_macro_by_itself(root: Path) -> None:
    lean = "ev-2026-11-21-aaaaaa"
    on = Subject("label", "lem:balanced", H)
    write(
        root,
        "attested",
        PERSON,
        on=on,
        lean=lean,
        statements={"A.b": H2},
        closure=[Subject("label", "def:x", H2).to_dict()],
        rulings=[],
    )
    write(root, "attested", PERSON, on=Subject("macro", "Zcyc", H2))
    with pytest.raises(EvidenceRefused):
        write(root, "attested", PERSON, on=Subject("macro", "Zcyc", H2), lean=lean)
    found = replay(root)
    assert [r.on.kind for r in found.of_kind("attested") if r.on] == ["label", "macro"]


def test_a_lean_record_needs_what_lean_said(root: Path) -> None:
    good = {
        "project": {"root": "lean", "toolchain": "leanprover/lean4:v4.36.0", "mathlib": "9d58", "manifest": H},
        "files": {"lean/A.lean": H},
        "declarations": [
            {
                "name": "A.b",
                "kind": "theorem",
                "role": "states",
                "names": {"label": "lem:b"},
                "statement": H,
                "axioms": ["propext"],
                "sorry": False,
            },
            {
                "name": "A.aux",
                "kind": "theorem",
                "role": "supports",
                "names": None,
                "statement": H2,
                "axioms": [],
                "sorry": False,
            },
        ],
        "assumed": [],
        "uses": [],
        "replay": {"tool": "leanchecker", "exit": 0, "output": ""},
        "ok": True,
    }
    write(root, "lean", LOOM, on=Subject("label", "lem:b", H), **good)
    stating_nothing = {**good, "declarations": [{**good["declarations"][0], "names": None}]}
    with pytest.raises(EvidenceRefused, match="names none"):
        write(root, "lean", LOOM, on=Subject("label", "lem:b", H), **stating_nothing)
    with pytest.raises(EvidenceRefused, match="files"):
        write(root, "lean", LOOM, on=Subject("label", "lem:b", H), **{**good, "files": {}})
    # a record whose print is missing says so, and then shows no declaration
    write(root, "lean", LOOM, on=Subject("label", "lem:b", H), **{**good, "print": "missing"})
    with pytest.raises(EvidenceRefused, match="print is 'missing'"):
        write(root, "lean", LOOM, on=Subject("label", "lem:b", H), **{**good, "print": "late"})
    shown = [{**good["declarations"][0], "shown": "theorem A.b : True"}]
    with pytest.raises(EvidenceRefused, match="shows no declaration"):
        write(
            root, "lean", LOOM, on=Subject("label", "lem:b", H), **{**good, "print": "missing", "declarations": shown}
        )


def test_a_line_that_cannot_be_used_is_reported_and_the_rest_read(root: Path) -> None:
    write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    with log.log_path(root).open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write(
            json.dumps(
                {"id": "ev-2026-11-21-zzzzzz", "kind": "verified", "at": "2026-11-21T10:00:00Z", "by": PERSON.to_dict()}
            )
            + "\n"
        )
        fh.write(
            json.dumps(
                {
                    "id": "ev-2026-11-21-yyyyyy",
                    "kind": "compared",
                    "at": "2026-11-21T10:00:00Z",
                    "by": AGENT.to_dict(),
                    "on": NODE.to_dict(),
                    "with": PAPER,
                }
            )
            + "\n"
        )
        fh.write("\n")
    write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    found = replay(root)
    assert len(found.records) == 2
    assert [p.split(": ", 1)[0] for p in found.problems] == [
        f"{log.EVIDENCE_LOG}:2",
        f"{log.EVIDENCE_LOG}:3",
        f"{log.EVIDENCE_LOG}:4",
    ]
    assert "not JSON" in found.problems[0] and "'verified'" in found.problems[1] and "not agent" in found.problems[2]


def test_a_replay_follows_an_append_made_elsewhere(root: Path) -> None:
    write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    assert len(replay(root).records) == 1
    line = log.log_path(root).read_text(encoding="utf-8").splitlines()[0]
    other = json.loads(line) | {"id": "ev-2026-11-21-zzzzzz"}
    with log.log_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(other) + "\n")
    assert [r.id for r in replay(root).records][-1] == "ev-2026-11-21-zzzzzz"


def test_a_declined_proposal_is_found_by_its_id(root: Path) -> None:
    proposal = write(root, "proposed", AGENT, on=NODE, bytes="+++\nschema = 1\n+++\n", why="page 4")
    write(root, "declined", PERSON, proposal=proposal.id, why="")
    found = replay(root)
    assert found.declined(proposal.id) is not None and found.by_id(proposal.id) == proposal


def test_unreadable_and_repeated_lines_are_lint_warnings(tmp_path: Path) -> None:
    from tests.helpers import ok
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    path = q / log.EVIDENCE_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps(
        {
            "at": "2026-11-21T10:00:00Z",
            "by": PERSON.to_dict(),
            "id": "ev-2026-11-21-aaaaaa",
            "kind": "compared",
            "on": NODE.to_dict(),
            "with": PAPER,
        }
    )
    path.write_text("{not json\n" + good + "\n" + good + "\n", encoding="utf-8")
    out = ok("lint", cwd=q).output
    assert "foreign-evidence" in out and log.EVIDENCE_LOG in out
    assert "repeated-id" in out
