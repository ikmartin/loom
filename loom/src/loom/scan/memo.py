"""What is derived from what a scan reads, remembered while it is in use.

A served quilt scans every file again on every change, and most files have not changed, so their tokens and comment-blanked text are looked up by the text itself rather than made again, and a style a preamble loads by its path and mtime. A memo keeps what is in use and nothing older: each scan and each build that scans is a `reading`, and when the outermost reading ends every memo forgets the entries not asked for since it began. An edited file's old text is let go by the build that reads the new one, so what a memo holds is bounded by the quilt as it is now, not by how many saves came before.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

_lock = threading.Lock()
_memos: list[Memo] = []  # type: ignore[type-arg]
#: The generation each open reading began in, in every thread; each reading begins one of its own.
_open: set[int] = set()
_generation = 0


class Memo(Generic[K, V]):
    """`make(key)`, made once for each key in use: a text, or what names a file as it now is.

    An entry is kept while it is asked for: one not asked for since the outermost reading began is forgotten when that reading ends, and one asked for outside any reading lives until the next reading ends.
    """

    def __init__(self, make: Callable[[K], V]) -> None:
        self._make = make
        self._entries: dict[K, tuple[V, int]] = {}
        with _lock:
            _memos.append(self)

    def __call__(self, key: K) -> V:
        hit = self._entries.get(key)
        value = self._make(key) if hit is None else hit[0]
        self._entries[key] = (value, _generation)
        return value

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __iter__(self) -> Iterator[K]:
        return iter(list(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def _forget(self, before: int) -> None:
        for key, (_, used) in list(self._entries.items()):
            if used < before:
                self._entries.pop(key, None)


@contextmanager
def reading() -> Iterator[None]:
    """Read the quilt inside this: when it ends with no older reading still open, every memo forgets what was not asked for since it began.

    A scan inside a build forgets nothing, so the build's rendering finds what the build before it derived; readings in other threads keep what they have asked for. A caller that builds from a scan it already holds opens none, since it reads no file and would otherwise forget every file's entry.
    """
    global _generation
    with _lock:
        _generation += 1
        began = _generation
        _open.add(began)
    try:
        yield
    finally:
        with _lock:
            _open.discard(began)
            if all(other > began for other in _open):
                for memo in _memos:
                    memo._forget(began)
