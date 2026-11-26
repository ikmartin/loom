"""`loom formal`: formalization on this machine. Turning it on and off is the person's; asking loom to check the Lean is anyone's, and what Lean says is loom's own record; reading a result's Lean in ordinary mathematics is an agent's."""

from __future__ import annotations

import click

from loom.cli._quilt import open_quilt, quilt_option
from loom.cli.help import CommandGroup
from loom.cli.report import Group, Item, Progress, Report, counted
from loom.cli.tasks_cmd import AS_OPTION, _agent
from loom.errors import ContentError, EnvError

JSON_OPTION = click.option("--json", "as_json", is_flag=True, help="Print the report as one JSON object.")


@click.group(name="formal", cls=CommandGroup, invoke_without_command=True)
@JSON_OPTION
@quilt_option
@click.pass_context
def formal(ctx: click.Context, as_json: bool, quilt_path: str | None) -> None:
    """Say whether formalization is on for this quilt on this machine, and whether loom can check its Lean here.

    The person turns it on (`loom formal on`), which installs Lean, its toolchain and Mathlib and makes the quilt's Lean project; from then an agent writes Lean in the project, marks each declaration that states a result with `@[loom "LABEL"]`, and asks loom to check it (`loom formal check`); a second agent, which did not write it, reads it in ordinary mathematics for the person (`loom formal read`). What Lean said is loom's own record, never an agent's.
    """
    if ctx.invoked_subcommand is not None:
        return
    from loom import fence
    from loom.formal import install, switch

    root = open_quilt(quilt_path).root
    on = switch.is_on(root)
    proj = install.project(root)
    has = (proj / "lakefile.toml").is_file()
    why = fence.lean_state()
    Report(
        f"formalization is {'on' if on else 'off'} for this quilt on this machine",
        groups=[
            Group(
                "here",
                [
                    Item(f"Lean project: {install.LEAN}/" if has else f"Lean project: none in {install.LEAN}/"),
                    Item("the fence: up" if why is None else f"the fence: not up ({why}); loom cannot check Lean here"),
                ],
            )
        ],
        data={"on": on, "project": install.LEAN if has else None, "fence": why},
    ).emit(as_json)


@formal.command(name="on")
@JSON_OPTION
@quilt_option
def on_command(as_json: bool, quilt_path: str | None) -> None:
    """Turn formalization on for this quilt on this machine: install elan, the Lean toolchain and Mathlib (about 11 GB and a few minutes the first time), and make the quilt's Lean project where it has none.

    Kept on this machine and never in the quilt, so a co-author who opens the quilt runs nothing until they turn it on themselves. It downloads and runs Lean's and Mathlib's own installers; the check that follows runs fenced. From then, while `loom serve` runs, loom also checks the Lean again on its own once a statement it states or the Lean a record rests on changes and has been still for a minute.
    """
    from loom.formal import install, switch
    from loom.identity import refuse_under_agent

    refuse_under_agent(
        "loom formal on",
        "Turning formalization on installs Lean and lets loom run it; run it in a terminal of your own.",
    )
    root = open_quilt(quilt_path).root
    switch.turn_on(root)
    with Progress("installing Lean") as progress:
        try:
            done = install.install(root, say=lambda step: progress.item(install.STEPS[step]))
        except install.Refused as e:
            raise EnvError(
                f"formalization is on, and installing failed: {e}\nRun `loom formal on` again once that is fixed."
            ) from None
    Report(
        f"formalization is on; Lean, Mathlib and the project in {install.LEAN}/ are ready ({done.seconds:.0f} s)",
        groups=[Group("installed", [Item(f"{step}: {seconds:.0f} s") for step, seconds in done.steps])],
        data={"on": True, "steps": [{"step": s, "seconds": round(t, 1)} for s, t in done.steps]},
    ).emit(as_json)


@formal.command(name="off")
@JSON_OPTION
@quilt_option
def off_command(as_json: bool, quilt_path: str | None) -> None:
    """Turn formalization off for this quilt on this machine: loom runs no Lean here until it is turned on again. What it installed stays, and so do its records."""
    from loom.formal import switch
    from loom.identity import refuse_under_agent

    refuse_under_agent(
        "loom formal off",
        "Turning formalization off is your choice about this machine; run it in a terminal of your own.",
    )
    root = open_quilt(quilt_path).root
    switch.turn_off(root)
    Report("formalization is off for this quilt on this machine", data={"on": False}).emit(as_json)


