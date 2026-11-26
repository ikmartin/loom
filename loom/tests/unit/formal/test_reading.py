"""An agent's reading of a result's Lean: an agent's record only, each part naming a declaration loom recorded and the person reads, stale once a newer `lean` record states the result."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence.log import EvidenceRefused, replay, write
from loom.evidence.subjects import Subject, Who
from loom.formal import reading

H = "sha256:" + "a" * 64
H2 = "sha256:" + "b" * 64
AGENT = Who("agent", "Reader Agent")
PERSON = Who("person", "A. Author")
LOOM = Who("loom")
RESULT = Subject("label", "lem:balanced", H)


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    return tmp_path


def _decl(name: str, kind: str, role: str, names: dict | None, means: list[str]) -> dict:
    return {"name": name, "kind": kind, "role": role, "names": names, "statement": H, "axioms": [], "sorry": False, "means": means, "shown": f"{kind} {name}"}  # fmt: skip


def _lean(root: Path, on: Subject = RESULT) -> str:
    return write(
        root,
        "lean",
        LOOM,
        on=on,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": H},
        files={"lean/A.lean": H},
        declarations=[
            _decl("F.balanced", "theorem", "states", {"label": "lem:balanced"}, ["F.Z"]),
            _decl("F.lemma", "theorem", "supports", None, ["F.Z"]),
            _decl("F.Z", "def", "states", {"label": "def:cycle"}, ["F.W"]),
            _decl("F.W", "def", "supports", None, []),
        ],
        assumed=[],
        uses=[],
        replay={"tool": "t", "exit": 0, "output": ""},
        ok=True,
    ).id


PART = {
    "part": "",
    "draft": "Every $w$ vanishes.",
    "declaration": "F.balanced",
    "reading": "If $w$ is balanced, $w = 0$.",
}


def test_a_reading_names_the_latest_record_and_its_text_and_reads_back(root: Path) -> None:
    lean = _lean(root)
    made = reading.write(root, "lem:balanced", AGENT, [PART, {**PART, "part": "Z", "declaration": "F.W"}], None)
    assert made.on == RESULT and made.get("lean") == lean and made.by == AGENT
    found = replay(root)
    assert found.problems == [] and reading.latest(found, "label", "lem:balanced") == made
    assert not reading.stale(found, made)
    assert reading.read_names(found.by_id(lean)) == ["F.balanced", "F.Z", "F.W"]


def test_a_part_naming_a_declaration_loom_did_not_record_or_the_person_does_not_read_is_refused(root: Path) -> None:
    _lean(root)
    for name in ("F.made_up", "F.lemma"):
        with pytest.raises(reading.Refused) as exc:
            reading.write(root, "lem:balanced", AGENT, [{**PART, "declaration": name}], None)
        assert exc.value.code == "no-such-declaration" and name in str(exc.value)
    assert replay(root).of_kind("reading") == []


def test_a_result_with_no_record_or_a_record_no_longer_the_latest_is_refused(root: Path) -> None:
    with pytest.raises(reading.Refused) as exc:
        reading.write(root, "lem:balanced", AGENT, [PART], None)
    assert exc.value.code == "no-lean"
    first = _lean(root)
    _lean(root)
    with pytest.raises(reading.Refused) as exc:
        reading.write(root, "lem:balanced", AGENT, [PART], None, record=first)
    assert exc.value.code == "changed"


def test_only_an_agent_writes_a_reading_and_it_is_refused_from_a_person(root: Path) -> None:
    _lean(root)
    with pytest.raises(reading.Refused) as exc:
        reading.write(root, "lem:balanced", PERSON, [PART], None)
    assert exc.value.code == "refused" and "agent" in str(exc.value)
    with pytest.raises(EvidenceRefused):
        write(root, "reading", LOOM, on=RESULT, lean="ev-2026-11-21-x", parts=[PART], difference=None)


def test_a_reading_is_stale_once_a_newer_lean_record_states_its_result_on_any_text(root: Path) -> None:
    _lean(root)
    made = reading.write(root, "lem:balanced", AGENT, [PART], "The draft fixes no $a_0$.")
    assert made.get("difference") == "The draft fixes no $a_0$."
    _lean(root, Subject("label", "lem:balanced", H2))
    assert reading.stale(replay(root), made)


def test_two_parts_of_one_name_are_refused(root: Path) -> None:
    _lean(root)
    with pytest.raises(reading.Refused) as exc:
        reading.write(root, "lem:balanced", AGENT, [PART, PART], None)
    assert exc.value.code == "refused"
