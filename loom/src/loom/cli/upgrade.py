"""`loom upgrade`: bring a quilt an earlier loom made forward to this loom's layout, its library carried into the node store; refresh the generated AI-layer files and the ignore lines loom relies on to the installed loom's versions; edited mode files are kept and a `.new` written beside them. The work is `loom.upgrade.upgrade`, which the publisher's `library-upgrade` runs too; this module reports it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click

from loom.cli._quilt import open_quilt, quilt_option
from loom.cli.report import Group, Item, Report, counted
from loom.paths import AI

if TYPE_CHECKING:
    from loom.library.carry import Carried


@click.command()
@click.option("--dry-run", is_flag=True, help="Say which files would be refreshed, and write nothing.")
@click.option("--json", "as_json", is_flag=True, help="Print the report as one JSON object.")
@quilt_option
def upgrade(dry_run: bool, as_json: bool, quilt_path: str | None) -> None:
    """Bring a quilt an earlier loom made forward, its library carried into the node store; refresh .loom/.gitignore, write .loom/records/annotation-types.toml where a quilt has none, and, where .loom/agents/instructions/ exists, its orientation.md and README.md, unedited mode files, the permission and MCP client files and their lines in the root .gitignore; report edited ones."""
    from loom.cli.ai import NO_SERVER, sdk_groups
    from loom.upgrade import upgrade as bring_forward

    quilt = open_quilt(quilt_path, older=True)
    done = bring_forward(quilt.root, write=not dry_run)
    sdk = sdk_groups(done.shell) if done.ai else []
    groups = [
        *(_carried_groups(done.carried, dry_run) if done.carried is not None else []),
        Group(
            "would write" if dry_run else "wrote",
            [
                Item(
                    f"{'would add' if dry_run else 'added'} {', '.join(done.gitignore)}" if rel == ".gitignore" else "",
                    key=rel,
                )
                for rel in done.written
            ],
            limit=None,
        ),
        Group(
            "kept, as you edited them",
            [
                Item(
                    f"the new version {'would go' if dry_run else 'is'} beside it as {rel.rsplit('/', 1)[-1]}.new"
                    if rel in done.beside
                    else "",
                    key=rel,
                    fixes=[
                        f"merge {rel}.new into {rel}, then delete {rel}.new: it is not written again until loom ships another"
                    ]
                    if rel in done.beside
                    else [],
                )
                for rel in done.kept
            ],
            limit=None,
            problem=True,
        ),
        Group(
            "would remove" if dry_run else "removed",
            [Item("loom's own, for a mode the quilt no longer has", key=rel) for rel in done.removed],
            limit=None,
        ),
        Group("yours, at a path loom writes, so left alone", [Item("", key=rel) for rel in done.theirs], limit=None),
        Group(
            "would take out" if dry_run else "took out",
            [Item("loom's own rule, which it no longer writes", key=rule) for rule in done.dropped],
            limit=None,
        ),
    ]
    verdict = done.verdict(dry_run=dry_run)
    if sdk:
        verdict += f"; {NO_SERVER}"
    Report(
        verdict,
        dry_run=dry_run,
        ok=not done.beside
        and not sdk
        and not done.blocked
        and not (done.carried is not None and done.carried.problems),
        groups=[*(g for g in groups if g.items), *sdk],
        lines=[]
        if done.ai
        else [
            f"left {AI}/ alone, since {done.blocked}; make it a directory of the quilt's own"
            if done.blocked
            else f"no {AI}/ to upgrade; loom ai init creates it"
        ],
        data={**done.agents(), "carried": None if done.carried is None else _carried_data(done.carried)},
    ).emit(as_json)


def _carried_groups(carried: Carried, dry_run: bool) -> list[Group]:
    """What the carry did, or would do, as the report's first groups: what it made and removed, then what it could not carry."""
    verb = "would carry" if dry_run else "carried"
    made = [
        Item(f"{counted(len(carried.references), 'work')} became references in the library"),
        Item(f"{counted(carried.documents, 'document')} moved into the store by hash"),
        Item(f"{counted(carried.notes_rekeyed, 'note')} on works now name their references"),
        Item(f"{counted(carried.overviews, 'overview')} became notes on their works"),
        Item(f"{counted(carried.links_rewritten, 'link')} to a work rewritten in loom's own pages"),
    ]
    return [
        Group(verb, made, limit=None),
        Group("would remove" if dry_run else "removed", [Item("", key=rel) for rel in carried.removed], limit=None),
        Group(
            "not carried",
            [Item(why) for why in carried.problems],
            limit=None,
            problem=True,
        ),
    ]


def _carried_data(carried: Carried) -> dict[str, Any]:
    return {
        "references": carried.references,
        "documents": carried.documents,
        "notes_rekeyed": carried.notes_rekeyed,
        "overviews": carried.overviews,
        "links_rewritten": carried.links_rewritten,
        "removed": carried.removed,
        "problems": carried.problems,
    }
