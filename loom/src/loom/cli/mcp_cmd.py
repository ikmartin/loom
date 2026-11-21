"""`loom mcp --as NAME`: the MCP server an agent's app starts for this quilt."""

from __future__ import annotations

from pathlib import Path

import click

from loom.cli._quilt import open_quilt, quilt_option
from loom.errors import EnvError
from loom.identity import is_agent


@click.command(name="mcp")
@click.option(
    "--as",
    "as_name",
    required=True,
    metavar="NAME",
    help="The agent this server serves, with Agent or AI in the name; every write is recorded under it.",
)
@quilt_option
def mcp_command(as_name: str, quilt_path: str | None) -> None:
    """Serve this quilt's agent commands as MCP tools over stdio, for an agent's app to start; it runs until the app closes it.

    One tool per agent command, named for it (`loom status` is `loom_status`), its options its arguments; the author's commands are not tools. Each call runs the command it names, as NAME, and its result is that command's report. The instructions tell the agent to call `loom_ai_orient` first. A result too long for a reply is written under `.loom/agents/scratch/` and the tool returns its path.
    """
    if not is_agent(as_name):
        raise EnvError(
            f"{as_name} does not say it is an agent; give a name with Agent or AI in it, such as --as 'Claude Agent'"
        )
    root = open_quilt(quilt_path).root
    _refuse_another_quilt(root, quilt_path)
    from loom.mcp.sdk import has_sdk, reinstall_hint

    if not has_sdk():
        raise EnvError(
            f"loom mcp needs the MCP SDK, which this loom's environment does not have; reinstalling loom brings it: {reinstall_hint()}"
        )
    from loom.mcp.server import serve

    serve(root, as_name)


def _refuse_another_quilt(root: Path, quilt_path: str | None) -> None:
    """Refuse a server whose `--quilt` names a quilt other than the one its app was started in: an app's server file names its quilt's path, so a quilt copied whole carries a file that would start loom on the original, and every write of the agent's would land there."""
    if quilt_path is None:
        return
    from loom.scan.quilt import NoQuiltError, find_quilt

    try:
        here = find_quilt(Path.cwd()).root
    except NoQuiltError:
        return  # started outside any quilt: the path it names is all there is to go by
    if here.resolve() != root.resolve():
        raise EnvError(
            f"this agent's app was started in the quilt {here}, but its server file names {root}, as one a copied quilt brings with it does; "
            "nothing was served. `loom ai init` in this quilt writes the file for it."
        )
