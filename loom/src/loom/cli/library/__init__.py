"""`loom library`: the works a quilt holds and the web of their results. The person takes documents in (`add`); an agent reads the web, fills and proposes nodes, proposes corrections and has loom digest a work (`web`)."""

from __future__ import annotations

import click

from loom.cli.help import CommandGroup
from loom.cli.library import add, web


@click.group(cls=CommandGroup)
def library() -> None:
    """The works this quilt holds and the web of their results: take PDFs, `.bib` files and LaTeX sources in, read a work's results, and give them their text."""


for _command in [*add.COMMANDS, *web.COMMANDS]:
    library.add_command(_command)
