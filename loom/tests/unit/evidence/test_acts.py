"""The acts on a library node's text (`evidence.acts`), on the spec's nine example nodes: a person's match with the paper, an agent's correction written at once or filed, its taking and declining, a person's own correction, and that every refusal leaves the store and the log as they were."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from loom.evidence import acts
from loom.evidence.acts import ActRefused
from loom.evidence.log import EvidenceRefused, Record, log_path, replay, write
from loom.evidence.status import status
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here, LibraryWeb
from loom.library.store import folder
from tests.unit.evidence._nothing import Nothing
from tests.unit.library._store import quilt

PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Claude Code")
LOOM = Who("loom")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    return quilt(tmp_path)


def _file(root: Path, node: str) -> Path:
    return folder(root) / f"{node}.node"


def _hash(root: Path, node: str) -> str:
    got = LibraryWeb(root).file(node)
    assert got is not None
    return got[0]


def _status(root: Path, node: str):  # type: ignore[no-untyped-def]
    return status(replay(root), LibraryWeb(root), Here("node", node), lean_now=lambda r: True)


def _state(root: Path) -> tuple[dict[str, bytes], bytes]:
    """Every node file's bytes and the evidence log's, to see that a refusal changed nothing."""
    log = log_path(root)
    return {p.name: p.read_bytes() for p in folder(root).iterdir()}, log.read_bytes() if log.exists() else b""


def _refused(root: Path, code: str, act, *args) -> ActRefused:  # type: ignore[no-untyped-def]
    before = _state(root)
    with pytest.raises(ActRefused) as caught:
        act(root, *args)
    assert caught.value.code == code, caught.value
    assert _state(root) == before
    return caught.value


def _corrected(root: Path, node: str, old: str, new: str) -> bytes:
    text = _file(root, node).read_text(encoding="utf-8")
    assert old in text
    return text.replace(old, new, 1).encode("utf-8")


def test_a_person_records_that_a_node_matches_its_paper_against_its_works_document(root: Path) -> None:
    record = acts.check(root, "tq-00A4", _hash(root, "tq-00A4"), PERSON)
    assert record.kind == "compared" and record.by == PERSON
    assert record.get("with") == {"ref": "tq-00A1-ref", "pdf": "sha256:41b7c0a9e3f2d5681c94ab07e6d3f81290ce5b47a8d1036f2e9c7b54a0d8e163", "pages": "4"}  # fmt: skip
    assert _status(root, "tq-00A4").reading == "matches"


def test_only_a_person_records_that_a_node_matches_its_paper_and_it_reads_matches_never_verified(root: Path) -> None:
    """A passing check is never called verification: no agent and not loom records a node's match with its paper, by the act or by the log, and what the person's act gives a node is worded `matches`."""
    shown = _hash(root, "tq-00A4")
    for who in (AGENT, LOOM):
        _refused(root, "author-only", acts.check, "tq-00A4", shown, who)
        with pytest.raises(EvidenceRefused):
            write(root, "compared", who, on=LibraryWeb(root).subject(Here("node", "tq-00A4")), **{"with": {"ref": "tq-00A1-ref", "pdf": shown}})  # fmt: skip
    readings = {_status(root, "tq-00A4").reading}
    acts.check(root, "tq-00A4", shown, PERSON)
    readings |= {_status(root, n).reading for n in ("tq-00A4", "tq-00B7", "tq-00K3")}
    assert readings == {"unchecked", "matches", "stub"} and "verified" not in readings


def test_a_check_is_refused_on_a_text_changed_since_it_was_shown_a_stub_and_a_work_with_no_document(root: Path) -> None:
    shown = _hash(root, "tq-00A4")
    _file(root, "tq-00A4").write_bytes(_corrected(root, "tq-00A4", "compact", "closed"))
    _refused(root, "changed", acts.check, "tq-00A4", shown, PERSON)
    _refused(root, "stub", acts.check, "tq-00B7", _hash(root, "tq-00B7"), PERSON)
    for missing in ("tq-9999", "tq-00A1-ref", "not an id"):
        _refused(root, "no-such-node", acts.check, missing, shown, PERSON)
    # the second work holds no document
    _file(root, "tq-00B7").write_bytes(_file(root, "tq-00B7").read_bytes() + b"A lemma.\n")
    _refused(root, "no-document", acts.check, "tq-00B7", _hash(root, "tq-00B7"), PERSON)


def test_an_agents_correction_of_a_node_nobody_compared_is_written_at_once_as_its_own(root: Path) -> None:
    data = _corrected(root, "tq-00A4", "compact", "closed")
    said, record = acts.propose(root, "tq-00A4", data, AGENT, "page 4 has closed")
    assert said == "written" and _file(root, "tq-00A4").read_bytes() == data
    assert record.kind == "digested" and record.get("how") == "corrected" and record.on is not None
    assert record.on.hash == _hash(root, "tq-00A4")
    found = _status(root, "tq-00A4")
    assert found.how == "corrected" and found.reading == "unchecked"


def test_an_agents_correction_of_a_compared_node_waits_and_the_compared_text_stands(root: Path) -> None:
    before = _file(root, "tq-00A4").read_bytes()
    acts.check(root, "tq-00A4", _hash(root, "tq-00A4"), PERSON)
    said, record = acts.propose(root, "tq-00A4", _corrected(root, "tq-00A4", "compact", "closed"), AGENT, "page 4")
    assert said == "proposed" and record.kind == "proposed" and _file(root, "tq-00A4").read_bytes() == before
    found = _status(root, "tq-00A4")
    assert found.reading == "matches" and found.proposal == record.id


def test_a_correction_is_an_agents_of_a_text_read_and_valid(root: Path) -> None:
    data = _corrected(root, "tq-00A4", "compact", "closed")
    _refused(root, "agent-only", acts.propose, "tq-00A4", data, PERSON, "")
    _refused(root, "stub", acts.propose, "tq-00B7", _file(root, "tq-00B7").read_bytes() + b"A lemma.\n", AGENT, "")
    _refused(root, "refused", acts.propose, "tq-00A4", b"not a node\n", AGENT, "")
    _refused(root, "refused", acts.propose, "tq-00A4", _file(root, "tq-00K3").read_bytes(), AGENT, "")
    _refused(root, "refused", acts.propose, "tq-00A4", _file(root, "tq-00A4").read_bytes(), AGENT, "")


def _filed(root: Path) -> str:
    acts.check(root, "tq-00A4", _hash(root, "tq-00A4"), PERSON)
    return acts.propose(root, "tq-00A4", _corrected(root, "tq-00A4", "compact", "closed"), AGENT, "page 4")[1].id


def test_taking_a_correction_writes_it_and_matches_the_new_text_with_the_paper(root: Path) -> None:
    proposal = _filed(root)
    record = acts.take(root, proposal, PERSON)
    assert b"closed set" in _file(root, "tq-00A4").read_bytes()
    assert record.kind == "compared" and record.on is not None and record.on.hash == _hash(root, "tq-00A4")
    found = _status(root, "tq-00A4")
    assert found.reading == "matches" and found.proposal is None
    _refused(root, "changed", acts.take, proposal, PERSON)


def test_a_correction_is_taken_only_by_a_person_only_while_open_and_only_over_the_text_it_corrects(root: Path) -> None:
    proposal = _filed(root)
    _refused(root, "author-only", acts.take, proposal, AGENT)
    _refused(root, "no-such-proposal", acts.take, "ev-2026-11-21-zzzzzz", PERSON)
    acts.decline(root, proposal, PERSON, "the paper says compact")
    _refused(root, "closed", acts.take, proposal, PERSON)
    _refused(root, "closed", acts.decline, proposal, PERSON)
    other = acts.propose(root, "tq-00A4", _corrected(root, "tq-00A4", "compact", "bounded"), AGENT, "")[1].id
    _file(root, "tq-00A4").write_bytes(_corrected(root, "tq-00A4", "whose", "with"))
    _refused(root, "changed", acts.take, other, PERSON)


def test_a_correction_that_fails_the_librarys_checks_now_is_refused_with_their_diagnostics(root: Path) -> None:
    acts.check(root, "tq-00K5", _hash(root, "tq-00K5"), PERSON)
    proposal = acts.propose(root, "tq-00K5", _corrected(root, "tq-00K5", 'uses = ["tq-00A4"]', 'uses = ["tq-00A4", "tq-00K3"]'), AGENT, "")[1].id  # fmt: skip
    _file(root, "tq-00K3").unlink()
    refusal = _refused(root, "refused", acts.take, proposal, PERSON)
    assert refusal.diagnostics


def test_declining_keeps_the_text_and_closes_the_proposal(root: Path) -> None:
    proposal = _filed(root)
    _refused(root, "author-only", acts.decline, proposal, AGENT)
    record = acts.decline(root, proposal, PERSON)
    assert record.kind == "declined" and record.get("proposal") == proposal
    assert _status(root, "tq-00A4").proposal is None and _status(root, "tq-00A4").reading == "matches"


def test_a_persons_own_correction_is_written_and_matched_with_the_paper_at_once(root: Path) -> None:
    shown = _hash(root, "tq-00A4")
    body = "A \\emph{widget} is a closed set $W \\subset \\mathbb{R}^n$ whose boundary lies in $\\Wid$.\n"
    record = acts.correct(root, "tq-00A4", shown, body, PERSON)
    text = _file(root, "tq-00A4").read_text(encoding="utf-8")
    assert text.endswith(body) and 'pages = "4"' in text
    assert record.kind == "compared" and record.on is not None and record.on.hash == _hash(root, "tq-00A4")
    found = _status(root, "tq-00A4")
    assert found.reading == "matches" and found.how == "written"


def test_a_persons_correction_is_refused_when_changed_a_stub_or_failing_the_checks(root: Path) -> None:
    shown = _hash(root, "tq-00A4")
    _refused(root, "author-only", acts.correct, "tq-00A4", shown, "A set.\n", AGENT)
    _refused(root, "stub", acts.correct, "tq-00B7", _hash(root, "tq-00B7"), "A lemma.\n", PERSON)
    refusal = _refused(root, "refused", acts.correct, "tq-00A4", shown, "See Lemma~\\ref{tq-77ZZ}.\n", PERSON)
    assert refusal.diagnostics
    _file(root, "tq-00A4").write_bytes(_corrected(root, "tq-00A4", "compact", "closed"))
    _refused(root, "changed", acts.correct, "tq-00A4", shown, "A set.\n", PERSON)


def test_how_a_node_was_made_is_recorded_on_its_text_now_by_the_hand_that_made_it(root: Path) -> None:
    source = {"ref": "tq-00A1-ref", "tex": "sha256:9e02f7d4b1a865c3097e4f2ab8d6c1e5730f9a24b6d8c0e1f3a57b92d4c6e801"}
    record = acts.digested(root, "tq-00K3", LOOM, "extracted", source)
    assert record.on is not None and record.on.hash == _hash(root, "tq-00K3")
    assert _status(root, "tq-00K3").how == "extracted"
    _refused(root, "refused", acts.digested, "tq-00K3", AGENT, "extracted", source)
    _refused(root, "stub", acts.digested, "tq-00B7", LOOM, "extracted", source)
    _refused(root, "no-such-node", acts.digested, "tq-9999", LOOM, "extracted", source)


# ---- attesting a Lean statement ---------------------------------------------------------------------------------------


def _lean(root: Path, on: Subject, names: dict[str, str], *, ok: bool = True) -> Record:
    declaration = {"name": "lem", "kind": "theorem", "role": "states", "names": names, "statement": "sha256:" + "5" * 64, "axioms": [], "sorry": False}  # fmt: skip
    return write(root, "lean", LOOM, on=on, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64}, files={"lean/A.lean": "sha256:" + "8" * 64}, declarations=[declaration], assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=ok)  # fmt: skip


def _attest(root: Path, web: Any, here: Here, observation: str, by: Who = PERSON) -> Record:
    return acts.attest(root, web, here, observation, by, lean_now=lambda r: True)


def test_attesting_a_library_result_waits_for_it_and_all_it_uses_to_be_read_and_compared(root: Path) -> None:
    web, here = LibraryWeb(root), Here("node", "tq-00K3")
    on = web.subject(here)
    assert on is not None
    record = _lean(root, on, {"node": "tq-00K3"})
    refusal = _refused(root, "unchecked", _attest, web, here, record.id)
    assert "tq-00K3" in str(refusal) and "tq-00A4" in str(refusal)
    for node in ("tq-00K3", "tq-00A4"):
        acts.check(root, node, _hash(root, node), PERSON)
    _refused(root, "author-only", _attest, LibraryWeb(root), here, record.id, AGENT)
    attested = _attest(root, LibraryWeb(root), here, record.id)
    assert attested.get("closure") == [{"node": "tq-00A4", "hash": _hash(root, "tq-00A4")}]
    assert attested.get("statements") == {"lem": "sha256:" + "5" * 64} and attested.get("lean") == record.id
    # its work's macros are not read yet, so its notation is unknown and it does not read formalized
    assert _status(root, "tq-00K3").lean == "unattested"


def test_attesting_is_of_the_latest_lean_lean_accepted_on_the_text_now(root: Path) -> None:
    web, here = LibraryWeb(root), Here("node", "tq-00A4")
    on = web.subject(here)
    assert on is not None
    acts.check(root, "tq-00A4", on.hash, PERSON)
    _refused(root, "no-lean", _attest, web, here, "ev-2026-11-21-zzzzzz")
    failed = _lean(root, on, {"node": "tq-00A4"}, ok=False)
    _refused(root, "no-lean", _attest, web, here, failed.id)
    accepted = _lean(root, on, {"node": "tq-00A4"})
    _refused(root, "changed", _attest, web, here, failed.id)
    _refused(root, "no-such-result", _attest, web, Here("node", "tq-9999"), accepted.id)
    _file(root, "tq-00A4").write_bytes(_corrected(root, "tq-00A4", "compact", "closed"))
    _refused(root, "no-lean", _attest, LibraryWeb(root), here, accepted.id)


class _Draft(Nothing):
    """One draft result, `lem:a`, typeset with one command of the person's and citing what `cites` says."""

    def __init__(self, cites: list[str]) -> None:
        self.cites = cites

    def subject(self, here: Here) -> Subject | None:
        return Subject("label", "lem:a", "sha256:" + "a" * 64) if here.kind == "block" else None

    def notation(self, here: Here) -> dict[str, str] | None:
        return {"Zcyc": "sha256:" + "c" * 64}

    def cited(self, here: Here) -> list[str]:
        return self.cites


def test_attesting_a_drafts_result_attests_the_notation_it_was_shown_and_waits_for_its_citations(root: Path) -> None:
    here = Here("block", "k1")
    on = _Draft([]).subject(here)
    assert on is not None
    record = _lean(root, on, {"label": "lem:a"})
    refusal = _refused(root, "unchecked", _attest, _Draft(["Cal14 Theorem 2"]), here, record.id)
    assert "Cal14 Theorem 2" in str(refusal)
    attested = _attest(root, _Draft([]), here, record.id)
    macros = replay(root).about("macro", "Zcyc", of="attested")
    assert [m.on.hash for m in macros if m.on is not None] == ["sha256:" + "c" * 64]
    assert attested.on == on and attested.get("closure") == []
    # a row attested in its definition now is not attested again
    _attest(root, _Draft([]), here, record.id)
    assert len(replay(root).about("macro", "Zcyc", of="attested")) == 1
