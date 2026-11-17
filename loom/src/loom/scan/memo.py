"""What is derived from a whole text, remembered while the text is in use.

A served quilt scans every file again on every change, and most files have not changed, so their tokens and comment-blanked text are looked up by the text itself rather than made again. A memo keeps what is in use and nothing older: each scan and each build that scans is a `reading`, and when the outermost reading ends every memo forgets the entries not asked for since it began. An edited file's old text is let go by the build that reads the new one, so what a memo holds is bounded by the quilt as it is now, not by how many saves came before.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar

V = TypeVar("V")

_lock = threading.Lock()
_memos: list[TextMemo] = []  # type: ignore[type-arg]
#: The generation each open reading began in, in every thread; each reading begins one of its own.
_open: set[int] = set()
_generation = 0


class TextMemo(Generic[V]):
    """`make(text)`, made once for each text in use.

    An entry is kept while it is asked for: one not asked for since the outermost reading began is forgotten when that reading ends, and one asked for outside any reading lives until the next reading ends.
    """

    def __init__(self, make: Callable[[str], V]) -> None:
        self._make = make
        self._entries: dict[str, tuple[V, int]] = {}
        with _lock:
            _memos.append(self)

    def __call__(self, text: str) -> V:
        hit = self._entries.get(text)
        value = self._make(text) if hit is None else hit[0]
        self._entries[text] = (value, _generation)
        return value

    def __contains__(self, text: object) -> bool:
        return text in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def _forget(self, before: int) -> None:
        for text, (_, used) in list(self._entries.items()):
            if used < before:
                self._entries.pop(text, None)


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
