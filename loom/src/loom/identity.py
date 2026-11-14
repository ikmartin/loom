"""Who is acting: the markers an agent's shell carries, the name a writer declares, and the refusals that keep the author's acts the author's."""

from __future__ import annotations

from pathlib import Path

from loom.errors import EnvError

#: Environment variables an agent's shell carries. `AI_AGENT` is the generic one; the rest name a particular tool.
#: Loom reads them only to refuse what an agent may not do (the author's verbs, a protected path, a write signed with a name that does not say it is an agent's), never to change what any other command does.
AGENT_MARKERS = ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX", "CURSOR_AGENT", "GEMINI_CLI")


def agent_marker() -> str | None:
    """The marker variable set in this environment, or None when no agent is running the shell."""
    import os

    return next((v for v in AGENT_MARKERS if os.environ.get(v)), None)


#: What to call an agent by the marker its app sets, the same name the app's MCP server gives it (`Client.agent`), the particular marker before the generic `AI_AGENT`, which apps set beside their own. A record that says "Claude Code Agent" is auditable; one that says the author's git name because the agent's shell inherited it is not, which is what DR-185 found.
AGENT_NAMES = {
    "CLAUDECODE": "Claude Code Agent",
    "CLAUDE_CODE_ENTRYPOINT": "Claude Code Agent",
    "CODEX_SANDBOX": "Codex Agent",
    "CURSOR_AGENT": "Cursor Agent",
    "GEMINI_CLI": "Gemini CLI Agent",
    "AI_AGENT": "agent",
}


def agent_name() -> str | None:
    """What the agent running this shell is called, or None when a person is."""
    import os

    return next((name for marker, name in AGENT_NAMES.items() if os.environ.get(marker)), None)


def name_yourself() -> str:
    """How a refusal tells the agent running this shell to sign: the name its app goes by where a marker says, else an example."""
    named = agent_name()
    example = named if named and named != AGENT_NAMES["AI_AGENT"] else "Referee Agent"
    return f'Name yourself with --as, including Agent or AI in the name, so the record says what wrote it: --as "{example}".'


#: What makes a declared name an agent's. An agent is instructed to include one when it names itself, so that a record
#: says what wrote it without loom having to guess from the environment it happened to run in.
AGENT_WORDS = ("agent", "ai", "bot", "assistant")


def is_agent(name: str) -> bool:
    """Whether a declared identity is an agent's, by the word it was asked to include in its own name.

    The words are matched however they are punctuated, because the form loom's own documents ask for is `Referee (Agent)` and the showcase writes exactly that. Splitting on whitespace and hyphens made `(agent)` a different word from `agent`, so the name the orientation teaches was read as a person's: the session picker showed a parked agent as `⟨person⟩`, and `refuse_under_agent` let that name run `loom accept` and `loom library verify`. Found by the reading study, 2026-09-21.
    """
    import re

    return any(w in re.findall(r"[a-z0-9]+", name.lower()) for w in AGENT_WORDS)


def writer(root: Path, declared: str | None) -> tuple[str, str]:
    """(name, kind) for whoever is writing, from what they declared; under an agent marker the declaration must say it is an agent's (`signed`).

    Parameters
    ----------
    root : Path
        The quilt.
    declared : str, optional
        What `--as` said. An agent names itself, with `Agent` or `AI` in the name.

    Returns
    -------
    tuple of (str, str)
        The name, and `agent` or `person`.
    """
    said = signed(declared)
    if said:
        return said, "agent" if is_agent(said) else "person"
    return whoever(root), "person"


def signed(declared: str | None) -> str:
    """What `--as` said, stripped, or a refusal when an agent is running the shell and it names nobody or does not say it is an agent.

    A name cannot be checked, so under a marker it may only say what the marker already does: an agent that signs `Claude` or the author's name would otherwise be recorded as a person, and `loom since` would hand its words back as the person's. A shell with a marker is not the author's to sign in, here as for the author's acts (`refuse_under_agent`); the viewer and a terminal of their own are. Without a marker a declared name is taken at its word, since nothing says otherwise. Every command that records a declared name comes through here.
    """
    said = (declared or "").strip()
    marker = agent_marker()
    if marker and not said:
        raise EnvError(
            f"an agent is running this shell ({marker} is set) and has not said who it is.\n{name_yourself()}"
        )
    if marker and not is_agent(said):
        raise EnvError(
            f"an agent is running this shell ({marker} is set), and {said} does not say it is an agent.\n"
            f"{name_yourself()} A person writes in the viewer or a terminal of their own."
        )
    return said


def whoever(root: Path, author: str | None = None, *, sniff: bool = True) -> str:
    """Who is running this, for a record that wants provenance and must not refuse for want of it.

    Opening, retitling or closing a session is not an authored claim about anybody's mathematics, so an unconfigured author name costs the record a name and never the command; a name that is declared is held to `signed` like any other. The verbs that *are* claims -- `accept`, `library verify`, a comment -- keep asking. `sniff=False` is the write API's: a write over HTTP is somebody at a browser, and the shell `loom serve` was started in says nothing about them.
    """
    from loom.scan.quilt import NoAuthorError, resolve_author

    if (author or "").strip():
        return signed(author) if sniff else str(author).strip()
    robot = agent_name() if sniff else None
    if robot:
        return robot
    try:
        return resolve_author(None, root)[0]
    except NoAuthorError:
        return ""


def refuse_under_agent(verb: str, how: str, declared: str | None = None) -> None:
    """Refuse one of the author's acts when an agent could be the one performing it.

    The claim these acts make -- *I checked this*, *I accept this mathematics*, *erase this* -- is the author's, and a record that credits the author with a check nobody made is worse than no record. A declared name that calls itself an agent is refused wherever it came from; and under an agent marker the act is refused **whatever name is declared**, because a name cannot be checked and an agent that types the author's name is exactly the case to stop (DR-325-ikmartin). The author runs these in a shell of their own.
    """
    if declared and is_agent(declared):
        raise EnvError(f"{verb} is the author's, and {declared} is an agent.\n{how}")
    marker = agent_marker()
    if marker:
        named = f", whatever --as says ({declared})" if declared else ""
        raise EnvError(
            f"{verb} is the author's, and an agent is running this shell ({marker} is set){named}; run it in a terminal of your own.\n{how}"
        )
