"""What a node's body says (docs/specs/nodes.md §4, §7, §8): the ids it points at and the anchors it defines, a reference's one BibTeX entry, and a macros node's items.

Every reading blanks comments first, so a reference commented out is not read. Nothing here judges what it finds; `checks` does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loom.scan.edges import CITE_CMDS
from loom.scan.tokenize import match_group, read_mandatory, read_optional, skip_space

#: The referencing commands whose one argument is an id or an anchor.
SINGLE = frozenset(
    {"ref", "eqref", "autoref", "pageref", "vref", "Vref", "vpageref", "fullref", "nameref", "Nameref", "autopageref"}
)
#: cleveref's commands, whose argument is a list of them.
LISTS = frozenset(
    {
        "cref",
        "Cref",
        "cpageref",
        "Cpageref",
        "labelcref",
        "labelcpageref",
        "namecref",
        "nameCref",
        "lcnamecref",
        "namecrefs",
        "nameCrefs",
        "lcnamecrefs",
    }
)
#: The commands whose two arguments are each one, the ends of a range.
RANGES = frozenset({"crefrange", "Crefrange", "cpagerefrange", "Cpagerefrange", "vrefrange", "vpagerefrange"})
#: Every referencing command whose mandatory arguments are ids or anchors; `\hyperref[...]` takes its one in brackets.
REFS = SINGLE | LISTS | RANGES
HYPERREF = "hyperref"
#: biblatex's commands that cite several groups of keys, each with its own notes, after up to two notes in parentheses for the whole.
MULTICITES = frozenset(
    {
        "cites",
        "Cites",
        "parencites",
        "Parencites",
        "textcites",
        "Textcites",
        "autocites",
        "Autocites",
        "footcites",
        "footcitetexts",
        "smartcites",
        "Smartcites",
        "supercites",
    }
)
#: The citation commands whose keys are references' ids: natbib's, biblatex's and LaTeX's own.
CITES = frozenset(
    CITE_CMDS
    | MULTICITES
    | {"citealp", "citealt", "Citealp", "Citealt", "Citep", "Citet", "Citeauthor", "citeyearpar", "citenum", "citetext", "nocite"}
    | {"Autocite", "footcitetext", "smartcite", "Smartcite", "supercite", "fullcite", "footfullcite", "citetitle", "Citetitle", "citedate", "citeurl"}
)  # fmt: skip
#: A command named like one that points at a node but read by none of the lists above: refused, so a new one is a list to widen and never a pointer that passes unread. `\href` points at a URL.
_SHAPED = re.compile(r"\\([A-Za-z]*[Rr]ef(?:s|range)?|[A-Za-z]*[Cc]ite[A-Za-z]*)(?![A-Za-z@])")
_NOT_POINTERS = frozenset({"href"})
_POINTER = re.compile(
    r"\\(" + "|".join(sorted(REFS | CITES | {HYPERREF}, key=len, reverse=True)) + r")\*?(?![A-Za-z@])"
)
_LABEL = re.compile(r"\\label(?![A-Za-z@])")
_ENTRY = re.compile(r"@([A-Za-z]+)\s*([{(])")
#: Text LaTeX prints as it stands, in which nothing points: `\verb` with its delimiter, and the verbatim environments.
_VERBATIM = re.compile(
    r"\\verb\*?([^A-Za-z\s*])(?:(?!\1).)*?\1|\\begin\{(verbatim|Verbatim|lstlisting|minted|comment)(\*?)\}.*?\\end\{\2\3\}",
    re.S,
)


@dataclass(frozen=True)
class Pointer:
    """One id or anchor a body names: the command (`ref`, `cite`, `label`, …), the argument exactly, and the 1-based line it is on."""

    command: str
    target: str
    line: int

    @property
    def cites(self) -> bool:
        return self.command in CITES


def unread(text: str) -> str:
    """`text` with what is never read as pointing blanked, offsets and lines kept: comments, then verbatim text."""
    return _VERBATIM.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), blank_comments(text))


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
        One for each name, empty names left out; an argument that is a command (`\\ref\\x`) is kept as it is, for the checks to refuse.
    """
    text = unread(body)
    out: list[Pointer] = []
    for m in _POINTER.finditer(text):
        cmd = m.group(1)
        groups: list[str] = []
        if cmd == HYPERREF:
            arg, _s, _e, _n = read_optional(text, m.end())
            groups += [arg] if arg is not None else []
        elif cmd in CITES:
            groups = _cited(text, m.end(), cmd in MULTICITES)
        else:
            pos = m.end()
            for _ in range(2 if cmd in RANGES else 1):
                arg, _s, _e, pos = read_mandatory(text, pos)
                if arg is None:
                    break
                groups.append(arg)
        line = text.count("\n", 0, m.start()) + 1
        for group in groups:
            names = group.split(",") if cmd in LISTS or cmd in CITES else [group]
            out.extend(Pointer(cmd, name.strip(), line) for name in names if name.strip())
    return out


def _cited(text: str, pos: int, multi: bool) -> list[str]:
    """The key groups of a citation whose name ends at `pos`: one, after up to two notes in brackets; or for a multicite, after up to two in parentheses, as many as follow."""
    groups: list[str] = []
    if multi:
        for _ in range(2):
            p = skip_space(text, pos)
            end = match_group(text, p, "(", ")") if p < len(text) and text[p] == "(" else -1
            if end < 0:
                break
            pos = end
    while True:
        for _ in range(2):
            opt, _s, _e, nxt = read_optional(text, pos)
            if opt is None:
                break
            pos = nxt
        p = skip_space(text, pos)
        end = match_group(text, p) if p < len(text) and text[p] == "{" else -1
        if end < 0:
            return groups
        groups.append(text[p + 1 : end - 1])
        pos = end
        if not multi:
            return groups


