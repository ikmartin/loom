"""Loom's own work on the works a draft cites, unasked (`library.unasked`): tried once for what each holds, compiling nothing, fetching only under `online`."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library import documents, log
from loom.library.gather import gather
from loom.library.references import attach
from loom.library.store import read
from loom.library.stubs import make
from loom.library.unasked import Unasked, attempt, due, key_of, wanted
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan

MAIN = r"""\documentclass{article}
\begin{document}
By \cite[Lemma 2.1]{Smi24}, \cite[Theorem 3]{Jon19} and \cite[Proposition 4.2]{Arx24}; \cite{Bare25} alone.
\bibliography{refs}
\end{document}
"""
BIB = (
    "@article{Smi24,\n  author = {Smith, Jane},\n  title = {Widgets},\n  year = {2024},\n}\n"
    "@article{Jon19,\n  author = {Jones, Alex},\n  title = {Gadgets},\n  year = {2019},\n}\n"
    "@article{Arx24,\n  author = {Arden, Elspeth},\n  title = {Towers},\n  year = {2024},\n  eprint = {2401.01234},\n  archiveprefix = {arXiv},\n}\n"
    "@article{Bare25,\n  author = {Bare, Ben},\n  title = {Nothing cited},\n  year = {2025},\n}\n"
)
SOURCE = "\\documentclass{article}\n\\newtheorem{lemma}{Lemma}[section]\n\\begin{document}\n\\section{One}\n\\begin{lemma}Every widget is bounded.\\end{lemma}\n\\end{document}\n"
ME = {"by": "A. Author", "kind": "person"}


def quilt(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A quilt whose draft cites three works by result and one alone, their references and the three stubs made: the works by key."""
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(MAIN)
    (root / "refs.bib").write_text(BIB)
    result = scan(load_quilt(root))
    gather(result)
    make(result)
    return root, dict(result.refs)


def given_source(root: Path, ref: str, tmp_path: Path) -> str:
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "main.tex").write_text(SOURCE)
    tex = documents.put_source(root, folder)
    attach(root, ref, "tex", tex, **ME)
    return tex


def a_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    return path


def tried(root: Path, ref: str) -> list[dict]:
    return [a for a in log.replay(root).of(ref) if a.get("event") == "tried"]


def test_the_works_the_stubs_name_are_due_and_a_work_cited_alone_is_not(tmp_path: Path) -> None:
    root, refs = quilt(tmp_path)
    assert wanted(root) == sorted([refs["Smi24"], refs["Jon19"], refs["Arx24"]])
    assert refs["Bare25"] not in due(root)


def test_a_work_with_a_source_is_surveyed_and_compiles_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.library import survey

    root, refs = quilt(tmp_path)
    smith = refs["Smi24"]
    given_source(root, smith, tmp_path)

    def compiled(*_a: object, **_k: object) -> None:
        raise AssertionError("the unasked job compiles nothing")

    monkeypatch.setattr(survey, "compile_marks", compiled)
    done = attempt(root, smith, online=False)
    assert done is not None and (done.outcome, done.why) == ("surveyed", "no-pdf"), done
    assert [(a["on"], a["outcome"]) for a in tried(root, smith)] == [(key_of(read(root, smith), ["2.1"]), "surveyed")]  # type: ignore[arg-type]
    assert smith not in due(root), "tried once for what it holds"


def test_a_work_held_only_as_a_pdf_waits_for_a_reader_and_no_ask_is_written(tmp_path: Path) -> None:
    from loom.evidence.asks import replay

    root, refs = quilt(tmp_path)
    jones = refs["Jon19"]
    attach(root, jones, "pdf", documents.put_pdf(root, a_pdf(tmp_path / "j.pdf")), **ME)
    done = attempt(root, jones, online=True)
    assert done is not None and (done.outcome, done.why) == ("waiting", "pdf-only")
    assert not replay(root).asks, "an ask is a person's to make"


