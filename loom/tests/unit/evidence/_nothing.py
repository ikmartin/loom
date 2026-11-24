"""A web that knows no text, for tests that answer a few questions themselves and leave the rest unanswered."""

from __future__ import annotations

from loom.evidence.subjects import Subject
from loom.evidence.web import Here


class Nothing:
    """Every question answered with nothing, so nothing reads as done and an ask a node would close stays open."""

    def subject(self, here: Here) -> Subject | None:
        return None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return None

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        return {}

    def notation(self, here: Here) -> dict[str, str] | None:
        return {}

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        return None

    def holds(self, ref: str, want: str) -> bool | None:
        return None

    def cited(self, here: Here) -> list[str]:
        return []

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        return None

    def texts(self, key: tuple[str, str]) -> set[str]:
        return set()
