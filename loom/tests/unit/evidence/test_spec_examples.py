"""The examples in `docs/specs/evidence.md` are what the code reads and writes: every line parses, is written back byte for byte, and between them they show every kind of record and every event."""

from __future__ import annotations

import json
import re
from pathlib import Path

from loom.evidence import asks, log

SPEC = Path(__file__).resolve().parents[4] / "docs" / "specs" / "evidence.md"


def _lines() -> list[str]:
    text = SPEC.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    assert blocks, "docs/specs/evidence.md has no json examples"
    return [line for block in blocks for line in block.splitlines() if line.strip()]


def _compact(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_every_example_is_written_as_loom_writes_it() -> None:
    for line in _lines():
        assert _compact(json.loads(line)) == line, line


def test_every_evidence_example_reads_and_every_kind_is_shown() -> None:
    kinds = set()
    for line in _lines():
        raw = json.loads(line)
        if "event" in raw:
            continue
        record = log.parse(raw)
        kinds.add(record.kind)
    assert kinds == set(log.KINDS)


def test_every_ask_example_reads_and_events_find_their_asks() -> None:
    text = "\n".join(line for line in _lines() if '"event"' in line)
    found = asks._read(text)
    assert found.problems == []
    events = {json.loads(line)["event"] for line in text.splitlines()}
    assert events >= {"asked", "took", "answered", "withdrawn"}
    assert {a.what for a in found.asks.values()} == {"read", "paper", "question"}
    question = found.asks["t-2026-11-21-w2c6ga"]
    assert question.answers[0]["choice"] == 1


def test_the_spec_names_every_kind_and_every_what() -> None:
    text = SPEC.read_text(encoding="utf-8")
    for kind in log.KINDS:
        assert f"`{kind}`" in text, kind
    for what in asks.WHATS:
        assert f"| `{what}` |" in text, what
    for how in log.HOWS:
        assert f"| `{how}` |" in text, how
