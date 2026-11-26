"""The write API over a running `loom serve` (specs/write-api.md): discovery, the CSRF gate, comments and their answers, refusals as JSON, citation suggestions, and who a browser write is from."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import the
from tests.unit._quilts import REPO, demo, new_session, open_session
from tests.unit.render._serve import get, log, post
from tests.unit.render.write_api import (  # noqa: F401  (each fills CASES as it is imported)
    cases_agents,
    cases_annotations,
    cases_changes,
    cases_files,
    cases_formal,
    cases_library,
    cases_library_evidence,
    cases_notes,
    cases_review,
    cases_sync,
    cases_web,
)
from tests.unit.render.write_api._cases import (
    CASES,
    WHO,
    Serve,
    drawn,
    refuses,
    succeeds,
    with_paper,
)


def test_the_write_api_binds_to_loopback_only(session) -> None:  # type: ignore[no-untyped-def]
    """specs/write-api.md §3 has no authentication and says so, resting entirely on the socket never leaving this machine. That was an assumption until this test."""
    s, _ = session
    assert s.httpd is not None
    assert s.httpd.server_address[0] == "127.0.0.1"


def test_discovery_lists_what_this_publisher_serves(session) -> None:  # type: ignore[no-untyped-def]
    s, _ = session
    status, _, raw = get(s.url + "_api")
    assert status == 200
    body = json.loads(raw)
    from loom.render.api import discovery

    assert body["write_api"] == 1
    assert body["capabilities"] == discovery()["capabilities"]
    # the frames origin is named, and it is not this server
    assert body["frames"].startswith("http://127.0.0.1:") and body["frames"] != s.url.rstrip("/")


def test_a_comment_written_over_http_is_the_same_comment(session) -> None:  # type: ignore[no-untyped-def]
    """One implementation of what an annotation is: the endpoint calls the function the CLI calls, so the two cannot drift."""
    s, d = session
    sid = open_session(d)
    status, body = post(
        s.url + "_api/annotate",
        {
            "session": sid,
            "target": "dm-0003",
            "message": "Written from the viewer.",
            "type": "revision",
            "look": {"color": "green"},
            "author": "A Reader",
        },
    )
    assert status == 200, body
    mine = [e for e in log(d) if e.get("body") == "Written from the viewer."]
    assert len(mine) == 1
    assert mine[0]["kind"] == "human" and mine[0]["author"] == "A Reader"
    assert (mine[0]["type"], mine[0]["look"], mine[0]["drawn"]["color"]) == ("revision", {"color": "green"}, "green")

    # and it can be answered, restated and deleted over the same surface
    ann = mine[0]["id"]
    for endpoint, extra in (
        ("reply", {"message": "Noted."}),
        ("edit", {"message": "Restated."}),
        ("delete", {}),
    ):
        status, body = post(
            s.url + f"_api/{endpoint}", {"session": sid, "annotation": ann, "author": "A Reader", **extra}
        )
        assert status == 200, (endpoint, body)
    assert [e["event"] for e in body["removed"]] == ["created", "replied", "edited"]  # the reply went with it
    assert not [e for e in log(d) if ann in (e.get("id"), e.get("reply_to"))]


def test_the_manifest_is_current_when_a_write_answers(session) -> None:  # type: ignore[no-untyped-def]
    """A write rebuilds before it answers, so the `refresh()` a viewer runs on the answer never races the watcher. Asserted as the property -- the manifest carries the write when the POST resolves -- rather than as a duration, which would be a flake on a loaded machine."""
    s, d = session
    sid = open_session(d)
    status, body = post(s.url + "_api/session-rename", {"session": sid, "title": "renamed in place"})
    assert status == 200, body
    # no sleep, no poll: the very next read must already have it
    _, _, raw = get(s.url + "build/manifest.json")
    rows = {x["id"]: x for x in json.loads(raw)["sessions"]}
    assert rows[sid]["title"] == "renamed in place", rows[sid]


def test_a_refused_write_answers_rather_than_dying(session) -> None:  # type: ignore[no-untyped-def]
    s, d = session
    sid = open_session(d)
    status, body = post(s.url + "_api/annotate", {"session": sid, "message": "no target"})
    assert status == 400 and body["error"]["code"] == "missing-field", body
    status, body = post(s.url + "_api/annotate", {"session": sid, "target": "nope-9999", "message": "x", "author": "R"})
    assert status == 404 and body["error"] == {"code": "no-such-node", "message": "no such key: nope-9999"}, body
    status, body = post(s.url + "_api/delete", {"session": sid, "annotation": "a-1999-01-01-ekn992", "author": "R"})
    assert status == 404 and body["error"] == {
        "code": "no-such-annotation",
        "message": "no annotation a-1999-01-01-ekn992",
    }, body
    # nobody to sign it: the quilt names no author and the browser gave none
    status, body = post(s.url + "_api/annotate", {"session": sid, "target": "dm-0003", "message": "unsigned"})
    assert status == 400 and body["error"]["code"] == "refused" and "no author name" in body["error"]["message"], body


def test_a_write_without_the_token_is_refused_over_the_wire(session) -> None:  # type: ignore[no-untyped-def]
    """A browser blocks a cross-origin response and never the request, so any page the author happens to be reading could otherwise POST into their quilt (plan 0.13 §8)."""
    s, d = session
    body = {"session": open_session(d), "target": "dm-0003", "message": "from somewhere else", "author": "Nobody"}
    status, said = post(s.url + "_api/annotate", body, token="")
    assert status == 403 and "X-Loom-Token" in said["error"]["message"], said
    assert not [e for e in log(d) if e.get("body") == "from somewhere else"]

    # the token is served where the viewer reads it, and the same well-formed write carrying it is written
    _, _, discovery = get(s.url + "_api")
    assert json.loads(discovery)["token"]
    # and which quilt it is, a digest of where it lies, never the place: what the viewer keeps per quilt is keyed by it
    served = json.loads(discovery)["quilt"]
    assert len(served) == 16 and str(d) not in discovery.decode() and str(d.resolve()) not in discovery.decode()
    status, said = post(s.url + "_api/annotate", body)
    assert status == 200, said
    assert len([e for e in log(d) if e.get("body") == "from somewhere else"]) == 1


def test_the_write_api_refuses_a_post_from_another_page() -> None:
    """The gate each branch of it: an Origin that is not this server, a content type a cross-site form can send, and a missing token are each refused by name."""
    from loom.render.serve import LoomHandler

    checks = LoomHandler._csrf

    class Fake:
        token = "right"
        server = type("S", (), {"server_address": ("127.0.0.1", 8791)})()

        def __init__(self, headers: dict[str, str]) -> None:
            self.headers = headers

    good = {"Content-Type": "application/json", "X-Loom-Token": "right", "Origin": "http://127.0.0.1:8791"}
    assert checks(Fake(good)) == ""  # type: ignore[arg-type]
    assert "not this server" in checks(Fake({**good, "Origin": "https://example.org"}))  # type: ignore[arg-type]
    # a cross-site form post can set neither a custom header nor a JSON content type
    assert "application/json" in checks(Fake({**good, "Content-Type": "application/x-www-form-urlencoded"}))  # type: ignore[arg-type]
    assert "X-Loom-Token" in checks(Fake({"Content-Type": "application/json"}))  # type: ignore[arg-type]
    # a sandboxed page has an opaque origin, which a browser sends as `null`
    assert "not this server" in checks(Fake({**good, "Origin": "null"}))  # type: ignore[arg-type]
    assert "cross-site" in checks(Fake({**good, "Sec-Fetch-Site": "cross-site"}))  # type: ignore[arg-type]


def test_a_page_the_quilt_holds_is_served_with_no_origin_of_the_viewers(session) -> None:  # type: ignore[no-untyped-def]
    """`/build/` and the library's stored PDFs are served in the viewer's origin, and an agent running as the person can write what they serve. An HTML or SVG page there that ran as the viewer could read the token from `/_api` and post the author's acts naming no author, which is the author's own click (K5). Each is served sandboxed: it runs no script and has an opaque origin. The viewer's own bundle is not."""
    from loom.paths import LIBRARY_DOCUMENTS, SITE

    s, d = session
    planted = {  # address: (file, text)
        "build/agent/x.html": (f"{SITE}/agent/x.html", "<!doctype html><script>fetch('/_api')</script>"),
        f"_api/library/pdf/{'a' * 64}": (
            f"{LIBRARY_DOCUMENTS}/{'a' * 64}.pdf",
            '<svg xmlns="http://www.w3.org/2000/svg"><script>fetch("/_api")</script></svg>',
        ),
        "build/agent/x.txt": (f"{SITE}/agent/x.txt", "<!doctype html><script>fetch('/_api')</script>"),
    }
    for rel, (file, text) in planted.items():
        (d / file).parent.mkdir(parents=True, exist_ok=True)
        (d / file).write_text(text, encoding="utf-8")
        status, headers, _ = get(s.url + rel)
        assert status == 200, rel
        assert headers.get("Content-Security-Policy") == "sandbox", (rel, headers)
        assert headers.get("X-Content-Type-Options") == "nosniff", (rel, headers)
        # a copy a browser cached before it was sandboxed is revalidated, and the answer that it is unchanged sandboxes it too
        status, headers, _ = get(s.url + rel, {"If-None-Match": headers["ETag"]})
        assert status == 304 and headers.get("Content-Security-Policy") == "sandbox", (rel, headers)
    for path in ("", "_app/x.js", "node/dm-0003"):
        status, headers, _ = get(s.url + path)
        assert status == 200 and "Content-Security-Policy" not in headers, (path, headers)


