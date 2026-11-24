"""The home server (`loom app`): the viewer's home page and its `quilt-` endpoints, on the home's own port, behind the guards every quilt's server keeps (specs/write-api.md, "The home server").

It holds no quilt. It serves the viewer it started with (`render.serve.HeldBundle`), answers `GET /_api` with `home: true` so the viewer draws the home page, and keeps the person's quilts served through its `Supervisor`.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
import tomllib
from collections.abc import Callable
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from loom.app import registry
from loom.app.registry import HOME_PORT, Entry, address
from loom.app.supervise import SETTLE, Supervisor, tail
from loom.files import FILES_URL
from loom.render.endpoints.base import ApiError
from loom.render.serve import BUILD_URL, STORE_URL, HeldBundle, LoomHandler, code_stamp, from_elsewhere

#: The largest JSON body the home reads; its writes are a few fields each.
MAX_BODY = 1024 * 1024
#: How many finished and running jobs `quilt-list` keeps.
KEPT_JOBS = 20


def choose_folder(prompt: str) -> Path | None:
    """The folder the person picks in the system's folder dialog, on their click; None when they cancel."""
    try:
        done = subprocess.run(
            ["osascript", "-e", f"POSIX path of (choose folder with prompt {json.dumps(prompt)})"],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ApiError("no-dialog", "this system has no folder dialog loom can show", status=501) from exc
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def _entry(body: dict[str, Any]) -> Entry:
    key = body.get("quilt")
    found = registry.find(key) if isinstance(key, str) else None
    if found is None:
        raise ApiError("no-such-quilt", "that quilt is not on the list", status=404)
    return found


def _name(entry: Entry) -> str:
    """The quilt's name as its `config.toml` gives it, else its folder's."""
    try:
        quilt = tomllib.loads((Path(entry.root) / "config.toml").read_text(encoding="utf-8")).get("quilt", {})
        name = quilt.get("name") if isinstance(quilt, dict) else None
    except (OSError, ValueError):
        name = None
    return name if isinstance(name, str) and name.strip() else Path(entry.root).name


def _list(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-list`: every quilt with its state, the person's name and where it comes from, which TeX is in use, and the jobs running or done."""
    from loom.scan.quilt import reviewer_identity
    from loom.tex import private

    quilts = [
        {"quilt": e.id, "name": _name(e), "folder": e.root, "port": e.port, "open": e.open, **home.supervisor.state(e)}
        for e in registry.entries()
    ]
    name, source = reviewer_identity(Path.home())
    return {
        "quilts": quilts,
        "name": {"name": name, "source": source},
        "tex": private.active(year=False).kind,
        "jobs": home.jobs_listing(),
    }


def _open(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-open`: serve the quilt on its port, or with `move` on a port never given before; left open for the home's next start."""
    entry = _entry(body)
    if body.get("move") is True:
        home.supervisor.stop(entry)
        entry = registry.readdress(entry.id)
    registry.set_open(entry.id, True)
    entry.open = True
    return {"quilt": entry.id, **home.supervisor.open(entry)}


def _stop(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-stop`: stop the quilt's server; the home's next start leaves it stopped."""
    entry = _entry(body)
    registry.set_open(entry.id, False)
    home.supervisor.stop(entry)
    return {"quilt": entry.id, **home.supervisor.state(entry)}


def _forget(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-forget`: stop the quilt's server and take it off the list; its folder is untouched."""
    entry = _entry(body)
    home.supervisor.stop(entry)
    registry.forget(entry.id)
    return {"quilt": entry.id, "forgotten": True}


def _choose(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-choose`: the system's folder dialog; `purpose` `open` puts the quilt chosen on the list, `place` answers the folder a new quilt goes in."""
    from loom.scan.quilt import is_quilt_root

    purpose = body.get("purpose")
    if purpose not in ("open", "place"):
        raise ApiError("bad-field", "purpose is open or place")
    chosen = choose_folder("Choose a quilt" if purpose == "open" else "Choose where the new quilt goes")
    if chosen is None:
        return {"cancelled": True}
    if purpose == "place":
        return {"folder": str(chosen)}
    if not is_quilt_root(chosen):
        raise ApiError("not-a-quilt", "that folder is not a quilt", status=409)
    return {"quilt": registry.remember(chosen).id}


def _person(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-name`: the person's name and where it comes from, saved first when `name` is sent, through what Settings › Profile uses (`reviewer-settings`)."""
    from loom.identity import is_agent
    from loom.scan.quilt import reviewer_identity, save_author

    said, _ = reviewer_identity(Path.home())
    author = body.get("author")
    if is_agent(author if isinstance(author, str) and author else said):
        raise ApiError("author-only", "An agent reads and annotates; only the author names the reviewer", status=403)
    name = body.get("name")
    if name is not None:
        if not isinstance(name, str):
            raise ApiError("bad-field", "name is the person's name")
        try:
            save_author(name)
        except (ValueError, OSError) as exc:
            raise ApiError("settings-refused", str(exc), status=409) from exc
    said, source = reviewer_identity(Path.home())
    return {"name": said, "source": source}


def _check(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-check`: doctor's report of the machine, and with `quilt` the last lines that quilt's server wrote, for Copy details."""
    from loom.doctor import run_doctor

    report = run_doctor(None).to_dict()
    log = tail(_entry(body), 40) if body.get("quilt") else ""
    return {"doctor": report, "log": log}


def _create(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-create`: a new quilt named `name` in `place` (default `~/Quilts`), from the paper in `drop` when one is given, made as a job; or, when the drop holds several files a paper could be typeset from and `main` does not say which, the question."""
    from loom.app import create

    name, place, drop, main = (body.get(k) for k in ("name", "place", "drop", "main"))
    if not isinstance(name, str) or not all(v is None or isinstance(v, str) for v in (place, drop, main)):
        raise ApiError("bad-field", "name, and place, drop and main where given, are strings")
    where = create.target(name, place)
    paper = create.paper(drop, main) if drop else None
    if isinstance(paper, list):
        return {"question": {"choices": paper}}

    def work(step: Callable[[str], None]) -> dict[str, Any]:
        done = create.make(where, paper, step, home.supervisor.open)
        if drop:
            create.let_go(drop)
        return done

    return {"job": home.start_job("create", work)}


def _receive_json(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-receive` is answered from the file's bytes (`HomeHandler._take`), never from JSON."""
    raise ApiError("not-a-stream", "a dropped file is sent as its bytes, application/octet-stream")


def _repair(home: Home, body: dict[str, Any]) -> dict[str, Any]:
    """`quilt-repair`: Repair TeX as a job, installing loom's own TeX or putting back what it lacks; nothing outside loom's folder is touched."""
    from loom.tex import private

    def work(step: Callable[[str], None]) -> dict[str, Any]:
        private.repair(say=step)
        private.activate()
        return {"tex": private.active(year=False).kind}

    return {"job": home.start_job("repair", work)}


#: The home's endpoints, each given the home and the request's body.
HANDLERS: dict[str, Callable[[Home, dict[str, Any]], dict[str, Any]]] = {
    "quilt-list": _list,
    "quilt-open": _open,
    "quilt-stop": _stop,
    "quilt-forget": _forget,
    "quilt-choose": _choose,
    "quilt-name": _person,
    "quilt-check": _check,
    "quilt-receive": _receive_json,
    "quilt-create": _create,
    "quilt-repair": _repair,
}


class HomeHandler(LoomHandler):
    """A quilt server's handler with no quilt: the viewer's files, `GET /_api` naming the home, and `HANDLERS`."""

    home: Any = None

    def _resolve(self) -> Path | None:
        if self.path.split("?", 1)[0].startswith((BUILD_URL, STORE_URL, FILES_URL)):
            return None  # the home holds no quilt, so none of a quilt's files
        return super()._resolve()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/_api":
            elsewhere = from_elsewhere(self)
            if elsewhere:
                self._json(HTTPStatus.FORBIDDEN, {"error": {"code": "refused", "message": elsewhere}})
                return
            held = self.held
            self._json(
                HTTPStatus.OK,
                {
                    "home": True,
                    "token": self.token,
                    "capabilities": sorted(HANDLERS),
                    **({"viewer": held.version, "stale": held.stale()} if held else {}),
                },
            )
            return
        if path.startswith("/_api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        kind = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if path == "/_api/quilt-receive" and kind == "application/octet-stream":
            self._take()
            return
        handler = HANDLERS.get(path.removeprefix("/_api/")) if path.startswith("/_api/") else None
        if handler is None:
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "no-such-endpoint", "message": "the home has no such endpoint"}},
            )
            return
        refused = self._csrf()
        if refused:
            self._json(HTTPStatus.FORBIDDEN, {"error": {"code": "refused", "message": refused}})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": {"code": "too-large", "message": "too large"}})
            return
        try:
            body = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8") or "{}")
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
        except (UnicodeDecodeError, ValueError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": {"code": "bad-json", "message": str(exc)}})
            return
        try:
            self._json(HTTPStatus.OK, handler(self.home, body))
        except ApiError as exc:
            self._json(exc.status, exc.answer())
        except Exception as exc:  # noqa: BLE001
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": {"code": "failed", "message": str(exc)}})

    def _take(self) -> None:
        """`quilt-receive`: one dropped file's bytes, streamed into its drop (`create.receive`); its path and drop in the query, the token in its header, and from this server's own pages only."""
        from urllib.parse import parse_qs, urlsplit

        from loom.app.create import MAX_DROP, receive

        elsewhere = from_elsewhere(self)
        if elsewhere or self.headers.get("X-Loom-Token") != self.token:
            self._json(HTTPStatus.FORBIDDEN, {"error": {"code": "refused", "message": elsewhere or "no valid token"}})
            return
        try:
            length = int(self.headers["Content-Length"])
        except (KeyError, TypeError, ValueError):
            self._json(HTTPStatus.LENGTH_REQUIRED, {"error": {"code": "length-required", "message": "no length"}})
            return
        query = parse_qs(urlsplit(self.path).query)
        drop = query["drop"][0] if query.get("drop") else None
        try:
            self._json(HTTPStatus.OK, receive(drop, (query.get("path") or [""])[0], self.rfile, length))
        except ApiError as exc:
            if 0 < length <= MAX_DROP:
                while length > 0 and (chunk := self.rfile.read(min(length, 1 << 20))):
                    length -= len(chunk)  # read to its end, so the browser hears the refusal
            self._json(exc.status, exc.answer())


class Home:
    """The home server.

    Parameters
    ----------
    bundle : Path
        The built viewer to serve.
    port : int, default HOME_PORT
        Where to listen; when the default is held, a free port. 0 is any free port.
    extra : tuple of str, default ()
        Options added to every quilt's `loom serve`.
    """

    def __init__(self, bundle: Path, port: int = HOME_PORT, extra: tuple[str, ...] = ()) -> None:
        self.bundle = bundle
        self.port = port
        self.supervisor = Supervisor(extra)
        self.token = secrets.token_urlsafe(24)
        self.code = code_stamp()
        self.httpd: ThreadingHTTPServer | None = None
        self.held: HeldBundle | None = None
        self.stopping = threading.Event()
        self.jobs: dict[str, dict[str, Any]] = {}

    def jobs_listing(self) -> list[dict[str, Any]]:
        """The jobs running or done, newest first."""
        return [dict(job) for job in reversed(self.jobs.values())]

    def start_job(self, kind: str, work: Callable[[Callable[[str], None]], dict[str, Any]]) -> str:
        """Run `work` in a thread of its own, told a step to show as each begins; the job is listed by `quilt-list` as `running`, then `done` with what `work` answered or `failed` with `why` and `said`."""
        key = secrets.token_hex(6)
        job: dict[str, Any] = {"job": key, "kind": kind, "state": "running", "step": ""}
        self.jobs[key] = job
        while len(self.jobs) > KEPT_JOBS:
            self.jobs.pop(next(iter(self.jobs)))

        def step(said: str) -> None:
            job["step"] = said

        def go() -> None:
            try:
                job.update(work(step), state="done")
            except ApiError as exc:
                job.update(state="failed", why=exc.code, said=exc.message)
            except Exception as exc:  # noqa: BLE001
                job.update(state="failed", why="failed", said=str(exc) or type(exc).__name__)

        threading.Thread(target=go, name=f"loom-home-{kind}", daemon=True).start()
        return key

    def listen(self) -> None:
        """Bind the port, record the home's address in loom's folder for the machine, and start answering."""
        from loom.app.create import sweep

        sweep()
        self.held = HeldBundle(self.bundle)
        handler = type(
            "Handler",
            (HomeHandler,),
            {"bundle_dir": self.held.path, "held": self.held, "home": self, "token": self.token},
        )
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        except OSError:
            if self.port != HOME_PORT:
                raise
            self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        p = address()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"port": self.port, "pid": os.getpid(), "url": self.url}) + "\n", encoding="utf-8")
        threading.Thread(target=self.httpd.serve_forever, name="loom-home", daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def run(self, reexec: Callable[[], None] | None = None) -> None:
        """Keep the quilts the person left open served, once a second, until `stop`; once loom's own code has moved and been still for `SETTLE`, call `reexec`."""
        while not self.stopping.wait(1.0):
            self.supervisor.tick(registry.entries())
            sup = self.supervisor
            if reexec is not None and sup.stamp != self.code and time.monotonic() - sup.still_since >= SETTLE:
                self.close()
                reexec()

    def close(self) -> None:
        """Stop answering and let go of the viewer and the home's address; the quilts' servers run on."""
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        try:
            if json.loads(address().read_text(encoding="utf-8")).get("pid") == os.getpid():
                address().unlink()
        except (OSError, ValueError):
            pass
        if self.held is not None:
            self.held.close()
            self.held = None

    def stop(self) -> None:
        """Stop the home and every quilt's server it runs; what the person left open stays so on the list."""
        self.stopping.set()
        self.supervisor.stop_all(registry.entries())
        self.close()
