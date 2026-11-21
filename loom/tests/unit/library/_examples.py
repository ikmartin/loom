"""The nine example files of docs/specs/nodes.md §12, as the spec prints them and as the fixtures beside this module hold them."""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent
EXAMPLES = HERE / "examples"
SPEC = HERE.parents[3] / "docs" / "specs" / "nodes.md"


def from_spec() -> dict[str, bytes]:
    """Each file §12 prints, by name: the code block under the sentence that names it, with the line feed that ends its last line."""
    text = SPEC.read_text(encoding="utf-8")
    section = text[text.index("## 12. Examples") :]
    return {
        name: (body + "\n").encode() for name, body in re.findall(r"`([^`]+\.node)`:\n\n```\n(.*?)\n```", section, re.S)
    }


def fixtures() -> dict[str, bytes]:
    """The committed copies, by name."""
    return {p.name: p.read_bytes() for p in sorted(EXAMPLES.glob("*.node"))}
