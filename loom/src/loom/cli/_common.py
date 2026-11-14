"""Shared CLI plumbing: JSON and notes out, a long text from standard input, the session a command names, and where a `--to` writes.

The errors every command raises, with their exit codes, are `loom.errors`; who is acting is `loom.identity`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from loom.errors import ContentError, EnvError, NotFoundError, fit
from loom.identity import agent_marker
from loom.paths import BUILD


def emit_json(obj: Any) -> None:
    """Print one JSON document to stdout and nothing else there; diagnostics go to stderr."""
    click.echo(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def from_stdin(texts: dict[str, str | None]) -> list[str | None]:
    """The texts given, in order, with the one given as `-` read from standard input: how every command that takes a long text (LaTeX a shell would mangle) reads one.

    Standard input holds one text, so two given as `-` are refused by name.
    """
    dashed = [name for name, value in texts.items() if value == "-"]
    if len(dashed) > 1:
        raise EnvError(f"{' and '.join(dashed)} are both -, and standard input holds one text; give one of them inline")
    if not dashed:
        return list(texts.values())
    import sys

    read = sys.stdin.read()
    return [read if name == dashed[0] else value for name, value in texts.items()]


def note(message: str) -> None:
    """Progress or diagnostic text, always on stderr so --json stdout stays clean, wrapped to fit."""
    click.echo(fit(message), err=True)


def find_session(root: Path, which: str | None, *, deleted: bool = False):  # type: ignore[no-untyped-def]
    """The session `which` names (`sessions.resolve`), or with nothing the active one; refused by name rather than guessed.

    A name that matches nothing is `NotFoundError`, one that matches several an `EnvError` naming them. Refusing rather than creating matters: a value that matched nothing used to be made as a directory at the quilt root, and that directory then satisfied every later lookup. Deleted sessions are found only with `deleted`, so nothing is written into a tombstone by accident.
    """
    from loom.sessions import SessionNotFound, active, resolve, sessions

    if not which:
        here = active(root)
        standing = sessions(root)
        if here and here in standing:
            return standing[here]
        raise EnvError('no session is active; loom session new --name "a name" opens one')
    try:
        return resolve(root, which, deleted=deleted)
    except SessionNotFound as exc:
        if exc.matches:
            raise EnvError(str(exc)) from None
        if not deleted:
            try:
                gone = resolve(root, which, deleted=True)
            except SessionNotFound:
                gone = None
            if gone is not None:
                raise ContentError(f"{gone.id} was deleted; nothing new can be written to it") from None
        raise NotFoundError("session", str(exc)) from None


#: What a file the scan reads ends in: a path loom writes with one of these, inside the quilt, would become source.
SOURCE_SUFFIXES = (".tex", ".sty", ".cls", ".bib")


def destination(
    quilt: Any,
    path: str | Path,
    *,
    document: bool = False,
    source: bool = False,
    overwrite: bool = False,
) -> Path:
    """Where a command's `--to` writes, by the one rule every `--to` follows (K2).

    Parameters
    ----------
    quilt : Quilt
        The quilt the command runs against.
    path : str or Path
        What `--to` said; a relative path is the quilt root's, as every path loom takes is.
    document : bool, default False
        The command writes a working document: a `.tex` anywhere in the quilt the scan reads.
    source : bool, default False
        The command writes a source file that takes another's place (`atomize`), so it may go wherever a source may.
    overwrite : bool, default False
        The command replaces what is there by design; otherwise an existing file is refused.

    Returns
    -------
    Path
        The absolute path to write.

    Raises
    ------
    EnvError
        A working document that is no `.tex`, lies outside the quilt or where the scan does not read; anything else among the quilt's sources, which loom never writes; a file that exists; or, under an agent, a path the quilt protects from agents (`refuse_protected`).
    """
    from loom.scan.scan import unread_dir

    root = Path(quilt.root).resolve()
    given = Path(path).expanduser()
    target = (given if given.is_absolute() else root / given).resolve()
    rel = target.relative_to(root).as_posix() if target.is_relative_to(root) else None
    if document:
        if rel is None:
            raise EnvError(f"{path} is outside the quilt; a working document goes inside it, e.g. --to {target.name}")
        if target.suffix != ".tex":
            raise EnvError(f"{path}: a working document is a .tex file")
        unread = unread_dir(quilt, rel)
        if unread is not None:
            raise EnvError(
                f"{path} is inside {unread}/, which loom never reads as a document; put it anywhere else in the quilt"
            )
    if (
        not document
        and not source
        and rel is not None
        and not rel.startswith(f"{BUILD}/")
        and target.suffix in SOURCE_SUFFIXES
    ):
        raise EnvError(
            f"{path} would be among the quilt's sources, which loom never writes; write it under {BUILD}/ or outside the quilt"
        )
    refuse_protected(quilt, target)
    if target.exists() and not overwrite:
        raise EnvError(f"{path} exists; loom does not overwrite it")
    return target


def refuse_protected(quilt: Any, target: Path) -> None:
    """Refuse an agent a file the quilt protects from agents, whichever command writes it and whatever client runs the agent (K5).

    Claude Code's permission file refuses the agent's own edits; this refuses the same paths when a loom command is the writer, which is the only refusal an agent in any other client meets. A person is never refused here.
    """
    if not agent_marker():
        return
    root = Path(quilt.root).resolve()
    resolved = target.resolve()
    if not resolved.is_relative_to(root):
        return
    from loom.agents import refusal

    why = refusal(quilt.config, resolved.relative_to(root).as_posix())
    if why is not None:
        raise EnvError(f"{resolved.relative_to(root).as_posix()}: {why}; write it elsewhere, or leave it to the author")
