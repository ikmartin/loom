"""The stream's `drafted` event (a demonstration): a save's changed blocks, as source, said before the build that publishes them."""

from __future__ import annotations

import json
import os
import time
import urllib.request

from tests.helpers import PATIENCE
from tests.unit.render._serve import get


def test_a_save_s_changed_statement_is_said_as_source_before_its_build_publishes(session) -> None:  # type: ignore[no-untyped-def]
    """A word saved in a lemma comes over the stream as the lemma's new body, keyed by the `data-src` the published page gives the lemma, naming the build that then publishes it, with how far the word moves every offset past it; the proof beside it, unchanged, is not said, and the file is only read."""
    s, d = session
    node = d / "drafting" / "nodes" / "dm-0002.tex"
    old = node.read_text(encoding="utf-8")
    start = old.index("\\begin{lemma}")
    end = old.index("\\end{lemma}") + len("\\end{lemma}")
    published = (d / ".loom/cache/site/fragments/nodes/dm-0002.html").read_text(encoding="utf-8")
    assert json.loads(get(s.url + "_api")[2])["stream"] is True
    with urllib.request.urlopen(s.url + "_api/stream", timeout=PATIENCE) as resp:
        while resp.readline() != b"event: built\n":
            pass
        resp.readline(), resp.readline()
        time.sleep(0.3)
        saved = old.replace("one or two points", "one or two marked points")
        node.write_text(saved, encoding="utf-8")
        os.utime(node, None)
        events: list[tuple[str, dict]] = []  # type: ignore[type-arg]
        event = ""
        deadline = time.monotonic() + PATIENCE
        while time.monotonic() < deadline and not (events and events[-1][0] == "built"):
            line = resp.readline()
            if line.startswith(b"event: "):
                event = line[len(b"event: ") :].strip().decode()
            elif line.startswith(b"data: ") and event in ("drafted", "built"):
                events.append((event, json.loads(line[len(b"data: ") :])))
    assert [e for e, _ in events] == ["drafted", "built"]
    draft, built = events[0][1], events[1][1]
    assert draft["server"] == os.getpid() and draft["build"] == built["published"]
    assert draft["blocks"] == [
        {
            "src": f"drafting/nodes/dm-0002.tex:{start}:{end}",
            "kind": "env",
            "body": "\\label{dm-0002}\\label{lem:orbits}\nEvery orbit of a widget has one or two marked points, and $\\Fix(\\sigma)$ is the union of the one-point orbits.\n",
        }
    ]
    assert draft["moves"] == {
        "drafting/nodes/dm-0002.tex": [[old.index("one or two ") + len("one or two "), len("marked ")]]
    }
    assert f'data-src="{draft["blocks"][0]["src"]}"' in published
    assert node.read_text(encoding="utf-8") == saved
