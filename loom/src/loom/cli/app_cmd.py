"""`loom app`: loom's home page, which opens, creates and lists quilts and keeps each one served on the port it keeps."""

from __future__ import annotations

import os
import signal
import sys

import click

from loom.app.registry import HOME_PORT
from loom.cli._common import note
from loom.errors import EnvError


@click.command(name="app")
@click.option(
    "--port",
    type=int,
    default=HOME_PORT,
    show_default=True,
    help=f"Port to listen on; when {HOME_PORT} is held, any free one.",
)
@click.option(
    "--open",
    "open_page",
    is_flag=True,
    help="Open the home page in the browser, starting the home first when it is not running, and return.",
)
@click.option(
    "--install", is_flag=True, help="Write Loom.app in ~/Applications, which opens the home page, and return."
)
@click.option(
    "--no-compile", is_flag=True, hidden=True, help="Serve every quilt with no compiles, as loom serve --no-compile."
)
def app_command(port: int, open_page: bool, install: bool, no_compile: bool) -> None:
    """Run loom's home page until interrupted: the quilts on this machine, each served on a port it keeps, and the ones left open served again when it starts.

    A home already running is left to run, and its address is printed. Once loom is updated, the home restarts each quilt's server and then itself.
    """
    from loom.app.registry import home_url
    from loom.app.server import Home
    from loom.render.serve import locate_bundle

    if install:
        from loom.app.launcher import write_launcher

        if sys.platform != "darwin":
            raise EnvError("Loom.app is written on macOS only; run loom app --open instead")
        note(f"loom app: wrote {write_launcher()}")
        return
    if open_page:
        _open(port)
        return
    running = home_url()
    if running:
        note(f"loom app: {running}")
        return
    bundle = locate_bundle()
    if bundle is None:
        raise EnvError(
            "the arras viewer bundle is not installed: set LOOM_ARRAS_BUNDLE, or use a loom with the vendored bundle"
        )
    extra = ("--no-compile",) if no_compile else ()
    home = Home(bundle, port, extra)
    home.listen()
    note(f"loom app: {home.url}  (Ctrl-C to stop it and the quilts it serves)")

    def again() -> None:
        # the same command in the code installed now; the quilts' servers run on and the new home finds them
        os.execv(
            sys.executable,
            [sys.executable, "-P", "-m", "loom", "app", "--port", str(port), *(["--no-compile"] if no_compile else [])],
        )

    def _term(*_: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _term)
    try:
        home.run(reexec=again)
    except KeyboardInterrupt:
        note("loom app: stopping")
    finally:
        home.stop()


def _open(port: int) -> None:
    """Open the home page in the browser, first starting `loom app` on `port` in a session of its own when no home runs."""
    import subprocess
    import time
    import webbrowser

    from loom.app.registry import folder, home_url

    url = home_url()
    if not url:
        log = folder() / "app.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "ab") as out:
            subprocess.Popen(
                [sys.executable, "-P", "-m", "loom", "app", "--port", str(port)],
                cwd=folder(),
                env={**os.environ, "PYTHONSAFEPATH": "1"},
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        end = time.monotonic() + 30
        while not url and time.monotonic() < end:
            time.sleep(0.1)
            url = home_url()
        if not url:
            raise EnvError(f"loom's home did not start; what it said is in {log}")
    webbrowser.open(url)
    note(f"loom app: {url}")
