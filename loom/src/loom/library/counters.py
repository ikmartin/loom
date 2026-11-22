"""Numbers a source's results would print, emulated from its counters, for a survey still `reading` (`library.survey`): shown in a work's outline until the source's compile gives the numbers it prints, and never written into a node.

Sectioning counters step and reset their descendants; a theorem counter shared with `[theorem]` follows the owning declaration's `[section]`-style reset; a theorem sharing a sectioning counter (`[subsection]`) steps it and prints as it; `\\newtheorem*` results have no number; `\\appendix` letters the section counter; `\\setcounter{section}{n}` sets where the next heading steps from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loom.scan.model import Taxon

#: The sectioning counters, by depth; a part numbers nothing below it.
LEVELS = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4, "subparagraph": 5}


@dataclass
class Numbering:
    """The counters of one pass through a source, stepped in the order its headings and results stand."""

    taxa: dict[str, Taxon]
    sec: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0])
    counters: dict[str, int] = field(default_factory=dict)
    appendix: bool = False

    def _counter(self, taxon: Taxon) -> str:
        return taxon.counter or taxon.env

    def _within(self, taxon: Taxon) -> str | None:
        owner = self.taxa.get(self._counter(taxon))
        return owner.within if owner is not None and owner.within else taxon.within

    def heading(self, name: str, starred: bool = False) -> str | None:
        """Step a sectioning counter and reset what numbers within it; the heading's number, None for a starred heading or a part."""
        level = LEVELS.get(name)
        if level is None or starred or name == "part":
            return None
        self.sec[level] += 1
        for deeper in range(level + 1, len(self.sec)):
            self.sec[deeper] = 0
        for t in self.taxa.values():
            w = self._within(t)
            if w is not None and LEVELS.get(w, 99) >= level:
                self.counters[self._counter(t)] = 0
        return self.number(level)

    def set_counter(self, name: str, value: int) -> None:
        """Follow `\\setcounter{section}{n}` and its kin: the next heading of that level steps from `value`."""
        level = LEVELS.get(name)
        if level is not None and name != "part":
            self.sec[level] = value

    def mark_appendix(self) -> None:
        """Follow `\\appendix`: sections start again, lettered."""
        self.appendix = True
        for deeper in range(1, len(self.sec)):
            self.sec[deeper] = 0

    def number(self, level: int) -> str:
        """The sectioning number down to `level`, an appendix's section lettered."""
        parts: list[str] = []
        for lv in range(1, level + 1):
            n = self.sec[lv]
            parts.append(chr(ord("A") + max(n, 1) - 1) if lv == 1 and self.appendix else str(n))
        return ".".join(parts)

    def theorem(self, taxon: Taxon) -> str | None:
        """Step the taxon's counter; the result's number, None for an unnumbered taxon."""
        if not taxon.numbered:
            return None
        c = self._counter(taxon)
        if c in LEVELS and c != "part":
            level = LEVELS[c]
            self.sec[level] += 1
            for deeper in range(level + 1, len(self.sec)):
                self.sec[deeper] = 0
            return self.number(level)
        self.counters[c] = self.counters.get(c, 0) + 1
        w = self._within(taxon)
        prefix = self.number(LEVELS[w]) if w in LEVELS else ""
        return f"{prefix}.{self.counters[c]}" if prefix else str(self.counters[c])