def test_with_the_network_off_nothing_is_fetched_and_the_try_waits_to_be_made_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.refs import fetch

    root, refs = quilt(tmp_path)
    arden = refs["Arx24"]

    def refused(*_a: object, **_k: object) -> None:
        raise AssertionError("nothing is fetched with the network off")

    monkeypatch.setattr(fetch, "arxiv_pdf", refused)
    monkeypatch.setattr(fetch, "arxiv_source", refused)
    done = attempt(root, arden, online=False)
    assert done is not None and done.held and tried(root, arden) == []
    assert arden in due(root), "tried again once the network is allowed"


def test_online_arxiv_s_pdf_and_source_are_fetched_and_filed_under_the_work_its_entry_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.refs import fetch

    root, refs = quilt(tmp_path)
    arden = refs["Arx24"]
    asked: list[str] = []

    def pdf(ident: str, dest: Path, *, attempts: int) -> Path:
        assert attempts == 1, "one request, never repeated"
        asked.append(f"pdf {ident}")
        return a_pdf(dest / f"{ident}.pdf")

    def source(ident: str, dest: Path, *, attempts: int) -> Path:
        import gzip

        assert attempts == 1, "one request, never repeated"
        asked.append(f"source {ident}")
        dest.mkdir(parents=True, exist_ok=True)
        got = dest / f"{ident}.gz"
        got.write_bytes(gzip.compress(SOURCE.encode()))
        return got

    monkeypatch.setattr(fetch, "arxiv_pdf", pdf)
    monkeypatch.setattr(fetch, "arxiv_source", source)
    done = attempt(root, arden, online=True)
    node = read(root, arden)
    assert asked == ["pdf 2401.01234", "source 2401.01234"], "one request at a time, the PDF first"
    assert node is not None and node.pdf and node.tex and done is not None and not done.held
    assert [(a["which"], a["by"]) for a in log.replay(root).of(arden) if a.get("event") == "filed"] == [
        ("pdf", "loom"),
        ("tex", "loom"),
    ]
    assert [a["on"] for a in tried(root, arden)] == [key_of(node, ["4.2"])] and arden not in due(root)


def test_the_server_s_worker_tries_a_work_once_however_often_it_is_asked(tmp_path: Path) -> None:
    root, refs = quilt(tmp_path)
    smith = refs["Smi24"]
    given_source(root, smith, tmp_path)
    worker = Unasked(root, online=lambda: False)
    try:
        worker.want([smith, smith])
        worker.want([smith])
        assert worker.idle(30)
    finally:
        worker.stop()
    assert len(tried(root, smith)) == 1


def test_a_work_is_tried_again_once_a_draft_cites_another_of_its_results(tmp_path: Path) -> None:
    root, refs = quilt(tmp_path)
    smith = refs["Smi24"]
    given_source(root, smith, tmp_path)
    attempt(root, smith, online=False)
    assert smith not in due(root)
    (root / "main.tex").write_text(MAIN.replace("By ", "By \\cite[Lemma 9.9]{Smi24}, "))
    make(scan(load_quilt(root)))
    assert smith in due(root), "a stub of it it was not tried for"


def test_a_refused_fetch_is_asked_once_recorded_and_not_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's D-22, ruled: one request for each document of a work and no retry; a refusal is recorded and shown, and tried again only when what the work holds changes or the person asks."""
    from loom.refs import fetch

    root, refs = quilt(tmp_path)
    arden = refs["Arx24"]
    asked: list[str] = []

    def refused(ident: str, dest: Path, *, attempts: int) -> Path:
        asked.append(f"{ident} {attempts}")
        raise fetch.FetchRefused(f"arxiv.org/pdf/{ident}: HTTP 503 Service Unavailable")

    monkeypatch.setattr(fetch, "arxiv_pdf", refused)
    monkeypatch.setattr(fetch, "arxiv_source", refused)
    done = attempt(root, arden, online=True)
    assert done is not None and done.outcome == "failed" and "503" in (done.why or "")
    assert asked == ["2401.01234 1"], "the PDF asked once; the source never, the work's fetch having failed"
    assert [a["outcome"] for a in tried(root, arden)] == ["failed"] and arden not in due(root)
