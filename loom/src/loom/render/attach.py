"""The parts of the manifest that are added to it after the records are applied, a function for each, which `build` calls in order.

A part of loom that publishes something of its own adds its function to `ATTACH` and leaves `build` alone.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loom.render.parts import agents, formal, library, records, review

if TYPE_CHECKING:
    from loom.library.gather import Gathered
    from loom.records.store import Records
    from loom.render.fragments import FragmentRenderer
    from loom.scan.scan import ScanResult


@dataclass(frozen=True)
class Attaching:
    """What a part is given: the scan and the records it reads, the renderer it may ask for previews, and the manifest and files of the publication being made, which it adds to."""

    result: ScanResult
    records: Records
    renderer: FragmentRenderer
    manifest: dict[str, Any]
    #: What the publication writes beside the manifest, by path under the build directory.
    files: dict[str, str | bytes]
    #: What the build's gathering made and refused (`library.gather`), before its fragments were drawn.
    gathered: Gathered | None = None


#: The parts, in the order they are added. Each runs once the records are applied and the changes and versions are attached, and before the previews it asked the renderer for are made; the unresolved rows, the files' list, the published config and the owners of the diagnostics follow, so a part may add a diagnostic to `manifest["diagnostics"]` and have it stamped with the rest.
ATTACH: tuple[Callable[[Attaching], None], ...] = (
    records.attach,
    review.attach,
    library.attach,
    agents.attach,
    formal.attach,
)
