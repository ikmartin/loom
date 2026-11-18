"""The library's part of the manifest: `arriving`, the drops that wait on the person; the works an agent suggests and what the library's page reads of each work are not built yet (docs/specs/reserved.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loom.render.attach import Attaching


def attach(build: Attaching) -> None:
    """Add `arriving`: each drop that waits, a question or a file received and not yet taken, as the intake's row (specs/manifest.md §1); empty when none does."""
    from loom.refs.intake import waiting

    build.manifest["arriving"] = waiting(build.result.quilt.root)
