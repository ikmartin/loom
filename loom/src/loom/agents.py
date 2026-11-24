"""Where an agent may write in a quilt: its own places, what is always protected, and the person's `[agents] deny` list.

One boundary, read two ways: `denied_by` is the predicate loom's own commands ask for every agent, and `claude_allows`/`claude_denies` render it into Claude Code's permission file, the one client whose file can refuse an edit by path. Inside `.loom/` loom's table alone decides; the list governs the rest of the quilt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from loom.paths import (
    ADOPTION_DECISIONS,
    AI,
    ANNOTATION_TYPES,
    ANNOTATIONS,
    CACHE,
    COPIES,
    EDITS,
    FORMAL,
    FORMAT,
    LEDGER,
    LIBRARY,
    LOCAL,
    LOOKED,
    LOOM,
    LOOM_GITIGNORE,
    RETIRED,
    REVIEW_DECISIONS,
    REVIEW_OBSERVATIONS,
    REVIEW_ORIGINS,
    SCRATCH,
    SESSION_INDEX,
    SESSIONS,
    SOURCE_SYNC,
)

if TYPE_CHECKING:
    from loom.scan.quilt import Quilt, QuiltConfig

CONFIG = "config.toml"
#: Where an agent always writes, whatever the list says: the sessions, its copies and its scratch.
AGENT_PLACES = (SESSIONS, COPIES, SCRATCH)
#: Files inside `.loom/` an agent may edit: the annotation types, which a quilt grows with its agents.
AGENT_FILES = (ANNOTATION_TYPES,)
#: Loom's directories under `.loom/`, each named, since a Claude Code deny of `.loom/` or of `.loom/records/` would beat the places' and the annotation types' allows; the history is the quilt's `[quilt] history` beside them.
LOOM_DIRS = (ANNOTATIONS, EDITS, RETIRED, LOOKED, FORMAL, LIBRARY, AI, LOCAL, CACHE)
#: Loom's files under `.loom/`, each named for the same reason.
LOOM_FILES = (
    FORMAT,
    LOOM_GITIGNORE,
    LEDGER,
    REVIEW_DECISIONS,
    REVIEW_ORIGINS,
    REVIEW_OBSERVATIONS,
    ADOPTION_DECISIONS,
    SOURCE_SYNC,
    SESSION_INDEX,
)


@dataclass(frozen=True)
class Pattern:
    """One `[agents] deny` entry: the text as written, and how it matches a quilt-relative path."""

    text: str
    body: str  # without the anchoring `/` and the trailing `/`
    anchored: bool  # matches from the root only
    directory: bool  # matches a directory, and so everything under it
    regex: re.Pattern[str]

    def matches(self, rel: str) -> bool:
        """Whether this entry denies the quilt-relative file `rel`: the file itself, or a directory it sits in."""
        return self.regex.match(rel) is not None


def _glob(body: str) -> str:
    """A gitignore glob as a regex: `*` and `?` stop at `/`, `**` crosses directories, `[...]` is a class, and a backslash takes the character after it as itself."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            out.append(re.escape(body[i + 1]))
            i += 2
        elif body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[" and (end := body.find("]", i + 2)) != -1:
            inner = body[i + 1 : end]
            out.append("[" + ("^" + inner[1:] if inner.startswith("!") else inner).replace("\\", "\\\\") + "]")
            i = end + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def compile_pattern(text: str) -> Pattern | str:
    """`text` as a `Pattern`, or why it is refused: negation (a Claude Code allow cannot undo a deny), `..`, an absolute path, or nothing to match."""
    raw = text.strip()
    if raw.startswith("!"):
        return f"{text!r} negates, which a deny list cannot: an agent's client lets a deny beat any allow"
    if raw.startswith(("//", "~")) or re.match(r"^[A-Za-z]:", raw):
        return f"{text!r} is not a path in the quilt"
    body = raw.strip("/")
    if not body:
        return f"{text!r} names nothing"
    if ".." in PurePosixPath(body).parts:
        return f"{text!r} leaves the quilt"
    directory = raw.endswith("/")
    anchored = raw.startswith("/") or "/" in body
    rest = r"/.+" if directory else r"(?:/.+)?"
    regex = re.compile(("^" if anchored else "^(?:.*/)?") + _glob(body) + rest + "$")
    return Pattern(raw, body, anchored, directory, regex)


