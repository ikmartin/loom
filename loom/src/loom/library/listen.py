"""While `loom serve` runs, a listener on the library's nodes folder (`docs/specs/nodes.md` §13): the node files it hears change are the only ones the index reads again, so an index opened while nothing changed looks at no file.

It is the operating system's own notice of a change, through `watchdog`: FSEvents on macOS, inotify on Linux, ReadDirectoryChangesW on Windows. A notice can be lost or merged, so whatever says one may have been lost (`EventsLostEvent`, FSEvents' dropped and must-scan flags), the folder itself removed or moved, a watch that stopped or never started, and the listener's first look all leave the index to scan every file's size and times, as an index opened with no listener does. The listener writes nothing; it only says which files to read again.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from loom.library.node import SUFFIX
from loom.paths import LIBRARY_NODES

#: The quilts this process listens to, by their resolved root, each with how many servers asked for it.
_LISTENING: dict[Path, tuple[Listener, int]] = {}
_REGISTRY = threading.Lock()


class Listener:
    """What changed in one quilt's nodes folder since the index last asked.

    `drain` hands over the names heard and forgets them, or None when the index must scan every file: before the watch has been asked of once, after a notice may have been lost, and while no watch runs. `lock` is held by the index while it brings itself up to date from what was drained, so a read in another thread waits for that rather than answering before it.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.folder = root / LIBRARY_NODES
        self.lock = threading.Lock()
        self._mu = threading.Lock()
        self._heard: set[str] = set()
        self._gap = True
        #: Which index the last scan of every file was made into, and when (`NodeIndex._scanned`), set by the index.
        self.scanned: tuple[int | None, str | None] | None = None
        #: The folder's own inode and times as that scan, or the last update, found them (`index._folder_stamp`), set by the index.
        self.stamp: tuple[int, int, int] | None = None
        self._observer: Any = None
        self._watching = threading.RLock()
        self._places: frozenset[str] = frozenset()

    # ---- the watch ---------------------------------------------------------------------------------------------------

    def start(self) -> bool:
        """Watch the folder, where it exists and no watch runs; whether one runs now. A watch begun counts as a gap, so the next update scans every file, after the watch is in place."""
        with self._watching:
            if self.live:
                return True
            self.stop()
            if not self.folder.is_dir():
                return False
            self._places = frozenset(
                {os.path.normcase(str(self.folder)), os.path.normcase(os.path.realpath(self.folder))}
            )
            observer = _observer()
            try:
                observer.schedule(_Handler(self), str(self.folder), recursive=False)
                observer.start()
            except (
                Exception
            ):  # a watch the system refuses (too many, a folder gone meanwhile) leaves every update a scan
                return False
            self._observer = observer
            # what changed before the watch was in place is the scan's to find
            self.lost()
            return True

    def stop(self) -> None:
        """Stop the watch, if one runs; what was heard is forgotten and the next update scans."""
        observer, self._observer = self._observer, None
        if observer is not None:
            observer.stop()
            if observer.is_alive() and threading.current_thread() is not observer:
                observer.join(timeout=5)
        self.lost()

    @property
    def live(self) -> bool:
        """Whether a watch runs: its observer and each of its emitters alive."""
        observer = self._observer
        return observer is not None and observer.is_alive() and all(e.is_alive() for e in observer.emitters)

    # ---- what was heard ----------------------------------------------------------------------------------------------

    def heard(self, path: str) -> None:
        """A node file directly in the folder changed, was made, removed or renamed; anything else there is no node's."""
        folder, name = os.path.split(path)
        if name.endswith(SUFFIX) and not name.startswith(".") and os.path.normcase(folder) in self._places:
            with self._mu:
                self._heard.add(name)

    def lost(self) -> None:
        """A notice may have been lost, or the watch changed: the next update scans every file."""
        with self._mu:
            self._gap = True
            self._heard.clear()

    def drain(self) -> set[str] | None:
        """The node files heard since the last drain, forgotten here; None when every file must be scanned, the watch being begun again first where none runs, so that what changes during the scan is heard.

        Returns
        -------
        set of str or None
            File names, `<id>.node`.
        """
        if not self.live:
            self.start()
            if not self.live:
                return None
        with self._mu:
            if self._gap:
                self._gap = False
                self._heard.clear()
                return None
            out, self._heard = self._heard, set()
        return out


