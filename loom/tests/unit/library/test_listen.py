"""The listener on the nodes folder (`library.listen`): while it runs, an index opened with nothing heard looks at no file; a hand edit is heard, so a check on the old text is never read for the new; and whatever says a notice may have been lost leaves the next update to scan every file."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from loom.evidence.log import replay, write
from loom.evidence.status import status
from loom.evidence.subjects import Who
from loom.evidence.web import Here, LibraryWeb
from loom.library import index as index_module
from loom.library import listen as listen_module
from loom.library.index import NodeIndex
from loom.library.listen import Listener, listen, listening, unlisten
from loom.paths import LIBRARY_NODES
from tests.helpers import PATIENCE
from tests.unit.library._store import quilt

PERSON = Who("person", "A. Author")
NODE = "tq-00A4"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    root = quilt(tmp_path, aged=True)
    yield root
    while listening(root) is not None:
        unlisten(root)


def _path(root: Path) -> Path:
    return root / LIBRARY_NODES / f"{NODE}.node"


def _compared(root: Path) -> None:
    """The person compared tq-00A4 with its paper, on its text now."""
    on = LibraryWeb(root, index=True).subject(Here("node", NODE))
    write(root, "compared", PERSON, on=on, **{"with": {"ref": "tq-00A1-ref", "pdf": "sha256:" + "4" * 64}})


def _reading(root: Path) -> Any:
    return status(replay(root), LibraryWeb(root, index=True), Here("node", NODE), lean_now=lambda r: True)


def _edit_in_place(root: Path) -> None:
    """A hand edit that keeps the file's size and its modification time: a word changed for one of the same length."""
    path = _path(root)
    st = path.stat()
    text = path.read_text(encoding="utf-8")
    assert "compact" in text
    path.write_text(text.replace("compact", "bounded"), encoding="utf-8")
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert path.stat().st_size == st.st_size


def _no_scan(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Every look at the whole folder from here on, recorded, so a test can say there was none."""
    looked: list[Path] = []
    real = index_module._scan

    def scan(folder: Path) -> Any:
        looked.append(folder)
        return real(folder)

    monkeypatch.setattr(index_module, "_scan", scan)
    return looked


def _heard(listener: Listener, name: str) -> None:
    began = time.monotonic()
    while name not in listener._heard:
        assert time.monotonic() - began < PATIENCE, f"{name} was never heard"
        time.sleep(0.01)


def test_an_index_opened_while_nothing_was_heard_looks_at_no_file(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    listener = listen(root)
    assert listener.live
    with NodeIndex.open(root) as index:
        assert index.count() == 9  # the listener's first update scans every file
    looked = _no_scan(monkeypatch)
    for _ in range(3):
        with NodeIndex.open(root) as index:
            assert index.refresh().read == 0
    assert looked == []
    unlisten(root)
    with NodeIndex.open(root):
        pass
    assert looked, "with no listener, an index opened scans every file"


def test_a_hand_edit_in_place_is_heard_and_a_check_on_the_old_text_is_never_read_for_the_new(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    listener = listen(root)
    _compared(root)
    assert _reading(root).reading == "matches"
    looked = _no_scan(monkeypatch)
    _edit_in_place(root)
    _heard(listener, f"{NODE}.node")
    found = _reading(root)
    assert found.reading == "unchecked" and found.compared_before
    assert looked == [], "the listener, not a scan, said what changed"


def test_a_notice_the_listener_lost_falls_back_to_a_scan(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from watchdog.events import EventsLostEvent

    listener = listen(root)
    _compared(root)
    assert _reading(root).reading == "matches"
    # the edit's notice dropped on the way, as a full queue drops it
    monkeypatch.setattr(listener, "heard", lambda path: None)
    _edit_in_place(root)
    time.sleep(0.3)
    assert _reading(root).reading == "matches", "nothing heard, nothing read again: the listener is trusted"
    listen_module._Handler(listener).dispatch(EventsLostEvent(str(root / LIBRARY_NODES), is_directory=True))
    looked = _no_scan(monkeypatch)
    found = _reading(root)
    assert found.reading == "unchecked" and found.compared_before
    assert looked, "a gap is a scan of every file"


def test_fsevents_dropped_or_must_scan_flags_are_a_gap() -> None:
    def native(**flags: bool) -> Any:
        return SimpleNamespace(
            **{"must_scan_subdirs": False, "is_user_dropped": False, "is_kernel_dropped": False, **flags}
        )

    assert not listen_module._dropped([native(), native()])
    for flag in ("must_scan_subdirs", "is_user_dropped", "is_kernel_dropped"):
        assert listen_module._dropped([native(), native(**{flag: True})]), flag


def test_the_folder_removed_or_a_watch_never_begun_is_a_scan_and_the_watch_begins_again(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from watchdog.events import DirDeletedEvent

    listener = listen(root)
    with NodeIndex.open(root):
        pass
    # a late notice of the files made just before may still come, and is read again, harmlessly
    assert listener.drain() is not None
    listen_module._Handler(listener).dispatch(DirDeletedEvent(str(root / LIBRARY_NODES)))
    assert listener.drain() is None and listener.drain() is not None
    # a watch that stopped is begun again by the next update, which scans
    listener.stop()
    assert not listener.live
    looked = _no_scan(monkeypatch)
    with NodeIndex.open(root):
        pass
    assert looked and listener.live


def test_a_library_with_no_folder_yet_is_scanned_until_one_appears(tmp_path: Path) -> None:
    root = tmp_path / "q"
    root.mkdir()
    listener = listen(root)
    try:
        assert not listener.live and listener.drain() is None
        (root / LIBRARY_NODES).mkdir(parents=True)
        with NodeIndex.open(root):
            pass
        assert listener.live
    finally:
        unlisten(root)
    assert listening(root) is None and not listener.live


def test_a_file_made_removed_or_renamed_is_read_at_once_though_its_notice_has_not_arrived(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loom's own writes rename a file into place or remove one, which moves the folder's times at once: the next update reads them, whatever the system's latency."""
    from loom.library.store import read, remove_node, write_node

    listener = listen(root)
    with NodeIndex.open(root) as index:
        assert index.row(NODE) is not None
    monkeypatch.setattr(listener, "heard", lambda path: None)
    held = read(root, "tq-00K3")
    assert held is not None
    write_node(root, replace(held, title="Another lemma"))
    with NodeIndex.open(root) as index:
        assert index.node("tq-00K3").title == "Another lemma"  # type: ignore[union-attr]
    assert remove_node(root, NODE)
    with NodeIndex.open(root) as index:
        assert index.row(NODE) is None
