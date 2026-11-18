"""`loom library add`: the author keeps the documents they hold, a PDF whatever is known about it: under the work it shows it is, or as a work of its own."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from loom.cli._quilt import open_scan, quilt_option
from loom.cli.library._works import one_work, present
from loom.cli.report import Group, Item, Progress, Report, counted
from loom.errors import EnvError
from loom.identity import refuse_under_agent, whoever


def _documents(paths: tuple[Path, ...]) -> list[tuple[Path, str]]:
    """(path, kind) for every document the arguments hold: each PDF, a `.tex` file, or a folder holding no PDF as one LaTeX source.

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
        elif path.suffix.lower() == ".tex":
            out.append((path, "source"))
        else:
            raise EnvError(f"{path.name} is neither a PDF nor LaTeX source; loom files those two things")
    return out


def _came_from(root: Path, path: Path) -> str:
    """Where a document came from, as the ledger and its entry record it: quilt-relative inside the quilt, else its name."""
    resolved = path.resolve()
    return resolved.relative_to(root.resolve()).as_posix() if resolved.is_relative_to(root.resolve()) else path.name


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
    """Take PDFs and LaTeX sources into the library, each added, already here, a question, or one that cannot be added.

    A FILE is a PDF, a `.tex` file, or a folder: each PDF in a folder is a document, and a folder holding no PDF is one LaTeX source. A PDF that may be a work the library has (the identifier it states as its own is that work's, its whole title is set over that work's first author, a reference manager's file name says so, or the entry it makes of itself shares the work's identifier, or title and year) is filed nowhere: the question names the work, `--for WORK` files it there and `--new` keeps it as a work of its own. Any other PDF is kept as a work of its own, its entry made from what it shows and keyed as its author, title and year give it. With `--for`, every FILE is that work's on your word, and what a PDF shows to the contrary is reported and recorded. A LaTeX source is filed only with `--for`, and refused when it shows it is another work's unless `--force`. A work that holds a document gets the new one beside it as its version (`KEY-v2`), never over it, however like that document it looks. Only the same bytes given twice are already here. A PDF's page text is read at once.
    """
    from loom.refs.intake import Item, Row, take

    if force and not for_work:
        raise EnvError("--force applies only with --for: name the work the document is")
    if new and for_work:
        raise EnvError("--new keeps each PDF as a work of its own and --for files it under one: give one of them")
    refuse_under_agent(
        "loom library add",
        "Filing a document under a work is the author's: a wrong PDF under the right entry is read by every anchor into it.",
        as_name,
    )
    docs = _documents(files)
    result = open_scan(quilt_path)
    root = result.quilt.root
    target = one_work(result, for_work) if for_work else None
    by = "" if dry_run else whoever(root, as_name)
    sources = [p for p, kind in docs if kind == "source"]
    refused = _refused_sources(result, sources, target, force)
    pdfs = [p for p, kind in docs if kind == "pdf"]
    items = [Item(path=p, name=p.name, work=target or "", on_word=target is not None, new=new) for p in pdfs]
    allowed = online or result.quilt.config.online
    with Progress("reading documents", len(docs)) as progress:
        progress.item(", ".join(p.name for p in pdfs[:3]))
        rows: list[tuple[Path, Row]] = [
            (pdfs[r.item], r)
            for r in take(result.quilt, dict(result.bib), items, by=by, online=allowed, write=not dry_run)
        ]
    for path in sources:
        rows.append((path, _take_source(result, path, target, refused.get(path, ""), dry_run, by)))
    notes = []
    if pdfs and not online and not result.quilt.config.online_asked:
        notes.append("this quilt has not said whether loom may look papers up online: --online allows this run")
    _report(rows, dry_run, notes).emit(as_json)


def _refused_sources(result: Any, sources: list[Path], target: str | None, force: bool) -> dict[Path, str]:
    """Why each LaTeX source shows it is another work than `--for` names, which `--force` overrides; EnvError, before anything is written, when one is refused."""
    from loom.refs.ingest import identify_source
    from loom.refs.scan import one_work_of

    if target is None:
        return {}
    out: dict[Path, str] = {}
    refused: list[tuple[Path, str]] = []
    versions: dict[Path, str] = {}
    for path in sources:
        identity = identify_source(path, result.bib)
        why = identity.refusal_for(target, result.bib[target])
        if why and not force:
            refused.append((path, why))
            other = next((m.citekey for m in identity.strong if m.citekey != target), "")
            if other and one_work_of([other, target], result.bib):
                versions[path] = other
        out[path] = why
    if refused:
        shown = "; ".join(f"{p.name}: {why}" for p, why in refused)
        version = next(iter(set(versions.values())), "") if len(set(versions.values())) == 1 else ""
        raise EnvError(
            f"nothing filed under {target}, {shown}. "
            + (
                f"{version} is a version of the same work: loom library add FILE --for {version} files it there"
                if version and len(versions) == len(refused)
                else f"If it is {target}'s, pass --force with --for {target}, and the override is recorded"
            )
        )
    return out


