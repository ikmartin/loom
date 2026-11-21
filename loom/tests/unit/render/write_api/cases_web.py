"""The cases of the Web's reads, over the drafts of the synthetic quilt (`docs/specs/evidence.md` §8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.render.write_api._cases import Serve, case, refuses, succeeds, synthetic

DOC = "drafting/main.tex"


@case("web-list")
def _web_list(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    listed = succeeds(s, "web-list", {"scope": "draft", "doc": DOC})
    [section] = listed["sections"]
    assert section["head"] == "draft" and listed["count"] == len(section["rows"]) > 0
    assert {"result", "name", "taxon", "source", "paper", "lean"} <= set(section["rows"][0])
    refuses(s, "web-list", {"scope": "draft"}, 400, "bad-field", "names a draft")


@case("web-group")
def _web_group(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    opened = succeeds(s, "web-group", {"scope": "all", "group": DOC})
    assert opened["group"] == DOC and opened["n"] == len(opened["rows"]) > 0
    refuses(s, "web-group", {"scope": "everything", "group": DOC}, 400, "bad-field", "scope is one of")


@case("web-search")
def _web_search(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    found = succeeds(s, "web-search", {"scope": "all", "q": "Definition"})
    assert found["count"] >= 1 and found["hits"][0]["row"]["name"].startswith("Definition")
    refuses(s, "web-search", {"scope": "all", "q": "x", "limit": 0}, 400, "bad-field", "limit")


@case("web-focus")
def _web_focus(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    card = succeeds(s, "web-focus", {"scope": "all", "result": "sy-0001", "more": True})
    assert card["row"]["result"] == "sy-0001" and card["statement"]["fragment"] and "proofs" in card["more"]
    refuses(s, "web-focus", {"scope": "all", "result": "sy-9999"}, 404, "no-such-result", "sy-9999")


@case("web-graph")
def _web_graph(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    drawn = succeeds(s, "web-graph", {"scope": "all", "result": "sy-0001"})
    assert drawn["focus"]["result"] == "sy-0001" and set(drawn["columns"]) == {"back", "uses", "used_by"}
    refuses(s, "web-graph", {"scope": "all", "result": "sy-9999"}, 404, "no-such-result", "sy-9999")
