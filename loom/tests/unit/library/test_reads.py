"""The Library's reads of a work and its results (`library.reads`, `library.places`), held to what `library-views.md` §8 says each must not do."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from loom.library import reads, survey
from loom.library.digest import digest, of_work
from loom.library.places import places
from loom.library.store import read
from loom.paths import LIBRARY_SURVEYS
from loom.scan.quilt import load_quilt
from loom.scan.scan import ScanResult, scan
from tests.unit._quilts import showcase

pytestmark = pytest.mark.poppler

ARDEN, BELLAMY = "sh-0402-ref", "sh-0403-ref"


def scanned(tmp_path: Path) -> ScanResult:
    return scan(load_quilt(showcase(tmp_path)))


def digested(result: ScanResult) -> str:
    """Arden 2024 digested whole; the id of its Lemma 2.2."""
    root = result.quilt.root
    work = read(root, ARDEN)
    assert work is not None
    s = reads.surveyed(root, work)
    assert s is not None
    digest(result, ARDEN, [i.item for i in s.items], s)
    return next(n.id for n in of_work(root, ARDEN) if n.label == "lem:saturated")


def test_a_work_s_outline_compiles_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def compiled(*_a: object, **_k: object) -> None:
        raise AssertionError("a read compiles nothing; the survey's compile is the person's act")

    monkeypatch.setattr(survey, "compile_marks", compiled)
    said = reads.work(scanned(tmp_path), ARDEN)
    assert said["outline"]["state"] == "ready" and len(said["outline"]["items"]) >= 8
    assert said["outline"]["uncounted"] is None, "the showcase's Arden 2024 keeps its equations' numbers"


def test_the_list_s_count_makes_no_survey(tmp_path: Path) -> None:
    result = scanned(tmp_path)
    kept = result.quilt.root / LIBRARY_SURVEYS
    before = sorted(kept.glob("*.json")) if kept.is_dir() else []
    assert reads.scopes(result, None)["used"] >= 1
    assert (sorted(kept.glob("*.json")) if kept.is_dir() else []) == before, "only a work's `all` makes its survey"
    reads.scopes(result, ARDEN)
    assert sorted(kept.glob("*.json")) != before


def test_a_node_reads_no_survey_and_no_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.library import documents

    result = scanned(tmp_path)
    lemma = digested(result)

    def touched(*_a: object, **_k: object) -> Any:
        raise AssertionError("a node's read opens its file, its macros node's and the index alone")

    monkeypatch.setattr(survey, "kept", touched)
    monkeypatch.setattr(documents, "source_dir", touched)
    said = reads.node(result, lemma)
    assert said["name"] == "Lemma 2.2" and said["digested"]["how"] == "extracted"
    assert said["work"] == {"ref": ARDEN, "short": "Arden 2024", "pdf": read(result.quilt.root, ARDEN).pdf}  # type: ignore[union-attr]


def test_a_node_s_place_reads_its_page_s_words_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = scanned(tmp_path)
    lemma = digested(result)
    first = places(result, ARDEN, node=lemma).places
    assert [p["node"] for p in first] == [lemma] and first[0]["page"] == 2 and first[0]["rects"]
    ran: list[list[str]] = []
    real = subprocess.run

    def counted(args: list[str], *a: Any, **k: Any) -> Any:
        ran.append(list(args))
        return real(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", counted)
    assert places(result, ARDEN, node=lemma).places == first
    assert not [a for a in ran if a and str(a[0]).endswith("pdftotext")], "the page's words are kept by the PDF's hash"


def test_a_guess_marks_nothing(tmp_path: Path) -> None:
    from loom.paths import ANNOTATION_LOG

    result = scanned(tmp_path)
    log = result.quilt.root / ANNOTATION_LOG
    before = log.read_bytes() if log.is_file() else b""
    found = reads.find(result, BELLAMY, "median order")
    assert found["hits"] and (log.read_bytes() if log.is_file() else b"") == before
