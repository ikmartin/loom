"""A local stand-in for Overleaf's git: bare repositories served over smart HTTP (`git http-backend` under `wsgiref`) behind Basic auth with the user `git` and one token, on 127.0.0.1."""

from __future__ import annotations

import base64
import os
import subprocess
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIRequestHandler, make_server

#: The token the stand-in accepts.
TOKEN = "olp_StandInToken0123456789"


class _Quiet(WSGIRequestHandler):
    def log_message(self, *_args: Any) -> None:
        pass


class Server:
    """The served projects under `root`; `access` False answers every request for one with 404, as Overleaf answers a project whose owner has no git access."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.access = True
        self.port = 0
        backend = subprocess.check_output(["git", "--exec-path"], text=True).strip()
        self.backend = str(Path(backend) / "git-http-backend")

    def url(self, project: str) -> str:
        return f"http://127.0.0.1:{self.port}/{project}"

    def app(self, environ: dict[str, Any], start: Any) -> list[bytes]:
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not (auth.startswith("Basic ") and base64.b64decode(auth[6:]).decode() == f"git:{TOKEN}"):
            start("401 Unauthorized", [("WWW-Authenticate", 'Basic realm="Git Bridge"')])
            return [b""]
        if not self.access:
            start("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Repository not found"]
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length else b""
        env = {
            "GIT_PROJECT_ROOT": str(self.root),
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": environ["PATH_INFO"],
            "QUERY_STRING": environ.get("QUERY_STRING", ""),
            "REQUEST_METHOD": environ["REQUEST_METHOD"],
            "CONTENT_TYPE": environ.get("CONTENT_TYPE", ""),
            "REMOTE_USER": "git",
            "PATH": os.environ["PATH"],
        }
        out = subprocess.run([self.backend], input=body, env=env, capture_output=True, check=False).stdout
        head, _, rest = out.partition(b"\r\n\r\n")
        status, headers = "200 OK", []
        for line in head.decode().split("\r\n"):
            key, _, value = line.partition(": ")
            if key.lower() == "status":
                status = value
            elif key:
                headers.append((key, value))
        start(status, headers)
        return [rest]


@contextmanager
def serving(root: Path) -> Iterator[Server]:
    """Serve the bare repositories under `root` until the block ends; the server is gone after it, so a call then is one that cannot reach Overleaf."""
    server = Server(root)
    httpd = make_server("127.0.0.1", 0, server.app, handler_class=_Quiet)
    server.port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()
