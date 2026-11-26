"""A new quilt from what is dropped on the home page (`loom.app.create`): a `.tex`, a folder, a `.tar.gz`, a `.zip` and a lone gzip each make a quilt whose document is drafted; an archive that reaches outside is refused and writes nothing outside; a paper that cannot typeset, or whose draft typesets differently, still comes in; several candidates make a question; the drop is gone once the quilt is made; a quilt comes into being whole or not at all, whatever stops its create; two creates of one name make one quilt; and nothing a drop holds stops the home starting.

Each test runs under the suite's own HOME and XDG folders, with the fake TeX on PATH.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import signal
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from loom.app import create, registry
from loom.app.registry import Entry
from loom.app.server import Home
from loom.render.endpoints.base import ApiError
from tests.helpers import PATIENCE
from tests.unit.app.conftest import until
from tests.unit.render._serve import post

PAPER = b"\\documentclass{article}\n\\newtheorem{thm}{Theorem}\n\\begin{document}\nHello.\n\\end{document}\n"
#: A theorem that shares its line with other text, which a plain import refuses (the queue, 22).
UNANCHORED = (
    b"\\documentclass{article}\n\\newtheorem{thm}{Theorem}\n\\begin{document}\n"
    b"Text. \\begin{thm}Hello.\n\\end{thm}\n\\end{document}\n"
)


def drop(files: dict[str, bytes]) -> str:
    """A drop holding `files`, each received as the home receives it."""
    key: str | None = None
    for rel, data in files.items():
        key = create.receive(key, rel, io.BytesIO(data), len(data))["drop"]
    assert key is not None
    return key


def served(entry: Entry) -> dict[str, Any]:
    return {"state": "running", "url": f"http://127.0.0.1:{entry.port}/"}


def made(tmp_path: Path, files: dict[str, bytes], name: str = "My paper") -> dict[str, Any]:
    """The quilt `files` make, in `tmp_path`, the way `quilt-create` makes it."""
    key = drop(files)
    main = create.paper(key, None)
    assert isinstance(main, Path), main
    done = create.make(create.target(name, str(tmp_path)), main, lambda step: None, served)
    create.let_go(key)
    return done


def tar_gz(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return out.getvalue()


def zipped(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return out.getvalue()


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({"paper.tex": PAPER}, id="a .tex"),
        pytest.param(
            {
                "paper/paper.tex": PAPER.replace(b"Hello.", b"\\input{intro}"),
                "paper/intro.tex": b"Hello.\n",
                "paper/notes.txt": b"x",
            },
            id="a folder",
        ),
        pytest.param({"arXiv-2009.07720v1.tar.gz": tar_gz({"paper.tex": PAPER, "fig/a.txt": b"x"})}, id="a .tar.gz"),
        pytest.param({"paper.zip": zipped({"paper.tex": PAPER})}, id="a .zip"),
        pytest.param({"paper.gz": gzip.compress(PAPER)}, id="a lone gzip"),
    ],
)
def test_each_form_of_a_paper_makes_a_quilt_whose_document_is_drafted(tmp_path: Path, files: dict[str, bytes]) -> None:
    from loom.scan.quilt import load_quilt

    done = made(tmp_path, files)
    q = tmp_path / "My paper"
    assert done["document"] == "paper/paper.tex" and (q / "paper" / "paper.tex").is_file()
    assert load_quilt(q).config.home == "paper/paper.tex"  # it opens on the paper
    assert not (q / "README.md").exists()  # and not on a page about loom's commands
    assert done["typeset"] is True and done["differs"] is False and done["state"] == "running"
    assert [e.root for e in registry.entries()] == [str(q.resolve())] and registry.entries()[0].open
    assert list(create.incoming().iterdir()) == []


@pytest.fixture
def place(tmp_path: Path) -> Path:
    """An empty folder of the person's that new quilts go in, apart from the test's home folder."""
    p = tmp_path / "place"
    p.mkdir()
    return p


def test_a_new_quilt_goes_in_quilts_in_the_home_folder_by_default(home: Path) -> None:
    assert create.target("Notes", None) == home / "Quilts" / "Notes"


def test_a_paper_whose_theorem_shares_its_line_comes_in(tmp_path: Path) -> None:
    done = made(tmp_path, {"paper.tex": UNANCHORED})
    assert "\\begin{thm}" in (tmp_path / "My paper" / done["document"]).read_text()


def test_a_paper_with_no_tex_still_comes_in_and_nothing_said_is_a_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    done = made(tmp_path, {"paper.tex": PAPER}, name="Notes")
    assert done["typeset"] is False and done["untypeset"] and done["tex"] == "none"
    assert (tmp_path / "Notes" / "paper" / "paper.tex").is_file()
    assert "loom " not in json.dumps(done) and "--" not in json.dumps(done)


def test_a_draft_that_typesets_differently_comes_in_all_the_same_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.cli import paper
    from loom.tex.identity import IdentityResult

    monkeypatch.setattr(paper, "identity_test", lambda *a, **k: IdentityResult(False, first_difference=("a", "b")))
    done = made(tmp_path, {"paper.tex": PAPER})
    assert done["differs"] is True and (tmp_path / "My paper" / "paper" / "paper.tex").is_file()


@pytest.mark.parametrize(
    "archive",
    [
        pytest.param(tar_gz({"../evil.tex": PAPER}), id="tar reaching up"),
        pytest.param(zipped({"../evil.tex": PAPER}), id="zip reaching up"),
    ],
)
def test_an_archive_that_reaches_outside_is_refused_and_writes_nothing_outside(tmp_path: Path, archive: bytes) -> None:
    key = drop({"paper.tar.gz": archive})
    with pytest.raises(ApiError) as refused:
        create.paper(key, None)
    assert refused.value.code == "bad-archive"
    assert not list(create.incoming().parent.rglob("evil.tex")) and not (create.incoming() / key / "unpacked").exists()


def test_a_link_in_a_tar_that_points_outside_is_refused(tmp_path: Path) -> None:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        link = tarfile.TarInfo("paper.tex")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        t.addfile(link)
    key = drop({"paper.tgz": out.getvalue()})
    with pytest.raises(ApiError, match="safely"):
        create.paper(key, None)


def test_a_dropped_files_path_must_stay_inside_the_drop() -> None:
    for bad in ("../x.tex", "/etc/x.tex", "a/../../x.tex", ""):
        with pytest.raises(ApiError, match="inside"):
            create.receive(None, bad, io.BytesIO(b"x"), 1)


def test_several_files_a_paper_could_be_typeset_from_make_one_question(tmp_path: Path) -> None:
    key = drop({"talk.tex": PAPER, "paper.tex": PAPER, "intro.tex": b"Hello.\n"})
    assert create.paper(key, None) == ["paper.tex", "talk.tex"]
    assert create.paper(key, "talk.tex") == create.sources(key) / "talk.tex"
    readme = json.dumps({"sources": [{"filename": "talk.tex", "usage": "toplevel"}]}).encode()
    arxiv = drop({"talk.tex": PAPER, "paper.tex": PAPER, "00README.json": readme})
    assert create.paper(arxiv, None) == create.sources(arxiv) / "talk.tex"  # arXiv's own word for which it is


def test_a_folder_of_that_name_there_already_is_refused(tmp_path: Path) -> None:
    (tmp_path / "Mine").mkdir()
    (tmp_path / "Mine" / "x").write_text("x")
    with pytest.raises(ApiError) as refused:
        create.target("Mine", str(tmp_path))
    assert refused.value.code == "exists"


@pytest.fixture
def home_server(bundle: Path, ports: None) -> Iterator[Home]:
    h = Home(bundle, port=0, extra=("--no-compile",))
    h.listen()
    yield h
    h.stop()


def test_a_paper_dropped_over_the_wire_becomes_a_quilt_that_is_served(home_server: Home, tmp_path: Path) -> None:
    import urllib.request

    def put(path: str, data: bytes, drop: str = "") -> dict[str, Any]:
        query = f"path={path}" + (f"&drop={drop}" if drop else "")
        req = urllib.request.Request(
            f"{home_server.url}_api/quilt-receive?{query}",
            data=data,
            headers={"Content-Type": "application/octet-stream", "X-Loom-Token": home_server.token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())  # type: ignore[no-any-return]
        except urllib.error.HTTPError as e:
            return {"status": e.code, **json.loads(e.read())}

    assert put("..%2Fx.tex", b"x")["error"]["code"] == "bad-path"
    key = put("paper%2Fpaper.tex", PAPER)["drop"]
    assert put("paper%2Fintro.tex", b"Hello.\n", key)["drop"] == key
    status, said = post(home_server.url + "_api/quilt-create", {"name": "Dropped", "place": str(tmp_path), "drop": key})
    assert status == 200, said

    def job() -> dict[str, Any]:
        jobs = post(home_server.url + "_api/quilt-list", {})[1]["jobs"]
        return next(j for j in jobs if j["job"] == said["job"])  # type: ignore[no-any-return]

    until(lambda: job()["state"] != "running", "the quilt made")
    done = job()
    assert done["state"] == "done" and done["document"] == "paper/paper.tex", done
    entry = registry.find(done["quilt"])
    assert entry is not None
    until(lambda: home_server.supervisor.state(entry)["state"] == "running", "the quilt served")


def test_a_quilt_made_on_the_home_page_is_the_persons_act_whichever_shell_started_the_home(
    home_server: Home, place: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.paths import JOURNAL

    monkeypatch.setenv("CLAUDECODE", "1")  # the home started from an agent's terminal
    job = create_job(home_server, "Mine", place, drop({"paper.tex": PAPER}))
    until(lambda: job()["state"] != "running", "the quilt made")
    assert job()["state"] == "done", job()
    lines = [json.loads(line) for line in (place / "Mine" / JOURNAL).read_text().splitlines()]
    imports = [e for e in lines if e.get("event") == "begin" and e.get("kind") == "import"]
    assert [e["by"] for e in imports] == ["person"], imports


def test_a_create_while_the_list_cannot_be_read_is_refused_and_makes_nothing(home_server: Home, place: Path) -> None:
    listed = registry.folder() / "quilts.json"
    listed.write_text("{")
    key = drop({"paper.tex": PAPER})
    status, said = post(home_server.url + "_api/quilt-create", {"name": "Unlisted", "place": str(place), "drop": key})
    assert status == 409 and said["error"]["code"] == "list-unreadable", said
    assert list(place.iterdir()) == [] and listed.read_text() == "{" and (create.incoming() / key).is_dir()


def test_a_file_dropped_where_a_folder_was_dropped_is_refused() -> None:
    key = drop({"a/b.tex": PAPER})
    with pytest.raises(ApiError) as refused:
        create.receive(key, "a", io.BytesIO(b"x"), 1)
    assert refused.value.code == "bad-path" and [p.name for p in (create.incoming() / key / "files").iterdir()] == ["a"]


def test_an_import_stopped_by_anything_leaves_no_folder_behind(place: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.cli import paper

    def stopped(*a: object, **k: object) -> None:
        raise RuntimeError("stopped")

    monkeypatch.setattr(paper, "run_import", stopped)
    key = drop({"paper.tex": PAPER})
    main = create.paper(key, None)
    assert isinstance(main, Path)
    with pytest.raises(RuntimeError):
        create.make(create.target("Gone", str(place)), main, lambda step: None, served)
    assert list(place.iterdir()) == [] and registry.entries() == []
    assert list(create.making().iterdir()) == []


#: A create whose process is killed outright as its import begins, as a crash, a forced quit or a power cut ends one.
CUT = """
import io, os, signal, sys
from loom.app import create
from loom.cli import paper

