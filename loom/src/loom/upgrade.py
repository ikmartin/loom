"""Bringing a quilt forward to the installed loom, the one way `loom upgrade` and the publisher's `library-upgrade` both take: an earlier layout's library carried into the node store and this loom's number stamped, `.loom/.gitignore` refreshed, the annotation types written where a quilt has none, and, where `.loom/agents/instructions/` is a directory of the quilt's own, the agents' layer, the client files and their lines in the root `.gitignore` made this loom's."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom import layout, own
from loom.paths import AI, ANNOTATION_TYPES, LOOM_GITIGNORE

if TYPE_CHECKING:
    from loom.library.carry import Carried


@dataclass
class Upgraded:
    """What one upgrade did, or with `write` False would do, by quilt-relative path.

    Attributes
    ----------
    carried : Carried or None
        What the carry did; None when the quilt was in this loom's layout already.
    written : list of str
        Files written: the ignore files, the annotation types, the agents' layer and the client files.
    kept : list of str
        Files of loom's the person edited, left as they are.
    beside : list of str
        Of `kept`, those with this loom's version written beside them as `<name>.new`, to merge.
    removed : list of str
        Loom's own files of a mode the quilt no longer has, taken away.
    theirs : list of str
        Files of the person's at a path loom writes, left alone.
    dropped : list of str
        Loom's own rules taken out of a permission file, as `FILE: allow RULE`.
    gitignore : list of str
        Lines added to the root `.gitignore`.
    ai : bool
        Whether the quilt has an agents' layer of its own, which was refreshed.
    blocked : str
        Why `.loom/agents/instructions/` was left alone; '' when it was not.
    shell : bool
        Whether the quilt's agents reach loom through the shell rather than its MCP server.
    """

    carried: Carried | None = None
    written: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    beside: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    theirs: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    gitignore: list[str] = field(default_factory=list)
    ai: bool = False
    blocked: str = ""
    shell: bool = False

    def verdict(self, *, dry_run: bool = False) -> str:
        """What the upgrade did, in one sentence: the carry first where there was one, then the files written, kept and removed, or `already current`."""
        from loom.cli.report import counted

        if self.written or self.kept or self.removed:
            parts = (
                (
                    [f"{'would write' if dry_run else 'wrote'} {counted(len(self.written), 'file')}"]
                    if self.written
                    else []
                )
                + (
                    [f"{'would keep' if dry_run else 'kept'} {counted(len(self.kept), 'edited file')}"]
                    if self.kept
                    else []
                )
                + (
                    [f"{'would remove' if dry_run else 'removed'} {counted(len(self.removed), 'file')}"]
                    if self.removed
                    else []
                )
            )
            # one file kept with its new version beside it is one file, said once (T5)
            merge = (
                ""
                if not self.beside
                else (
                    ", its new version beside it to merge"
                    if len(self.kept) == 1
                    else ", each with its new version beside it to merge"
                )
                if len(self.beside) == len(self.kept)
                else f", {len(self.beside)} with a new version beside it to merge"
            )
            said = ("" if dry_run else "upgraded: ") + "; ".join(parts) + merge
        else:
            said = "already current" + (f": {AI}/ and the ignore files" if self.ai else f": {LOOM_GITIGNORE}")
        if self.carried is None:
            return said
        brought = f"{'would bring' if dry_run else 'brought'} the quilt forward to format {layout.NUMBER}, {counted(len(self.carried.references), 'work')} carried into the library"
        return brought + ("" if said.startswith("already current") else "; " + said.removeprefix("upgraded: "))

    def agents(self) -> dict[str, Any]:
        """What was done to the files beside the library, as `loom upgrade --json` and `library-upgrade` give it."""
        return {
            "written": self.written,
            "kept": self.kept,
            "beside": self.beside,
            "removed": self.removed,
            "theirs": self.theirs,
            "dropped": self.dropped,
            "gitignore": self.gitignore,
            "ai": self.ai,
        }


def upgrade(root: Path, *, write: bool = True) -> Upgraded:
    """Bring the quilt at `root` forward to this loom, or say what doing so would change.

    Parameters
    ----------
    root : Path
        The quilt, in this loom's layout or in one it carries (`layout.carriable`).
    write : bool, default True
        Do it; False writes nothing and says what would be done, byte for byte what a real run compares.

    Returns
    -------
    Upgraded
        What was carried, written, kept, removed and left alone.

    Notes
    -----
    The carry holds the id lock and the library's lock itself and carries nothing a second time, and every other step writes only what differs from this loom's, so a second upgrade, or one beside another, changes nothing. A quilt whose layout this loom neither reads nor carries is the caller's to refuse first (`layout.refusal`).
    """
    from loom.ai.clients import write_clients
    from loom.ai.layout import SHELL, blocker, upgrade_layer, variant
    from loom.gitignore import ensure, missing, write_loom_ignore
    from loom.records.types import default_text

    out = Upgraded()
    if layout.carriable(root):
        out.carried = _carry(root, write=write)
    if write_loom_ignore(root, write=write):
        out.written.append(LOOM_GITIGNORE)
    if not (root / ANNOTATION_TYPES).exists():
        # a quilt made before there were types gets the defaults; a file that is there is the person's, edited or not
        if write:
            own.mkdir((root / ANNOTATION_TYPES).parent, root=root)
            own.write_text(root / ANNOTATION_TYPES, default_text(), encoding="utf-8", root=root)
        out.written.append(ANNOTATION_TYPES)
    # a `.loom/agents/instructions` that is not the quilt's own leads elsewhere, so nothing of the agent layer is written there
    out.blocked = blocker(root, AI, folder=True)
    out.ai = (root / AI).is_dir() and not out.blocked
    if not out.ai:
        return out
    out.shell = variant(root) == SHELL
    rep = upgrade_layer(root, write=write, shell=out.shell)
    out.written += [str(rel) for rel in rep.written]
    # the client files follow the variant: what starts the server over MCP, nothing in a shell
    out.written += write_clients(root, write=write, shell=out.shell).written
    out.gitignore = ensure(root) if write else missing(root)
    if out.gitignore:
        out.written.append(".gitignore")
    out.kept = [str(rel) for rel in rep.kept]
    out.beside = [rel for rel in out.kept if f"{rel}.new" in rep.new_beside]
    out.removed, out.theirs, out.dropped = rep.removed, rep.theirs, rep.dropped
    return out


def _carry(root: Path, *, write: bool) -> Carried:
    """Carry an earlier layout's library into the node store and, when writing, stamp this loom's number, so every other command and the publisher open the quilt again."""
    from loom.library.carry import carry
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    carried = carry(root, scan(load_quilt(root, older=True)), write=write)
    if write:
        layout.stamp(root)
    return carried
