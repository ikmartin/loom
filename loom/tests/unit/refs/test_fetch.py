"""Downloading an arXiv source or PDF (`refs.fetch`) through a stand-in for the network: the answer kept under arXiv's name, a burst or an outage retried, and a refusal said."""

from __future__ import annotations

import io
import urllib.error
from collections.abc import Iterator
from pathlib import Path

import pytest

from loom.refs import fetch
from loom.refs.fetch import ARXIV, USER_AGENT, FetchRefused, arxiv_pdf, arxiv_source, get

PDF = b"%PDF-1.4\n% a paper\n"
GZ = b"\x1f\x8b\x08\x00 a gzipped tar"


class Answer:
    """What the stand-in urlopen returns: a body read once, as a response is."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> Answer:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[list[object], list[tuple[str, dict[str, str]]]]]:
    """A stand-in for the network: give it what each request answers, in order, a body or an error; it records each request's address and headers. No pause between attempts."""
    answers: list[object] = []
    asked: list[tuple[str, dict[str, str]]] = []

    def urlopen(req: object, timeout: float = 0) -> Answer:
        asked.append((req.full_url, dict(req.header_items())))  # type: ignore[attr-defined]
        said = answers.pop(0)
        if isinstance(said, Exception):
            raise said
        assert isinstance(said, bytes)
        return Answer(said)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(fetch.time, "sleep", lambda _s: None)
    yield answers, asked


def http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://export.arxiv.org/x", code, "said so", {}, io.BytesIO())  # type: ignore[arg-type]


def test_a_download_says_who_asks_and_returns_the_body(network: tuple[list[object], list]) -> None:
    answers, asked = network
    answers.append(b"body")
    assert get("https://export.arxiv.org/x") == b"body"
    [(url, headers)] = asked
    assert url == "https://export.arxiv.org/x" and headers["User-agent"] == USER_AGENT


@pytest.mark.parametrize("busy", [http(406), http(429), http(503), urllib.error.URLError("no route")])
def test_a_burst_or_an_outage_is_asked_again(network: tuple[list[object], list], busy: Exception) -> None:
    answers, asked = network
    answers += [busy, busy, b"at last"]
    assert get("https://export.arxiv.org/x") == b"at last" and len(asked) == 3


def test_after_the_last_attempt_the_refusal_says_why(network: tuple[list[object], list]) -> None:
    answers, asked = network
    answers += [http(503)] * 3
    with pytest.raises(FetchRefused, match="HTTP 503 said so"):
        get("https://export.arxiv.org/x")
    assert len(asked) == 3


def test_a_paper_that_is_not_there_is_not_asked_for_again(network: tuple[list[object], list]) -> None:
    answers, asked = network
    answers.append(http(404))
    with pytest.raises(FetchRefused, match="HTTP 404"):
        get("https://export.arxiv.org/x")
    assert len(asked) == 1


def test_a_source_is_kept_under_arxiv_s_name_or_as_the_pdf_arxiv_holds_instead(
    network: tuple[list[object], list], tmp_path: Path
) -> None:
    answers, asked = network
    answers += [GZ, PDF, GZ]
    made = arxiv_source("2401.01234v2", tmp_path / "in")
    assert made == tmp_path / "in" / "2401.01234v2.gz" and made.read_bytes() == GZ
    assert arxiv_source("2402.00001", tmp_path / "in").name == "2402.00001.pdf"
    assert arxiv_source("math/0601001", tmp_path / "in").name == "math_0601001.gz"
    assert [url for url, _h in asked] == [
        f"{ARXIV}/e-print/2401.01234v2",
        f"{ARXIV}/e-print/2402.00001",
        f"{ARXIV}/e-print/math/0601001",
    ]


def test_a_pdf_is_kept_and_an_answer_that_is_no_pdf_refused(network: tuple[list[object], list], tmp_path: Path) -> None:
    answers, asked = network
    answers += [PDF, b"<html>not found</html>"]
    assert arxiv_pdf("2401.01234", tmp_path).read_bytes() == PDF
    with pytest.raises(FetchRefused, match="did not return a PDF"):
        arxiv_pdf("2401.09999", tmp_path)
    assert not (tmp_path / "2401.09999.pdf").exists()
    assert [url for url, _h in asked] == [f"{ARXIV}/pdf/2401.01234", f"{ARXIV}/pdf/2401.09999"]
