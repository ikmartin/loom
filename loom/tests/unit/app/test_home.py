"""The home server (`loom app`, `loom.app.server`): its guards, its endpoints for opening, stopping, forgetting and choosing quilts and for the person's name, and the home page's address in every quilt server's `/_api`.

Each test runs a home in this process and real `loom serve` processes, with no compiles and a stand-in viewer, under the suite's own HOME and XDG folders.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from loom.app import registry, server
from loom.app.server import Home
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
    assert status == 200 and said["home"] is True and said["token"] == home.token
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