class _Handler:
    """The observer's handler: a node file's notice to `heard`, a lost one or the folder's own removal to `lost`."""

    def __init__(self, listener: Listener) -> None:
        self.listener = listener

    def dispatch(self, event: Any) -> None:
        try:
            self._dispatch(event)
        except Exception:
            self.listener.lost()

    def _dispatch(self, event: Any) -> None:
        from watchdog.events import (
            EVENT_TYPE_CLOSED_NO_WRITE,
            EVENT_TYPE_DELETED,
            EVENT_TYPE_EVENTS_LOST,
            EVENT_TYPE_MOVED,
            EVENT_TYPE_OPENED,
        )

        listener = self.listener
        if event.event_type == EVENT_TYPE_EVENTS_LOST:
            listener.lost()
            return
        if event.event_type in (EVENT_TYPE_OPENED, EVENT_TYPE_CLOSED_NO_WRITE):
            return  # a file read, which changes nothing
        src = os.fsdecode(event.src_path)
        if event.is_directory:
            # the folder itself removed or moved away: its watch is gone with it
            if event.event_type in (EVENT_TYPE_DELETED, EVENT_TYPE_MOVED) and os.path.normcase(src) in listener._places:
                listener.lost()
            return
        listener.heard(src)
        dest = getattr(event, "dest_path", "")
        if dest:
            listener.heard(os.fsdecode(dest))


def _observer() -> Any:
    """The platform's observer, on macOS one that says a gap FSEvents reports (events dropped, or a folder to scan again), which watchdog's own lets pass."""
    import sys

    if sys.platform != "darwin":
        from watchdog.observers import Observer

        return Observer()
    from watchdog.events import EventsLostEvent
    from watchdog.observers.fsevents import FSEventsEmitter, FSEventsObserver

    class Emitter(FSEventsEmitter):
        def queue_events(self, timeout: Any, events: list[Any]) -> None:  # type: ignore[override]
            if _dropped(events):
                self.queue_event(EventsLostEvent(self.watch.path, is_directory=True))
            super().queue_events(timeout, events)

    observer = FSEventsObserver()
    observer._emitter_class = Emitter
    return observer


def _dropped(events: list[Any]) -> bool:
    """Whether FSEvents says, of any of these native events, that events were dropped (by the kernel or in this process) or that a folder must be scanned again."""
    return any(e.must_scan_subdirs or e.is_user_dropped or e.is_kernel_dropped for e in events)


def listening(root: Path) -> Listener | None:
    """The listener on `root`'s nodes folder in this process, None where no server here listens to it."""
    found = _LISTENING.get(_key(root))
    return found[0] if found is not None else None


def listen(root: Path) -> Listener:
    """Listen to `root`'s nodes folder for as long as some caller has not said `unlisten`; `loom serve` does as it starts.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Listener
        The quilt's one listener in this process, started where its folder exists, and otherwise started by the first update after the folder appears.
    """
    key = _key(root)
    with _REGISTRY:
        found = _LISTENING.get(key)
        listener = found[0] if found is not None else Listener(key)
        _LISTENING[key] = (listener, (found[1] if found is not None else 0) + 1)
    listener.start()
    return listener


def unlisten(root: Path) -> None:
    """One caller of `listen` done; the watch stops when the last is."""
    key = _key(root)
    with _REGISTRY:
        found = _LISTENING.get(key)
        if found is None:
            return
        if found[1] > 1:
            _LISTENING[key] = (found[0], found[1] - 1)
            return
        del _LISTENING[key]
    found[0].stop()


def _key(root: Path) -> Path:
    return Path(os.path.realpath(root))
