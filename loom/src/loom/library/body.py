"""What a node's body says (docs/specs/nodes.md §4, §7, §8): the ids it points at and the anchors it defines, a reference's one BibTeX entry, and a macros node's items.

Every reading blanks comments first, so a reference commented out is not read. Nothing here judges what it finds; `checks` does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loom.scan.edges import CITE_CMDS, REF_CMDS
from loom.scan.tokenize import match_group, read_mandatory, read_optional, skip_space

#: The citation commands whose keys are references' ids: the scanner's, with natbib's `citealp` and `citealt`.
CITES = frozenset(CITE_CMDS | {"citealp", "citealt", "Citep", "Citet"})
#: The referencing commands whose argument is an id or an anchor; `\cref` and `\Cref` take a list.
REFS = frozenset(REF_CMDS)
LISTS = frozenset({"cref", "Cref"})
_POINTER = re.compile(r"\\(" + "|".join(sorted(REFS | CITES, key=len, reverse=True)) + r")\*?(?![A-Za-z@])")
_LABEL = re.compile(r"\\label(?![A-Za-z@])")
_ENTRY = re.compile(r"@([A-Za-z]+)\s*([{(])")


@dataclass(frozen=True)
class Pointer:
    """One id or anchor a body names: the command (`ref`, `cite`, `label`, …), the argument exactly, and the 1-based line it is on."""

    command: str
    target: str
    line: int

    @property
    def cites(self) -> bool:
        return self.command in CITES


def blank_comments(text: str) -> str:
    """`text` with each comment, from an unescaped `%` to its line's end, made spaces of the same length, so offsets and lines still agree."""
    out: list[str] = []
    for line in text.split("\n"):
        i = 0
        while True:
            i = line.find("%", i)
            if i < 0:
                out.append(line)
                break
            slashes = len(line[:i]) - len(line[:i].rstrip("\\"))
            if slashes % 2 == 0:
                out.append(line[:i] + " " * (len(line) - i))
                break
            i += 1
    return "\n".join(out)


def pointers(body: str) -> list[Pointer]:
    """Every id or anchor the body points at by rules 1 to 3 of §4, in order: each argument of a referencing command and each key of a citation, a list split at its commas.

    Parameters
    ----------
    body : str
        A statement's or a proof's body.

    Returns
    -------
    list of Pointer
        One for each name, empty names left out.
    """
    text = blank_comments(body)
    out: list[Pointer] = []
    for m in _POINTER.finditer(text):
        cmd = m.group(1)
        pos = m.end()
        groups: list[str] = []
        if cmd in CITES:
            while True:
                for _ in range(2):
                    opt, _s, _e, nxt = read_optional(text, pos)
                    if opt is None:
                        break
                    pos = nxt
                p = skip_space(text, pos)
                if p >= len(text) or text[p] != "{":
                    break
                end = match_group(text, p)
                if end < 0:
                    break
                groups.append(text[p + 1 : end - 1])
                pos = end
                if cmd != "cites":
                    break
        else:
            arg, _s, _e, nxt = read_mandatory(text, pos)
            if arg is not None and not arg.startswith("\\"):
                groups.append(arg)
        line = text.count("\n", 0, m.start()) + 1
        for group in groups:
            names = group.split(",") if cmd in LISTS or cmd in CITES else [group]
            out.extend(Pointer(cmd, name.strip(), line) for name in names if name.strip())
    return out


def labels(body: str) -> list[Pointer]:
    """Every `\\label` of the body, in order, each argument exactly; by rule 4 of §4 each is an anchor of the node."""
    text = blank_comments(body)
    out: list[Pointer] = []
    for m in _LABEL.finditer(text):
        arg, _s, _e, _n = read_mandatory(text, m.end())
        if arg is not None:
            out.append(Pointer("label", arg.strip(), text.count("\n", 0, m.start()) + 1))
    return out


@dataclass(frozen=True)
class Entry:
    """A reference's body read as one BibTeX entry: its type and key, and what stands outside it, which should be nothing."""

    type: str
    key: str
    outside: str


def entry_of(body: str) -> Entry | None:
    """The BibTeX entry a reference's body begins with, or None when it begins with none.

    Parameters
    ----------
    body : str
        A reference's body.

    Returns
    -------
    Entry or None
        The entry's type in lower case, its key (empty when it has none), and the text after it, stripped; None when the body, stripped, does not begin with `@type{` or `@type(` closed in balance.
    """
    text = body.strip()
    m = _ENTRY.match(text)
    if m is None:
        return None
    opening = m.group(2)
    end = match_group(text, m.end() - 1, opening, "}" if opening == "{" else ")")
    if end < 0:
        return None
    key = re.match(r"\s*([^,\s{}()=\"#%']+)\s*,", text[m.end() : end - 1])
    return Entry(m.group(1).lower(), key.group(1) if key else "", text[end:].strip())


