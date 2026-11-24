"""What a node's body says (docs/specs/nodes.md §4, §7, §8): the ids it points at and the anchors it defines, a reference's one BibTeX entry, and a macros node's items.

Every reading blanks comments first, so a reference commented out is not read. Nothing here judges what it finds; `checks` does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

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
    """One id or anchor a body names: the command (`ref`, `cite`, `label`, …), the argument exactly, and the 1-based line it is on; `via` the work's own command it was written through (`Wrapper`), if any."""

    command: str
    target: str
    line: int
    via: str = ""

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


@dataclass(frozen=True)
class Wrapper:
    """A command a work's macros define: each use of a referencing command, a citation or `\\label` its definition makes, directly or through the work's other commands (`command`, its argument with `#1`… where the wrapper's arguments go), none for a command that points at nothing; the number of its arguments; and the default of the first when it is optional."""

    uses: tuple[tuple[str, str], ...]
    count: int
    default: str | None = None


_DEFINITION = re.compile(r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)\*?(?![A-Za-z@])")
_DEF = re.compile(r"\\[gex]?def\s*(\\[A-Za-z@]+)((?:#[1-9])*)\s*(?=\{)")
_DOCUMENT_COMMAND = re.compile(r"\\(?:New|Renew|Provide|Declare)DocumentCommand(?![A-Za-z@])")
_LET = re.compile(r"\\let\s*(\\[A-Za-z@]+)\s*=?\s*(\\[A-Za-z@]+)")
#: The other definitions whose first argument is the name they define and whose text points at nothing.
_NAMES_ONLY = re.compile(
    r"\\(?:DeclareMathOperator|DeclarePairedDelimiter(?:X|XPP)?|DeclareMathSymbol|DeclareMathAccent|DeclareMathAlphabet|mathchardef|chardef)\*?(?![A-Za-z@])"
)
#: How many times a work's commands are followed through each other: enough for any real chain, and an end to one that grows as it is followed.
_ROUNDS = 8


