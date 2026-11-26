"""`loom library add`: the author keeps the documents they hold, a PDF whatever is known about it: under the work it shows it is, or as a work of its own."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from loom import own
from loom.cli._quilt import open_scan, quilt_option
from loom.cli.report import Group, Item, Progress, Report, counted
from loom.errors import EnvError
from loom.identity import refuse_under_agent, whoever


def _documents(paths: tuple[Path, ...]) -> list[tuple[Path, str]]:
    """(path, kind) for every document the arguments hold: each PDF, a `.bib`, a `.tex` file or an archive, or a folder holding no PDF as one LaTeX source.

    Checked before anything is read or written; an argument holding neither is refused by name (K3).
    """
    out: list[tuple[Path, str]] = []
    for path in paths:
        if path.is_dir():
            pdfs = sorted(p for p in path.rglob("*.pdf") if p.is_file())
            if pdfs:
                out += [(p, "pdf") for p in pdfs]
            elif any(path.rglob("*.tex")):
                out.append((path, "source"))
            else:
                raise EnvError(f"{path} holds no PDF and no LaTeX source")
        elif path.suffix.lower() == ".pdf":
            out.append((path, "pdf"))
        elif path.suffix.lower() == ".bib":
            out.append((path, "bib"))
        elif path.suffix.lower() in (".tex", ".tar", ".gz", ".tgz", ".zip"):
            out.append((path, "source"))
        else:
            raise EnvError(f"{path.name} is no PDF, .bib, LaTeX file or archive of a source; loom files those")
    return out


@click.command(name="add")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path), metavar="FILE...")
@click.option(
    "--for",
    "for_work",
    default=None,
    metavar="WORK",
    help="The work every FILE is: a PDF is filed under it on your word, and what it shows to the contrary is reported and recorded.",
)
@click.option("--new", is_flag=True, help="Keep every PDF as a work of its own, whatever work it may be.")
@click.option(
    "--force",
    is_flag=True,
    help="With --for, file a LaTeX source that shows it is another work; the override is recorded.",
)
@click.option(
    "--online", is_flag=True, help="Allow this run to look up the identifier a PDF states, over `[library] online`."
)
@click.option(
    "--as", "as_name", default=None, metavar="NAME", help="Who is filing, when the user config and git do not say."
)
@click.option("--dry-run", is_flag=True, help="Say what would be added, asked and refused, and write nothing.")
@click.option("--json", "as_json", is_flag=True, help="Print the report as one JSON object.")
@quilt_option
def add_command(
    files: tuple[Path, ...],
    for_work: str | None,
    new: bool,
    force: bool,
    online: bool,
    as_name: str | None,
    dry_run: bool,
    as_json: bool,
    quilt_path: str | None,
) -> None:
    """Take PDFs, `.bib` files and LaTeX sources into the library, each added, already here, a question, or one that cannot be added.

    A FILE is a PDF, a `.bib`, a `.tex` file, an archive of a source, or a folder: each PDF in a folder is a document, and a folder holding no PDF is one LaTeX source. A document is offered as a work the library has only by an identifier it states (arXiv's stamp or an identifier set apart on a PDF's first page, or an arXiv number in its name), never by its title or byline: such a document is filed nowhere, the question names the work, `--for WORK` files it there and `--new` keeps it as a work of its own. Any other document is a work of its own, its entry looked up by the identifier it states where the network is allowed, else made from what it says of itself. With `--for`, every FILE is filed under that work (a reference, or the key its entry has, the entries the documents' bibliographies hold among them), refused where it states another work's identifier unless `--force`. Only the same bytes given twice are already here. A `.bib` adds each of its entries.
    """
    from loom.library.intake import Item, take

    if force and not for_work:
        raise EnvError("--force applies only with --for: name the work the document is")
    if new and for_work:
        raise EnvError("--new keeps each document as a work of its own and --for files it under one: give one of them")
    refuse_under_agent(
        "loom library add",
        "Filing a document under a work is the author's: a wrong PDF under the right entry is read by every anchor into it.",
        as_name,
    )
    docs = _documents(files)
    result = open_scan(quilt_path)
    root = result.quilt.root
    if not dry_run:
        from loom.library.gather import gather

        # a reference for each entry the documents' bibliographies hold, so `--for` names a work by the key a document cites it by
        gather(result)
    target = _work(root, for_work) if for_work else ""
    by = "" if dry_run else whoever(root, as_name)
    items: list[Item] = []
    made_here: list[str] = []
    for path, kind in docs:
        if kind == "source" and path.is_dir():
            drop, fresh = _received_folder(root, path)
            if fresh:
                made_here.append(drop)
            items.append(Item(drop=drop, work=target, new=new, force=force))
        else:
            items.append(Item(path=path, work=target, new=new, force=force))
    allowed = online or result.quilt.config.online
    with Progress("reading documents", len(docs)) as progress:
        progress.item(", ".join(p.name for p, _ in docs[:3]))
        rows = take(root, items, by=by, online=allowed, write=not dry_run, result=result)
    if dry_run:
        from loom.library.intake import incoming

        for drop in made_here:
            own.rmtree(incoming(root) / drop, root=root, ignore_errors=True)
    notes = []
    if not online and not result.quilt.config.online_asked:
        notes.append("this quilt has not said whether loom may look papers up online: --online allows this run")
    _report(rows, dry_run, notes).emit(as_json)


def _work(root: Path, named: str) -> str:
    """The reference `--for` names, by its id or by the key its entry has, ignoring case; EnvError for one the library lacks."""
    from loom.library.intake import Library

    lib = Library.read(root)
    if named in lib.refs:
        return named
    if found := lib.by_key.get(named.casefold()):
        return found
    raise EnvError(f"the library has no work {named}: name a reference or the key its entry has")


def _received_folder(root: Path, folder: Path) -> tuple[str, bool]:
    """A folder of a LaTeX source kept as a drop, packed as the store keeps a source, a file at a time; its drop, and whether this made it."""
    import os
    import secrets

    from loom.library.documents import NotASource, pack
    from loom.library.intake import incoming, receive_file

    base = incoming(root)
    own.mkdir(base, root=root)
    packed = base / f".{folder.name}.{os.getpid()}.{secrets.token_hex(4)}.tar"
    try:
        try:
            with own.open(packed, "wb", root=root) as out:
                drop = pack(folder, out, name=folder.name, work=base).removeprefix("sha256:")
        except NotASource as exc:
            raise EnvError(str(exc)) from exc
        fresh = not (base / drop).is_dir()
        receive_file(root, packed, name=f"{folder.name}.tar")
    finally:
        own.unlink(packed, root=root, missing_ok=True)
    return drop, fresh


def _report(rows: list[Any], dry_run: bool, notes: list[str]) -> Report:
    """Every document in one of four states, each with its reason: added (as a work of its own, or under the work named), already here, a question with the commands that answer it, or one that cannot be added."""
    added = [r for r in rows if r.state == "added"]
    here = [r for r in rows if r.state == "here"]
    asked = [r for r in rows if r.state == "question"]
    cannot = [r for r in rows if r.state == "cannot"]
    items: list[Item] = []
    for r in added:
        text = f"{r.name} under {r.short}" if r.under else f'{r.name} as the work {r.short}, titled "{r.title}"'
        if r.unconfirmed:
            text += ", its details unconfirmed until it is looked up"
        items.append(Item(text, key=r.ref))
    questions = []
    for r in asked:
        named = " or ".join(c["short"] for c in r.candidates)
        how = "; ".join(f"{c['short']}: {c['how']}" for c in r.candidates)
        fixes = [f"loom library add FILE --for {c['ref']} files it there" for c in r.candidates]
        fixes.append("loom library add FILE --new keeps it as a work of its own")
        questions.append(Item(f"{r.name} may be {named} ({how})", fixes=fixes))
    verdict = (
        f"{counted(len(rows), 'document')}: {len(added)} {'would be added' if dry_run else 'added'}, "
        f"{len(here)} already here, {len(asked)} to answer, {len(cannot)} cannot be added"
    )
    return Report(
        verdict,
        ok=not (asked or cannot),
        dry_run=dry_run,
        groups=_present(
            Group("cannot be added", [Item(f"{r.name}: {r.why}") for r in cannot], problem=True, limit=None),
            Group("to answer: filed nowhere until you say which work each is", questions, problem=True, limit=None),
            Group("would be added" if dry_run else "added", items, limit=None),
            Group("already here", [Item(f"{r.name}: {r.why}", key=r.ref) for r in here], limit=None),
        ),
        notes=notes,
        data={
            "added": len(added),
            "here": len(here),
            "questions": len(asked),
            "cannot": len(cannot),
            "documents": [r.to_json() for r in rows],
        },
    )


def _present(*groups: Group) -> list[Group]:
    """The groups that hold something; an empty one would print a heading over nothing."""
    return [g for g in groups if g.items]


#: The commands this module adds to `loom library`.
COMMANDS: list[click.Command] = [add_command]
