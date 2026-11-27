"""The showcase opens on a page written for its reader: its README, which names nothing a person would type and links only to what the showcase holds."""

from __future__ import annotations

import re
import tomllib

from tests.unit._quilts import SHOWCASE


def test_the_showcase_opens_on_its_readme_written_for_a_reader() -> None:
    """No `[quilt] home`, so the README is the front door; it holds no code, command or developer's file, and each `quilt:` link names a file or a label of the showcase."""
    config = tomllib.loads((SHOWCASE / "config.toml").read_text(encoding="utf-8"))
    assert "home" not in config["quilt"]
    text = (SHOWCASE / "README.md").read_text(encoding="utf-8")
    for never in ("`", ".loom", "scripts/", "EXPECTED-LINT", "fixture", " --"):
        assert never not in text, never
    assert not re.search(
        r"\bloom (serve|lint|init|build|compile|draft|stamp|accept|annotate|suggest|session|library|ai|fork|live)\b",
        text,
    )
    links = re.findall(r"\]\(quilt:([^)#]+)\)", text)
    assert links
    sources = "".join(p.read_text(encoding="utf-8") for p in (SHOWCASE / "drafting").rglob("*.tex"))
    for target in links:
        assert (SHOWCASE / target).is_file() or f"\\label{{{target}}}" in sources, target
