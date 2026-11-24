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
    "--no-compile", is_flag=True, hidden=True, help="Serve every quilt with no compiles, as loom serve --no-compile."
)
def app_command(port: int, no_compile: bool) -> None:
    """Run loom's home page until interrupted: the quilts on this machine, each served on a port it keeps, and the ones left open served again when it starts.

    A home already running is left to run, and its address is printed. Once loom is updated, the home restarts each quilt's server and then itself.
    """
    from loom.app.registry import home_url
    from loom.app.server import Home
    from loom.render.serve import locate_bundle

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
