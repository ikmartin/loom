# WQ-70 · A hook that renders notes in other formats

**Repo:** loom, viewer

## Trigger

A person asks to read a note in a format the viewer does not draw, such as org, rendered rather than as text.

## Why deferred

Notes as files (`docs/design/model.md`, "Notes") count the `quilt:` links in any plain-text file, so an org note already links to the quilt and appears beside what it links to; it only reads as text in the viewer. Until someone wants it drawn, text is enough, and loom stays without code for any one note format.

## Rough design

A quilt setting maps a file suffix to a command that turns the file into HTML (`pandoc -f org -t html`, or the person's own exporter), run when the file changes, as loom runs TeX, under the same fence. The command writes note-to-note links as `quilt:` links; loom shows the HTML as it shows a Markdown page and reads its links from it. Like the new-note command, a command that runs is the person's, kept in their own configuration rather than the quilt's.

## Blast radius

The publisher's file kinds (`loom/src/loom/files.py`), the fence's runner, the link index, Settings › Notes.

## Related

WQ-71 (wikilinks); the pilot's tasks for notes as files in `docs/plans/0.32-v0.1-remaining-task-list.md`.