@lru_cache(maxsize=64)
def wrappers(macros: str) -> dict[str, Wrapper]:
    """Every command a macros node's body defines, by name without the backslash, with what its definition points at or labels, followed through the work's other commands until nothing more is found: `\\newcommand{\\eq}[1]{(\\ref{#1})}` makes `\\eq{eq:bound}` point at `eq:bound`, and `\\newcommand{\\via}[1]{\\eq{#1}}` makes `\\via` do the same.

    Parameters
    ----------
    macros : str
        A macros node's body; '' for a work with none.

    Returns
    -------
    dict of str to Wrapper
        Read from `\\newcommand`, `\\renewcommand`, `\\providecommand`, `\\DeclareRobustCommand`, xparse's `\\NewDocumentCommand` and kin, `\\def` and its kin, and `\\let`, and named, with no uses, from the definitions that point at nothing (`\\DeclareMathOperator` and the like); a name `pointers` reads already is left out. Shared between calls: do not change it.
    """
    text = unread(macros)
    defined: dict[str, tuple[str, int, str | None]] = {}
    for m in _DEFINITION.finditer(text):
        name, pos = _defined_name(text, m.end())
        count, _s, _e, pos = read_optional(text, pos)
        default, _s, _e, pos = read_optional(text, pos)
        body, _s, _e, _n = read_mandatory(text, pos)
        n = int(count) if count is not None and count.strip().isdigit() else 0
        _define(defined, name, body, n, default if n else None)
    for m in _DOCUMENT_COMMAND.finditer(text):
        name, pos = _defined_name(text, m.end())
        spec, _s, _e, pos = read_mandatory(text, pos)
        body, _s, _e, _n = read_mandatory(text, pos)
        first = re.match(r"\s*O\{([^{}]*)\}", spec or "")
        taken = len(re.findall(r"[mo]", spec or "")) + (1 if first else 0)
        _define(defined, name, body, taken, first.group(1) if first else None)
    for m in _DEF.finditer(text):
        end = match_group(text, m.end())
        if end > 0:
            _define(defined, m.group(1), text[m.end() + 1 : end - 1], len(m.group(2)) // 2, None)
    lets: dict[str, str] = {}
    for m in _LET.finditer(text):
        # `\\let\\via\\ref` makes `\\via` the very command it names, one loom reads or one of the work's
        if m.group(2)[1:] in REFS | CITES:
            _define(defined, m.group(1), f"{m.group(2)}{{#1}}", 1, None)
        elif re.fullmatch(r"\\[A-Za-z@]+", m.group(1)) and m.group(1)[1:] not in REFS | CITES | {HYPERREF, "label"}:
            lets[m.group(1)[1:]] = m.group(2)[1:]
    for m in _NAMES_ONLY.finditer(text):
        name, _pos = _defined_name(text, m.end())
        _define(defined, name, "", 0, None)

    def follow(given: dict[str, Wrapper]) -> dict[str, Wrapper]:
        made = {name: Wrapper(_uses(body, given), count, default) for name, (body, count, default) in defined.items()}
        return made | {name: given.get(same, Wrapper((), 0)) for name, same in lets.items()}

    out = follow({})
    for _ in range(_ROUNDS):
        followed = follow(out)
        if followed == out:
            break
        out = followed
    return out


def _defined_name(text: str, pos: int) -> tuple[str, int]:
    """The name a definition makes, `{\\x}` or `\\x`, from `pos`, and where it ends."""
    p = skip_space(text, pos)
    if p < len(text) and text[p] == "{":
        end = match_group(text, p)
        return (text[p + 1 : end - 1].strip(), end) if end > 0 else ("", p)
    cs = _CS.match(text, p)
    return (cs.group(0), cs.end()) if cs else ("", p)


def _define(
    out: dict[str, tuple[str, int, str | None]], name: str, body: str | None, count: int, default: str | None
) -> None:
    """Add `name` to `out` with its definition; a name loom reads already, or none, is left out."""
    if body is None or not re.fullmatch(r"\\[A-Za-z@]+", name) or name[1:] in REFS | CITES | {HYPERREF, "label"}:
        return
    out[name[1:]] = (body, count, default)


def _uses(body: str, given: dict[str, Wrapper]) -> tuple[tuple[str, str], ...]:
    """What a definition's `body` points at or labels, plainly and through `given`, each once, in order."""
    found = [(p.command, p.target) for p in [*pointers(body), *labels(body), *wrapped(body, given)]]
    return tuple(dict.fromkeys(found))


def wrapped(body: str, given: dict[str, Wrapper]) -> list[Pointer]:
    """What a body points at, or labels, through its work's own commands (`wrappers`): each use in a wrapper's definition with the arguments the body gives in place of `#1`…, a list split at its commas as `pointers` splits one.

    Parameters
    ----------
    body : str
        A statement's or a proof's body.
    given : dict of str to Wrapper
        Its work's wrappers.

    Returns
    -------
    list of Pointer
        Each with `via` the wrapper's name; a `label` among them is a label the body defines through it.
    """
    pointing = [n for n, w in given.items() if w.uses]
    if not pointing:
        return []
    text = unread(body)
    out: list[Pointer] = []
    names = "|".join(sorted((re.escape(n) for n in pointing), key=len, reverse=True))
    for m in re.finditer(r"\\(" + names + r")(?![A-Za-z@])", text):
        w = given[m.group(1)]
        args: list[str] = []
        pos = m.end()
        for k in range(w.count):
            if k == 0 and w.default is not None:
                arg, _s, _e, pos = read_optional(text, pos)
                args.append(w.default if arg is None else arg)
            else:
                arg, _s, _e, pos = read_mandatory(text, pos)
                args.append(arg or "")
        line = text.count("\n", 0, m.start()) + 1
        for command, template in w.uses:
            target = _fill(template, args)
            names_ = target.split(",") if command in LISTS or command in CITES else [target]
            out.extend(Pointer(command, t.strip(), line, m.group(1)) for t in names_ if t.strip())
    return out


def _fill(template: str, args: list[str]) -> str:
    """A use's argument with the wrapper's arguments in place of `#1`…; one not given is empty."""
    return re.sub(r"#([1-9])", lambda g: args[int(g.group(1)) - 1] if int(g.group(1)) <= len(args) else "", template)


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
    """One thing at the top level of a macros body: the command, or `text` for words that are none, its 1-based line, and where it starts and ends in the body."""

    command: str
    line: int
    text: str = ""
    start: int = 0
    end: int = 0


#: What a macros node may hold (§8), each command with how its arguments are read after its name: `o` an optional `[...]`, `m` a mandatory group, `n` the name defined (a group or a control sequence), `p` a `\def`'s parameter text up to its body, `t` `\let`'s one token after an optional `=`, `c` a `\chardef`'s number after an optional `=`. A starred form is its command's; what `\AtBeginDocument` holds is checked item by item as the body is, and a conditional (`is_conditional`) is one item, allowed when each of its branches is. Package loads, definitions (of commands, environments, colours, counters, lengths, conditionals, cleveref's names and fonts' symbols), and the settings TikZ and pgfplots take in a preamble; nothing that typesets, and no setting of the page's layout (`\setlength`, `\setcounter`), which is the document's, not the work's.
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
    "DeclareMathAccent": "nmmm",
    "SetMathAlphabet": "nmmmmm",
    "DeclareFontFamily": "mmm",
    "DeclareFontShape": "mmmmmm",
    "DeclareUnicodeCharacter": "mm",
    "mathchardef": "nc",
    "chardef": "nc",
    "newtoks": "n",
    "newdimen": "n",
    "newskip": "n",
    "newcount": "n",
    "newcolumntype": "mom",
    "newtheoremstyle": "mmmmmmmmm",
    "allowdisplaybreaks": "o",
    "tikzcdset": "m",
    "SelectTips": "mm",
    "xymatrixcolsep": "m",
    "xymatrixrowsep": "m",
    "AtBeginDocument": "m",
}
_CS = re.compile(r"\\(?:[A-Za-z@]+|.)")
#: The arguments read after a command `ARGUMENTS` does not know: its star, then every bracket and brace group that follows.
_ANY = "*"

