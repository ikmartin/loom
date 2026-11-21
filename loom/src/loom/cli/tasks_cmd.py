"""`loom tasks`, `loom ask` and `loom evidence`: an agent's side of the asks and the evidence.

An agent reads what is open for it, says it is working on one, says what it produced, answers a person's question, withdraws its own ask, asks the person a question or for a paper it could not fetch, and reads what is known of a result. Every act of a person's (comparing, attesting, accepting, answering an agent's question) is the viewer's, and none has a command here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from loom.cli._quilt import open_quilt, quilt_option
from loom.cli.help import CommandGroup
from loom.cli.report import Group, Item, Report, counted
from loom.errors import ContentError, EnvError

SESSION_OPTION = click.option(
    "--session",
    "session",
    default=None,
    metavar="ID",
    help="The loom session you work in, by which loom tells your asks from another conversation's; default the active one.",
)
AS_OPTION = click.option(
    "--as", "declared", default=None, metavar="NAME", help="Who acts; an agent names itself, including Agent or AI."
)
JSON_OPTION = click.option("--json", "as_json", is_flag=True, help="Print the report as one JSON object.")


def _agent(root: Path, declared: str | None) -> Any:
    """Who an agent's command acts as: the name it declares, which must say it is an agent's (`identity.writer`)."""
    from loom.evidence.subjects import Who
    from loom.identity import writer

    name, kind = writer(root, declared)
    if kind != "agent":
        raise EnvError(
            f"{name or 'nobody'} is not an agent's name; a person acts in the viewer. Name yourself with --as, including Agent or AI."
        )
    return Who("agent", name)


def _session(root: Path, given: str | None) -> str | None:
    """The session an agent's command acts in: the one it names, else the quilt's active one, else none."""
    from loom.cli._common import find_session
    from loom.sessions import active

    return str(find_session(root, given).id) if given else active(root)


def _refused(exc: Exception) -> ContentError:
    return ContentError(str(exc))


def _row(found: Any, standing: Any, marks: dict[str, Any] | None = None) -> dict[str, Any]:
    """An ask as a command prints it in JSON: the asking line's fields, how it stands, and for a `digest` of marks where each mark stands."""
    a = found
    places = [_mark_place(marks[m]) for m in a.get("marks", []) if marks and m in marks]
    return {
        **({"mark_places": places} if places else {}),
        "id": a.id,
        "what": a.what,
        "to": a.to,
        "by": a.by.to_dict(),
        "at": a.at,
        "on": dict(a.on),
        "for": list(a.origin),
        "words": a.words,
        **{
            k: v
            for k, v in a.fields.items()
            if k not in ("id", "what", "to", "by", "at", "on", "from", "words", "event")
        },
        "open": standing.open,
        "closed": standing.why or None,
        "working": standing.working,
        "taken_by": [t["by"]["name"] for t in a.took],
        "answers": [{k: v for k, v in x.items() if k in ("by", "at", "choice", "words")} for x in a.answers],
    }


def _mark_place(mark: Any) -> dict[str, Any]:
    """Where a mark to digest stands, as its annotation records it: the work, the page, the words and the rectangles."""
    return {
        "mark": mark.id,
        "work": mark.target_key,
        "page": mark.anchor.page if mark.anchor else mark.page,
        "quote": mark.selector.exact if mark.selector else None,
        "rects": mark.rects,
    }


def _line(found: Any, standing: Any) -> str:
    a = found
    if a.to == "person":
        # another agent's words, named and quoted, never read as part of the list
        asker = f" by {a.by.name}:"
    else:
        asker = ""
    if a.what in ("question", "ask", "correct"):
        said = f'"{a.get("text")}"'
    elif a.what == "paper":
        said = f"the {a.get('want')} of {a.get('ref')}, from {a.get('link')}"
    elif a.what in ("read", "digest"):
        said = ", ".join(a.get("nodes") or [str(a.get("ref"))])
    elif a.what in ("formalize", "restate"):
        target = a.get("target") or {}
        said = str(target.get("label") or target.get("node"))
    else:
        said = f"which result of {a.get('cites')} {a.on['block']['key']} rests on"
    state = "working" if standing.working else ("open" if standing.open else str(standing.why))
    words = f" ({a.words})" if a.words else ""
    line = f"{a.id}  {a.what}{asker} {said}{words}  [{state}]"
    for answer in a.answers:
        choice = answer.get("choice")
        picked = f'"{a.get("choices", [])[choice]}"' if isinstance(choice, int) else ""
        own = f'"{answer.get("words")}"' if answer.get("words") else ""
        line += "\n  answered: " + " and ".join(x for x in (picked, own) if x)
    return line


