# Notes on the library mock-up, round six

The author's 25 marks on rounds three to five, the rulings on them, and the critic's two findings on round five. Everything else is round five's. Open `index.html` at 1440 by 900; the strip at the top moves between screens and opens these notes. Two rules now hold everywhere: loom writes nothing into his TeX by itself, and Review is filtered from its column, with no tabs.

| mark | | done? | in a line |
| --- | --- | --- | --- |
| 1 | drag cover wording | done | "Drop to add to your library." and, only while papers wait for their file, "If it is one of the 3 papers waiting to be fetched, it is attached to that paper." (01b) |
| 2 | add work…, and how 1b and 1c are reached | done | `add work…` opens a small panel under the button: `choose files…`, a field for an arXiv number or DOI, and "or drop files anywhere in loom" (01-add-work). The strip labels 1b and 4d "drag only" and 1c "empty library only", and the notes say so. |
| 3 | a work's outline | done | Sections as headings with their page, results under the section they stand in; a click on either goes to its place on the page (02). For a PDF-only work, the PDF's own outline, with your marks under the section their page falls in (03). |
| 4 | the digest control | done | `digest…` with no chevron; items finish the sentence with counts: `results my drafts use (2)`, `what I marked in this paper (0)`, `results I choose…`, `everything in Smith 2024 (51)`, and a foot line saying who does it (02-digest-menu). `results I choose…` starts choosing in the outline (02-choosing-results). In the works list: `results my drafts use, in every paper (14)` and `everything in the papers I select` (01-digest-every-paper). |
| 5 | the selection menu | kept | `mark to digest · highlight · note · ask an agent…` unchanged (03). |
| 6 | thumbnails in the Library | done | `list` and `thumbnails` beside the search, as in the picker; the choice stays while you move between views (01-works-thumbnails). |
| 7 | Review's column | done | `Waiting for you`, `Everything`, the kinds alphabetically, a rule, `Waiting for an agent`, a rule, `Drafts`. The list under `Everything` follows the same order (04). |
| 8 | the kinds' names | done | `Accepted results that changed`, `Agent questions`, `Attested results that changed`, `Cited results to digest`, `Digested results to check`, `Lean statements to attest`, `Papers to fetch`, `Proposed edits`. |
| 9 | hover cards on the queues | done | The given texts, after the same delay as the view names, beside the column (04-review-hover-card). |
| 10 | "attested" made plain | done | The queue names its object, its hover card defines the act, and the row asks "Does the Lean say what you wrote?" with `yes, I attest it` and `no, it differs…`; the line beside says what the yes covers (06). |
| 11 | answering in his own words | done | Each question has its choices and a field, "or answer in your own words", with `send` (04-agent-question). |
| 12 | the edit that stopped a compile | done | "bounds.tex has not compiled since this edit (line 14)." (12) |
| 13 | rows tied to their paper | done | A paper's results, and a definition's resting results, sit indented under it with a line down their left (04f, 04-results-to-check, 04j). |
| 14 | a citation that names no result | done | Loom writes nothing. The row shows the sentence, says what to add, "for example `\cite[Lemma 2.4]{Oka22}`", and offers `ask an agent which result` (its answer comes back as a proposed edit) and `only a mention` (remembered) (04h). |
| 15 | the changed-since-attested row | done | Three headed steps: what you attested with its date and the Lean beside; how it reads now, the change marked; "Does the Lean still say this?". Below, apart and tied by a line, the results resting on a changed definition (04i, 04j). `see it in main.tex` opens the document over Review at that place, a panel you close (04-see-it-in-main-tex); proposed edits have the same control. |
| 16 | the whole lemma first | done | The statement as main.tex has it, then the part-by-part table (06). |
| 17 | how 4d is reached | done | Labelled "drag only" in the strip; said in the notes. |
| 18 | the Web's list by document | done | Under `everything`: `your drafts` and `library`, each document a row that opens to its results, Zotero-like (07a-web-everything). Under `a draft and what it rests on`: `main.tex` and `library results main.tex uses` (07a-web-draft-and-what-it-rests-on). |
| 19 | search in the statements | done | `find a result, or words in it` matches number, name, work and the words of the statement, and shows the words found (07a-web-search). |
| 20 | the card under the graph | done | The graph takes the whole width and the focus's card sits under it at full width; `graph` everywhere (07b). |
| 21 | formalizing from the Web | done | The graph draws no plan, only each result's marks; the boundary drawing is gone. In the list, results not formalized can be chosen; "3 chosen · formalize…" opens the panel of 23 (11c, 11e). On the graph, `formalize…` is on the focus's card. |
| 22 | the Docs column | done, as corrected | Today's tree, its rows (19 px), folds, document and PDF rows and `AI` marks, under a `Files` head with a rule and no arrow. Folded, a hover lets a short drawer of the first rows down, and a click opens it all (08-docs-files-open, -folded, -drawer). |
| 23 | the formalize panel | done | A large panel over Docs, reached from the Lean mark in the margin (hover: "not formalized · formalize…"). The theorem in full; "To formalize this, an agent will state 3 definitions in Lean, prove 2 of your lemmas, and assume 4 results from your library."; `Needed first`; `To state`, `To prove` with `prove` or `assume for now`, `To assume`, each statement one click away; `Already formalized`, folded; the button and the line about Review (11a blocked by a missing label, 11b ready). The doc's `view ▾` can hide the Lean marks. |
| 24 | notes keep their width | done | The page is 760 px wide whatever the sort (08b-notes-by-date, -by-work). |
| 25 | the error page | kept | 8d unchanged. |