def unknown(body: str) -> list[Pointer]:
    """Each command of the body named as a pointer is (ending in `ref`, `refs` or `refrange`, or holding `cite`, either case of their first letter) that `pointers` does not read; check 8 refuses them, so a new command is never a pointer that passes unread."""
    text = unread(body)
    known = REFS | CITES | {HYPERREF} | _NOT_POINTERS
    return [
        Pointer(m.group(1), "", text.count("\n", 0, m.start()) + 1)
        for m in _SHAPED.finditer(text)
        if m.group(1) not in known
    ]


def labels(body: str) -> list[Pointer]:
    """Every `\\label` of the body, in order, each argument exactly, past cleveref's optional `[type]`; by rule 4 of §4 each is an anchor of the node."""
    text = unread(body)
    out: list[Pointer] = []
    for m in _LABEL.finditer(text):
        _o, _s, _e, pos = read_optional(text, m.end())
        arg, _s, _e, _n = read_mandatory(text, pos)
        if arg is not None:
            out.append(Pointer("label", arg.strip(), text.count("\n", 0, m.start()) + 1))
    return out


@dataclass(frozen=True)
class Entry:
    """A reference's body read as one BibTeX entry: its type and key, and what stands outside it, which should be nothing."""

    type: str
    key: str
    outside: str
    #: Abbreviations its fields use unexpanded, months apart.
    bare: tuple[str, ...] = ()


def entry_of(body: str) -> Entry | None:
    """The BibTeX entry a reference's body begins with, or None when it begins with none.

    Parameters
    ----------
    body : str
        A reference's body.

    Returns
    -------
    Entry or None
        The entry's type in lower case, its key (empty when it has none), the text after it, stripped, and the abbreviations its fields use; None when the body, stripped, does not begin with `@type{` or `@type(` closed in balance.
    """
    text = body.strip()
    m = _ENTRY.match(text)
    if m is None:
        return None
    opening = m.group(2)
    end = match_group(text, m.end() - 1, opening, "}" if opening == "{" else ")")
    if end < 0:
        return None
    inside = text[m.end() : end - 1]
    key = re.match(r"\s*([^,\s{}()=\"#%']+)\s*(?:,|$)", inside)
    bare = _bare_words(inside[key.end() :]) if key else ()
    return Entry(m.group(1).lower(), key.group(1) if key else "", text[end:].strip(), bare)


#: The abbreviations BibTeX's styles define, which an entry may use unexpanded.
MONTHS = frozenset({"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"})
_FIELD = re.compile(r"[\s,]*([A-Za-z][\w\-:.+]*)\s*=\s*")


def _bare_words(fields: str) -> tuple[str, ...]:
    """The abbreviations an entry's fields use, each bare word of a value that is no number and no month, in order; reading stops where the fields stop reading as `name = value # value …`."""
    out: list[str] = []
    pos = 0
    while (m := _FIELD.match(fields, pos)) is not None:
        pos = m.end()
        while True:
            p = skip_space(fields, pos)
            if p < len(fields) and fields[p] in '{"':
                end = match_group(fields, p) if fields[p] == "{" else _quoted(fields, p)
                if end < 0:
                    return tuple(out)
            elif word := re.match(r"[^\s,#{}\"=]+", fields[p:]):
                end = p + word.end()
                if not word.group(0).isdigit() and word.group(0).lower() not in MONTHS:
                    out.append(word.group(0))
            else:
                return tuple(out)
            pos = skip_space(fields, end)
            if pos < len(fields) and fields[pos] == "#":
                pos += 1
                continue
            break
    return tuple(out)


def _quoted(text: str, pos: int) -> int:
    """The offset after the `"` that closes the string opening at `pos`, braces inside it kept whole; -1 when none does."""
    depth = 0
    for i in range(pos + 1, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == '"' and depth == 0 and text[i - 1] != "\\":
            return i + 1
    return -1


@dataclass(frozen=True)
class Item:
    """One thing at the top level of a macros body: the command, or `text` for words that are none, and its 1-based line."""

    command: str
    line: int
    text: str = ""


#: What a macros node may hold (§8), each command with how its arguments are read after its name: `o` an optional `[...]`, `m` a mandatory group, `n` the name defined (a group or a control sequence), `p` a `\def`'s parameter text up to its body, `t` `\let`'s one token after an optional `=`. A starred form is its command's. Package loads, definitions (of commands, environments, colours, counters, lengths, conditionals, cleveref's names and fonts' symbols), and the settings TikZ and pgfplots take in a preamble; nothing that typesets, and no setting of the page's layout (`\setlength`, `\setcounter`), which is the document's, not the work's.
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
    "PassOptionsToPackage": "mm",
    "definecolor": "ommm",
    "colorlet": "omm",
    "numberwithin": "omm",
    "newcounter": "mo",
    "newlength": "n",
    "newif": "n",
    "crefname": "mmm",
    "Crefname": "mmm",
    "DeclareMathAlphabet": "nmmmm",
    "DeclareSymbolFont": "mmmmm",
    "DeclareMathSymbol": "nmmm",
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
