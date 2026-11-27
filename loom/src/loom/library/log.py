"""The library's log, `.loom/records/library/log.jsonl`: one line for every act on a work, with who and when, appended and never rewritten.

It holds what a reference's file does not (`docs/specs/nodes.md` §10): how the reference was made and from what, whether its details were looked up, who edited it, the documents given to it and taken off it, its deletion and restoring, an intake's add taken back (`undone`), and each time loom tried it unasked (`tried`, `library.unasked`), which, unlike a delete, leaves gathering free to make its key. A reference made from an identifier with no look-up after it reads as unconfirmed (`library-views.md` Open 7); gathering does not make again a key whose work the person deleted, and stops following a `.bib` entry once the person edits the reference in loom. A line that is no act is skipped and reported (`loom:foreign-library-acts`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom import clock, own
from loom.locks import locked
from loom.paths import LIBRARY_LOG
from loom.scan.model import Diagnostic, Location

#: The acts, each with the keys its line carries beyond `event`, `ref`, `by`, `kind` and `at`.
EVENTS: dict[str, tuple[str, ...]] = {
    "made": ("how", "found_by", "looked_up", "source", "key"),
    "looked-up": ("identifier", "found"),
    "edited": (),
    "followed": ("source",),
    "filed": ("which", "hash", "source"),
    "unfiled": ("which", "hash"),
    "deleted": ("key", "undo"),
    "restored": ("undo",),
    "undone": ("act",),
    "tried": ("on", "outcome", "why"),
}
#: How a reference was made: `cited` from the bibliography of a work loom digested, whose id is its `source`.
HOW = ("drop", "paste", "gather", "carry", "source", "cited")
#: What a work was known by when it was made, as the intake's rows say it (`write-api.md` §6): an identifier it states, its entry (a pasted or gathered one, or the work a document was dropped on), its file's name, or nothing.
FOUND_BY = ("arxiv", "doi", "zbl", "entry", "title", "none")
#: Who acts: a person, an agent, or loom of itself (gathering, the carry-over).
KINDS = ("person", "agent", "loom")
#: What a reference was known by that a look-up could confirm: the identifiers `refs.lookup` asks a service about.
LOOKABLE = ("arxiv", "doi", "zbl")


@dataclass
class Acts:
    """The log as it stands: every act by reference and in the log's order, and the lines skipped."""

    by_ref: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    lines: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)

    def of(self, ref: str) -> list[dict[str, Any]]:
        """Every act on `ref`, oldest first."""
        return list(self.by_ref.get(ref, []))

    def made(self, ref: str) -> dict[str, Any] | None:
        """The latest act that made `ref`, or None when the log holds none."""
        return next((a for a in reversed(self.of(ref)) if a["event"] == "made"), None)

    def cited_from(self, ref: str) -> str | None:
        """The work whose bibliography `ref` was made from, as digesting that work made it; None for a work made any other way."""
        made = self.made(ref)
        return str(made.get("source")) if made is not None and made.get("how") == "cited" else None

    def unconfirmed(self, ref: str) -> bool:
        """Whether `ref` was made from an identifier and its details were not looked up, by the act that made it or since."""
        made = self.made(ref)
        if made is None or made.get("found_by") not in LOOKABLE or made.get("looked_up"):
            return False
        after = self.of(ref)[self.of(ref).index(made) + 1 :]
        return not any(a["event"] == "looked-up" and a.get("found") for a in after)

    def follows(self, ref: str) -> bool:
        """Whether gathering still rewrites `ref` from its `.bib` entry: it made it, and nobody has edited it in loom since."""
        made = self.made(ref)
        if made is None or made.get("how") != "gather":
            return False
        after = self.of(ref)[self.of(ref).index(made) + 1 :]
        return not any(a["event"] == "edited" for a in after)

    def deleted_keys(self) -> set[str]:
        """The entry keys whose work the person deleted and nobody has made or restored since, by the log's order, which gathering leaves alone."""
        key_of: dict[str, str] = {}
        state: dict[str, bool] = {}
        for act in self.lines:
            key = act.get("key") or key_of.get(act["ref"])
            if not key:
                continue
            key_of[act["ref"]] = key
            if act["event"] == "deleted":
                state[key] = True
            elif act["event"] in ("made", "restored"):
                state[key] = False
        return {key for key, gone in state.items() if gone}


def replay(root: Path) -> Acts:
    """The quilt's log, every line read in order; empty when there is none.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Acts
        The acts by reference, and the lines that were none.
    """
    acts = Acts()
    path = root / LIBRARY_LOG
    if not path.is_file():
        return acts
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            act = json.loads(line)
        except json.JSONDecodeError:
            acts.skipped.append((number, "it is not JSON"))
            continue
        why = _why_not(act)
        if why:
            acts.skipped.append((number, why))
            continue
        acts.by_ref.setdefault(act["ref"], []).append(act)
        acts.lines.append(act)
    return acts


def _why_not(act: Any) -> str | None:
    if not isinstance(act, dict):
        return "it is not a JSON object"
    if act.get("event") not in EVENTS:
        return "it names no act"
    if not isinstance(act.get("ref"), str) or not act["ref"]:
        return "it names no work"
    if act.get("kind") not in KINDS or not isinstance(act.get("by"), str):
        return "it does not say who"
    if not isinstance(act.get("at"), str):
        return "it does not say when"
    return None


def record(root: Path, event: str, ref: str, *, by: str, kind: str, **fields: Any) -> dict[str, Any]:
    """Append one act to the log, under its lock.

    Parameters
    ----------
    root : Path
        The quilt.
    event : str
        One of `EVENTS`.
    ref : str
        The reference acted on.
    by : str
        Who acted, by name; `loom` for loom's own acts.
    kind : str
        `person`, `agent` or `loom`.
    **fields
        The act's own keys (`EVENTS`); a key given None is left out.

    Returns
    -------
    dict
        The line written.

    Raises
    ------
    ValueError
        For an act, a kind or a key the log does not have.
    """
    if event not in EVENTS:
        raise ValueError(f"the library's log has no act {event}")
    if kind not in KINDS:
        raise ValueError(f"who acts on a work is a person, an agent or loom, not {kind}")
    unknown = set(fields) - set(EVENTS[event])
    if unknown:
        raise ValueError(f"a {event} act has no {', '.join(sorted(unknown))}")
    line = {"event": event, "ref": ref, "by": by, "kind": kind, "at": clock.stamp()}
    line.update({k: v for k, v in fields.items() if v is not None})
    path = root / LIBRARY_LOG
    own.mkdir(path.parent, root=root)
    with locked(path):
        with own.open(path, "a", encoding="utf-8", root=root) as fh:
            fh.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    return line


def problems(acts: Acts) -> list[Diagnostic]:
    """One `loom:foreign-library-acts` for each line `replay` skipped, naming the line and why."""
    return [
        Diagnostic(
            "warning",
            "loom:foreign-library-acts",
            f"Line {number} of {LIBRARY_LOG} is not an act on a work ({why}), so it is skipped.",
            [Location(LIBRARY_LOG, number)],
            subject="record",
        )
        for number, why in acts.skipped
    ]
