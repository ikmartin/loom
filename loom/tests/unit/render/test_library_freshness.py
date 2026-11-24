"""The library's one generation, served (`library-views.md` §2, "Freshness"): a write through the publisher answers with it, the stream says once that it moved, and the list read again shows the change; a publication that changes nothing in the library says nothing, and a node an agent writes outside the publisher is said too."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loom.library.node import Node
from loom.library.store import write_node
from loom.render.serve import ServeSession
from tests.helpers import PATIENCE
from tests.unit._quilts import demo
from tests.unit.render.write_api._cases import succeeds

#: A work the demo does not hold, so taking it in writes a reference.
FRESH = "@article{Fresh21,\n  author = {Fresh, A.},\n  title = {A fresh paper},\n  year = {2021},\n}\n"


class Heard:
    """The `library` events a served quilt's stream sends, as the viewer hears them, collected on a thread of their own."""

    def __init__(self, s: ServeSession) -> None:
        self.gens: list[int] = []
        self._resp = urllib.request.urlopen(s.url + "_api/stream", timeout=PATIENCE)
        assert self._resp.readline() == b": open\n"
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        event = ""
        try:
            for raw in self._resp:
                line = raw.decode().rstrip("\n")
                if line.startswith("event: "):
                    event = line[len("event: ") :]
                elif line.startswith("data: ") and event == "library":
                    self.gens.append(int(json.loads(line[len("data: ") :])["gen"]))
        except (OSError, ValueError):
            return

    def after(self, count: int, *, settle: float = 1.5) -> list[int]:
        """The gens heard once there are `count`, waiting `settle` seconds more so a second one would be heard too."""
        deadline = time.time() + PATIENCE
        while len(self.gens) < count and time.time() < deadline:
            time.sleep(0.05)
        time.sleep(settle)
        return list(self.gens)


def _works(s: ServeSession, **body: Any) -> dict[str, Any]:
    return succeeds(s, "library-works", body)


def test_a_write_answers_with_the_generation_the_stream_says_once_and_the_list_shows_it(
    serve: Callable[[Path], ServeSession], tmp_path: Path
) -> None:
    """The joined review's J-1: no library write showed on a served quilt until a reload, since the stream said nothing and no write answered with `gen`."""
    s = serve(demo(tmp_path))
    first = _works(s)
    heard = Heard(s)
    added = succeeds(s, "library-take", {"items": [{"text": FRESH}]})
    ref = added["rows"][0]["ref"]
    assert added["gen"] > first["gen"], (added, first)
    assert heard.after(1) == [added["gen"]], "said once, with the gen the write answered"
    listed = _works(s, since=first["gen"])
    assert listed["gen"] == added["gen"] and ref in [w["ref"] for w in listed["works"]]
    assert _works(s, since=added["gen"])["unchanged"] is True
    deleted = succeeds(s, "library-delete", {"ref": ref})
    assert deleted["gen"] > added["gen"]
    assert heard.after(2) == [added["gen"], deleted["gen"]]
    assert ref not in [w["ref"] for w in _works(s, since=added["gen"])["works"]], "a deleted row goes"
    restored = succeeds(s, "library-restore", {"undo": deleted["undo"]})
    assert heard.after(3) == [added["gen"], deleted["gen"], restored["gen"]]
    assert ref in [w["ref"] for w in _works(s, since=deleted["gen"])["works"]]


def test_a_publication_that_changes_nothing_in_the_library_says_nothing(
    serve: Callable[[Path], ServeSession], tmp_path: Path
) -> None:
    q = demo(tmp_path)
    s = serve(q)
    before = _works(s)["gen"]
    heard = Heard(s)
    builds = s.builds
    s.rebuild()
    main = next(p for p in sorted(q.rglob("*.tex")) if ".loom" not in p.parts)
    main.write_text(
        main.read_text(encoding="utf-8") + "\n% a comment, and nothing the library reads\n", encoding="utf-8"
    )
    deadline = time.time() + PATIENCE
    while s.builds < builds + 2 and time.time() < deadline:
        time.sleep(0.05)
    assert s.builds >= builds + 2 and heard.after(0) == []
    assert _works(s, since=before)["unchanged"] is True


def test_a_node_an_agent_writes_outside_the_publisher_is_said_on_the_stream(
    serve: Callable[[Path], ServeSession], tmp_path: Path
) -> None:
    q = demo(tmp_path)
    s = serve(q)
    ref = succeeds(s, "library-take", {"items": [{"text": FRESH}]})["rows"][0]["ref"]
    before = _works(s)["gen"]
    heard = Heard(s)
    stem = ref.split("-")[0]
    write_node(q, Node(id=f"{stem}-0ZZZ", taxon="lemma", number="2.1", source=ref))
    [gen] = heard.after(1)
    assert gen > before
    row = next(w for w in _works(s, since=before)["works"] if w["ref"] == ref)
    assert row["digested"] == {"statements": 0, "of": None, "compared": 0, "stubs": 1}