#: TeX's own conditionals, which `\fi` ends, by how their condition is read: '' none, `cs` one control sequence, `two` two tokens, `csname` a name up to `\endcsname`, `number` numbers or dimensions compared, of registers, digits, signs and units. Any other `\if…` followed by no group is read as a flag `\newif` makes, which has none; `\unless` before one reverses it.
TEX_CONDITIONALS = {
    "iftrue": "",
    "iffalse": "",
    "ifvmode": "",
    "ifhmode": "",
    "ifmmode": "",
    "ifinner": "",
    "ifdefined": "cs",
    "ifx": "two",
    "if": "two",
    "ifcat": "two",
    "ifcsname": "csname",
    "ifnum": "number",
    "ifdim": "number",
    "ifodd": "number",
    "ifcase": "number",
    "ifvoid": "number",
    "ifhbox": "number",
    "ifvbox": "number",
    "ifeof": "number",
}
#: The conditionals that take their branches as groups, each with how its arguments are read after its name: `m` a name holding no command, `n` a control sequence, `x` ifthen's test of booleans, `b` a branch.
GROUP_CONDITIONALS = {
    "@ifundefined": "mbb",
    "@ifdefinable": "nb",
    "@ifpackageloaded": "mbb",
    "@ifclassloaded": "mbb",
    "@ifpackagewith": "mmbb",
    "IfPackageLoadedTF": "mbb",
    "IfClassLoadedTF": "mbb",
    "ifdef": "nbb",
    "ifundef": "nbb",
    "ifdefmacro": "nbb",
    "ifdefempty": "nbb",
    "ifcsdef": "mbb",
    "ifcsundef": "mbb",
    "ifcsmacro": "mbb",
    "ifbool": "mbb",
    "iftoggle": "mbb",
    "ifthenelse": "xbb",
}
#: Named like a conditional, and none: the relation.
_NOT_CONDITIONALS = frozenset({"iff"})
#: The commands whose next control sequence is a name they define, never a conditional opened.
_NAMING = frozenset({"newif", "def", "gdef", "edef", "xdef", "let", "global"})
#: ifthen's tests a macros node's conditional may make: of booleans and of whether a command is defined.
_IFTHEN = re.compile(
    r"(?:\s|\\(?:boolean|isundefined)\s*\{\\?[A-Za-z@]+\}|\\(?:not|and|or|NOT|AND|OR)(?![A-Za-z@])|\\[()])*"
)
_NUMBER = re.compile(r"(?:\s|[0-9.,<>=+\-*/()\"'`]|[A-Za-z]+|\\[A-Za-z@]+(?![A-Za-z@]))*")


