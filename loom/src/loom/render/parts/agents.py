"""How agents are set up in the quilt and what they are told: the manifest's `agents` (`docs/specs/manifest.md` §1)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.render.attach import Attaching


def attach(build: Attaching) -> None:
    """Add `agents`: each app `agents-setup` sets up and whether it is, the line an agent is told first, and the quilt's modes.

    Read off the files at each build and asking git nothing, since a build runs on every save. Who is connected is not here: it changes with every call an agent makes, and goes on the stream (`loom.presence`).
    """
    from loom.ai.clients import PROJECT, chosen, names_loom
    from loom.ai.layout import MCP_LINE, SHELL, SHELL_LINE, modes, read_versions, tracked_docs, variant
    from loom.paths import AI

    root = build.result.quilt.root
    layer = (root / AI).is_dir()
    way = variant(root)
    have = chosen(root, None) if layer else []
    apps: list[dict[str, Any]] = []
    for c in PROJECT:
        server = root / (c.file or "")
        started = server.is_file() and names_loom(c, server.read_text(encoding="utf-8", errors="replace"))
        apps.append({"key": c.key, "label": c.label, "set_up": c.key in have and (way == SHELL or started)})
    versions, shipped = read_versions(root), tracked_docs(root)
    build.manifest["agents"] = {
        "apps": apps,
        "line": (SHELL_LINE if way == SHELL else MCP_LINE) if layer else "",
        "modes": [_mode(root, name, versions, shipped) for name in modes(root)],
    }


def _mode(root: Path, name: str, versions: dict[str, str], shipped: dict[str, str]) -> dict[str, Any]:
    """One mode for the manifest: its `When it fits` line, the quilt's copy, whether that copy is the author's own (differing from what this loom ships and from what the layer records loom last wrote), its text as a person edits it, and whether `loom upgrade` left a newer version of loom's beside it.

    `text` is the file, the quilt's copy else loom's, with each `{type:ID}` as written: what Settings › Modes edits, which an agent reads with each type named (`orient.mode_text`).
    """
    from loom.ai.layout import read_plain, sha
    from loom.ai.orient import fits
    from loom.paths import AI

    path = f"{AI}/modes/{name}.md"
    text = read_plain(root, path)
    wrote = {versions.get(f"{name}.md"), sha(shipped[path])}
    return {
        "name": name,
        "fits": fits(root, name),
        "path": path,
        "edited": text is not None and sha(text) not in wrote,
        "text": shipped[path] if text is None else text,
        "newer": read_plain(root, f"{path}.new") is not None,
    }
