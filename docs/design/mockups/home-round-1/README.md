# The home page mock-up, round one

The clickable mock-up of loom's home page (the list of a person's quilts, opening one, making a new one) and its drop window (a paper, folder or archive dropped on the page becoming a quilt). It is drawn from the states and words of the Install hand-over (`install-home-handover.md`, "For the mock-up and the viewer's half") and section 3 of its cut, in the look of the library mock-up's round six (`../library-round-6/`). Nothing in it is built: the home page's server is (`loom app`, `docs/specs/write-api.md` §7), but the page and the drop window are not. Its quilts, names, paths and messages are invented.

- `index.html` is the prototype. Open it in a browser at 1440 by 900; it makes no network request. The strip at the top, outside the application, moves between screens, and names the one shown at its right. A screen can be opened directly as `index.html#2d`. Cancel, Close and a few buttons move between screens as they would; nothing else is live.
- `screens/` holds a picture of every screen, named by its number and label.

## The screens

| screen | what it is | the hand-over state it draws |
| --- | --- | --- |
| 1 | First launch: the empty list with its drop area, New quilt and Open a quilt…, and the name asked | `quilt-name` with `name: ''`; cut §3 step 1 |
| 1b | First launch with git's name in the footer, and no TeX | `name.source` git ("from git", Change); `tex: none` with Repair TeX |
| 1c | Repair TeX running, its progress line in place of the notice | `quilt-repair` as a job, `step` its progress lines |
| 1d | The name being changed, in the footer | `quilt-name` with `name` sent |
| 2 | A paper, folder or archive dragged over the page | the drop, "New quilt from your paper" |
| 2b | A PDF dragged over the page | the drop, "New quilt for reading this paper" |
| 2c | The drop window's form: Name filled from the folder's name, "In ~/Quilts" with Change…, Create | `quilt-receive`, then the form before `quilt-create` |
| 2d | The one question: which file is the paper, each choice by its path; nothing chosen, so Create waits for a choice | `quilt-create` answering `question.choices` |
| 2e | The steps, the second running | `step` `making`, `importing`, `starting` |
| 2f | Done: the steps give way to "gadget-towers is ready." and Open it; the list behind has its row, running | `done`, the row `running` in `quilt-list` |
| 2g | Done but not typeset, with no TeX: Repair TeX beside Open it | `done` with `typeset: false` and `tex: none` |
| 2h | Done but not typeset: where TeX stopped | `done` with `typeset: false`, `untypeset` the first error |
| 2i | The drop window for a PDF | the PDF drop (its back end is V1, not built) |
| 3 | The list: running (Open, Stop), not running (Open, Forget), starting; the footer's name has no source | `running`, `stopped`, `starting`; `name.source` other than git ("else nothing") |
| 3b | The list with every kind of trouble, one quilt each | `missing`; `failed` with `why` `port-taken`, `refused` (twice: an ordinary refusal, and a quilt a newer loom made), `exited`, `cannot-start`; Copy details, once shown as copied |
| 3c | The list cannot be read: nothing listed, New quilt and Open a quilt… disabled, Copy details for the machine's report | `list: "unreadable"` |
| 4a | Refused: a folder of that name is there, said under the name | `exists` |
| 4b | Refused: that quilt is being made already | `exists`, while another create of that name runs |
| 4c | Refused: the home page is stopping | `stopping` |
| 4d | Refused: no LaTeX file that begins a document | `no-paper` |
| 4e | Refused: an archive loom cannot open | `bad-archive` |
| 4f | Refused: more than 1 GB | `too-large` |
| 4g | Failed during the import: the steps give way to what loom said, and Copy details | `cannot-import` with `said` (a job's `failed`) |
| 5 | New quilt with no paper: the name only, with where it goes as plain text | "New quilt" (no drop) |
| 5b | Open a quilt… on a folder that is not one | `quilt-choose` `open`, `not-a-quilt` |
| 6a | The quilt opened from a drop, on its document, saying its working copy differs | `done` with `differs: true`, said on the quilt's first page |
| 6b | A quilt's page whose server stopped: it says so and links to the home page | V4 |
| 6c | A quilt's page after an update: "Loom was updated." with Reload, above the document | V4 and cut §3 step 5 ("reload", never a command) |

## Choices a reader should know about

- **Words that are mine, not the hand-over's.** The state word "Running" (the hand-over gives a running row only its Open link; "Running" pairs with "Not running"); the empty state's three sentences, including "A quilt is a folder for one piece of research: the papers you write or read, and your notes on them", from `model.md`'s definition; the drop hint under the list; "You dropped gadget-towers, a folder of 14 files."; "gadget-towers is ready."; "Loom could not bring your paper in, and made nothing:" (true because a create is whole or nothing); the hints under `no-paper`, `stopping`, `bad-archive` and `too-large`; "Loom could not open it:" leading a `refused` row; the newer-loom hint, which says to paste the line from loom's GitHub page into Terminal again (updating is pasting the line again, cut §3 step 5), and that row offers no Open again, which would only refuse; "Quilts already open stay open." after the unreadable list's sentence; the stopped-server card in 6b; the hover texts on Open, Stop, Forget and Copy details; "In ~/Quilts" under New quilt's name; and "Loom has no TeX yet" as what 2g's untypeset says when there is no TeX at all. The step "Bringing your paper in and typesetting it" carries its parenthesis as a second line, "The first time can take a few minutes.", while it runs.
- **A step list shows only work in progress.** Once a create ends, its steps give way to the outcome, so no step is ticked that did not wholly happen: a paper not typeset is said in the amber box (2g, 2h), and a failed import made nothing (4g).
- **Done asks for one click.** The hand-over has done open the quilt's address by itself. A browser lets a page open a tab only on a click, and the create ends minutes after the click on Create, so the window says the quilt is ready and offers Open it. Where a browser allows it, the viewer's half may open it unasked and leave the window as the fallback.
- **The cover cannot name the file.** While a file is dragged, a browser tells a page its type but not its name, so the cover says only which of the two kinds it is (a PDF, or anything else). The name appears in the window once dropped.
- **What a row shows** is what `quilt-list` gives: the quilt's name, its folder, and its state. No dates, sizes or counts, which loom does not report. The folder of a missing quilt is where it was.
- **New quilt with no paper asks only the name**, as the hand-over says; the quilt goes in `~/Quilts`. The drop window's form has the folder's Change…, as the hand-over gives it.
- **The quilt pages (6a to 6c)** are a plain stand-in for round six's Docs view, drawn only to place the three messages. In 6b the card links to the home page; that is a different page of loom, not a jump between the four views. Where 2g and 2h's "shown as its source" lands on the quilt's own page is the viewer's half's, as round six's compile words are.
- **Not drawn:** the macOS folder dialogs behind Change… and Open a quilt…, which are the system's; a PDF's steps, which the hand-over does not word (V1 is not built); Repair TeX's real progress lines, which the job gives (1c's line is invented); a quilt made earlier by an older loom, which opens and shows its bring-forward page on the quilt, not here; the moment a running row's Open is clicked, which only opens a tab.
- **Capitals.** Controls here are capitalised as the hand-over words them ("New quilt", "Open", "Repair TeX", "Copy details"); round six's controls are lower case ("add work…", "digest…"). One convention should hold in both; that is the author's call.
- **Open, for the author or the viewer's half.** Whether closing the window during the steps stops the create (the hand-over has the quilt's row on the list either way); whether a quilt being made should show as a row (4b says it is being made, and the list shows nothing of it, since `quilt-list` lists jobs apart from quilts); and whether the newer-loom hint, which sends the person to Terminal, is acceptable where no human types a command.
- **Sizes.** Icon controls are 28 by 28 with a 16 px glyph, as in round six; buttons are round six's (13 px, about 28 px tall); the list's rows are at least 58 px; one footer, at the bottom of the home page, holds the person's name.

