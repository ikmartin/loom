# WQ-36 · Annotation bodies and PDF geometry beside the manifest rather than inside it

**Repo:** loom, arras

## Trigger

A corpus's manifest crosses a few megabytes and the reason is annotation prose rather than nodes — a long review, a pasted proof in a suggested edit — or crosses one megabyte because of the rectangles and strokes of annotations drawn on PDF pages.

## Why deferred

Raised by the hostile demo (`docs/reports/hostile-demo.md`, direction 5) and deliberately not acted on, because the condition it guards against has not happened.

The manifest is **loaded whole on every poll**. `.loom/cache/site/source/<key>.tex` exists precisely so that a key's own LaTeX is fetched one key at a time and only when a reader asks; annotation bodies and suggested edits' text have no such arrangement and are carried inline; a session's messages already have one, paged beside the manifest (manifest.md §10.1). A single 400 KB annotation body put into a hostile quilt took its manifest to 3.2 MB on its own.

That is a real shape, and it is not yet a real problem. No corpus anyone has has a large annotation: the largest real manifest measured is relloc's at 772 KB (5.7 MB on 2026-11-02, but from digest results, which is [WQ-58](WQ-58-lazy-digests.md); its annotation prose is about 0.1 MB), and none of that is annotation prose. Building the split — a `build/annotations/` directory, a fetch path, a viewer that renders a body it may not have yet — costs an interface change, a publisher change and a loading state in every surface that draws a comment, to solve a size nobody has reached.

**PDF geometry** is the same shape. An annotation on a PDF page carries its rectangles and strokes in its manifest row, and the manifest is read whole whenever it changes. A paper read closely holds a few dozen at a few hundred bytes each, so a heavily marked book of a few thousand comes to about a megabyte; below that the row is the simpler place, since every surface that lists an annotation already reads it.

**The trigger above is observable**, which is the test for whether this belongs in the queue at all: it is a number in a file, and `loom build` already knows it.

**The arrangement exists for node text.** `.loom/cache/site/source/<key>.tex` is a file beside the manifest, fetched by the one surface that wants it. Plan 0.13 built the same for a quoted span's rectangles on a work's page, a sidecar named by a hash on the manifest row, and it went with the digests; a work's page geometry comes back through `library-places` (library-views.md §3.3). What is left for this item is *applying* the pattern to annotation bodies — a `.loom/cache/site/annotations/` directory, the fetch path, and a viewer that renders a body it may not have yet — rather than inventing it. The loading state in every surface that draws a comment is still the cost, and the size nobody has reached is still the reason not to pay it.

## Rough design

Two steps, and the first may be all that is ever wanted:

- **Make the condition visible.** `loom build` reports a manifest over some threshold, saying what the largest contributors are. A diagnostic costs nothing and turns "the viewer feels slow on this corpus" into a sentence naming the cause. It also means the trigger fires by itself rather than waiting to be noticed.
- **Move the prose** if it does. `.loom/cache/site/annotations/<id>.html` beside `.loom/cache/site/source/<key>.tex`, with the manifest keeping every field a reader filters or sorts by — author, type, look, status, target, anchor — and carrying the body only as a length. Geometry leaves the row for a sidecar named by the PDF's hash, a work's or a project PDF's, fetched by the one surface drawing that PDF; rows keep `mark`, `quote` and `page`. Everything that lists, counts or filters annotations keeps working from the manifest alone; only the surfaces that *render* prose fetch.

The second step changes both sides at once, as every change to what crosses does: the viewer fetches a body by its path.

## Blast radius

`loom/src/loom/records/store.py`'s annotation emission, `render/build.py` for the new directory, `specs/manifest.md` §9, every arras surface that renders `body_html`, and `arras/src/lib/pdf/desk.svelte.ts` for geometry.

## Related

[the hostile demo](../reports/hostile-demo.md), which measured it; WQ-65, merged into this item by plan 0.30, for the geometry; [plan 0.11](../plans/0.11-run-review-view.md), which introduced the build output's `source/` for the same reason about node text.