def deny_list(entries: list[str]) -> tuple[list[Pattern], list[str]]:
    """(the patterns, the refusals) for `[agents] deny`'s entries, in order."""
    patterns: list[Pattern] = []
    refused: list[str] = []
    for entry in entries:
        got = compile_pattern(entry)
        if isinstance(got, Pattern):
            patterns.append(got)
        else:
            refused.append(got)
    return patterns, refused


def _under(rel: str, dirs: tuple[str, ...]) -> bool:
    return any(rel == d or rel.startswith(f"{d}/") for d in dirs)


def always_protected(config: QuiltConfig) -> list[str]:
    """What no agent writes whatever the list says, as the orientation names it: loom's directory but for the agent's places and the files it may edit, the history wherever it sits, the config and the research state."""
    out = [f"{LOOM}/ (but {', '.join([*(f'{p}/' for p in AGENT_PLACES), *AGENT_FILES])})"]
    if not _under(config.history, (LOOM,)):
        out.append(f"{config.history}/")
    return [*out, CONFIG, config.research_state]


def denied_by(config: QuiltConfig, rel: str) -> str | None:
    """What keeps an agent from writing the quilt-relative file `rel`: the protection or the list's entry, as the person reads it; None when the agent may write it."""
    rel = PurePosixPath(rel).as_posix()
    if rel == SESSION_INDEX:
        return rel
    if _under(rel, AGENT_PLACES) or rel in AGENT_FILES:
        return None
    if _under(rel, (LOOM,)):
        return f"{LOOM}/"
    if _under(rel, (config.history,)):
        return f"{config.history}/"
    if rel in (CONFIG, config.research_state):
        return rel
    return next((p.text for p in deny_list(config.agents_deny)[0] if p.matches(rel)), None)


def places_to_deny(config: QuiltConfig, paths: Iterable[str]) -> list[str]:
    """The `[agents] deny` entries that would protect each of the person's files `paths` (quilt-relative) nothing protects yet: a file's directory, or the file itself at the quilt's top, shallowest first, so one entry covering another's files leaves the second out; each anchored at the quilt's top (`/main/`) and escaped (`_literal`)."""
    import dataclasses

    added: list[str] = []
    for rel in sorted(set(paths), key=lambda r: (r.count("/"), r)):
        if denied_by(dataclasses.replace(config, agents_deny=[*config.agents_deny, *added]), rel) is not None:
            continue
        parent = PurePosixPath(rel).parent.as_posix()
        # anchored at the quilt's top and every glob character escaped, so the entry names that place and no other
        added.append(f"/{_literal(rel)}" if parent == "." else f"/{_literal(parent)}/")
    return added


def how_far_deny_holds(root: Path) -> str:
    """One sentence, in the person's words, of how far the places agents are denied hold for the apps the quilt at `root` is set up for (`ai.clients.chosen`): an app is refused an edit there only where the file loom wrote for it holds the list as it stands now (`ai.layout.holds_deny_now`), and every other app, any app loom does not know among them, is only asked not to, a change of theirs there going unlisted, since the look leaves the person's own places alone (`looks.watching`). '' where the quilt has no agent layer."""
    from loom.ai.clients import PROJECT, chosen
    from loom.ai.layout import holds_deny_now
    from loom.scan.quilt import load_quilt

    if not (root / AI).is_dir():
        return ""
    config = load_quilt(root).config
    keys = chosen(root, None)
    apps = [c for c in PROJECT if c.key in keys]
    held = [c.label for c in apps if holds_deny_now(root, config, c)]
    return deny_sentence(held, [c.label for c in apps if c.label not in held])


def deny_sentence(held: list[str], told: list[str]) -> str:
    """`how_far_deny_holds`'s sentence for the apps `held` to the deny by their file now and those only `told` it, by name, any other app among the told.

    A held app's file refuses its own edits there and no shell command but `rm` and loom's author verbs, so a command that writes there is left to the person's permission, which the sentence says.
    """

    def names(labels: list[str]) -> str:
        return labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"

    told = [*told, "any other app" if held or told else "any app"]
    one = len(told) == 1
    parts = []
    if held:
        parts.append(
            f"{names(held)} {'is' if len(held) == 1 else 'are'} refused an edit, though a shell command that writes there is left to your permission rather than refused"
        )
    parts.append(
        f"{names(told)} {'is' if one else 'are'} only asked not to edit, and a change {'it' if one else 'one of them'} makes there anyway is not listed in Your Changes"
    )
    return f"In the places agents are denied, {'; '.join(parts)}."


