# WQ-71 · Wikilinks between Markdown notes

**Repo:** loom, arras

## Trigger

A quilt holds Markdown notes that link each other with `[[Note name]]`, as Obsidian, Logseq, Foam and Zettlr write them.

## Why deferred

Notes as files link to the quilt with `quilt:` links and to each other by path or by an editor's own ids. No one using loom writes wikilinks yet, and resolving them by name means choosing among notes of one name.

## Rough design

In a shown Markdown file, `[[Name]]`, `[[Name|text]]` and `[[Name#Heading]]` resolve to the shown Markdown file of that name, the nearest by path when two share it, and are drawn and indexed as the `quilt:` link to it; one that names nothing is a broken link in Problems. `![[Name]]` embeds are left as text.

## Blast radius

The Markdown dialect (`docs/specs/dialect.md`), the link resolver (`loom/src/loom/links.py`, `arras/src/lib/workspace/links.ts`), the link index.

## Related

WQ-70 (a renderer hook for other formats).
