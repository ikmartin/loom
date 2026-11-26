"""Recognising a pasted identifier, and looking one up against services faked here: what is found, what names nothing, what could not be asked, and what loom does not look up; and the key a new work's entry is given."""

from __future__ import annotations

import json
from typing import Any

import pytest

from loom.refs.lookup import LookupRefused, NothingFound, key_for, look_up, recognise

CSL = {
    "type": "article-journal",
    "title": "Widget categories and their duals",
    "author": [{"family": "Ostrander", "given": "D."}, {"family": "Vale", "given": "E."}],
    "issued": {"date-parts": [[2018, 3]]},
    "container-title": "J. Widget Theory",
    "DOI": "10.5555/widget.2018.031",
}
ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/0805.2065v2</id>
    <published>2008-05-14T00:00:00Z</published>
    <title>Virtual
      pull-backs</title>
    <author><name>Cristina Manolache</name></author>
    <arxiv:doi>10.1090/S1056-3911-2011-00606-1</arxiv:doi>
  </entry>
</feed>"""
ATOM_ERROR = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#incorrect_id_format</id><title>Error</title></entry></feed>"""


def fake(answers: dict[str, Any]) -> Any:
    """An `http` answering each URL whose start it matches with bytes, a JSON-able value, or an exception to raise."""
    asked: list[tuple[str, dict[str, str]]] = []

    def http(url: str, headers: dict[str, str]) -> bytes:
        asked.append((url, headers))
        for start, answer in answers.items():
            if url.startswith(start):
                if isinstance(answer, Exception):
                    raise answer
                return answer if isinstance(answer, bytes) else json.dumps(answer).encode()
        raise AssertionError(f"unexpected request {url}")

    http.asked = asked  # type: ignore[attr-defined]
    return http


def test_a_doi_is_asked_of_doi_org_and_found() -> None:
    http = fake({"https://doi.org/10.5555/widget.2018.031": CSL})
    got = look_up("https://doi.org/10.5555/widget.2018.031", online=True, http=http)
    assert got.state == "found" and got.kind == "doi"
    assert got.entry["title"] == "Widget categories and their duals" and got.entry["year"] == "2018"
    assert got.entry["author"] == "Ostrander, D. and Vale, E." and got.entry["journal"] == "J. Widget Theory"
    assert key_for(got.entry, set()) == "ostranderWidgetCategoriesTheir2018"
    # content negotiation, so every registry's DOIs answer
    assert http.asked[0][1]["Accept"] == "application/vnd.citationstyles.csl+json"


def test_a_doi_that_names_nothing_did_not_resolve() -> None:
    http = fake({"https://doi.org/": NothingFound("https://doi.org/10.9999/x")})
    got = look_up("10.9999/not.a.real.doi", online=True, http=http)
    assert got.state == "missing" and "did not resolve" in got.message and "10.9999/not.a.real.doi" in got.message


def test_an_arxiv_id_is_found() -> None:
    got = look_up("arXiv:0805.2065", online=True, http=fake({"https://export.arxiv.org/api/query": ATOM}))
    assert got.state == "found"
    assert got.entry["title"] == "Virtual pull-backs" and got.entry["author"] == "Manolache, Cristina"
    assert got.entry["eprint"] == "0805.2065" and got.entry["year"] == "2008"
    assert key_for(got.entry, set()) == "manolacheVirtualPullBacks2008"


def test_an_arxiv_id_arxiv_does_not_have_is_missing() -> None:
    got = look_up("2499.99999", online=True, http=fake({"https://export.arxiv.org/api/query": ATOM_ERROR}))
    assert got.state == "missing" and "arXiv has no paper" in got.message


def test_a_service_that_cannot_be_reached_says_why() -> None:
    http = fake(
        {"https://doi.org/": LookupRefused("https://doi.org/10.5555/x: [Errno 8] nodename nor servname provided")}
    )
    got = look_up("10.5555/x", online=True, http=http)
    assert got.state == "unreachable" and "nodename" in got.message


def test_without_the_network_an_identifier_is_not_looked_up() -> None:
    def never(url: str, headers: dict[str, str]) -> bytes:
        raise AssertionError("asked the network offline")

    assert look_up("10.5555/x", online=False, http=never).state == "offline"


