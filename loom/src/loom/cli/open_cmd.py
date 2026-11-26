"""`loom open LINK`: open the quilt's viewer at a `quilt:` or `cited:` link, which is how an editor follows one written in a note."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import click

from loom.cli._common import note
from loom.cli._quilt import open_scan, quilt_option
from loom.errors import EnvError

#: How long a viewer started for the link has to answer.
START_WAIT = 60.0


@click.command(name="open")
@click.argument("link")
@quilt_option
def open_command(link: str, quilt_path: str | None) -> None:
    """Open this quilt's viewer at LINK, a quilt: or cited: link, at the words it quotes.

    Run inside the quilt, as an editor runs it on the link under the cursor: `quilt:notes/day1.md#setup`, `quilt:REF#page=3&quote=…`, or the link inside a Markdown or org link around it. A `cited:` link opens the work that states its identifier, at its pages. The viewer running for the quilt opens it; with none running, loom serve is started for it first. A link that names nothing the viewer shows is refused, with why.
    """
    import webbrowser
    from urllib.parse import quote

    from loom.links import LinkError, quilt_link, resolve
    from loom.render.serve import open_url

    href = bare(link)
    result = open_scan(quilt_path)
    root = result.quilt.root
    try:
        target = resolve(result, root, href)
    except LinkError as exc:
        raise EnvError(str(exc)) from None
    if href.startswith("cited:"):
        # a work by its identifier opens at its own pages here, as the quilt names it
        href = quilt_link(target.key, target.place, _cited_quote(href))[len("[](") : -1]
    url = open_url(root) or _start(root)
    at = f"{url}open?link={quote(href, safe='')}"
    webbrowser.open(at)
    note(f"loom open: {at}")


def _cited_quote(href: str) -> str:
    """The words a `cited:` link quotes, from its query or its fragment; '' for none."""
    from urllib.parse import parse_qs

    keys = parse_qs(href.partition("?")[2].replace("#", "&") or href.partition("#")[2])
    return (keys.get("quote") or [""])[0]


def bare(link: str) -> str:
    """The link inside what an editor hands over: a raw link, `<…>`, a Markdown link `[…](…)` or an org link `[[…][…]]`; EnvError for text holding none."""
    from loom.links import raw_links

    found = raw_links(link.strip())
    if not found:
        raise EnvError(f"{link!r} holds no quilt: or cited: link")
    return found[0][1]


def _start(root: Path) -> str:
    """Start loom serve for the quilt in a session of its own, logging beside its `serve.json`, and return its address once it answers."""
    import subprocess

    from loom.paths import SERVE_JSON
    from loom.render.serve import open_url

    log = (root / SERVE_JSON).parent / "open-serve.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        subprocess.Popen(
            [sys.executable, "-P", "-m", "loom", "serve", "--quilt", str(root)],
            cwd=root,
            env={**os.environ, "PYTHONSAFEPATH": "1"},
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    end = time.monotonic() + START_WAIT
    while time.monotonic() < end:
        url = open_url(root)
        if url:
            return url
        time.sleep(0.1)
    raise EnvError(f"loom serve did not start for this quilt; what it said is in {log}")