@click.group(name="tasks", cls=CommandGroup, invoke_without_command=True)
@click.option("--all", "show_all", is_flag=True, help="Include asks that are closed or withdrawn.")
@JSON_OPTION
@quilt_option
@click.pass_context
def tasks(ctx: click.Context, show_all: bool, as_json: bool, quilt_path: str | None) -> None:
    """List what waits for an agent: what a person asked of agents, the questions and papers agents asked of the person, and each answer the person gave that the agent that asked has not seen since its last `loom since`.

    Nothing is assigned or ranked: take what you can do (`loom tasks take ID`), and say what you produced (`loom tasks done ID --made ID`). An ask closes by what it produces, a stub read or Lean run on its result, whoever produced it.
    """
    if ctx.invoked_subcommand is not None:
        return
    from loom.evidence.asks import answered_unseen, open_asks
    from loom.records.annotations import load_records

    root = open_quilt(quilt_path).root
    every = [s for s in open_asks(root, closed=True) if show_all or s.open or answered_unseen(root, s.ask)]
    marks = {a.id: a for rec in load_records(root)[0] for a in rec.annotations if a.purpose == "to-digest"}
    for_agents = [s for s in every if s.ask.to == "agent"]
    of_person = [s for s in every if s.ask.to == "person"]
    groups = [
        Group("asked of agents", [Item(_line(s.ask, s)) for s in for_agents]),
        Group("asked of the person by agents", [Item(_line(s.ask, s)) for s in of_person]),
    ]
    waiting = sum(1 for s in for_agents if s.open)
    Report(
        f"{counted(waiting, 'task waits', 'tasks wait')} for an agent; {counted(sum(1 for s in of_person if s.open), 'ask waits', 'asks wait')} for the person"
        + (
            f"; {counted(answered, 'answer')} not yet seen"
            if (answered := sum(1 for s in of_person if answered_unseen(root, s.ask)))
            else ""
        ),
        groups=[g for g in groups if g.items],
        data={"tasks": [_row(s.ask, s, marks) for s in for_agents], "asked": [_row(s.ask, s) for s in of_person]},
    ).emit(as_json)


def _say(
    event: str, task: str, declared: str | None, as_json: bool, quilt_path: str | None, verdict: str, **fields: Any
) -> None:
    from loom.evidence.asks import AskRefused, say

    root = open_quilt(quilt_path).root
    who = _agent(root, declared)
    try:
        after = say(root, who, event, task, **fields)
    except AskRefused as exc:
        raise _refused(exc) from None
    Report(verdict.format(id=after.id), data={"task": after.id, "event": event}).emit(as_json)


@tasks.command(name="take")
@click.argument("task")
@SESSION_OPTION
@AS_OPTION
@JSON_OPTION
@quilt_option
def take_command(task: str, session: str | None, declared: str | None, as_json: bool, quilt_path: str | None) -> None:
    """Say that your session is working on TASK, so the person sees it taken; refused while a live session of another works on it."""
    root = open_quilt(quilt_path).root
    session = _session(root, session)
    if not session:
        raise EnvError("no session is active; open one with `loom session new` and take the task again")
    _say("took", task, declared, as_json, quilt_path, "{id}: taken by this session", session=session)