@pytest.mark.parametrize(
    ("text", "kind"), [("ISBN 978-0-387-98549-7", "isbn"), ("MR1667326", "mr"), ("widgets, somewhere", "unknown")]
)
def test_what_loom_does_not_look_up_asks_for_more(text: str, kind: str) -> None:
    got = look_up(text, online=True, http=fake({}))
    assert got.state == "cannot" and got.kind == kind and "DOI" in got.message


def test_a_key_is_better_bibtexs_and_never_one_taken() -> None:
    """`auth.lower + shorttitle(3,3) + year`, the key Better BibTeX gives by default and the author's own export uses; a part not known is left out, never guessed."""
    assert key_for({"author": "Ångström, A. and Euler, L.", "year": "1999"}, set()) == "angstrom1999"
    assert (
        key_for({"author": "Cox, John C.", "title": "Option pricing: A simplified approach", "year": "1979"}, set())
        == "coxOptionPricingSimplified1979"
    )
    assert (
        key_for(
            {"author": "Perelman, Grisha", "title": "Ricci flow with surgery on three-manifolds", "year": "2003"}, set()
        )
        == "perelmanRicciFlowSurgery2003"
    )
    assert (
        key_for({"author": "Shreve, Steven E.", "title": "Stochastic Calculus for Finance II"}, set())
        == "shreveStochasticCalculusFinance"
    )
    godel = {"author": r"G{\"o}del, Kurt", "title": r"{\"U}ber formal unentscheidbare S{\"a}tze", "year": "1931"}
    assert key_for(godel, set()) == "godelUberFormalUnentscheidbare1931"
    assert key_for({"author": "Kresch, Andrew", "year": "1999"}, {"kresch1999", "kresch1999a"}) == "kresch1999b"
    assert key_for({"title": "1 2 3"}, set()) == "untitled"


@pytest.mark.parametrize(
    ("text", "kind", "value"),
    [
        ("10.1007/s002220050351", "doi", "10.1007/s002220050351"),
        ("doi:10.1090/S1056-3911-2011-00606-1", "doi", "10.1090/S1056-3911-2011-00606-1"),
        ("https://doi.org/10.1112/S0010437X20007393.", "doi", "10.1112/S0010437X20007393"),
        ("http://dx.doi.org/10.1007/BF01234659", "doi", "10.1007/BF01234659"),
        # arXiv's own DOI names a preprint
        ("10.48550/arXiv.2207.01652", "arxiv", "2207.01652"),
        ("arXiv:0805.2065", "arxiv", "0805.2065"),
        ("0805.2065v2", "arxiv", "0805.2065v2"),
        ("https://arxiv.org/abs/2207.01652v3", "arxiv", "2207.01652v3"),
        ("https://arxiv.org/pdf/2207.01652.pdf", "arxiv", "2207.01652"),
        ("math/9810166", "arxiv", "math/9810166"),
        ("arXiv:math.AG/9810166v2", "arxiv", "math.AG/9810166v2"),
        ("solv-int/9901001", "arxiv", "solv-int/9901001"),
        ("Zbl 0921.14007", "zbl", "0921.14007"),
        ("https://zbmath.org/?q=an:0921.14007", "zbl", "0921.14007"),
        ("MR1667326", "mr", "1667326"),
        ("MR 1667326", "mr", "1667326"),
        ("ISBN 978-0-387-98549-7", "isbn", "9780387985497"),
        ("0-387-98549-2", "isbn", "0387985492"),
    ],
)
def test_each_identifier_is_recognised_in_each_form(text: str, kind: str, value: str) -> None:
    got = recognise(text)
    assert (got.kind, got.value) == (kind, value), got


@pytest.mark.parametrize(
    "text",
    ["", "somewhere I read about widgets", "978-0-387-98549-8", "10.1/x", "@article{X, title={y}}", "MR12"],
)
def test_what_is_none_of_them_is_not_recognised(text: str) -> None:
    """A wrong ISBN check digit, a prefix too short for a DOI, an entry with no body: none is guessed at."""
    assert recognise(text).kind == "unknown"