def is_conditional(command: str) -> bool:
    """Whether a macros body's item of `command` is a conditional, read whole (`conditional`): one of `TEX_CONDITIONALS` or `GROUP_CONDITIONALS`, or a flag's `\\if…`."""
    return (
        command in TEX_CONDITIONALS
        or command in GROUP_CONDITIONALS
        or (command.startswith("if") and command not in _NOT_CONDITIONALS)
    )


@dataclass(frozen=True)
class Conditional:
    """A conditional of a macros body read into its parts: `head`, its opener and condition as written; each branch's text; and between them and after the last the words TeX reads there (`\\else`, `\\or`, `\\fi`, or a group's braces)."""

    head: str
    branches: tuple[str, ...]
    joints: tuple[str, ...]
    tail: str
    #: What goes between the parts when they are put together again: a line break after a control word, nothing between braces.
    sep: str = ""

    def text(self, branches: tuple[str, ...] | list[str] | None = None) -> str:
        """The conditional with `branches` in place of its own, which default to them."""
        parts = [self.head]
        for i, branch in enumerate(self.branches if branches is None else branches):
            parts += [branch, self.joints[i] if i < len(self.joints) else self.tail]
        return self.sep.join(parts)


def conditional(body: str, item: Item) -> Conditional | None:
    """The parts of a conditional item of a macros body (`is_conditional`), or None when loom does not read it whole: a condition other than `TEX_CONDITIONALS` and `GROUP_CONDITIONALS` say, or no `\\fi` ending it.

    Parameters
    ----------
    body : str
        The macros body, or the part of it that holds `item`.
    item : Item
        What `macros_items` gave for the conditional.

    Returns
    -------
    Conditional or None
        Its head, branches, joints and tail, each as `body` writes them.
    """
    text = blank_comments(body)
    m = _CS.match(text, item.start)
    if m is None:
        return None
    if item.command in GROUP_CONDITIONALS:
        return _group_conditional(body, text, m.end(), item, GROUP_CONDITIONALS[item.command])
    pos = m.end()
    if m.group(0) == "\\unless":
        following = _CS.match(text, skip_space(text, pos))
        if following is None:
            return None
        pos = following.end()
    after = _condition(text, pos, TEX_CONDITIONALS.get(item.command, ""))
    block = _block(text, after) if after is not None else None
    if after is None or block is None or block[1] != item.end:
        return None
    joints, end = block
    cuts = [after, *(x for j in joints for x in j), end - len("\\fi")]
    branches = tuple(body[cuts[i] : cuts[i + 1]].strip() for i in range(0, len(cuts), 2))
    return Conditional(body[item.start : after].strip(), branches, tuple(body[a:b] for a, b in joints), "\\fi", "\n")


def _group_conditional(body: str, text: str, pos: int, item: Item, shape: str) -> Conditional | None:
    """A conditional taking its branches as groups, read as `shape` says from `pos`, after its name."""
    head = ""
    branches: list[str] = []
    for arg in shape:
        p = skip_space(text, pos)
        if arg == "n" and p < len(text) and text[p] != "{":
            cs = _CS.match(text, p)
            if cs is None:
                return None
            pos = cs.end()
            continue
        end = match_group(text, p) if p < len(text) and text[p] == "{" else -1
        if end < 0:
            return None
        inner = text[p + 1 : end - 1]
        if arg == "b":
            head = head or body[item.start : p + 1]
            branches.append(body[p + 1 : end - 1])
        elif arg == "m" and "\\" in inner:
            return None
        elif arg == "n" and not re.fullmatch(r"\s*\\(?:[A-Za-z@]+|.)\s*", inner):
            return None
        elif arg == "x" and _IFTHEN.fullmatch(inner) is None:
            return None
        pos = end
    if pos != item.end or not branches:
        return None
    return Conditional(head, tuple(branches), ("}{",) * (len(branches) - 1), "}")


def _opens(text: str, pos: int, name: str) -> bool:
    """Whether `\\name`, ending at `pos`, opens a conditional `\\fi` ends: one of TeX's own, or a flag's `\\if…` with no group after it, which a command taking groups would have."""
    if name in TEX_CONDITIONALS:
        return True
    if not name.startswith("if") or name in _NOT_CONDITIONALS or name in GROUP_CONDITIONALS:
        return False
    p = skip_space(text, pos)
    return not (p < len(text) and text[p] == "{")


