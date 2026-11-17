"""`loom since`: what people did since an agent last looked, against its own marker, reported once and only once."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from loom.since import marker_path
from tests.helpers import json_of, ok
from tests.unit._quilts import demo, new_session

WHO = "A. Author"
AGENT = "Referee Agent"


def look(q: Path, *more: str, who: str = AGENT, env: dict[str, str] | None = None) -> dict[str, Any]:
    """One `loom since --json` as `who`; the report."""
    return json_of("since", "--as", who, "--json", *more, cwd=q, env=env)  # type: ignore[no-any-return]


def last_id(q: Path) -> str:
    return str(json.loads((q / ".loom/annotations" / "log.jsonl").read_text().splitlines()[-1])["id"])


@pytest.fixture
def q(tmp_path: Path) -> Path:
    """The demo with a fresh session, which is where a first look starts."""
    q = demo(tmp_path)
    new_session(q, "a sitting", WHO)
    return q


def test_a_first_look_reports_a_persons_annotations_whole_and_the_next_reports_nothing(q: Path) -> None:
    ok("annotate", "dm-0003", "Is this sharp?", "--type", "question", "--quote", "finite set", "--as", WHO, cwd=q)
    ok("annotate", "dm-0004", "A gap here.", "--as", AGENT, cwd=q)
    mine = last_id(q)
    ok("annotate", "--reply", mine, "It is not; see dm-0004.", "--as", WHO, cwd=q)
    got = look(q)
    assert got["first"] is True and got["verdict"].startswith(f"your first look as {AGENT}, since the session opened")
    asked, answered = got["annotations"]
    assert (asked["target"], asked["type"], asked["quote"], asked["body"]) == (
        "dm-0003",
        "question",
        "finite set",
        "Is this sharp?",
    )
    assert answered["act"] == "replied" and answered["yours"] is True and answered["to"] == AGENT
    assert all(a["by"] == WHO for a in got["annotations"]), "an agent's own annotation is no news to it"
    again = look(q)
    assert again["first"] is False and again["annotations"] == [] and again["verdict"].endswith(": nothing")


def test_the_boxes_a_person_set_are_reported_as_they_last_stood_and_once(q: Path) -> None:
    from loom.scan.quilt import load_quilt
    from loom.tasks import items, tick

    p = q / "todo.md"
    p.write_text("- [ ] one\n- [ ] two\n- [ ] three\n", encoding="utf-8")
    one, two, three = (t.id for t in items(p.read_text(encoding="utf-8")))
    quilt = load_quilt(q)
    tick(quilt, WHO, "todo.md", one, True)
    tick(quilt, WHO, "todo.md", two, True)
    tick(quilt, WHO, "todo.md", two, False)
    tick(quilt, AGENT, "todo.md", three, True)
    got = look(q, "--dry-run")
    assert [(t["path"], t["line"], t["done"], t["words"], t["by"]) for t in got["ticks"]] == [
        ("todo.md", 1, True, "one", WHO),
        ("todo.md", 2, False, "two", WHO),
    ]
    assert "2 boxes set" in got["verdict"]
    said = ok("since", "--as", AGENT, cwd=q).stdout
    assert "boxes set (2)" in said and "[x] todo.md:1  one" in said and "[ ] todo.md:2  two" in said
    assert look(q)["ticks"] == []


def test_a_record_of_the_markers_own_second_is_reported_once(q: Path) -> None:
    """Under one fixed clock every record carries the marker's second, so only what the marker carries tells old from new; the clock is set after the session's opening, which the real one stamped."""
    fixed = {"LOOM_FIXED_TIME": "2099-01-01T00:00:00Z"}
    ok("annotate", "dm-0002", "First.", "--as", WHO, cwd=q, env=fixed)
    assert [a["body"] for a in look(q, env=fixed)["annotations"]] == ["First."]
    ok("annotate", "dm-0003", "Second, in the same second.", "--as", WHO, cwd=q, env=fixed)
    assert [a["body"] for a in look(q, env=fixed)["annotations"]] == ["Second, in the same second."]
    assert look(q, env=fixed)["annotations"] == []


def test_what_a_person_settled_is_reported_with_whose_it_was(q: Path) -> None:
    ok("annotate", "dm-0003", "A gap here.", "--type", "revision", "--as", AGENT, cwd=q)
    gap = last_id(q)
    look(q)
    ok("annotate", "--resolve", gap, "Fixed in the source.", "--as", WHO, cwd=q)
    acts = {a["id"]: a for a in look(q)["acts"]}
    assert (acts[gap]["act"], acts[gap]["yours"], acts[gap]["body"], acts[gap]["type"]) == (
        "resolved",
        True,
        "Fixed in the source.",
        "revision",
    )
    # what a person wrote and deleted in one window is no news at all
    ok("annotate", "dm-0002", "Never mind.", "--as", WHO, cwd=q)
    ok("annotate", "--delete", last_id(q), "--as", WHO, cwd=q)
    later = look(q)
    assert later["annotations"] == [] and later["acts"] == []


def test_a_person_deleting_an_agents_annotation_is_said_to_that_agent_once(q: Path) -> None:
    """Nothing of a deleted annotation stays in the log, so the agent learns of it from one line kept for it until its next look: its type, its place and its quoted words, so it does not raise it again."""
    ok("annotate", "dm-0003", "A gap here.", "--type", "revision", "--quote", "finite set", "--as", AGENT, cwd=q)
    gap = last_id(q)
    ok("annotate", "dm-0004", "Mine.", "--as", "Other Agent", cwd=q)
    theirs = last_id(q)
    look(q)
    ok("annotate", "--delete", gap, "--as", WHO, cwd=q)
    ok("annotate", "--delete", theirs, "--as", WHO, cwd=q)
    said = ok("since", "--as", AGENT, "--dry-run", cwd=q).stdout
    assert gap in said and "deleted by A. Author" in said
    got = look(q)
    [act] = got["acts"]  # another agent's deletion is that agent's news
    assert (act["id"], act["act"], act["type"], act["target"], act["body"], act["by"], act["yours"]) == (
        gap,
        "deleted",
        "revision",
        "dm-0003",
        'on "finite set"',
        WHO,
        True,
    )
    # said once: the next look does not say it again, and the other agent's is still waiting for it
    assert look(q)["acts"] == []
    assert [a["id"] for a in look(q, who="Other Agent")["acts"]] == [theirs]
    assert look(q, who="Other Agent")["acts"] == []
    # an agent deleting its own leaves nothing to say
    ok("annotate", "dm-0002", "Wrong.", "--as", AGENT, cwd=q)
    ok("annotate", "--delete", last_id(q), "--as", AGENT, cwd=q)
    assert look(q)["acts"] == []


def test_an_acceptance_and_a_key_gone_stale_are_each_reported_once(q: Path) -> None:
    look(q)
    # staleness is the local reviewer's, as `loom status` shows it, so the acceptance is theirs
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "loom" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f'[author]\nname = "{WHO}"\n')
    ok("accept", "dm-0002", cwd=q)
    got = look(q)
    assert [r["key"] for r in got["accepted"]] == ["dm-0002"] and got["stale"] == []
    node = next(p for p in (q / "drafting" / "nodes").glob("*.tex") if "\\label{dm-0002}" in p.read_text())
    text = node.read_text()
    node.write_text(text.replace("\\label{dm-0002}", "\\label{dm-0002} An added clause.", 1))
    stale = look(q)["stale"]
    assert [r["key"] for r in stale] == ["dm-0002"] and stale[0]["why"] == ["edited"]
    assert look(q)["stale"] == []


def test_the_research_state_reports_a_persons_writes_and_edits_by_hand_as_diffs(q: Path) -> None:
    ok("write", "state", "Goals: the parity theorem.\n", "--as", AGENT, cwd=q)
    look(q)
    page = q / "research-state.md"
    page.write_text(page.read_text() + "Open: the balanced case.\n")
    [edited] = look(q)["state"]
    assert edited["act"] == "edited" and edited["by"] is None and "+Open: the balanced case." in edited["diff"]
    from loom.pages import text_hash

    ok(
        "write",
        "state",
        "Goals: the parity theorem, both cases.\n",
        "--base",
        text_hash(page.read_text()),
        "--as",
        WHO,
        cwd=q,
    )
    [written] = look(q)["state"]
    assert (written["act"], written["by"]) == ("written", WHO) and "+Goals: the parity theorem, both cases." in written[
        "diff"
    ]
    ok("write", "state", "Goals: settled.\n", "--base", text_hash(page.read_text()), "--as", AGENT, cwd=q)
    assert look(q)["state"] == [], "the agent's own write is no news to it"


def test_what_a_person_said_is_reported_and_an_agents_words_are_not(q: Path) -> None:
    look(q)
    ok("session", "say", "Have a look at dm-0003.", "--as", WHO, cwd=q)
    ok("session", "say", "Looked; one gap.", "--as", AGENT, cwd=q)
    [said] = look(q)["said"]
    assert (said["by"], said["body"]) == (WHO, "Have a look at dm-0003.")


def test_each_name_has_its_own_marker_and_a_dry_run_leaves_it(q: Path) -> None:
    ok("annotate", "dm-0002", "Is this sharp?", "--as", WHO, cwd=q)
    look(q)
    assert marker_path(q, AGENT).is_file()
    assert len(look(q, who="Tutor Agent")["annotations"]) == 1, "another agent has not looked yet"
    ok("annotate", "dm-0003", "And this?", "--as", WHO, cwd=q)
    before = marker_path(q, AGENT).read_text()
    assert len(look(q, "--dry-run")["annotations"]) == 1
    assert marker_path(q, AGENT).read_text() == before
    text = ok("since", "--as", AGENT, cwd=q).stdout
    assert text.startswith("since you last looked") and "annotations and replies (1)" in text and "And this?" in text


def test_the_marker_is_neither_committed_nor_watched(q: Path) -> None:
    from loom.gitignore import LOOM_LINES
    from loom.render.watch import snapshot

    look(q)
    assert "since/" in LOOM_LINES
    assert "\nsince/\n" in (q / ".loom" / ".gitignore").read_text()
    assert marker_path(q, AGENT) not in snapshot(q), "a look would rebuild the site"


@pytest.mark.poppler
def test_a_mark_on_a_pdf_page_is_reported_with_where_it_stands_and_a_crop(q: Path) -> None:
    """A mark on a project PDF names its page, file and tool, where it stands now and whether a changed file moved it; and the page round it as a crop, which `loom since` also prints."""
    from tests.unit._pdfs import PROSE, lines_pdf

    lines_pdf(q / "notes" / "paper.pdf", [PROSE])
    ok(
        "annotate",
        "notes/paper.pdf",
        "Is this used?",
        "--page",
        "1",
        "--box",
        "70,117,330,133",
        "--mark",
        "box",
        "--as",
        WHO,
        cwd=q,
    )
    (row,) = look(q)["annotations"]
    assert (row["page"], row["file"], row["mark"], row["refound"], row["source"]) == (
        1,
        "notes/paper.pdf",
        "box",
        False,
        None,
    )
    assert row["rects"] == [[70.0, 117.0, 330.0, 133.0]] and row["crop"].startswith(".loom/build/crops/")
    assert (q / row["crop"]).is_file()
    ok("annotate", "notes/paper.pdf", "And this?", "--page", "1", "--quote", "the median polytope", "--as", WHO, cwd=q)
    text = ok("since", "--as", AGENT, cwd=q).stdout
    assert "notes/paper.pdf p.1" in text and "      crop: .loom/build/crops/" in text


def test_a_session_looks_first_from_where_its_name_last_looked_and_then_on_its_own(q: Path) -> None:
    """Two conversations of one agent each look as their own session: one looking does not move the other's window, and a new one starts where the name last looked."""
    one = new_session(q, "conversation one", WHO)
    two = new_session(q, "conversation two", WHO)
    look(q)
    ok("annotate", "dm-0003", "First.", "--as", WHO, cwd=q)
    got = look(q, "--session", one)
    assert got["first"] is True and got["session"] == one
    assert got["verdict"].startswith(f"your first look in {one}, since {AGENT} last looked")
    assert [a["body"] for a in got["annotations"]] == ["First."]
    assert marker_path(q, AGENT, one).is_file() and marker_path(q, AGENT).is_file()
    assert look(q, "--session", two)["annotations"] == [], "it starts where the name's marker stands"
    ok("annotate", "dm-0003", "Second.", "--as", WHO, cwd=q)
    assert [a["body"] for a in look(q, "--session", one)["annotations"]] == ["Second."]
    assert [a["body"] for a in look(q, "--session", two)["annotations"]] == ["Second."]


def test_a_session_whose_name_never_looked_starts_when_it_opened(q: Path) -> None:
    ok("annotate", "dm-0003", "Before.", "--as", WHO, cwd=q)
    sid = new_session(q, "later", WHO)
    got = look(q, "--session", sid)
    assert got["first"] is True and got["verdict"].startswith(f"your first look as {AGENT}, since the session opened")


def test_a_sessions_first_look_with_no_marker_starts_where_a_look_with_no_session_does(q: Path) -> None:
    """Over MCP a conversation's session is made at its first look, so that look opens where the name's first look would, at the active session's opening, and not at its own: a person comments, then asks their agent."""
    from loom.sessions import for_conversation

    ok("annotate", "dm-0003", "Please look at this first.", "--as", WHO, cwd=q)
    time.sleep(1.1)  # the clock counts seconds: a session made in the annotation's own second would see it either way
    sid = for_conversation(q, "conv-a", AGENT, f"{AGENT} · now").id
    got = look(q, "--session", sid)
    assert got["first"] is True and [a["body"] for a in got["annotations"]] == ["Please look at this first."]
    assert look(q)["annotations"] == [], "the name's marker moved with the session's"

