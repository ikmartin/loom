"""The home server (`loom app`, `loom.app.server`): its guards, its endpoints for opening, stopping, forgetting and choosing quilts and for the person's name, the home page's address in every quilt server's `/_api`, a list it cannot read said and left alone, and a loop that goes on past any fault.

Each test runs a home in this process and real `loom serve` processes, with no compiles and a stand-in viewer, under the suite's own HOME and XDG folders.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from loom.app import registry, server, supervise
from loom.app.server import Home
from tests.helpers import PATIENCE
from tests.unit.app.conftest import until
from tests.unit.render._serve import get, post


@pytest.fixture
def home(bundle: Path, ports: None) -> Iterator[Home]:
    h = Home(bundle, port=0, extra=("--no-compile",))
    h.listen()
    yield h
    h.stop()


def quilt(where: Path) -> registry.Entry:
    from loom.cli.quilt import write_minimal_quilt

    write_minimal_quilt(where, "q")
    return registry.remember(where)


def call(home: Home, endpoint: str, body: dict[str, object] | None = None) -> tuple[int, dict[str, object]]:
    return post(home.url + "_api/" + endpoint, body or {})


def test_the_home_names_itself_and_gives_its_token_only_to_its_own_pages(home: Home) -> None:
    status, _, raw = get(home.url + "_api")
    said = json.loads(raw)
    assert status == 200 and said["home"] is True and said["token"] == home.token and said["pid"] == os.getpid()
    assert "quilt-open" in said["capabilities"] and said["viewer"] == "1" and said["stale"] is False
    assert get(home.url + "_api", {"Origin": "http://evil.test"})[0] == 403
    assert get(home.url + "_api", {"Host": f"evil.test:{home.port}"})[0] == 403
    assert get(home.url + "build/manifest.json")[0] == 404  # the home holds no quilt
    assert get(home.url + "anything")[2] == b"<p>viewer</p>"  # every other path is the viewer's


def test_a_write_without_the_token_or_from_another_page_is_refused(home: Home) -> None:
    assert post(home.url + "_api/quilt-list", {}, token="")[0] == 403
    assert post(home.url + "_api/quilt-list", {}, token="wrong")[0] == 403
    assert call(home, "quilt-nothing")[0] == 404


def test_a_quilt_is_opened_listed_stopped_and_forgotten(home: Home, tmp_path: Path) -> None:
    entry = quilt(tmp_path / "q")
    status, said = call(home, "quilt-open", {"quilt": entry.id})
    assert status == 200 and said["state"] in ("starting", "running")

    def listed() -> dict[str, object]:
        quilts = call(home, "quilt-list")[1]["quilts"]
        assert isinstance(quilts, list) and len(quilts) == 1
        return quilts[0]  # type: ignore[no-any-return]

    until(lambda: listed()["state"] == "running", "the quilt served")
    row = listed()
    assert row["name"] == "q" and row["url"] == f"http://127.0.0.1:{entry.port}/" and row["open"] is True
    assert call(home, "quilt-stop", {"quilt": entry.id})[1]["state"] == "stopped"
    assert listed()["open"] is False
    log = call(home, "quilt-check", {"quilt": entry.id})[1]
    assert "loom serve" in str(log["log"]) and isinstance(log["doctor"], dict)
    assert call(home, "quilt-forget", {"quilt": entry.id})[1]["forgotten"] is True
    assert call(home, "quilt-list")[1]["quilts"] == [] and (tmp_path / "q" / "config.toml").is_file()
    assert call(home, "quilt-open", {"quilt": entry.id})[0] == 404


def test_the_persons_name_is_asked_once_and_kept_for_every_quilt(home: Home) -> None:
    from loom.scan.quilt import user_config_path

    assert call(home, "quilt-list")[1]["name"] == {"name": "", "source": ""}
    status, said = call(home, "quilt-name", {"name": "Ada Lovelace"})
    assert status == 200 and said == {"name": "Ada Lovelace", "source": str(user_config_path())}
    assert 'name = "Ada Lovelace"' in user_config_path().read_text()
    assert call(home, "quilt-list")[1]["name"] == said


def test_a_folder_chosen_is_put_on_the_list_only_when_it_is_a_quilt(
    home: Home, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    picked: list[Path | None] = [None, tmp_path / "plain", tmp_path / "q", tmp_path / "somewhere"]
    (tmp_path / "plain").mkdir()
    quilt(tmp_path / "q")
    registry.forget(registry.remember(tmp_path / "q").id)
    monkeypatch.setattr(server, "choose_folder", lambda prompt: picked.pop(0))
    assert call(home, "quilt-choose", {"purpose": "open"})[1] == {"cancelled": True}
    status, said = call(home, "quilt-choose", {"purpose": "open"})
    assert status == 409 and said["error"]["code"] == "not-a-quilt"  # type: ignore[index]
    said = call(home, "quilt-choose", {"purpose": "open"})[1]
    assert [e.id for e in registry.entries()] == [said["quilt"]]
    assert call(home, "quilt-choose", {"purpose": "place"})[1] == {"folder": str(tmp_path / "somewhere")}


def test_a_quilts_server_names_the_home_page(home: Home, tmp_path: Path) -> None:
    """So a page whose server stopped can send the person back to the home page."""
    entry = quilt(tmp_path / "q")
    call(home, "quilt-open", {"quilt": entry.id})
    until(lambda: home.supervisor.state(entry)["state"] == "running", "the quilt served")
    assert json.loads(get(f"http://127.0.0.1:{entry.port}/_api")[2])["home"] == home.url


def test_every_endpoint_of_the_home_has_a_row_in_the_spec() -> None:
    import re

    spec = (Path(__file__).resolve().parents[4] / "docs" / "specs" / "write-api.md").read_text(encoding="utf-8")
    section = spec.split("## 7. The home server", 1)[1]
    assert sorted(re.findall(r"^\| `(quilt-[\w-]+)` \|", section, re.M)) == sorted(server.HANDLERS)


def test_repair_tex_runs_as_a_job_the_list_follows(home: Home, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.tex import private

    steps: list[str] = []

    def repair(*, say: object) -> None:
        assert callable(say)
        say("fetching TeX")
        steps.append("ran")

    monkeypatch.setattr(private, "repair", repair)
    job = call(home, "quilt-repair")[1]["job"]
    until(lambda: call(home, "quilt-list")[1]["jobs"][0]["state"] == "done", "Repair TeX")  # type: ignore[index]
    done = call(home, "quilt-list")[1]["jobs"][0]  # type: ignore[index]
    assert done["job"] == job and done["kind"] == "repair" and done["step"] == "fetching TeX"
    assert done["tex"] == private.active(year=False).kind
    assert steps == ["ran"]


def test_the_agents_server_says_once_loom_was_updated_under_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each call runs the loom on disk while the server, its tools and its instructions stay the one it started as; loom cannot restart it, only say so."""
    from loom.mcp import server as mcp_server
    from loom.version import code_stamp

    started = code_stamp()
    assert mcp_server.updated(started) == ""
    monkeypatch.setattr(mcp_server, "code_stamp", lambda: (started[0], started[1] + 1))
    said = mcp_server.updated(started)
    assert "updated" in said and "restart" in said and "loom " not in said.replace("loom in", "")


