"""`loom doctor`: the one command to run when something is off -- the machine's tools, the author name and the viewer bundle, and the quilt's own setup when run inside one."""

from __future__ import annotations

import click

from loom.cli._quilt import quilt_option
from loom.doctor import run_doctor


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Machine-readable report on stdout.")
@click.option("--strict", is_flag=True, help="Count a warning as a failure: exit 2 when any item warns.")
@click.option(
    "--repair",
    is_flag=True,
    help="Repair TeX first: install loom's own TeX, or put back what it lacks. Touches nothing outside loom's directory.",
)
@click.option(
    "--settle",
    "settle_act",
    metavar="ID",
    help="Settle a write loom could neither finish nor undo as it stands, by the id the writes item gives: your files stay as they are, each suggested edit it wrote is recorded as the files show, and it is no longer said. The author's; refused in an agent's shell.",
)
@quilt_option
def doctor(as_json: bool, strict: bool, repair: bool, settle_act: str | None, quilt_path: str | None) -> None:
    """Check the TeX toolchain and what loom needs of it, poppler, git, the author name and the viewer bundle; inside a quilt, also its engine, its generated files, its .gitignore and its config.

    Each item is ok, warn (works, but you will hit it) or fail (a command you need will refuse), with the command that fixes it. Exits 0 when nothing fails and 2 when anything does; under --strict a warning counts as a failure. Without --repair it writes nothing; a tool is run only to ask its version or test what loom needs of it, and one that has not answered in 10 s is reported as hung.
    """
    if settle_act is not None:
        _settle(settle_act, quilt_path)
        return
    if repair:
        from loom.cli._common import note
        from loom.tex import private

        try:
            done = private.repair(say=note)
        except OSError as exc:
            note(f"Repair TeX did not finish: {exc}")
        else:
            for step in done.steps:
                note(step)
        private.activate()
    run_doctor(quilt_path, strict=strict).report().emit(as_json)


def _settle(act_id: str, quilt_path: str | None) -> None:
    """`--settle`: the person's settling of one left write (`settling.settle`), refused in a shell an agent runs, its preview's words printed."""
    from loom import settling
    from loom.cli._quilt import open_quilt
    from loom.errors import EnvError
    from loom.identity import refuse_under_agent
    from loom.scan.quilt import reviewer_identity
    from loom.writes import WriteRefused

    refuse_under_agent(
        "Settling a write", "Settle it in the viewer's Problems, or run loom doctor --settle in a terminal of your own."
    )
    quilt = open_quilt(quilt_path)
    try:
        plan = settling.settle(quilt.root, quilt.history_dir, act_id, reviewer_identity(quilt.root)[0])
    except (settling.SettleRefused, WriteRefused) as exc:
        raise EnvError(str(exc)) from exc
    for line in plan.said():
        click.echo(line)
