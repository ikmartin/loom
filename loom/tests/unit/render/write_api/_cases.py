"""The register of cases, one for each endpoint the publisher serves, and what the cases share.

A case runs against a real `loom serve`: one write that succeeds, with what the server wrote read back from the quilt, and one refusal, with its status, code and message. `test_every_capability_has_a_case_and_a_row_in_the_spec` fails for an endpoint with no case.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from loom.render.serve import ServeSession
from tests.helpers import the
from tests.unit._quilts import REPO, demo, new_session
from tests.unit.render._serve import log, post

Serve = Callable[..., ServeSession]


Case = Callable[[Serve, Path, pytest.MonkeyPatch], None]


CASES: dict[str, Case] = {}


WHO = "A Reader"


def case(endpoint: str) -> Callable[[Case], Case]:
    def register(fn: Case) -> Case:
        CASES[endpoint] = fn
        return fn

    return register


def succeeds(s: ServeSession, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST and assert 200 with `ok`; the answer."""
    status, said = post(s.url + f"_api/{endpoint}", body)
    assert status == 200 and said.get("ok") is True, (endpoint, status, said)
    return said  # type: ignore[no-any-return]


def refuses(s: ServeSession, endpoint: str, body: dict[str, Any], status: int, code: str, match: str) -> None:
    """POST and assert the refusal: its status, its code, and `match` in its message."""
    got, said = post(s.url + f"_api/{endpoint}", body)
    assert got == status and said.get("error", {}).get("code") == code, (endpoint, got, said)
    assert match in said["error"]["message"], (endpoint, said)


def events(q: Path, ann: str) -> list[dict[str, Any]]:
    """The log's events that name one annotation, in order."""
    return [e for e in log(q) if e.get("id") == ann]


def noted(s: ServeSession, q: Path, sid: str, body: str = "A note to act on.", type_id: str = "note") -> str:
    """Write one annotation on dm-0003 over the wire, a note unless `type_id` says otherwise; its id."""
    succeeds(s, "annotate", {"session": sid, "target": "dm-0003", "message": body, "type": type_id, "author": WHO})
    return the(log(q), lambda e: e.get("body") == body and e["event"] == "created", body)["id"]  # type: ignore[no-any-return]


def on_demo(serve: Serve, tmp_path: Path) -> tuple[ServeSession, Path, str]:
    q = demo(tmp_path)
    return serve(q), q, new_session(q)


ARDEN = Path(__file__).resolve().parents[3] / "quilts" / "sources" / "showcase-works" / "arden-cycle-spaces.pdf"


def with_paper(serve: Serve, tmp_path: Path) -> tuple[ServeSession, Path]:
    """A served quilt with a PDF among its shown files."""
    q = demo(tmp_path)
    (q / "notes").mkdir()
    (q / "notes" / "paper.pdf").write_bytes(ARDEN.read_bytes())
    return serve(q), q


def drawn(s: ServeSession, q: Path) -> str:
    """A box on the served PDF, over the wire; its id."""
    done = succeeds(
        s,
        "annotate",
        {"target": "notes/paper.pdf", "page": 1, "rects": [[10, 10, 60, 60]], "mark": "box", "author": WHO},
    )
    return str(done["result"].split()[0])


def synthetic(serve: Serve, tmp_path: Path, *, watch: bool = True) -> tuple[ServeSession, Path]:
    """A copy of loom's synthetic quilt, served (which builds it)."""
    root = tmp_path / "synthetic"
    shutil.copytree(REPO / "tests" / "quilts" / "synthetic", root, ignore=shutil.ignore_patterns("build", ".git"))
    from loom.scan.quilt import save_author

    save_author("The synthetic quilt")
    return serve(root, watch=watch), root


def filed(q: Path, *args: str, who: str = WHO) -> str:
    """A suggested edit on dm-0002, as `loom suggest` files it; its id."""
    from tests.helpers import json_of

    return str(json_of("suggest", "dm-0002", *args, "--as", who, "--json", cwd=q)["edit"])