From the critic's check of round five:

- Nothing not yet done reads as done: the panel says to state, to prove, to assume, and the graph no longer tags a request not yet made.
- The search hit on a paper's page is the reader's ordinary yellow find highlight (04f).

## What the Files tree takes from today's product

From today's `FileTree.svelte` and the Files shelf: rows at 12 px with a line height of 1.4 and 2 px between them (a 19 px pitch); folds as `▾ name` and `▸ name` text buttons in the soft ink; each level indented with a 1 px rule down its left; documents in the link colour, the open one bold in ink, other files in the soft ink; the `AI` mark at 9.5 px in the agent's colour, struck through where only the person edits; and each document's compiled PDF as a row beneath it, with its compile word ("did not compile" under bounds.tex). Not reproduced: the `AI` mark's explanation, which opens beside it today (a plain tooltip here); agent copies hung under their document by the hooked arrow (the fixture has none); the research state row; the live "compiling" and "waiting to compile" words; and dragging the column's edge. `AGENTS.md` is not shown, as today hides agents' config files by default. The PDF row's indent under its document is my reading of the source.

## What I was unsure of

- **Unread or unchecked results in `Needed first`.** Only the missing label stops the request, as the brief says. But `library.md` says nothing is assumed in Lean on a result nobody checked. So the panel lets the request go ahead and says the result reads formalized only once all of them are done. If assuming must wait, these become blockers too.
- **A PDF-only work's cited results.** Theorem 2.3 and Corollary 4.2 are listed apart, as "Cited, not yet placed". Filing them under section 2 or section 4 because of their numbers would be a guess about where they stand.
- **Selecting several works.** In the list, ⌘-click selects without opening, as in Zotero, and `everything in the papers I select` uses that selection. A plain click still opens a work.
- **Clicking a section that is not drawn.** The outline's sections whose pages the mock-up does not draw say where they begin, rather than moving.

## Where following a mark may be a mistake

- **Mark 7, the order under `Everything`.** Alphabetical order is good for finding a kind in the column. In the list itself it puts `Accepted results that changed` first and `Agent questions`, where an agent is stopped until he answers, second. It also splits the path a cited result travels (fetch, digest, check, attest) across the alphabet. I followed the mark. I would order the list by who is waiting, agents' questions first, and keep the column alphabetical.
- **Mark 22 and the compile word.** Today's tree says "did not compile" under bounds.tex's PDF row, and I drew it so, because he asked for today's tree. That is a problem shown in the tree, which round four ruled out. It is quiet and true, and it answers the worry I raised in round four, so I would keep it. The ruling may want amending.

## Row heights and targets that moved

| | round five | round six |
| --- | --- | --- |
| file tree rows | 28 px (round five) | 19 px, today's product |
| a work's outline | results only, 26 px | section heads 26 px, results 26 px |
| Web list | 28 px rows | 28 px rows, 28 px document rows |
| formalize panel | a 540 px panel, 28 px rows | over the view, 30 px rows |
| icon targets | 28 px, 16 px glyph | unchanged: settings, column, tab close, row chevrons, panel close all 28 by 28 with a 16 px glyph; the tree's folds are today's text buttons |

## Checks

- No control but the four view names changes view: the critic's crawl clicked about 300 controls on the changed screens (02, 04, 04j, 04-see-it, 07a, 07b, 08, 11a, 11b), each from a fresh load, and none changed view. Formalizing from Docs stays in Docs. `see it in main.tex` opens the document over Review and closes there.\n- `tools/check6.cjs` walks the new flows. Review's counts agree: Everything 29, the kinds 29, main.tex and bounds.tex 29, agents 6 apart. The attestation's folds keep the column. Choosing results in the outline and digesting them changes their marks. A missing label disables the formalize button with its reason, and with the label the request adds a task. ⌘-click selects works for `everything in the papers I select`. `add work…` opens its panel. Files folds and opens. No script errors.\n- `tools/rows6.cjs` measures the rows and targets in the table above.

## Pictures

Every changed screen is in `screens/`, named by its screen number: `01-add-work.png`, `01-digest-every-paper.png`, `01-works-thumbnails.png`, `01-works.png`, `01b-drag-cover.png`, `02-choosing-results.png`, `02-digest-menu.png`, `02-tex-work-outline.png`, `03-pdf-work-outline.png`, `04-agent-question.png`, `04-results-to-check.png`, `04-review-everything.png`, `04-review-hover-card.png`, `04-see-it-in-main-tex.png`, `04d-drag-cover-review.png`, `04f-cited-results.png`, `04h-citation-names-no-result.png`, `04i-attested-result-changed.png`, `04j-definition-changed.png`, `06-attest.png`, `07a-web-draft-and-what-it-rests-on.png`, `07a-web-everything.png`, `07a-web-search.png`, `07b-web-graph.png`, `08-docs-files-drawer.png`, `08-docs-files-folded.png`, `08-docs-files-open.png`, `08b-notes-by-date.png`, `08b-notes-by-work.png`, `11a-formalize-blocked.png`, `11b-formalize-ready.png`, `11c-web-chosen.png`, `11e-web-formalize.png`, `12-edit-that-stopped-compiling.png`.
