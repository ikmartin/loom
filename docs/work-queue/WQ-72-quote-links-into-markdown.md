# WQ-72 · Quote links into Markdown files

**Repo:** loom, viewer

## Trigger

T033 of the v0.1 task list (annotations and suggested edits on Markdown) has landed, so the viewer can find quoted words in a Markdown page.

## Why deferred

A note's `quilt:` link carries the quoted words to a document place, a project PDF or a work (`docs/design/model.md`, "Notes"). Finding words again in a Markdown page is the anchoring T033 builds for annotations; until it exists, a link into a Markdown file names the file or a heading only.

## Rough design

`quilt:FILE.md#quote=…` resolves with T033's anchor, opens the page at the words and lights them; selecting words in a Markdown page offers New note with that link. A link whose words are gone is a broken link in Problems, as for every other target.

## Blast radius

The link resolver (`loom/src/loom/links.py`, `viewer/src/lib/workspace/links.ts`), `docs/specs/dialect.md`, the Markdown file item.

## Related

WQ-70, WQ-71; T044 and T045 of `docs/plans/0.32-v0.1-remaining-task-list.md`.
