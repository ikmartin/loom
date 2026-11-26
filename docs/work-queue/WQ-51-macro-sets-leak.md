# WQ-51 · A view's macros stay its own

**Repo:** viewer

## Trigger

A quilt other than the synthetic fixture has two macro sets in its manifest that define one macro name differently (`macros.sets` and `macros.default`; a two-minute script over `.loom/cache/site/manifest.json` finds them). Checked 2026-09-26: none of acgs, hostile, kpsv, man12, mmp or showcase has one.

## Why deferred

The leak shows only when two sets disagree on a name, and no real quilt's sets do yet. Plan 0.16 found the mechanism while fixing the landmark formula bug: `typeset()` in `viewer/src/lib/math/mathjax.ts` gives a fragment its macros by typesetting one formula of `\renewcommand` definitions, off the page, just before the fragment's own formulas, and MathJax keeps those definitions in one page-wide table. Every view typeset afterwards, in either pane, sees the last set defined, so a document opened after another can render a shared macro name with the other's meaning. The review comparison already avoids this: it passes macros through `isolatedMacros` (`viewer/src/lib/math/scoped.ts`) and places nothing in a formula.

## Rough design

Give every fragment that names a macro set the scoped path the comparison uses: its macros as configuration for that typesetting and no formula of definitions, so `define` and `macroPrefix` go. Measure first what a scoped typesetting costs per set against the shared one, on the demo with the most landmarks, since a landmark's view and its nodes' previews each name a set.

**The test needs a set of its own.** The fixture's other definition of `\Hom`, its `Kre99` digest's set, went with the digests, and every set it has now agrees on it. Give the fixture a landmark whose preamble defines `\Hom` otherwise, open `/canon/widgets-v1` and then that landmark in the same page, and assert that each renders `\Hom` with its own definition; today the second shows the first's.

## Blast radius

`viewer/src/lib/math/mathjax.ts` (`typeset`, `define`, `macroPrefix`), `viewer/src/lib/math/scoped.ts`, the callers in `fragments/Fragment.svelte` and `NodePreview.svelte`; an e2e test on the fixture's `\Hom`.
