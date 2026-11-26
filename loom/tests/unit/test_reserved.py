"""The page of reserved names (docs/specs/reserved.md) lists only what is not built: a name is taken off it by the change that builds it, and what loom can check of that it checks here."""

from __future__ import annotations

import re
from pathlib import Path

from loom import paths
from loom.agents import AGENT_PLACES, denied_by
from loom.render.api import CAPABILITIES, HANDLERS
from loom.render.attach import ATTACH
from loom.scan.quilt import QuiltConfig

PAGE = (Path(__file__).resolve().parents[3] / "docs" / "specs" / "reserved.md").read_text(encoding="utf-8")


def section(title: str) -> str:
    """The page's text under the heading `title`, up to the next heading."""
    found = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", PAGE, re.M | re.S)
    assert found is not None, f"docs/specs/reserved.md has no section {title!r}"
    return found.group(1)


def first_cells(text: str) -> list[str]:
    """Every backticked name in the first cell of each row of the tables in `text`."""
    rows = [line.split("|")[1] for line in text.splitlines() if line.startswith("| `")]
    return [name for cell in rows for name in re.findall(r"`([^`]+)`", cell)]


def test_no_reserved_write_operation_is_served() -> None:
    """An operation that is served belongs in specs/write-api.md, whose rows are the served endpoints, and its row here is deleted by the change that serves it."""
    reserved = first_cells(section("Write operations"))
    assert reserved, "the table of reserved write operations parsed to nothing"
    assert all(re.fullmatch(r"[a-z]+(-[a-z]+)+", name) for name in reserved), reserved
    served = sorted(set(reserved) & (set(CAPABILITIES) | set(HANDLERS)))
    assert served == [], f"served, and still on the page of reserved names: {served}"


def test_every_reserved_path_is_named_once_and_kept_from_agents() -> None:
    """A reserved path is a constant in `loom.paths` already, so that two pieces of work do not spell it twice, and no agent may write it, so that the permission files a quilt has today already say so."""
    named = {v for k, v in vars(paths).items() if k.isupper() and isinstance(v, str)}
    reserved = [name for name in first_cells(section("Paths in a quilt")) if name.startswith(".loom/")]
    assert reserved, "the table of reserved paths parsed to nothing"
    for path in reserved:
        rel = path.rstrip("/")
        assert rel in named, f"{path} is reserved and loom.paths does not name it"
        assert not any(rel == place or rel.startswith(place + "/") for place in AGENT_PLACES), path
        assert denied_by(QuiltConfig(), rel if "." in Path(rel).name else f"{rel}/any") is not None, path
    for inside in (paths.SUGGESTED_WORKS,):
        assert denied_by(QuiltConfig(), inside) is not None, inside


def test_a_part_of_the_manifest_that_is_not_built_adds_nothing() -> None:
    """Each subject has its function in `ATTACH` already, in a module of its own, so the work that builds one edits that module and nothing shared."""
    assert [part.__module__.rsplit(".", 1)[-1] for part in ATTACH] == [
        "records",
        "review",
        "library",
        "agents",
        "formal",
    ]


def test_a_path_some_part_of_loom_uses_is_not_on_the_page() -> None:
    """A path leaves the page when it is built: once a module beyond `loom.paths` and the agents' boundary reads its constant, the page no longer names it, as `.loom/library/nodes/` left it when the node store was built."""
    import ast

    src = Path(paths.__file__).parent
    used: set[str] = set()
    for module in src.rglob("*.py"):
        if module.name in ("paths.py", "agents.py") and module.parent == src:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        used |= {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    named = {k: v for k, v in vars(paths).items() if k.isupper() and isinstance(v, str) and v.startswith(".loom/")}
    on_page = set(re.findall(r"`(\.loom/[^`]*?)/?`", PAGE))
    built = sorted(f"{k} = {v}" for k, v in named.items() if v in on_page and k in used)
    assert built == [], f"built, and still on the page of reserved names: {built}"
    assert paths.LIBRARY_NODES not in on_page


def test_the_mirror_s_names_are_the_overleaf_ones_it_serves() -> None:
    """The mirror serves `overleaf-*`, which took the place of the `sync-` names reserved for it, so the page reserves `overleaf-` to Overleaf and no `sync-` name."""
    served = sorted(name for name in HANDLERS if name.startswith("overleaf-"))
    assert served, "no overleaf-* endpoint is served"
    assert not [name for name in first_cells(section("Write operations")) if name.startswith("sync-")]
    prefixes = re.search(r"^Prefixes: (.*)$", section("Write operations"), re.M)
    assert prefixes is not None and "`sync-`" not in prefixes.group(1)
    assert "`overleaf-` to Overleaf" in prefixes.group(1)