@tasks.command(name="done")
@click.argument("task")
@click.option(
    "--made",
    "made",
    multiple=True,
    metavar="ID",
    help="What you produced: a node's id, a suggested edit's id. Repeat for each.",
)
@AS_OPTION
@JSON_OPTION
@quilt_option
def done_command(task: str, made: tuple[str, ...], declared: str | None, as_json: bool, quilt_path: str | None) -> None:
    """Say what you produced for TASK. The task closes when what it asked for exists, which loom checks, not when you say so."""
    _say("done", task, declared, as_json, quilt_path, "{id}: what you made is recorded", made=list(made))


@tasks.command(name="answer")
@click.argument("task")
@click.argument("text")
@AS_OPTION
@JSON_OPTION
@quilt_option
def answer_command(task: str, text: str, declared: str | None, as_json: bool, quilt_path: str | None) -> None:
    """Answer TASK, a question the person asked of an agent, in TEXT."""
    _say("answered", task, declared, as_json, quilt_path, "{id}: answered", words=text)


@tasks.command(name="withdraw")
@click.argument("task")
@SESSION_OPTION
@AS_OPTION
@JSON_OPTION
@quilt_option
def withdraw_command(
    task: str, session: str | None, declared: str | None, as_json: bool, quilt_path: str | None
) -> None:
    """Withdraw TASK, a question or a paper you asked of the person and no longer need: one you asked, under your name, and in your session where it was asked in one."""
    session = _session(open_quilt(quilt_path).root, session)
    _say(
        "withdrawn", task, declared, as_json, quilt_path, "{id}: withdrawn", **({"session": session} if session else {})
    )


@click.command(name="ask")
@click.argument("text", required=False, default="")
@click.option(
    "--choice",
    "choices",
    multiple=True,
    metavar="TEXT",
    help="One choice the person may pick; up to six. They may always answer in their own words.",
)
@click.option(
    "--on",
    "place",
    default=None,
    metavar="PLACE",
    help="What it is about: a result's label or id, a key, a work's id with :PAGE, or a document's path.",
)
@click.option(
    "--paper",
    "ref",
    default=None,
    metavar="REF",
    help="Ask for a paper you could not fetch, by its reference's id; give --link.",
)
@click.option(
    "--link",
    default=None,
    metavar="URL",
    help="With --paper: the http or https page you could not fetch it from, which the person opens.",
)
@click.option(
    "--want",
    type=click.Choice(["pdf", "tex"]),
    default="pdf",
    show_default=True,
    help="With --paper: which document of the work.",
)
@click.option(
    "--for",
    "drafts",
    multiple=True,
    metavar="DOC",
    help="A draft it is asked for, so the person can see it with that draft's; default the documents that read the place.",
)
@SESSION_OPTION
@AS_OPTION
@JSON_OPTION
@quilt_option
def ask_command(
    text: str,
    choices: tuple[str, ...],
    place: str | None,
    ref: str | None,
    link: str | None,
    want: str,
    drafts: tuple[str, ...],
    session: str | None,
    declared: str | None,
    as_json: bool,
    quilt_path: str | None,
) -> None:
    """Ask the person a question in TEXT, or with --paper for a paper you could not fetch.

    A question waits in Review with its choices and a field for the person's own words; once they answer, `loom tasks` shows the answer until your next `loom since`, which reports it. A paper waits in Review with its link, for the person to fetch and add; the request closes once the work holds the document.
    """
    from loom.evidence.asks import AskRefused, ask, place_of
    from loom.scan.scan import scan

    quilt = open_quilt(quilt_path)
    root = quilt.root
    who = _agent(root, declared)
    session = _session(root, session)
    stray = [d for d in drafts if d not in scan(quilt).masters] if drafts else []
    if stray:
        raise ContentError(f"{stray[0]} is not a document of this quilt; --for names a draft by its path")
    mine = {"session": session} if session else {}
    try:
        if ref is not None:
            if not link:
                raise ContentError("--paper needs --link, the page you could not fetch it from")
            if choices:
                raise ContentError("a paper is asked for with no choices")
            made = ask(
                root,
                who,
                "paper",
                "person",
                {"ref": ref},
                origin=list(drafts),
                words=text,
                ref=ref,
                link=link,
                want=want,
                **mine,
            )
            verdict = f"{made.id}: asked the person for the {want} of {ref}"
        else:
            if not text.strip():
                raise ContentError("say the question, in TEXT")
            if not place:
                raise ContentError("say what the question is about with --on")
            on, readers = place_of(quilt, place)
            fields: dict[str, Any] = {"text": text}
            if choices:
                fields["choices"] = list(choices)
            made = ask(root, who, "question", "person", on, origin=list(drafts) or readers, **fields, **mine)
            verdict = f"{made.id}: asked the person"
    except AskRefused as exc:
        raise _refused(exc) from None
    Report(verdict, data={"task": made.id}).emit(as_json)


