"""Shared provenance for incorporated contributions: a pull from the document workspace or an adopted agent document."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loom.paths import REVIEW_ORIGINS


def read(root: Path) -> dict[str, dict[str, Any]]:
    """Read the shared provenance store, empty when nothing has been incorporated.

    Parameters
    ----------
    root : Path
        Quilt root containing the local records.

    Returns
    -------
    dict
        Per-node provenance: where each key's incorporated text came from; inside an act that stages loom's records, as it has staged it (`writes.staging`).
    """
    from loom.writes import staged

    path = root / REVIEW_ORIGINS
    held, data = staged(path)
    if held:
        return json.loads(data) if data is not None else {}
    return json.loads(path.read_text()) if path.is_file() else {}


def write(root: Path, origins: dict[str, dict[str, Any]]) -> None:
    """Atomically persist a complete shared provenance store.

    Parameters
    ----------
    root : Path
        Quilt root containing the local records.
    origins : dict
        Complete per-node provenance, including unrelated contributions retained by the caller. Inside an act that stages loom's records it is staged into the act, and written with it (`writes.staging`).
    """
    from loom.writes import stage

    path = root / REVIEW_ORIGINS
    if stage(path, (json.dumps(origins, indent=2, sort_keys=True) + "\n").encode("utf-8")):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(origins, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
