"""The cases of Review's endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    Serve,
    case,
    refuses,
    succeeds,
    synthetic,
)


@case("review-accept")
def _review_accept(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.records.store import Records
    from loom.scan.quilt import load_quilt

    s, root = synthetic(serve, tmp_path, watch=False)
    monkeypatch.setattr("loom.cli.review._master_compiles", lambda _result, _master=None: (True, ""))
    # accepting is the author's, whatever reviewer an agent names beside itself
    agent = {"reviewer": "The synthetic quilt", "keys": ["sy-0001"], "author": "Referee (Agent)"}
    refuses(s, "review-accept", agent, 403, "author-only", "only the author accepts")
    refuses(
        s, "review-accept", {"reviewer": "The synthetic quilt", "keys": ["sy-9999"]}, 409, "not-unresolved", "sy-9999"
    )
    # the fixture's acceptance of sy-0001 is stale; accepting records a fresh one beside it, and the queue loses it
    builds = s.builds
    stale = Records(root, load_quilt(root).history_dir).latest["sy-0001"]
    answer = succeeds(s, "review-accept", {"reviewer": "The synthetic quilt", "keys": ["sy-0001", "sy-000B"]})
    assert answer["result"] == "accepted 1 of 2" and answer["accepted"] == ["sy-0001"]
    assert answer["refused"][0]["key"] == "sy-000B" and "basis" in answer["refused"][0]["why"]
    fresh = Records(root, load_quilt(root).history_dir).latest["sy-0001"]
    assert fresh != stale and fresh.author == "The synthetic quilt", fresh
    assert s.builds == builds + 1
    raw = get(s.url + "build/manifest.json")[2]
    assert not [r for r in json.loads(raw)["unresolved"] if r["key"] == "sy-0001"]