@click.command(name="evidence")
@click.argument("name")
@JSON_OPTION
@quilt_option
def evidence_command(name: str, as_json: bool, quilt_path: str | None) -> None:
    """What is known of a result: its status, and every record about it. NAME is a draft's label or a node's id."""
    from loom.evidence.asks import replay as replay_asks
    from loom.evidence.log import replay
    from loom.evidence.status import files_unchanged, status
    from loom.evidence.subjects import NODE
    from loom.evidence.web import DraftWeb, Here
    from loom.scan.quilt import reviewer_identity
    from loom.scan.scan import scan

    quilt = open_quilt(quilt_path)
    root = quilt.root
    evidence = replay(root)
    web = DraftWeb(scan(quilt), reviewer=reviewer_identity(root)[0] or None)
    # a draft's id has the shape of a node's, so the drafts are asked first
    kind = "label" if name in web.bearing or not NODE.fullmatch(name) else "node"
    heres = [Here("node", name)] if kind == "node" else web.heres(name)
    now = files_unchanged(root)
    found = [(h, status(evidence, web, h, lean_now=now)) for h in heres]
    records = [dict(r.fields) for r in evidence.about(kind, name)]
    asked = [
        a
        for a in replay_asks(root).asks.values()
        if a.on.get(kind) == name or (a.get("target") or {}).get(kind) == name
    ]
    if not found or all(s.subject is None for _h, s in found):
        if not records:
            raise ContentError(f"no result of this quilt is named {name}")
    rows = [_status_row(h, s) for h, s in found]
    groups = [Group("where it stands", [Item(f"{r['at']}: {_says(r)}") for r in rows])]
    groups.append(
        Group("records", [Item(f"{r['at']}  {r['kind']} by {r['by'].get('name') or 'loom'}") for r in records])
    )
    Report(
        f"{name}: {counted(len(records), 'record')}, {counted(len(asked), 'ask')}",
        groups=[g for g in groups if g.items],
        data={"status": rows, "records": records, "asks": [a.id for a in asked]},
    ).emit(as_json)


def _status_row(here: Any, s: Any) -> dict[str, Any]:
    return {
        "at": here.name,
        "kind": here.kind,
        "subject": s.subject.to_dict() if s.subject else None,
        "reading": s.reading,
        "lean": s.lean,
        "role": s.role,
        "relative_to": [x.to_dict() for x in s.relative_to],
        "causes": [{"changed": {c.key[0]: c.key[1]}, "then": c.then, "now": c.now} for c in s.causes],
        "unattested_notation": list(s.unattested_notation),
        "accepted": s.accepted,
        "proposal": s.proposal,
        "waiting_on": [{w.key[0]: w.key[1], "why": w.why} for w in s.waiting_on],
    }


def _says(row: dict[str, Any]) -> str:
    if row["subject"] is None:
        return "not in the library" if row["kind"] == "node" else "no lasting name: it has no label"
    lean = {
        "none": "not formalized",
        "rerun": "Lean changed or the text did since loom ran it; loom runs it again",
        "failed": "Lean did not accept it",
        "unattested": "Lean accepted it; the person has not attested it",
        "changed": "attested, and changed since",
        "waiting": "attested and accepted by Lean; a library result under it is not yet read, compared or attested",
        "formalized": "formalized",
    }[row["lean"]]
    accepted = {"fresh": "; accepted", "changed": "; accepted, and changed since"}.get(row["accepted"] or "", "")
    return lean + accepted
