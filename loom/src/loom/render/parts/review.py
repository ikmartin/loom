"""What changed in the person's documents, and what is proposed to them: this part of the manifest is not built yet, and adds nothing (docs/specs/reserved.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loom.render.attach import Attaching


def attach(build: Attaching) -> None:
    """Add this part to the manifest being made. It adds nothing yet."""