def _literal(path: str) -> str:
    """`path` as a deny pattern that matches it alone: each character a glob reads (`*`, `?`, `[`, `]`, a backslash) escaped."""
    return re.sub(r"([*?\[\]\\])", r"\\\1", path)


def deny_documents(quilt: Quilt, paths: Iterable[str]) -> list[str]:
    """Add to `[agents] deny` what `places_to_deny` gives for the person's files `paths`, as `loom import` and `loom init --from` do for the paper they bring in.

    The config is read as the act staging on this thread holds it, if one does, so a `main` set in the same act stands; the person's entries are kept as written, a refused one among them. The permission files are not written here: the caller writes them once its act is done (`write_denies`), since recovery never writes a file loom keeps for an agent app, and one written inside the act would leave that act, cut short, half made. Returns the entries added: none when everything is covered, or when the config is laid out in a way loom cannot edit (`ConfigRefused`).
    """
    import tomllib

    from loom.config_edit import ConfigRefused, set_values
    from loom.scan.quilt import QuiltConfig
    from loom.writes import staged

    path = quilt.root / CONFIG
    held, data = staged(path)
    text = data.decode("utf-8") if held and data is not None else path.read_text(encoding="utf-8")
    table = tomllib.loads(text).get("agents", {})
    written = table.get("deny", []) if isinstance(table, dict) else []
    added = places_to_deny(QuiltConfig.from_dict(tomllib.loads(text)), paths)
    if not added or not isinstance(written, list):
        return []
    try:
        set_values(quilt, {"agents.deny": [*written, *added]})
    except ConfigRefused:
        return []
    return added


def write_denies(root: Path) -> list[str]:
    """Write the quilt's permission files from its config as it stands, each in an act of its own, so an app reading one refuses an agent's own edit in the places `[agents] deny` names.

    Call it once the act that changed the list is done, never inside it: recovery never writes a file loom keeps for an agent app (`writes._judge`).

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    list of str
        The files written, quilt-relative: none where the quilt has no agent layer, where each was current, or where one cannot be written, which stays as it was and `loom lint` says lags.
    """
    if not (root / AI).is_dir():
        return []
    from loom.ai.layout import SHELL, variant, write_permissions
    from loom.scan.quilt import load_quilt
    from loom.writes import WriteRefused

    try:
        written, _ = write_permissions(root, load_quilt(root).config, shell=variant(root) == SHELL)
    except WriteRefused:
        return []
    return list(written)


def always_denied(config: QuiltConfig, why: str) -> bool:
    """Whether `denied_by`'s answer is a protection that holds whatever the list says, rather than one of the list's entries."""
    return why in (f"{LOOM}/", SESSION_INDEX, f"{config.history}/", CONFIG, config.research_state)


def refusal(config: QuiltConfig, rel: str) -> str | None:
    """Why an agent may not write the quilt-relative file `rel`, as a refusal says it; None when it may."""
    why = denied_by(config, rel)
    if why is None:
        return None
    if why == config.research_state:
        return f"an agent writes {why} only through `loom write`, which records the write"
    if why in (f"{LOOM}/", SESSION_INDEX, f"{config.history}/", CONFIG):
        places = ", ".join(f"{p}/" for p in AGENT_PLACES)
        return (
            f"{why} is loom's, and an agent writes only in {places} there"
            if why != CONFIG
            else f"{CONFIG} is the person's, and no agent writes it"
        )
    return f"the quilt protects it from agents ([agents] deny names {why} in {CONFIG})"


def claude_allows() -> list[str]:
    """The paths Claude Code lets an agent edit without asking: its places, relative to the quilt root it is started in (DR-343-ikmartin)."""
    return [f"{p}/**" for p in AGENT_PLACES] + list(AGENT_FILES)


def claude_denies(config: QuiltConfig) -> list[str]:
    """The paths Claude Code refuses an agent, anchored to the quilt root with `/`: loom's records named one by one, the history, the config, the research state, then the list."""
    dirs = [*LOOM_DIRS] + ([config.history] if config.history not in LOOM_DIRS else [])
    out = [f"/{d}/**" for d in dirs]
    out += [f"/{f}" for f in (*LOOM_FILES, CONFIG, config.research_state)]
    for p in deny_list(config.agents_deny)[0]:
        at = f"/{p.body}" if p.anchored else f"/**/{p.body}"
        # a pattern without a trailing `/` names a file or a directory, as in gitignore, so both are refused
        out += [f"{at}/**"] if p.directory else [at, f"{at}/**"]
    return out
