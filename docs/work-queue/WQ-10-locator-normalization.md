# WQ-10 · Locator normalization beyond English

**Repo:** loom

## Trigger

A citation's locator in another language (`\cite[Satz 2.1]{…}`) that the postnote matcher (`loom/src/loom/scan/postnote.py`) does not match to the result it names, once something reads a citation's locator against a work's results; nothing calls the matcher yet.

## Why deferred

Results numbered by letters (`Theorem A` → `thm-A.20`) and by Roman numerals already match through the lowercase normalization of §8.7.1, and no fixture has produced a miss. The matcher is a table; the table grows when something falls out of it.

## Rough design

Extend the locator table with the abbreviations used in French, German, Italian and Russian mathematical writing (*Satz*, *Lemme*, *Proposizione*, and so on), mapping to the same display names the English abbreviations map to. A table entry, not a mechanism.

## Blast radius

The abbreviation table in `loom/src/loom/scan/postnote.py`, and a test of a locator in the new language.

## Related

DR-66, which built the matcher for digests, now deleted with them; `scan/postnote.py` keeps the matching.
