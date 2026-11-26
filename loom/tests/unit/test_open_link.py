"""`loom open LINK`: an editor follows a `quilt:` link written in a note by opening the quilt's viewer there, the running one or one started for it."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.helpers import ok, refused
from tests.unit._quilts import demo


def listening(q: Path, port: int = 8765) -> None:
    """Write what a running `loom serve` says about itself, naming this process, so `open_url` takes it as listening."""
    from loom.paths import SERVE_JSON

    p = q / SERVE_JSON
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"port": port, "pid": os.getpid(), "url": f"http://127.0.0.1:{port}/", "root": str(q.resolve())})
    )


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import webbrowser

    got: list[str] = []
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: got.append(url) or True)
    return got


def test_the_link_under_the_cursor_opens_in_the_running_viewer(tmp_path: Path, opened: list[str]) -> None:
    q = demo(tmp_path)
    listening(q)
    href = "quilt:drafting/main.tex#dm-0003&quote=every%20vertex"
    for given in (href, f"[[{href}][the vertex]]", f"[the vertex]({href})", f"<{href}>"):
        ok("open", given, cwd=q)
    assert opened == [f"http://127.0.0.1:8765/open?link={quote(href, safe='')}"] * 4


def test_a_cited_link_opens_the_work_at_its_pages_here(tmp_path: Path, opened: list[str]) -> None:
    from loom.cli._quilt import open_scan

    q = demo(tmp_path)
    listening(q)
    ok("open", "cited:doi:10.4171/demo/14-1?page=2&quote=a%20phrase", cwd=q)
    ref = open_scan(str(q)).refs["Calloway14"]
    assert opened == [f"http://127.0.0.1:8765/open?link={quote(f'quilt:{ref}#page=2&quote=a%20phrase', safe='')}"]


def test_a_link_to_nothing_is_refused_and_opens_nothing(tmp_path: Path, opened: list[str]) -> None:
    q = demo(tmp_path)
    listening(q)
    refused("open", "quilt:dm-9999", cwd=q, code=2, match="no key dm-9999")
    refused("open", "just words", cwd=q, code=2, match="holds no quilt: or cited: link")
    assert opened == []


def test_with_no_viewer_running_one_is_started_for_the_link(
    tmp_path: Path, opened: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    q = demo(tmp_path)
    started: list[list[str]] = []

    class Serve:
        def __init__(self, argv: list[str], **_: object) -> None:
            started.append(argv)
            listening(q, 8790)

    monkeypatch.setattr(subprocess, "Popen", Serve)
    ok("open", "quilt:dm-0003", cwd=q)
    assert started and started[0][-4:] == ["loom", "serve", "--quilt", str(q)]
    assert opened == ["http://127.0.0.1:8790/open?link=quilt%3Adm-0003"]
