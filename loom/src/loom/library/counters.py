"""Numbers a source's results would print, emulated from its counters, for a survey still `reading` (`library.survey`): shown in a work's outline, and kept as printed only where a compile or the stored PDF agrees.

Sectioning counters step and reset what numbers within them, a chapter's sections numbered within it where the class has chapters; a theorem counter shared with `[theorem]` follows the owning declaration's `[section]`-style reset; a theorem sharing a sectioning counter (`[subsection]`) steps it and prints as it; `\\newtheorem*` results have no number; a heading deeper than `secnumdepth` (the class's, or one set by hand) steps nothing and prints no number; `\\appendix` letters the section counter, or the chapter counter where there are chapters. A source's own settings move it as TeX would: `\\numberwithin` and `\\counterwithin` / `\\counterwithout`, starred or not; `\\setcounter` and `\\addtocounter` of a sectioning or theorem counter; and `\\the<counter>` redefined, until its group closes, from `\\arabic`, `\\roman`, `\\Roman`, `\\alph`, `\\Alph`, other counters' `\\the`, a `\\ref` of a label loom has read (a restated result) and plain text, with font commands such as `\\textup` read through. Only what the source writes literally is followed, never a value it computes or reads, so what loom reads cannot carry a file the source read; a format loom cannot read leaves the counter with no reading at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from loom.scan.model import Taxon

#: The sectioning counters, by depth; a part numbers nothing below it.
LEVELS = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4, "subparagraph": 5}
#: The sectioning counter at each depth, as `\the<name>` names it.
NAMES = ("chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph")
#: Commands that set a number in a face or a box without changing what it says, read through in a format and in a printed number.
FACES = re.compile(
    r"\\(?:textup|textnormal|textrm|textbf|textit|textsl|textsf|textmd|emph|mbox|hbox|upshape|normalfont|rmfamily"
    r"|bfseries|mdseries|itshape|slshape|sffamily|relax|protect)(?![A-Za-z@])\s*"
)
_PIECE = re.compile(
    r"\\ref\s*\*?\s*\{\s*([^{}\s]+)\s*\}"
    r"|\\(arabic|roman|Roman|alph|Alph)\s*\{\s*([A-Za-z@]+)\s*\}"
    r"|\\@(arabic|roman|Roman|alph|Alph)\s*\\c@([A-Za-z@]+)"
    r"|\\the([A-Za-z@]+)"
    r"|([A-Za-z0-9.\-()/:])"
    r"|[{}\s]+"
)

#: One piece of a format: a counter's value in a style, another counter's `\the`, a label's reading (`ref`, as a restated result prints its original's number), or text.
Piece = tuple[str, str]


def _styled(style: str, n: int) -> str:
    """`n` as `\\arabic`, `\\roman`, `\\Roman`, `\\alph` or `\\Alph` prints it.

    A letter outside 1 to 26 and a roman numeral of 0 are empty, as TeX prints them: a theorem after `\\appendix` and before its first section reads `.2`.
    """
    if style == "arabic":
        return str(n)
    if style in ("alph", "Alph"):
        letter = chr(ord("a") + n - 1) if 1 <= n <= 26 else ""
        return letter.upper() if style == "Alph" else letter
    out, rest = "", n
    for value, numeral in (
        (1000, "m"),
        (900, "cm"),
        (500, "d"),
        (400, "cd"),
        (100, "c"),
        (90, "xc"),
        (50, "l"),
        (40, "xl"),
        (10, "x"),
        (9, "ix"),
        (5, "v"),
        (4, "iv"),
        (1, "i"),
    ):
        while rest >= value:
            out, rest = out + numeral, rest - value
    return out.upper() if style == "Roman" else out


def plain(printed: str) -> str:
    """A printed number with the font commands and braces a format set it in taken out: `\\textup {1}` reads `1`.

    Parameters
    ----------
    printed : str
        A number as a compile wrote it into an `.aux`.

    Returns
    -------
    str
        The number as the page shows it.
    """
    return FACES.sub("", printed).replace("{", "").replace("}", "").strip()


def _format_of(body: str) -> tuple[Piece, ...] | None:
    """The pieces of a `\\the<counter>` definition's `body`.

    None where any of it is something else, a macro or a value the source computes, so a format a source reads a file into has no reading.
    """
    pieces: list[Piece] = []
    body, at = FACES.sub("", body), 0
    while at < len(body):
        m = _PIECE.match(body, at)
        if m is None:
            return None
        if m.group(1):
            pieces.append(("ref", m.group(1)))
        elif m.group(2) or m.group(4):
            pieces.append((m.group(2) or m.group(4), m.group(3) or m.group(5)))
        elif m.group(6):
            pieces.append(("the", m.group(6)))
        elif m.group(7):
            pieces.append(("text", m.group(7)))
        at = m.end()
    return tuple(pieces)


@dataclass
class Numbering:
    """The counters of one pass through a source, stepped and set in the order its headings, results and settings stand.

    Parameters
    ----------
    taxa : dict[str, Taxon]
        The source's theorem-like environments, by name.
    chapters : bool, default False
        Whether the class numbers sections within chapters.
    depth : int, default 3
        `secnumdepth`: a heading deeper than it steps nothing and prints no number.
    sec : list[int]
        The sectioning counters' values, by depth.
    counters : dict[str, int]
        The theorem counters' values.
    parents : dict[str, str | None]
        The resets `\\numberwithin` and its kin set; None where `\\counterwithout` took one away.
    formats : dict[str, tuple[Piece, ...] | None]
        Each `\\the<counter>` as redefined; None where loom cannot read it.
    saved : dict[str, list[tuple[bool, tuple[Piece, ...] | None]]]
        Each counter's format before a definition still in force, whether there was one, put back by `close`.
    labels : dict[str, str]
        Each label met so far with loom's reading of what it numbers, which a `\\ref` in a format reads.
    """

    taxa: dict[str, Taxon]
    chapters: bool = False
    depth: int = 3
    sec: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])
    counters: dict[str, int] = field(default_factory=dict)
    parents: dict[str, str | None] = field(default_factory=dict)
    formats: dict[str, tuple[Piece, ...] | None] = field(default_factory=dict)
    saved: dict[str, list[tuple[bool, tuple[Piece, ...] | None]]] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    def _counter(self, taxon: Taxon) -> str:
        return taxon.counter or taxon.env

    def _theorems(self) -> set[str]:
        return {self._counter(t) for t in self.taxa.values()} - set(LEVELS)

    def _known(self, name: str) -> bool:
        """Whether `name` is a counter this numbering steps: a sectioning one or a theorem's."""
        return (name in LEVELS and name != "part") or name in self._theorems()

    def _declared(self, counter: str) -> str | None:
        """The counter a theorem counter's declaration numbers it within (`[section]`), which its default `\\the` prints before it."""
        owner = self.taxa.get(counter)
        return owner.within if owner is not None and owner.within else None

    def _parent(self, counter: str) -> str | None:
        """The counter whose step resets `counter`: the declaration's, unless `\\numberwithin` or its kin moved it."""
        return self.parents[counter] if counter in self.parents else self._declared(counter)

    def _reset_within(self, counter: str, seen: frozenset[str] = frozenset()) -> None:
        """Reset every theorem counter numbered within `counter`, and what numbers within those."""
        for c in self._theorems() - seen:
            if self._parent(c) == counter:
                self.counters[c] = 0
                self._reset_within(c, seen | {counter})

    def _step(self, level: int) -> None:
        self.sec[level] += 1
        for deeper in range(level + 1, len(self.sec)):
            self.sec[deeper] = 0
        for c in self._theorems():
            p = self._parent(c)
            if p in LEVELS and p != "part" and LEVELS[p] >= level:
                self.counters[c] = 0
                self._reset_within(c)

    def heading(self, name: str, starred: bool = False) -> str | None:
        """Step a sectioning counter and reset what numbers within it.

        Parameters
        ----------
        name : str
            The sectioning command, `section` say.
        starred : bool, default False
            Whether the heading is starred, and so steps nothing.

        Returns
        -------
        str or None
            The heading's number; None for a starred heading, a part, one deeper than `secnumdepth`, or a format loom cannot read.
        """
        level = LEVELS.get(name)
        if level is None or starred or name == "part" or level > self.depth:
            return None
        self._step(level)
        return self._the(name)

    def set_counter(self, name: str, value: int, *, add: bool = False) -> None:
        """Follow `\\setcounter{name}{value}`, or `\\addtocounter`, `secnumdepth` included; a counter this numbering does not step is left alone.

        Parameters
        ----------
        name : str
            The counter.
        value : int
            The literal integer the source wrote.
        add : bool, default False
            Whether it is `\\addtocounter`.
        """
        if name == "secnumdepth":
            self.depth = (self.depth if add else 0) + value
            return
        if not self._known(name):
            return
        now = (self._value(name) if add else 0) + value
        if name in LEVELS:
            self.sec[LEVELS[name]] = now
        else:
            self.counters[name] = now

    def within(
        self, counter: str, parent: str, *, style: str = "arabic", reset: bool = True, renumber: bool = True
    ) -> None:
        """Follow `\\numberwithin[\\style]{counter}{parent}`, `\\counterwithin` and `\\counterwithout`; a counter or parent this numbering does not step is left alone.

        Parameters
        ----------
        counter : str
            The theorem counter numbered within `parent`.
        parent : str
            The counter whose step resets it.
        style : str, default 'arabic'
            How the counter's own part prints, `\\numberwithin`'s optional argument.
        reset : bool, default True
            False for `\\counterwithout`, which takes the reset away.
        renumber : bool, default True
            False for a starred form, which moves the reset and leaves `\\the<counter>` as it was.
        """
        if not self._known(counter) or not self._known(parent) or counter in LEVELS:
            return
        self.parents[counter] = parent if reset else None
        if renumber:
            self.formats[counter] = (("the", parent), ("text", "."), (style, counter)) if reset else ((style, counter),)

    def define(self, counter: str, body: str) -> None:
        """Follow `\\renewcommand{\\the<counter>}{body}`; a counter this numbering does not step is left alone.

        Parameters
        ----------
        counter : str
            The counter whose `\\the` is defined.
        body : str
            The definition; the counter prints as it reads, or has no reading where loom cannot read it.
        """
        if self._known(counter):
            pieces = _format_of(body)
            readable = pieces is not None and all(kind in ("text", "ref") or self._known(arg) for kind, arg in pieces)
            self.saved.setdefault(counter, []).append((counter in self.formats, self.formats.get(counter)))
            self.formats[counter] = pieces if readable else None

    def close(self, counter: str) -> None:
        """Follow the end of the group a `\\the<counter>` definition stood in: the counter prints as it did before it.

        Parameters
        ----------
        counter : str
            The counter whose definition's group closed.
        """
        if self.saved.get(counter):
            was, pieces = self.saved[counter].pop()
            if was:
                self.formats[counter] = pieces
            else:
                self.formats.pop(counter, None)

    def mark_appendix(self) -> None:
        """Follow `\\appendix`: sections start again lettered, or chapters where there are chapters."""
        top = 0 if self.chapters else 1
        for level in range(top, len(self.sec)):
            self.sec[level] = 0
        self.formats[NAMES[top]] = (("Alph", NAMES[top]),)

    def _value(self, counter: str) -> int:
        return self.sec[LEVELS[counter]] if counter in LEVELS else self.counters.get(counter, 0)

    def _the(self, counter: str, depth: int = 0) -> str | None:
        """What `\\the<counter>` prints now; None where a format in it cannot be read."""
        if depth > 8:
            return None
        if counter in self.formats:
            pieces = self.formats[counter]
            if pieces is None:
                return None
            out: list[str] = []
            for kind, arg in pieces:
                if kind == "text":
                    out.append(arg)
                elif kind == "ref":
                    if arg not in self.labels:
                        return None
                    out.append(self.labels[arg])
                elif kind != "the":
                    out.append(_styled(kind, self._value(arg)))
                elif (got := self._the(arg, depth + 1)) is not None:
                    out.append(got)
                else:
                    return None
            return "".join(out)
        n = str(self._value(counter))
        if counter in LEVELS:
            level = LEVELS[counter]
            above = NAMES[level - 1] if level > 1 or (level == 1 and self.chapters) else None
        else:
            above = self._declared(counter)
        if above is None:
            return n
        head = self._the(above, depth + 1)
        return None if head is None else f"{head}.{n}"

    def theorem(self, taxon: Taxon) -> str | None:
        """Step the taxon's counter and reset what numbers within it.

        Parameters
        ----------
        taxon : Taxon
            The result's theorem-like environment.

        Returns
        -------
        str or None
            The result's number; None for an unnumbered taxon or a format loom cannot read.
        """
        if not taxon.numbered:
            return None
        c = self._counter(taxon)
        if c in LEVELS and c != "part":
            self._step(LEVELS[c])
            return self._the(c)
        self.counters[c] = self.counters.get(c, 0) + 1
        self._reset_within(c)
        return self._the(c)