def _block(text: str, pos: int) -> tuple[list[tuple[int, int]], int] | None:
    """From just after a conditional's opener, where each of its own `\\else` and `\\or` stands, and the offset after the `\\fi` ending it; None when none does. A group is passed over whole, so a conditional inside a definition is the definition's."""
    joints: list[tuple[int, int]] = []
    depth = 0
    i = pos
    while i < len(text):
        if text[i] == "{":
            end = match_group(text, i)
            if end < 0:
                return None
            i = end
            continue
        if text[i] != "\\":
            i += 1
            continue
        m = _CS.match(text, i)
        assert m is not None
        name = m.group(0)[1:]
        if name == "fi":
            if depth == 0:
                return joints, m.end()
            depth -= 1
        elif name in ("else", "or") and depth == 0:
            joints.append((i, m.end()))
        elif name in _NAMING and (named := _CS.match(text, skip_space(text, m.end()))):
            i = named.end()  # `\newif\ifdraft` names a conditional and opens none
            continue
        elif _opens(text, m.end(), name):
            depth += 1
        i = m.end()
    return None


def _condition(text: str, pos: int, kind: str) -> int | None:
    """Where a TeX conditional's condition of `kind` (`TEX_CONDITIONALS`) that starts at `pos` ends; None when it is not one loom reads."""
    if kind == "":
        return pos
    if kind in ("cs", "two"):
        for _ in range(1 if kind == "cs" else 2):
            p = skip_space(text, pos)
            token = _CS.match(text, p) if kind == "cs" else re.compile(r"\\(?:[A-Za-z@]+|.)|[^\s{}\\]").match(text, p)
            if token is None:
                return None
            pos = token.end()
        return pos
    if kind == "csname":
        m = re.compile(r"[A-Za-z@0-9 :._\-]*\\endcsname(?![A-Za-z@])").match(text, pos)
        return m.end() if m else None
    # numbers compared: registers, digits, signs and units, up to the first definition or the conditional's own words
    end = pos
    for m in re.finditer(r"\\[A-Za-z@]+|\S", text[pos:]):
        read = m.group(0)
        word = read[1:]
        if read.startswith("\\") and (word in ARGUMENTS or word in ("else", "or", "fi") or word.startswith("if")):
            break
        if read in ("{", "}", "[", "]"):
            return None
        end = pos + m.end()
    return end if _NUMBER.fullmatch(text[pos:end]) and text[pos:end].strip() else None


def macros_items(body: str) -> list[Item]:
    """What a macros body holds at its top level, in order: each command with its arguments read as `ARGUMENTS` says, and each run of anything else as `text`.

    A command `ARGUMENTS` does not know takes with it the groups that follow it, so `\\newtheorem{lemma}{Lemma}` is one item. A conditional `\\fi` ends is one item from its `\\if…` (or `\\unless`) to its `\\fi`, named by its `\\if…`; one taking its branches as groups is read as `GROUP_CONDITIONALS` says.
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
            out.append(Item("text", line, text[pos:stop].strip(), pos, stop))
            pos = stop
            continue
        start = pos
        name = m.group(0)[1:]
        pos = m.end()
        opener, after = name, pos
        if name == "unless" and (following := _CS.match(text, skip_space(text, pos))):
            opener, after = following.group(0)[1:], following.end()
        if _opens(text, after, opener) and (block := _block(text, after)) is not None:
            # a conditional `\fi` ends is one item, whatever its branches hold
            out.append(Item(opener, line, "", start, block[1]))
            pos = block[1]
            continue
        if pos < n and text[pos] == "*" and name in ARGUMENTS:
            pos += 1
        pos = _arguments(text, pos, ARGUMENTS.get(name) or GROUP_CONDITIONALS.get(name) or _ANY)
        out.append(Item(name, line, "", start, pos))


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
        elif arg in "mnbx":
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
        elif arg == "c":
            p = skip_space(text, pos)
            if p < len(text) and text[p] == "=":
                p = skip_space(text, p + 1)
            number = re.match(r"[\"'`]?[0-9A-Fa-f]+|\\[A-Za-z@]+|`\\?.", text[p:])
            pos = p + number.end() if number else p
    return pos
