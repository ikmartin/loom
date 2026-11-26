"""`loom library`: the works a quilt holds. Its one command takes documents in (`add`)."""

from __future__ import annotations

import click

from loom.cli.help import CommandGroup
from loom.cli.library import add


@click.group(cls=CommandGroup)
def library() -> None:
    """The works this quilt holds: take PDFs, `.bib` files and LaTeX sources in."""


for _command in add.COMMANDS:
    library.add_command(_command)