@formal.command(name="check")
@JSON_OPTION
@quilt_option
def check_command(as_json: bool, quilt_path: str | None) -> None:
    """Have loom check the quilt's Lean itself: rebuild the project from clean, read which declaration states which result (`@[loom "LABEL"]`) and the axioms each rests on, and replay the build in Lean's kernel, every step fenced, with no network and writes only in the project. Each result a declaration states gets loom's own record of what Lean said, which stops standing once its Lean or its statement changes.

    Refused when formalization is off here, and from a shell that is itself fenced, such as an agent's sandbox, where the fence cannot be put up: ask through loom's tools instead.
    """
    from loom.formal import check

    root = open_quilt(quilt_path).root
    with Progress("checking the Lean") as progress:
        try:
            done = check.check(root, say=lambda step: progress.item(check.STEPS[step]))
        except check.Refused as e:
            raise EnvError(str(e)) from None
    groups = [
        Group("recorded", [Item(n) for n in done.written]),
        Group("as recorded before", [Item(n) for n in done.unchanged]),
        Group("markers that name no result", [Item(n) for n in done.unknown]),
        Group("Lean's errors", [Item(e) for e in done.errors]),
        Group("steps", [Item(f"{step}: {seconds:.0f} s") for step, seconds in done.steps]),
    ]
    report = Report(
        f"loom checked the Lean: {counted(len(done.written), 'record')} written, {counted(len(done.unchanged), 'result')} as before"
        + (f", {counted(len(done.errors), 'error')}" if done.errors else ""),
        ok=not done.errors and not done.unknown,
        exit=1 if done.errors else 0,
        groups=[g for g in groups if g.items],
        data={
            "written": done.written,
            "unchanged": done.unchanged,
            "unknown": done.unknown,
            "errors": done.errors,
            "steps": [{"step": s, "seconds": round(t, 1)} for s, t in done.steps],
        },
    )
    if done.errors and not done.written and not done.unchanged:
        raise ContentError(report.verdict + ":\n" + "\n".join(done.errors[:20]))
    report.emit(as_json)


@formal.command(name="read")
@click.argument("result")
@click.option(
    "--declaration",
    "declarations",
    multiple=True,
    metavar="NAME",
    help="The declaration a part reads, one of those the command lists without a reading; once for each part, in order.",
)
@click.option(
    "--reading",
    "readings",
    multiple=True,
    metavar="LATEX",
    help="Your reading of that declaration in ordinary mathematics, as LaTeX; once for each part, in the order of --declaration.",
)
@click.option(
    "--part",
    "parts",
    multiple=True,
    metavar="NAME",
    help="Each part's name, as (i) or a notion's word, in the same order; needed where there are several parts.",
)
@click.option(
    "--draft",
    "drafts",
    multiple=True,
    metavar="LATEX",
    help="What the statement says in each part, as LaTeX, in the same order; '' where nothing in it answers.",
)
@click.option(
    "--difference", default=None, help="Where the Lean and the statement differ; leave it out if you found nothing."
)
@click.option(
    "--record",
    default=None,
    metavar="ID",
    help="The Lean record you read, as listed; refused once a newer one states the result.",
)
@AS_OPTION
@JSON_OPTION
@quilt_option
def read_command(result: str, declarations: tuple[str, ...], readings: tuple[str, ...], parts: tuple[str, ...], drafts: tuple[str, ...], difference: str | None, record: str | None, declared: str | None, as_json: bool, quilt_path: str | None) -> None:  # fmt: skip
    """Read a result's Lean in ordinary mathematics, for the person to read beside it before attesting. RESULT is a draft's label or a node's id.

    Without a reading, list the Lean to read: the latest record of loom's check stating the result, and each declaration the person reads there, as Lean printed it. With one, record your reading as yours, part by part, each part naming one of those declarations. Nothing checks a reading against the Lean, and it is stale once loom records a newer Lean for the result. Write it only for Lean you did not write.
    """
    from loom.evidence.log import replay
    from loom.formal import reading

    root = open_quilt(quilt_path).root
    if not declarations and not readings:
        found = reading.to_read(replay(root), result)
        if found is None:
            raise ContentError(f"no record of loom's check states {result}; it has no Lean to read yet")
        Report(
            f"{result}: the Lean to read, from {found['record']}",
            groups=[
                Group(
                    "declarations",
                    [Item(f"{d['shown'] or d['kind'] + ' ' + d['name']}") for d in found["declarations"]],
                )
            ],
            data=found,
        ).emit(as_json)
        return
    by = _agent(root, declared)
    if len(readings) != len(declarations):
        raise EnvError("give one --reading for each --declaration, in the same order")
    for flag, given in (("--part", parts), ("--draft", drafts)):
        if given and len(given) != len(declarations):
            raise EnvError(f"give {flag} once for each part, or not at all")
    if len(declarations) > 1 and not parts:
        raise EnvError("name each part with --part, as (i) or a notion's word")
    rows = [
        {
            "part": parts[i] if parts else "",
            "draft": drafts[i] if drafts else "",
            "declaration": d,
            "reading": readings[i],
        }
        for i, d in enumerate(declarations)
    ]
    try:
        made = reading.write(root, result, by, rows, difference or None, record=record)
    except reading.Refused as exc:
        raise ContentError(str(exc)) from None
    Report(
        f"{result}: your reading of {made.get('lean')} is recorded, {counted(len(rows), 'part')}",
        data={"reading": made.id, "lean": made.get("lean")},
    ).emit(as_json)
