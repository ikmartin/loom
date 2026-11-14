# Reserved names

**Nothing on this page is built yet.** It lists the names that work in progress will add to what loom writes and what its viewer asks of it: paths in a quilt, write operations, refusals, record fields, manifest fields, commands, diagnostic codes and the viewer's routes. They are fixed here, before the work that builds them, so that two pieces of work done at once do not give one thing two names or two things one name.

A name leaves this page when it is built: the change that builds it moves it into the specification it belongs to (`manifest.md`, `write-api.md`, `diagnostics.md`, `digests.md`) and deletes its row here. `loom/tests/unit/test_reserved.py` fails for a write operation that is served while this page still lists it. A name that turns out wrong is changed here first.

Two kinds of entry. A name that crosses a boundary, made by one part of loom and read by another, is fixed. Where one part alone will add names of a kind, its prefix is reserved and the names are its own to choose. The owner is the part of loom that builds the name.

## Paths in a quilt

Each is a constant in `loom/src/loom/paths.py` and is protected from agents (`loom/src/loom/agents.py`), so a quilt's generated permission files already deny them.

| path | holds | owner |
|---|---|---|
| `.loom/format` | the quilt's format number, which a loom older than the quilt reads to say so | the safe write path |
| `.loom/live/`, one `<pid>.json` each | a record for each agent server process attached to the quilt | attaching an agent |
| `.loom/incoming/`, one `<sha>/` each | files dropped on the viewer and not yet filed | the library |
| `.loom/digests/suggested.jsonl` | the works an agent suggested | the library |
| `.loom/formal/`, with `evidence.jsonl` and `attest.toml` | formal evidence, and the person's attestations | formalization |

Named and not yet a constant, since each has one owner and stands under a directory that is protected already: `lean/` at the quilt's root is the Lean project, a place agents write, which the scan and the list of what changed leave out. Files outside any quilt (the list of recent quilts, the switch that turns formalization on for this machine) are their owner's alone.

## Write operations

None is served. The table is not in the shape of `write-api.md`'s tables, whose rows are the served endpoints.

| operation | does | owner |
|---|---|---|
| `change-undo` | undoes the Keep of the suggested edits it names, each in one step | the safe write path; Review and the document call it |
| `library-take` | takes in what was dropped or what an agent suggested | the library |
| `library-answer` | answers the one question an intake asked | the library |
| `library-undo` | undoes an intake | the library |
| `library-unfile` | takes a wrongly filed document off a work | the library |
| `library-dismiss` | dismisses works an agent suggested | the library |
| `formal-enable` | turns formalization on for the quilt, on this machine | formalization |
| `formal-check` | runs loom's own check of a formal proof again | formalization |
| `formal-attest` | records the person's attestation that a formal statement is theirs | formalization |
| `agents-setup` | writes the files an agent's app needs to work in the quilt | attaching an agent |
| `quilt-import` | brings a dropped paper, folder or archive into the quilt | install and launch; the window's drop target calls it |
| `sync-pair` | pairs the quilt with an Overleaf project from its link | Overleaf |
| `sync-fetch` | fetches what changed there | Overleaf |
| `changed-seen` | marks what changed as seen, one row or all | Review |

Prefixes: `change-` and `history-` belong to the safe write path; `library-` to the library; `session-` and `agents-` to attaching an agent; `sync-` to Overleaf; `adopt-`, `review-` and `changed-` to Review; `formal-` to formalization; `quilt-` to install and launch.

## Refusals, and what a write answers

| name | means | owner |
|---|---|---|
| `changed-since` | an undo refused: the text has changed where it was written | the safe write path |
| `outside-quilt` | a restore or a put-back that would write outside the quilt | the safe write path |
| `published`, in every write's answer and in the manifest | the number of the publication that will show the write, which the viewer waits for | designed with the safe write path, built by the speed work |

## Record fields

| field | on | owner |
|---|---|---|
| `edge` | a created edit at the head or foot of a body: the body's first or last 32 characters | the safe write path |
| `context` | annotations and edits: the neighbours either side, `twin`, and the quote's count in the quilt | the safe write path |
| the annotation types `dead-end` and `claim` | a quilt's `annotation-types.toml` | the learner's work |

`near`, the line above a block named by its place, is written on created edits already (`loom suggest`).

## The manifest

Loom writes none of these, so `manifest.md`, which says loom writes every top-level section, does not list them; the top-level ones are optional and untyped in `arras/src/lib/manifest/types.ts`.

| field | holds | owner |
|---|---|---|
| `published` | the number of this publication | the speed work |
| `unplaced` | the records that could be placed on no block | the safe write path makes it; Review and the page of notes draw it |
| `suggested_works` | the works an agent suggested and nobody has added or dismissed | the library |
| `formal`, and `keys[K].formal` | the formal proposals, and each key's formal state | formalization; Review's list of proposals reads it |
| `diagnostics[*].class` | whose problem a code is, so that a person is shown only problems in their own text | Review; every part that adds a code gives its class |

With one owner and no name fixed: the list of what changed and an AI document's state (Review, which may reshape `changes` and `changes_since`); who is connected and what agents may read and change (attaching an agent, sent over the stream and read at `/_api`); a work's state word and its page text (the library).

## Commands and modes

None is registered, so help, the command reference and the agent's tools are unchanged.

| name | owner |
|---|---|
| `loom library suggest REF --why`, an agent's command and tool | the library |
| `loom formal record KEY …`, an agent's command and tool | formalization |
| `loom formal attest KEY`, the author's | formalization |
| `loom app` | install and launch |
| the mode `formalize` | formalization |

## Diagnostics and doctor

Code prefixes: `loom:formal-` for formalization; `loom:markdown-` for the checks of links in Markdown; `loom:tex-` for a missing picture or package; `loom:compile-` for a failed compile shown as a problem. Doctor items: `writes`, what recovery of the journal could not settle; and the Lean and TeX items of formalization and install.

## The viewer

Routes: `/library`, the page of every work; `/activity`, what agents did; `/notes`, every note. In Review's list of proposals, the card kind `formal`; the badge `formalized`. What the column draws is under `arras/src/lib/shell/column/`, and the window's drop target is `arras/src/lib/components/DropZone.svelte`.
