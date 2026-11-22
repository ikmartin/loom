"""Who is acting: the markers an agent's shell carries, the name a writer declares, and the refusals that keep the author's acts the author's."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from loom.errors import EnvError

#: Environment variables an agent's shell carries. `AI_AGENT` is the generic one; the rest name a particular tool.
#: Loom reads them to refuse what an agent may not do (the author's verbs, a protected path, a write signed with a name that does not say it is an agent's), and to tell whose act a command run in that shell is (`agents_act`), never to change what any other command does.
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


#: Set while a thread serves the viewer's request (`at_the_viewer`): a write over HTTP is a person at a browser, whatever shell started the server.
_AT_VIEWER: ContextVar[bool] = ContextVar("loom_at_the_viewer", default=False)


@contextmanager
def at_the_viewer() -> Iterator[None]:
    """Mark what this thread does as a request from the viewer, a person at a browser, for `agents_act`: the server's own shell, an agent's terminal perhaps, says nothing about who asked."""
    token = _AT_VIEWER.set(True)
    try:
        yield
    finally:
        _AT_VIEWER.reset(token)


def agents_act(actor: str | None) -> bool:
    """Whether an act was an agent's: one made under a name that says so; never one the viewer asked for (`at_the_viewer`); else one made in a shell an agent runs (`agent_marker`), since a command there names the author by default (`history.ledger.actor_for`)."""
    if actor and is_agent(actor):
        return True
    if _AT_VIEWER.get():
        return False
    return agent_marker() is not None


def agent_name() -> str | None:
    """What the agent running this shell is called, or None when a person is."""
    import os

    return next((name for marker, name in AGENT_NAMES.items() if os.environ.get(marker)), None)


def name_yourself() -> str:
    """How a refusal tells the agent running this shell to sign: the name its app goes by where a marker says, else an example."""
    named = agent_name()
    example = named if named and named != AGENT_NAMES["AI_AGENT"] else "Referee Agent"
    return f'Name yourself with --as, a name ending in Agent, so the record says what wrote it: --as "{example}".'


#: The last word of every name loom gives an agent (`AGENT_NAMES`, `ai.clients.Client.agent`), and so of the name an agent signs with.
AGENT_WORD = "agent"


def is_agent(name: str) -> bool:
    """Whether a declared identity is an agent's: one formed as loom forms the names it gives the agents it sets up (`AGENT_NAMES`, `ai.clients.Client.agent`), its last word `Agent`, however punctuated, `Referee (Agent)` as the showcase writes it included.

    A word elsewhere in a name says nothing of whose it is: `Ai Tanaka` is a person, and so is `Claude (AI)`.
    """
    import re

    words = re.findall(r"[a-z0-9]+", name.lower())
    return bool(words) and words[-1] == AGENT_WORD


def writer(root: Path, declared: str | None) -> tuple[str, str]:
    """(name, kind) for whoever is writing, from what they declared; under an agent marker the declaration must say it is an agent's (`signed`).

    Parameters
    ----------
    root : Path
        The quilt.
    declared : str, optional
        What `--as` said. An agent's name ends in `Agent`.

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