@dataclass(frozen=True)
class Item:
    """One thing at the top level of a macros body: the command, or `text` for words that are none, and its 1-based line."""

    command: str
    line: int
    text: str = ""


#: What a macros node may hold (§8), each command with how its arguments are read after its name: `o` an optional `[...]`, `m` a mandatory group, `n` the name defined (a group or a control sequence), `p` a `\def`'s parameter text up to its body, `t` `\let`'s one token after an optional `=`. A starred form is its command's. Package loads, definitions, and the settings TikZ and pgfplots take in a preamble; nothing that typesets.
ARGUMENTS = {
    "usepackage": "oom",
    "RequirePackage": "oom",
    "newcommand": "noom",
    "renewcommand": "noom",
    "providecommand": "noom",
    "DeclareRobustCommand": "noom",
    "DeclareMathOperator": "nm",
    "DeclarePairedDelimiter": "nmm",
    "DeclarePairedDelimiterX": "nommm",
    "DeclarePairedDelimiterXPP": "nommmmm",
    "NewDocumentCommand": "nmm",
    "RenewDocumentCommand": "nmm",
    "ProvideDocumentCommand": "nmm",
    "DeclareDocumentCommand": "nmm",
    "newenvironment": "moomm",
    "renewenvironment": "moomm",
    "def": "npm",
    "gdef": "npm",
    "edef": "npm",
    "xdef": "npm",
    "let": "nt",
    "makeatletter": "",
    "makeatother": "",
    "usetikzlibrary": "m",
    "tikzset": "m",
    "pgfplotsset": "m",
}
_CS = re.compile(r"\\(?:[A-Za-z@]+|.)")
#: The arguments read after a command `ARGUMENTS` does not know: its star, then every bracket and brace group that follows.
_ANY = "*"


def macros_items(body: str) -> list[Item]:
    """What a macros body holds at its top level, in order: each command with its arguments read as `ARGUMENTS` says, and each run of anything else as `text`.

    A command `ARGUMENTS` does not know takes with it the groups that follow it, so `\\newtheorem{lemma}{Lemma}` is one item.
    """
    text = blank_comments(body)
    out: list[Item] = []
    pos = 0
    n = len(text)
    while True:
        pos = skip_space(text, pos)
        if pos >= n:
            return out
        line = text.count("\n", 0, pos) + 1
        m = _CS.match(text, pos)
        if m is None:
            stop = text.find("\\", pos + 1)
            stop = n if stop < 0 else stop
            out.append(Item("text", line, text[pos:stop].strip()))
            pos = stop
            continue
        name = m.group(0)[1:]
        pos = m.end()
        if pos < n and text[pos] == "*" and name in ARGUMENTS:
            pos += 1
        out.append(Item(name, line))
        pos = _arguments(text, pos, ARGUMENTS.get(name) or _ANY)


def _arguments(text: str, pos: int, shape: str) -> int:
    """The offset after the arguments `shape` reads from `pos`; an argument that is not there ends the reading where it stands."""
    if shape == _ANY:
        while True:
            p = skip_space(text, pos)
            if p < len(text) and text[p] == "*":
                pos = p + 1
                continue
            if p < len(text) and text[p] in "[{":
                end = match_group(text, p, text[p], "]" if text[p] == "[" else "}")
                if end < 0:
                    return len(text)
                pos = end
                continue
            return pos
    for arg in shape:
        if arg == "o":
            _o, _s, _e, pos = read_optional(text, pos)
        elif arg in "mn":
            p = skip_space(text, pos)
            if p < len(text) and text[p] == "{":
                end = match_group(text, p)
                if end < 0:
                    return len(text)
                pos = end
            elif arg == "n" and (cs := _CS.match(text, p)):
                pos = cs.end()
            else:
                return pos
        elif arg == "p":
            brace = text.find("{", pos)
            if brace < 0:
                return len(text)
            pos = brace
        elif arg == "t":
            p = skip_space(text, pos)
            if p < len(text) and text[p] == "=":
                p = skip_space(text, p + 1)
            cs = _CS.match(text, p)
            pos = cs.end() if cs else min(p + 1, len(text))
    return pos
