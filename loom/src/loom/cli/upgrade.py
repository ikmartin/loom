"""`loom upgrade`: bring a quilt an earlier loom made forward to this loom's layout, its library carried into the node store; refresh the generated AI-layer files and the ignore lines loom relies on to the installed loom's versions; edited mode files are kept and a `.new` written beside them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import click

from loom import layout
from loom.cli._quilt import open_quilt, quilt_option
from loom.cli.report import Group, Item, Report, counted
from loom.paths import AI, ANNOTATION_TYPES, LOOM_GITIGNORE
from loom.records.types import default_text

if TYPE_CHECKING:
    from loom.library.carry import Carried
    from loom.scan.quilt import Quilt


@click.command()
@click.option("--dry-run", is_flag=True, help="Say which files would be refreshed, and write nothing.")
@click.option("--json", "as_json", is_flag=True, help="Print the report as one JSON object.")
@quilt_option
def upgrade(dry_run: bool, as_json: bool, quilt_path: str | None) -> None:
    """Bring a quilt an earlier loom made forward, its library carried into the node store; refresh .loom/.gitignore, write .loom/records/annotation-types.toml where a quilt has none, and, where .loom/agents/instructions/ exists, its orientation.md and README.md, unedited mode files, the permission and MCP client files and their lines in the root .gitignore; report edited ones."""
    from loom.ai.clients import write_clients
    from loom.ai.layout import SHELL, blocker, upgrade_layer, variant
    from loom.cli.ai import NO_SERVER, sdk_groups
    from loom.gitignore import ensure, missing, write_loom_ignore

    quilt = open_quilt(quilt_path, older=True)
    root = quilt.root
    carried = _carry(quilt, write=not dry_run) if layout.carriable(root) else None
    written: list[str] = []
    kept: list[str] = []
    beside: list[str] = []
    removed: list[str] = []
    theirs: list[str] = []
    dropped: list[str] = []
    if write_loom_ignore(root, write=not dry_run):
        written.append(LOOM_GITIGNORE)
    if not (root / ANNOTATION_TYPES).exists():
        # a quilt made before there were types gets the defaults; a file that is there is the person's, edited or not
        if not dry_run:
            (root / ANNOTATION_TYPES).parent.mkdir(parents=True, exist_ok=True)
            (root / ANNOTATION_TYPES).write_text(default_text(), encoding="utf-8")
        written.append(ANNOTATION_TYPES)
    added: list[str] = []
    sdk: list[Group] = []
    # a `.loom/agents/instructions` that is not the quilt's own leads elsewhere, so nothing of the agent layer is written there
    blocked = blocker(root, AI, folder=True)
    has_ai = (root / AI).is_dir() and not blocked
    if has_ai:
        shell = variant(root) == SHELL
        rep = upgrade_layer(root, write=not dry_run, shell=shell)
        written += [str(rel) for rel in rep.written]
        # the client files follow the variant: what starts the server over MCP, nothing in a shell
        written += write_clients(root, write=not dry_run, shell=shell).written
        sdk = sdk_groups(shell)
        added = missing(root) if dry_run else ensure(root)
        if added:
            written.append(".gitignore")
        kept += [str(rel) for rel in rep.kept]
        beside = [rel for rel in kept if f"{rel}.new" in rep.new_beside]
        removed, theirs, dropped = rep.removed, rep.theirs, rep.dropped
    groups = [
        *(_carried_groups(carried, dry_run) if carried is not None else []),
        Group(
            "would write" if dry_run else "wrote",
            [
                Item(
                    f"{'would add' if dry_run else 'added'} {', '.join(added)}" if rel == ".gitignore" else "", key=rel
                )
                for rel in written
            ],
            limit=None,
        ),
        Group(
            "kept, as you edited them",
            [
                Item(
                    f"the new version {'would go' if dry_run else 'is'} beside it as {rel.rsplit('/', 1)[-1]}.new"
                    if rel in beside
                    else "",
                    key=rel,
                    fixes=[
                        f"merge {rel}.new into {rel}, then delete {rel}.new: it is not written again until loom ships another"
                    ]
                    if rel in beside
                    else [],
                )
                for rel in kept
            ],
            limit=None,
            problem=True,
        ),
        Group(
            "would remove" if dry_run else "removed",
            [Item("loom's own, for a mode the quilt no longer has", key=rel) for rel in removed],
            limit=None,
        ),
        Group("yours, at a path loom writes, so left alone", [Item("", key=rel) for rel in theirs], limit=None),
        Group(
            "would take out" if dry_run else "took out",
            [Item("loom's own rule, which it no longer writes", key=rule) for rule in dropped],
            limit=None,
        ),
    ]
    if written or kept or removed:
        parts = (
            ([f"{'would write' if dry_run else 'wrote'} {counted(len(written), 'file')}"] if written else [])
            + ([f"{'would keep' if dry_run else 'kept'} {counted(len(kept), 'edited file')}"] if kept else [])
            + ([f"{'would remove' if dry_run else 'removed'} {counted(len(removed), 'file')}"] if removed else [])
        )
        # one file kept with its new version beside it is one file, said once (T5)
        merge = (
            ""
            if not beside
            else (
                ", its new version beside it to merge"
                if len(kept) == 1
                else ", each with its new version beside it to merge"
            )
            if len(beside) == len(kept)
            else f", {len(beside)} with a new version beside it to merge"
        )
        verdict = ("" if dry_run else "upgraded: ") + "; ".join(parts) + merge
    else:
        verdict = "already current" + (f": {AI}/ and the ignore files" if has_ai else f": {LOOM_GITIGNORE}")
    if carried is not None:
        brought = f"{'would bring' if dry_run else 'brought'} the quilt forward to format {layout.NUMBER}, {counted(len(carried.references), 'work')} carried into the library"
        verdict = brought + ("" if verdict.startswith("already current") else "; " + verdict.removeprefix("upgraded: "))
    if sdk:
        verdict += f"; {NO_SERVER}"
    Report(
        verdict,
        dry_run=dry_run,
        ok=not beside and not sdk and not blocked and not (carried is not None and carried.problems),
        groups=[*(g for g in groups if g.items), *sdk],
        lines=[]
        if has_ai
        else [
            f"left {AI}/ alone, since {blocked}; make it a directory of the quilt's own"
            if blocked
            else f"no {AI}/ to upgrade; loom ai init creates it"
        ],
        data={
            "written": written,
            "kept": kept,
            "beside": beside,
            "removed": removed,
            "theirs": theirs,
            "dropped": dropped,
            "gitignore": added,
            "ai": has_ai,
            "carried": None if carried is None else _carried_data(carried),
        },
    ).emit(as_json)


def _carry(quilt: Quilt, *, write: bool) -> Carried:
    """Carry an earlier layout's library into the node store and, when writing, stamp this loom's number, so every other command opens the quilt again."""
    from loom.library.carry import carry
    from loom.scan.scan import scan

    carried = carry(quilt.root, scan(quilt), write=write)
    if write:
        layout.stamp(quilt.root)
    return carried


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