def _take_source(result: Any, path: Path, target: str | None, forced: str, dry_run: bool, by: str) -> Any:
    """A LaTeX source as a row: filed under `--for`'s work, beside its first source as a version where it has one; without `--for`, a question naming the work it shows it is, or one that cannot be added."""
    from loom.refs.ingest import identify_source
    from loom.refs.intake import Row
    from loom.refs.scan import Filing, append_entries, bib_file, file_document, one_work_of, plan_filing, tree_sha

    root = result.quilt.root
    if target is None:
        identity = identify_source(path, result.bib)
        best = identity.best()
        if len(best) > 1 and (top := one_work_of([m.citekey for m in best], result.bib)):
            best = [m for m in best if m.citekey == top] or best[:1]
        if not best:
            where = bib_file(result) or "your bibliography"
            return Row(
                "",
                0,
                path.name,
                "cannot",
                code="not-recognised",
                why=f"{identity.weak}; add its entry to {where}, then loom library add FILE --for KEY files it",
            )
        candidates = [{"citekey": m.citekey, "title": "", "authors": "", "year": "", "how": m.how} for m in best]
        return Row("", 0, path.name, "question", candidates=candidates)
    f = Filing(path, target, "source", tree_sha(path), _came_from(root, path), forced=forced, named=True)
    sibling = plan_filing(result.quilt, dict(result.bib), f, set(result.bib), {})
    if f.already:
        return Row("", 0, path.name, "here", target, why=f.already)
    if not dry_run:
        file_document(result.quilt, f, by=by)
        append_entries(result.quilt, [sibling] if sibling is not None else [])
    return Row(
        "",
        0,
        path.name,
        "added",
        target,
        under=target,
        sibling=f.sibling,
        why=forced,
        filed_as=f.sibling or target,
        pages="source",
    )


def _is_pdf(path: Path) -> bool:
    """Whether a file opens as a PDF does, which is all that is asked of one before it is kept."""
    try:
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False


def _report(rows: list[tuple[Path, Any]], dry_run: bool, notes: list[str]) -> Report:
    """Every document in one of four states, each with its reason: added (as a new work, or under the work named, beside its first document), already here, a question with the commands that answer it, or one that cannot be added."""
    added = [(p, r) for p, r in rows if r.state == "added"]
    here = [(p, r) for p, r in rows if r.state == "here"]
    asked = [(p, r) for p, r in rows if r.state == "question"]
    cannot = [(p, r) for p, r in rows if r.state == "cannot"]
    items: list[Item] = []
    for p, r in added:
        what = "LaTeX source" if r.pages == "source" else "PDF"
        text = (
            f'{p.name} as the new work {r.citekey}, titled "{r.title}"'
            if not r.under
            else f"{p.name} as {r.under}'s {what}"
        )
        if r.sibling:
            text += f", beside its first document as {r.sibling}"
        elif r.replaced:
            text += ", in place of the document you set aside"
        if what == "PDF" and not dry_run:
            text += f", without page text ({r.why})" if r.pages == "none" else ", with its page text"
        if r.under and r.why and r.pages != "none":
            text += f"; on your word, though {r.why}"
        fixes = [f"loom library update {r.filed_as} --only extract makes its digest"] if what == "LaTeX source" else []
        if not r.under and r.nearest:
            fixes.append(f"loom library add FILE --for {r.nearest} files it there instead, if that is what it is")
        items.append(Item(text, key=r.citekey, fixes=fixes))
    questions = []
    for p, r in asked:
        named = " or ".join(c["citekey"] for c in r.candidates)
        how = "; ".join(f"{c['citekey']}: {c['how']}" for c in r.candidates)
        fixes = [f"loom library add FILE --for {c['citekey']} files it there" for c in r.candidates]
        if p.suffix.lower() == ".pdf":
            fixes.append("loom library add FILE --new keeps it as a work of its own")
        questions.append(Item(f"{p.name} may be {named} ({how})", fixes=fixes))
    total = len(rows)
    verdict = (
        f"{counted(total, 'document')}: {len(added)} {'would be added' if dry_run else 'added'}, "
        f"{len(here)} already here, {len(asked)} to answer, {len(cannot)} cannot be added"
    )
    return Report(
        verdict,
        ok=not (asked or cannot),
        dry_run=dry_run,
        groups=present(
            Group("cannot be added", [Item(f"{p.name}: {r.why}") for p, r in cannot], problem=True, limit=None),
            Group("to answer: filed nowhere until you say which work each is", questions, problem=True, limit=None),
            Group("would be added" if dry_run else "added", items, limit=None),
            Group("already here", [Item(f"{p.name}: {r.why}", key=r.citekey) for p, r in here], limit=None),
        ),
        notes=notes
        + (
            ["the store is not in version control: a collaborator fetches or adds their own copy"]
            if added and not dry_run
            else []
        ),
        data={
            "added": len(added),
            "here": len(here),
            "questions": len(asked),
            "cannot": len(cannot),
            "documents": [{"file": str(p), **r.to_json(), "nearest": r.nearest, "apart": r.apart} for p, r in rows],
        },
    )


#: The commands this module adds to `loom library`.
COMMANDS: list[click.Command] = [add_command]