def test_a_forgotten_quilt_stays_stopped(home: Home, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A turn of the home's loop that waits for the lock while Forget stops the server must not start it again once the stop lets go: off the list, nothing could stop it."""
    entry = quilt(tmp_path / "q")
    call(home, "quilt-open", {"quilt": entry.id})
    until(lambda: home.supervisor.state(entry)["state"] == "running", "the quilt served")
    turns: list[threading.Thread] = []
    stop = home.supervisor.stop

    def stopping(e: registry.Entry) -> bool:
        with home.supervisor.lock:
            turn = threading.Thread(target=home.beat)
            turn.start()
            turns.append(turn)
            time.sleep(0.3)  # the turn is waiting for the lock the stop holds
            return stop(e)

    monkeypatch.setattr(home.supervisor, "stop", stopping)
    assert call(home, "quilt-forget", {"quilt": entry.id})[1]["forgotten"] is True
    for turn in turns:
        turn.join()
    home.beat()
    assert entry.id not in home.supervisor.children and supervise.ask(entry) is None


def test_a_list_the_home_cannot_read_is_said_and_left_as_it_is(home: Home, tmp_path: Path) -> None:
    entry = quilt(tmp_path / "q")
    listed = registry.folder() / "quilts.json"
    listed.write_text("{")
    said = call(home, "quilt-list")[1]
    assert said["list"] == "unreadable" and said["quilts"] == []
    status, refused = call(home, "quilt-open", {"quilt": entry.id})
    assert status == 409 and refused["error"]["code"] == "list-unreadable"  # type: ignore[index]
    assert not any(c in refused["error"]["message"] for c in ("`", "--", "/"))  # type: ignore[index]  # words, no command or path
    home.beat()
    assert listed.read_text() == "{"


def test_the_jobs_that_ended_outlive_the_homes_restart_after_an_update_which_waits_on_one_running(
    home: Home, bundle: Path
) -> None:
    go = threading.Event()
    ended = home.start_job("repair", lambda step: {"tex": "mine"})
    held = home.start_job("repair", lambda step: {"tex": "loom"} if go.wait(PATIENCE) else {})
    until(lambda: home.jobs[ended]["state"] == "done", "the first job ended")
    home.code = (0, 0)  # loom's code moved under the home long ago
    home.supervisor.still_since = time.monotonic() - 3600
    restarted = threading.Event()

    def reexec() -> None:
        restarted.set()
        home.stopping.set()

    threading.Thread(target=home.run, args=(reexec,), daemon=True).start()
    time.sleep(2.5)
    assert not restarted.is_set()
    go.set()
    until(restarted.is_set, "the restart once no job ran")
    again = Home(bundle, port=0, extra=("--no-compile",))
    again.listen()
    try:
        jobs: list[dict[str, object]] = call(again, "quilt-list")[1]["jobs"]  # type: ignore[assignment]
        assert [(j["job"], j["state"], j["tex"]) for j in jobs] == [(held, "done", "loom"), (ended, "done", "mine")]
    finally:
        again.stop()
    assert not (registry.folder() / "jobs.json").exists()


def test_the_homes_loop_goes_on_past_any_fault(home: Home, monkeypatch: pytest.MonkeyPatch) -> None:
    def fault() -> None:
        raise RuntimeError("anything")

    monkeypatch.setattr(home.supervisor, "tick", fault)
    home.beat()
    assert get(home.url + "_api")[0] == 200
