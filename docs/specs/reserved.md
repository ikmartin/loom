# Reserved names

**Nothing on this page is built yet.** It lists the names that work in progress will add to what loom writes and what its viewer asks of it: paths in a quilt, write operations, refusals, record fields, manifest fields, commands, diagnostic codes and the viewer's routes. They are fixed here, before the work that builds them, so that two pieces of work done at once do not give one thing two names or two things one name.

A name leaves this page when it is built: the change that builds it moves it into the specification it belongs to (`manifest.md`, `write-api.md`, `diagnostics.md`, `nodes.md`) and deletes its row here. `loom/tests/unit/test_reserved.py` fails for a write operation that is served while this page still lists it. A name that turns out wrong is changed here first.

Two kinds of entry. A name that crosses a boundary, made by one part of loom and read by another, is fixed. Where one part alone will add names of a kind, its prefix is reserved and the names are its own to choose. The owner is the part of loom that builds the name.

## Paths in a quilt

Each is a constant in `loom/src/loom/paths.py` and is protected from agents (`loom/src/loom/agents.py`), so a quilt's generated permission files already deny them.

| path | holds | owner |
|---|---|---|
| `.loom/library/suggested.jsonl` | the works an agent suggested | the library |
| `.loom/records/formal/`, with `evidence.jsonl` and `attest.toml` | formal evidence, and the person's attestations | formalization |

Named and not yet a constant, since each has one owner and stands under a directory that is protected already: `lean/` at the quilt's root is the Lean project, a place agents write, which the scan and the list of what changed leave out. Files outside any quilt (the list of recent quilts, the switch that turns formalization on for this machine) are their owner's alone.

## Write operations

None is served. The table is not in the shape of `write-api.md`'s tables, whose rows are the served endpoints.

| operation | does | owner |
|---|---|---|
| `library-dismiss` | dismisses works an agent suggested | the library |
| `formal-enable` | turns formalization on for the quilt, on this machine | formalization |
| `formal-check` | runs loom's own check of a formal proof again | formalization |
| `formal-attest` | records the person's attestation that a formal statement is theirs | formalization |
| `quilt-import` | brings a dropped paper, folder or archive into the quilt | install and launch; the window's drop target calls it |
| `sync-pair` | pairs the quilt with an Overleaf project from its link | Overleaf |
| `sync-fetch` | fetches what changed there | Overleaf |
| `changed-seen` | marks what changed as seen, one row or all | Review |

Prefixes: `change-` and `history-` belong to the safe write path; `library-` to the library; `session-` and `agents-` to attaching an agent; `sync-` to Overleaf; `adopt-`, `review-` and `changed-` to Review; `formal-` to formalization; `quilt-` to install and launch.

## Refusals, and what a write answers

| name | means | owner |
|---|---|---|
| `published`, in every write's answer and in the manifest | the number of the publication that will show the write, which the viewer waits for | designed with the safe write path, built by the speed work |

## Record fields

| field | on | owner |
|---|---|---|
| the annotation types `dead-end` and `claim` | a quilt's `annotation-types.toml` | the learner's work |

`near`, the line above a block named by its place, is written on created edits already (`loom suggest`), and `context`, what tells a record's block from others, on created annotations and edits (`docs/design/writes.md`, "Where a record goes").

## The manifest

Loom writes none of these, so `manifest.md`, which says loom writes every top-level section, does not list them; the top-level ones are optional and untyped in `arras/src/lib/manifest/types.ts`.

| field | holds | owner |
|---|---|---|
| `published` | the number of this publication | the speed work |
| `suggested_works` | the works an agent suggested and nobody has added or dismissed | the library |
| `formal`, and `keys[K].formal` | the formal proposals, and each key's formal state | formalization; Review's list of proposals reads it |

With one owner and no name fixed: the list of what changed and an AI document's state (Review, which may reshape `changes` and `changes_since`); a work's state word and its page text (the library).

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

Code prefixes: `loom:formal-` for formalization; `loom:markdown-` for the checks of links in Markdown; `loom:tex-` for a missing picture or package; `loom:compile-` for a failed compile shown as a problem. Doctor items: `writes`, what recovery of the journal could not settle; and the Lean items of formalization.

## The viewer

Routes: `/activity`, what agents did; `/notes`, every note. In Review's list of proposals, the card kind `formal`; the badge `formalized`. What the column draws is under `arras/src/lib/shell/column/`, and the window's drop target is `arras/src/lib/components/DropZone.svelte`.
