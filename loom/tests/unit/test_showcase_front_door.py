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


def test_the_readme_promises_no_problem_its_reader_is_not_shown() -> None:
    """A person's Problems shows `latex` diagnostics alone, and the faults the showcase carries on purpose are the model's, which an agent keeps; so its README speaks of problems only while its lint holds one a person is shown."""
    text = (SHOWCASE.parent / "sources" / "showcase" / "README.md").read_text(encoding="utf-8")
    lint = (SHOWCASE / "EXPECTED-LINT.txt").read_text(encoding="utf-8").splitlines()
    if "problem" in text.lower():
        assert any(line.split()[-1] == "latex" for line in lint if line.strip())