def test_the_token_is_served_only_to_the_viewers_own_origin(session) -> None:  # type: ignore[no-untyped-def]
    """`GET /_api` hands out the token, so a request a browser says came from another origin, a sandboxed page's `null` included, is refused; a request with no browser's headers, and the person typing the address, are answered."""
    from loom.machine import read_token

    s, d = session
    here = s.url.rstrip("/")
    for headers in (
        {"Origin": "null"},
        {"Origin": "https://example.org"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ):
        status, _, _ = get(s.url + "_api", headers)
        assert status == 403, headers
    for headers in ({}, {"Origin": here}, {"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}):
        status, _, raw = get(s.url + "_api", headers)
        assert status == 200 and json.loads(raw)["token"] == read_token(d), headers


def test_a_request_that_names_another_host_is_answered_nothing(session) -> None:  # type: ignore[no-untyped-def]
    """DNS rebinding: a domain pointed at 127.0.0.1 is same-origin with the server as the browser sees it, so its page's reads carry no foreign `Origin` and would be given the token and every file; each still names the domain as its `Host`."""
    import urllib.error
    import urllib.request

    from loom.machine import read_token
    from tests.helpers import PATIENCE

    s, d = session
    token = read_token(d)
    for host in (f"rebound.example:{s.port}", "rebound.example", f"127.0.0.1:{s.port + 1}", "127.0.0.1"):
        for path in ("_api", "", "node/dm-0003", "build/manifest.json", "_app/x.js", "_api/stream"):
            status, _, _ = get(s.url + path, {"Host": host, "X-Loom-Token": token})
            assert status == 403, (host, path)
        for method, data in (("HEAD", None), ("POST", b"{}")):
            asked = urllib.request.Request(
                s.url + ("_api/here" if data else ""),
                data=data,
                method=method,
                headers={"Host": host, "X-Loom-Token": token, "Content-Type": "application/json"},
            )
            with pytest.raises(urllib.error.HTTPError) as refused:
                urllib.request.urlopen(asked, timeout=PATIENCE)
            assert refused.value.code == 403 and token.encode() not in refused.value.read(), (host, method)
    for host in (f"127.0.0.1:{s.port}", f"localhost:{s.port}", f"LOCALHOST:{s.port}"):
        status, _, raw = get(s.url + "_api", {"Host": host})
        assert status == 200 and json.loads(raw)["token"] == token, host
        assert get(s.url + "build/manifest.json", {"Host": host})[0] == 200, host


def test_a_browser_write_is_the_person_at_the_browser_not_the_servers_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With `loom serve` started in an agent's terminal, a note written in the author's own browser is the configured author's, never `agent`; an agent posting to the same endpoint names itself and is believed by its name."""
    from loom.render.api import handle

    q = demo(tmp_path)
    (q / "config.toml").write_text(
        (q / "config.toml").read_text() + '\n[author]\nname = "Wren Halloway"\n', encoding="utf-8"
    )
    from loom.scan.quilt import save_author

    save_author("Wren Halloway")
    monkeypatch.setenv("AI_AGENT", "1")
    said = handle(q, "annotate", {"session": open_session(q), "target": "dm-0003", "message": "from the browser"})
    assert said["ok"], said
    written = log(q)[-1]
    assert written["author"] == "Wren Halloway" and written["kind"] == "human", written
    handle(
        q,
        "annotate",
        {
            "session": open_session(q),
            "target": "dm-0003",
            "message": "from an agent",
            "author": "Referee (Agent)",
        },
    )
    robot = log(q)[-1]
    assert robot["author"] == "Referee (Agent)" and robot["kind"] == "agent", robot


def test_an_annotation_on_a_pdf_is_written_and_redrawn_over_the_wire(serve: Serve, tmp_path: Path) -> None:
    """A project PDF by its path with its page and place, a tool and its strokes; an edit moves or redraws it, and an agent edits only its own."""
    s, q = with_paper(serve, tmp_path)
    ann = drawn(s, q)
    made = the(log(q), lambda e: e.get("id") == ann, "the box")
    assert (made["target"], made["page"], made["rects"], made["mark"]) == (
        "notes/paper.pdf",
        1,
        [[10, 10, 60, 60]],
        "box",
    )
    succeeds(s, "edit", {"annotation": ann, "message": "says this now", "rects": [[20, 20, 70, 70]], "author": WHO})
    edited = log(q)[-1]
    assert (edited["body"], edited["rects"]) == ("says this now", [[20, 20, 70, 70]])
    ink = succeeds(
        s,
        "annotate",
        {"target": "notes/paper.pdf", "page": 1, "strokes": [[1, 2, 30, 40]], "mark": "ink", "author": WHO},
    )["result"].split()[0]
    succeeds(s, "edit", {"annotation": ink, "strokes": [[5, 5, 9, 9]], "author": WHO})
    assert (log(q)[-1]["strokes"], log(q)[-1]["rects"]) == ([[5, 5, 9, 9]], [[5, 5, 9, 9]])
    refuses(s, "edit", {"annotation": ann, "strokes": "x", "author": WHO}, 400, "bad-field", "strokes")
    refuses(
        s,
        "annotate",
        {"target": "notes/paper.pdf", "page": 1, "mark": "pin", "rects": [[1, 1, 9, 9]], "author": WHO},
        400,
        "bad-request",
        "says something",
    )
    # a note on a whole work, named by the key its entry has, is recorded on its reference
    from loom.cli._quilt import open_scan

    whole = succeeds(s, "annotate", {"target": "Calloway14", "message": "Read this paper through.", "author": WHO})
    said = the(log(q), lambda e: e.get("body") == "Read this paper through.", "whole")
    assert said["target"] == open_scan(str(q)).refs["Calloway14"] and whole["ok"]


def test_a_write_larger_than_the_publisher_reads_is_refused_before_it_is_read(session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    s, _ = session
    monkeypatch.setattr("loom.render.api.MAX_BODY", 64)
    status, said = post(s.url + "_api/library-take", {"items": [{"text": "x" * 200}]})
    assert status == 413 and said["error"]["code"] == "too-large"


#: The endpoints whose cases read a stored PDF's text or word boxes, which the real poppler gives.
POPPLER = (
    "locate",
    "library-places",
    "library-work",
    "library-digest-scopes",
    "library-node",
    "library-find",
    "library-digest",
)


@pytest.mark.parametrize(
    "endpoint",
    [pytest.param(e, marks=pytest.mark.poppler) if e in POPPLER else e for e in sorted(CASES)],
)
def test_each_endpoint_writes_and_refuses_over_the_wire(
    endpoint: str, serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One success, with what the server wrote read back from the quilt, and one refusal with its status, code and message; `locate` needs the real pdftotext for its page's word boxes."""
    CASES[endpoint](serve, tmp_path, monkeypatch)


def test_every_capability_has_a_case_and_a_row_in_the_spec() -> None:
    """A capability served without a case above fails here, as does a case for one no longer served, and one specs/write-api.md does not list; `open`, served only where loom can open an application, has its case and its row everywhere."""
    import re

    from loom.render.api import CAPABILITIES

    CAPABILITIES = [*CAPABILITIES, "open"]  # noqa: N806
    assert sorted(CASES) == sorted(CAPABILITIES)
    spec = (REPO.parent / "docs" / "specs" / "write-api.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| `POST` \| `/_api/([\w-]+)`", spec, re.M))
    assert sorted(set(CAPABILITIES) - listed) == [], "served but not in specs/write-api.md's tables"
    assert sorted(listed - set(CAPABILITIES)) == [], "in specs/write-api.md's tables but not served"


def test_every_endpoint_belongs_to_one_family_which_says_what_the_publisher_does_after_it() -> None:
    """An endpoint is in one family's `HANDLERS` and no other's, and a family's `READS`, `NO_REBUILD` and `RECORD_WRITES` name its own endpoints: a name left in a table after its handler went would be rebuilt after, or not, for nothing."""
    from loom.render.api import FAMILIES, HANDLERS

    assert sum(len(family.HANDLERS) for family in FAMILIES) == len(HANDLERS)
    for family in FAMILIES:
        for table in (family.READS, family.NO_REBUILD, family.RECORD_WRITES):
            assert set(table) <= set(family.HANDLERS), (family.__name__, sorted(set(table) - set(family.HANDLERS)))
        assert set(family.READS) <= set(family.NO_REBUILD), family.__name__


def test_an_endpoint_not_served_is_a_404_naming_it(session) -> None:  # type: ignore[no-untyped-def]
    """An endpoint outside the list is a 404, which is what lets a viewer hide the affordance."""
    s, _ = session
    status, said = post(s.url + "_api/accept", {"keys": ["dm-0003"]})
    assert status == 404 and said == {"error": {"code": "unknown-endpoint", "message": "no endpoint accept"}}, said


def test_events_needs_a_session_and_reads_a_bad_since_as_the_start(session) -> None:  # type: ignore[no-untyped-def]
    from loom.mailbox import post as say

    s, d = session
    status, _, raw = get(s.url + "_api/events")
    assert status == 400
    sid = new_session(d)
    say(d, sid, "First.", WHO)
    status, _, raw = get(s.url + f"_api/events?session={sid}&since=abc")
    body = json.loads(raw)
    assert status == 200 and body["from"] == 0 and [e["body"] for e in body["events"]] == ["First."], body
