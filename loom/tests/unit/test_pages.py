"""Pages (plan 0.21.3): the research state, written through `loom write` with the hash the reader was shown, recorded in the history, and published with who wrote it."""

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import edit, ok, refused
from tests.unit._quilts import showcase

AGENT = ("--as", "Test Agent")


def hash_of(q: Path, rel: str) -> str:
    from loom.pages import text_hash

    return text_hash((q / rel).read_text())


def writes(q: Path) -> list[dict]:  # type: ignore[type-arg]
    lines = (q / ".loom" / "records" / "history" / "ledger.jsonl").read_text().splitlines()
    return [e for e in (json.loads(ln) for ln in lines if ln.strip()) if e["action"] == "page-write"]


def test_the_research_state_is_written_once_without_a_base_and_then_only_over_what_was_read(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    (q / "research-state.md").unlink()  # the showcase ships one; start without
    refused("write", "state", "Goals.", "--base", "sha256:00", *AGENT, cwd=q, code=2, match="does not exist yet")
    ok("write", "state", "Goals: the rank theorem.", *AGENT, cwd=q)
    first = hash_of(q, "research-state.md")
    refused("write", "state", "Goals: v2.", *AGENT, cwd=q, code=2, match="read it first")
    # the author edits it by hand; a write from what was read before is refused, and shows the edit it missed
    edit(q / "research-state.md", "the rank theorem.", "the rank theorem, for connected quivers.")
    stale = refused(
        "write", "state", "Goals: v2.", "--base", first, *AGENT, cwd=q, code=1, match="has changed since you read it"
    )
    assert "+Goals: the rank theorem, for connected quivers." in stale.output
    ok("write", "state", "Goals: v2, connected quivers.", "--base", hash_of(q, "research-state.md"), *AGENT, cwd=q)
    last = writes(q)[-1]
    assert last["actor"] == "Test Agent" and last["page"] == "state" and last["outside"] is True
    from loom.records.snapshots import read_raw

    assert (
        read_raw(q, last["from"], q / ".loom" / "records" / "history")
        == "Goals: the rank theorem, for connected quivers.\n"
    )
    assert "the research state written by Test Agent, over an edit made outside loom" in " ".join(
        ok("history", cwd=q).stdout.split()
    )


def test_a_link_that_names_nothing_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    before = (q / "research-state.md").read_text()
    refused(
        "write", "state", "See [](quilt:sh-9999).", "--base", hash_of(q, "research-state.md"), *AGENT,
        cwd=q, code=2, match="no key sh-9999",
    )  # fmt: skip
    assert (q / "research-state.md").read_text() == before


def test_the_manifest_publishes_each_page_with_who_wrote_it_and_its_links_that_moved_or_broke(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    ok(
        "build", cwd=q
    )  # the showcase's duplicate id is in two documents, which LaTeX accepts: a warning of loom's model
    m = json.loads((q / ".loom/cache/site" / "manifest.json").read_text())
    state = m["research_state"]
    assert state["by"] == {"kind": "agent", "id": "Referee (Agent)"} and state["edited_since"] is False
    assert state["links"] == {"broken": [], "moved": []} and "<h2>Goals</h2>" in state["body_html"]
    # a linked result changes, and the author adds a link to nothing by hand
    edit(q / "drafting" / "nodes" / "sh-0009.tex", "has $c$ connected components", "has $c$ components")
    with (q / "research-state.md").open("a") as fh:
        fh.write("- See [](quilt:sh-9999).\n")
    ok("build", cwd=q)
    state = json.loads((q / ".loom/cache/site" / "manifest.json").read_text())["research_state"]
    assert state["edited_since"] is True
    assert [b["href"] for b in state["links"]["broken"]] == ["quilt:sh-9999"]
    assert [mv["href"] for mv in state["links"]["moved"]] == ["quilt:sh-0009"]


def test_orient_prints_the_research_state_with_its_hash(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    out = ok("ai", "orient", cwd=q).stdout
    state = out.split("# Research state", 1)[1]
    assert hash_of(q, "research-state.md") in state and "last written by Referee (Agent)" in state
    assert "A loop counts once in the rank formula." in state


def test_an_agent_may_not_edit_the_research_state_by_hand(tmp_path: Path) -> None:
    from loom.ai.layout import settings_deny_paths
    from loom.scan.quilt import QuiltConfig

    assert "Edit(/research-state.md)" in settings_deny_paths(QuiltConfig())
    assert "Edit(/notes/state.md)" in settings_deny_paths(QuiltConfig(research_state="notes/state.md"))


def test_a_link_whose_result_is_gone_is_reported_broken_and_the_build_goes_on(tmp_path: Path) -> None:
    """The research state links `sh-0009`; once its environment is no longer declared the key finds only a label, and the page says the link is dead rather than the build failing."""
    q = showcase(tmp_path)
    node = q / "drafting" / "nodes" / "sh-0009.tex"
    node.write_text(node.read_text().replace("{theorem}", "{undeclared}"))
    ok(
        "build", cwd=q
    )  # the showcase's duplicate id is in two documents, which LaTeX accepts: a warning of loom's model
    state = json.loads((q / ".loom/cache/site" / "manifest.json").read_text())["research_state"]
    assert [b["href"] for b in state["links"]["broken"]] == ["quilt:sh-0009"]
    assert state["links"]["moved"] == []