text = sys.argv[2].encode()
main = create.paper(create.receive(None, "paper.tex", io.BytesIO(text), len(text))["drop"], None)
paper.run_import = lambda *a, **k: os.kill(os.getpid(), signal.SIGKILL)
create.make(create.target("Cut", sys.argv[1]), main, lambda step: None, lambda entry: {})
"""


def test_a_create_cut_short_leaves_nothing_in_its_place_and_the_next_start_clears_what_it_left(place: Path) -> None:
    cut = subprocess.run([sys.executable, "-c", CUT, str(place), PAPER.decode()], check=False)
    assert cut.returncode == -signal.SIGKILL
    assert not (place / "Cut").exists()  # so a create of the same name is not refused for ever
    assert [p.name.startswith(".loom-making-") for p in place.iterdir()] == [True]
    create.recover()  # what the home's start does
    assert list(place.iterdir()) == [] and list(create.making().iterdir()) == []
    assert made(place, {"paper.tex": PAPER}, name="Cut")["document"] == "paper/paper.tex"


def test_a_quilt_moved_into_its_place_before_its_create_was_cut_is_put_on_the_list_at_the_next_start(
    place: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def cut(*a: object) -> registry.Entry:
        raise KeyboardInterrupt  # stands in for the process ending between the move and the list

    monkeypatch.setattr(registry, "remember", cut)
    key = drop({"paper.tex": PAPER})
    main = create.paper(key, None)
    assert isinstance(main, Path)
    with pytest.raises(KeyboardInterrupt):
        create.make(create.target("Moved", str(place)), main, lambda step: None, served)
    monkeypatch.undo()
    create.recover()
    assert [e.root for e in registry.entries()] == [str((place / "Moved").resolve())] and registry.entries()[0].open
    assert [p.name for p in place.iterdir()] == ["Moved"] and list(create.making().iterdir()) == []


@pytest.fixture
def held_import(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[threading.Event, threading.Event]]:
    """The import waits, once begun, until the test lets it go: (begun, go)."""
    from loom.cli import paper

    begun, go = threading.Event(), threading.Event()
    real = paper.run_import

    def held(*a: Any, **k: Any) -> Any:
        begun.set()
        go.wait(PATIENCE)
        return real(*a, **k)

    monkeypatch.setattr(paper, "run_import", held)
    yield begun, go
    go.set()


def create_job(home: Home, name: str, place: Path, key: str) -> Callable[[], dict[str, Any]]:
    status, said = post(home.url + "_api/quilt-create", {"name": name, "place": str(place), "drop": key})
    assert status == 200, said
    return lambda: home.jobs[said["job"]]


def test_the_home_stopping_ends_a_create_and_leaves_nothing_of_it(
    bundle: Path, ports: None, place: Path, held_import: tuple[threading.Event, threading.Event]
) -> None:
    begun, go = held_import
    h = Home(bundle, port=0, extra=("--no-compile",))
    h.listen()
    job = create_job(h, "Stopped", place, drop({"paper.tex": PAPER}))
    until(begun.is_set, "the import begun")
    h.stop()
    go.set()
    until(lambda: job()["state"] != "running", "the create ended")
    assert job()["state"] == "failed" and list(place.iterdir()) == [] and registry.entries() == []


def test_the_home_restarts_after_an_update_only_once_no_quilt_is_being_made(
    home_server: Home, place: Path, held_import: tuple[threading.Event, threading.Event]
) -> None:
    begun, go = held_import
    job = create_job(home_server, "Waited", place, drop({"paper.tex": PAPER}))
    until(begun.is_set, "the import begun")
    home_server.code = (0, 0)  # loom's code moved under the home long ago
    home_server.supervisor.still_since = time.monotonic() - 3600
    restarted = threading.Event()

    def reexec() -> None:
        restarted.set()
        home_server.stopping.set()

    threading.Thread(target=home_server.run, args=(reexec,), daemon=True).start()
    time.sleep(2.5)
    assert not restarted.is_set()
    go.set()
    until(restarted.is_set, "the restart once the quilt was made")
    assert job()["state"] == "done" and (place / "Waited" / "config.toml").is_file()


def test_two_creates_of_one_name_at_once_make_one_quilt_and_refuse_the_other(
    home_server: Home, place: Path, held_import: tuple[threading.Event, threading.Event]
) -> None:
    """A double click sends the same drop twice."""
    begun, go = held_import
    key = drop({"paper.tex": PAPER})
    job = create_job(home_server, "Twice", place, key)
    status, said = post(home_server.url + "_api/quilt-create", {"name": "Twice", "place": str(place), "drop": key})
    assert status == 409 and said["error"]["code"] == "exists"
    go.set()
    until(lambda: job()["state"] != "running", "the quilt made")
    assert job()["state"] == "done" and len(registry.entries()) == 1


def test_a_drop_holding_a_link_to_nothing_cannot_stop_the_home_starting(bundle: Path, ports: None) -> None:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        notes = tarfile.TarInfo("notes.txt")
        notes.size = 1
        t.addfile(notes, io.BytesIO(b"x"))
        link = tarfile.TarInfo("figs")
        link.type, link.linkname = tarfile.SYMTYPE, "figures-not-shipped"
        t.addfile(link)
    key = drop({"paper.tar.gz": out.getvalue()})
    with pytest.raises(ApiError) as refused:
        create.paper(key, None)
    assert refused.value.code == "no-paper" and (create.incoming() / key / "unpacked" / "figs").is_symlink()
    h = Home(bundle, port=0, extra=("--no-compile",))
    h.listen()
    h.stop()
    old = time.time() - (create.KEEP_DAYS + 1) * 86400
    for p in [create.incoming() / key, *(create.incoming() / key).rglob("*")]:
        os.utime(p, (old, old), follow_symlinks=False)
    create.sweep()
    assert not (create.incoming() / key).exists()