## The critic's rubric

A fresh critic judges the screenshots against these six, one finding per failure, each naming the screen.

1. **Every hand-over state drawn.** Each list state (`running`, `starting`, `stopped`, `missing`, `failed` with each `why`), the unreadable list, the name asked and shown with its source, no TeX and Repair TeX, the two drops, the form, the one question, the three steps, done with `typeset: false` and with `differs: true`, every refusal, New quilt without a drop, and Open a quilt… refused.
2. **Words match the hand-over.** Where the hand-over proposes words, they are used, or the departure is listed above; no word names a command, an id or an endpoint.
3. **Controls sized reasonably.** No icon control smaller than 28 px, no glyph that strains, no button that reads as text or text that reads as a button.
4. **Consistent with round six's look.** Its colours, type sizes, buttons, rules and panels; nothing that looks like another product.
5. **Nothing misleading.** No screen claims what loom does not know or has not done (V3), nothing unbuilt reads as built, and no control on a quilt's page jumps between the four views.
6. **A first-time mathematician knows what to do.** On every screen, someone who has never seen loom and has just installed it can tell what the page is, what to do next, and what each control will do.

## The critic's verdict

A fresh critic (an Opus agent given the screenshots, this rubric, the hand-over and round six, and nothing of the designer's reasoning) judged all 28 screens. Rubric 1 (states), 2 (words) and 4 (round six's look) passed with minor findings; 3 (controls), 5 (misleading) and 6 (first-timer) failed. In its words: a careful, faithful round, with every state drawn, the words matching almost to the character, one footer, no jump between views, plainly round six's look; "not ready to show yet", for six must-fix reasons.

Fixed, all six must-fixes:

- Stop and Forget read as disabled or as labels: they are now bordered buttons like Open (3, 3b, every list).
- 2g and 2h ticked a typesetting that did not happen, and 4g ticked a quilt that was not made: the steps now give way to the outcome when a create ends.
- A `refused` row gave only a log line: it now leads with "Loom could not open it:" (3b).
- The newer-loom hint pointed at a line the person cannot find, and its Open again could only fail: the hint names loom's GitHub page, and the row offers only Forget (3b).

Also fixed, from its minor findings: "Loom has no TeX yet" capitalised (2g); a log line that said "home" in another sense replaced (3b); Copy details a small bordered button (3b, 3c, 4g); no choice preselected in the one question (2d); a hint under each dead-end refusal (4c, 4e, 4f); Copy details on the unreadable list (3c); where New quilt puts the quilt (5); a name shown with no source (3); a distinct mark for a missing quilt (3b); the whole stopped page dimmed (6b); "Loom was updated." moved above the document (6c); one paper's file name throughout (2h).

A confirming look by the same critic found all six must-fixes fixed and one new fault, 4c's hint promising a page that would not come back by itself; it now says to open Loom from the Applications folder or the Dock. Its minor 4f (the hint fitted a drop that was already the paper's folder) is fixed with a large drop.

Not taken: round six's agent footer on the stand-in quilt page (a quilt just made has no agent connected, and showing one would claim a connection); a hint on the first launch that the name can wait; and the capitals, the window's close during the steps and a row for a quilt being made, which are listed above as open.
