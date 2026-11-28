# The names a person reads

**[decided]** The names below are frozen for v0.1 (plan 0.32, decision 14): the viewer calls each thing by its name here and by no other, in every view, in Settings, on the home page, in a notice, a card, a tooltip and an empty state. The words themselves live in `viewer/src/lib/words/`; this list says which name each thing has, and changing one is a decision for the author, made here and in the words in one change.

Three rules hold beside the list. No screen shows a command, a flag, an endpoint or a path a person would type: a step loom cannot take from the viewer is a control, or "ask your agent". No tooltip or card shows an internal id or raw TeX, except where the person turned on Settings › Appearance › Show ids. A refusal of loom's is said in the viewer's words for its code (`frame.ts`, `refused`), never in loom's own message, which is written for the command line.

| thing | its name | not |
|---|---|---|
| the folder loom manages | quilt | corpus, manifest |
| the four views | Docs, Library, Web, Review | |
| a statement or proof loom reads | result | node, key |
| a paper the library holds | work, or paper where it is a PDF to read | |
| a document an agent made, a copy of one of the person's or a new one | agent document | an agent's copy, AI document |
| a change waiting in the person's text | proposed edit (Review's list: Proposed edits) | pending change, Proposed Changes |
| a proposed edit an agent wrote beside the text | suggested edit | |
| a proposed edit written into the file by an agent | edit made in place | |
| taking a proposed edit, or leaving it | keep, discard (undo the edit, for one made in place) | accept |
| a person's word that a result reads right | accept (Results to accept) | keep |
| a mark on words with a comment | annotation; its words are a comment, the answer to it a reply | note |
| the annotation type for proposed words | Suggestion | |
| a file of the person's own linking into the quilt | note | annotation |
| a saved state of a file | version; putting one back is restore | |
| Review's page of versions, sessions and acts | History | |
| what is wrong in the person's own files | Problems, a problem | diagnostics |
| a conversation an agent worked in | session | |
| a way of working an agent is given | mode | |
| the drawing of what results rest on | graph | |
| where a result stands with its paper or its Lean | status | standing |
| a result's Lean, accepted and given the person's word | formalized; giving the word is to attest | |
| the page an agent keeps on where the work stands | research state | |
| loom serving a quilt | loom | the publisher |

**Settled 2026-11-28 by the author.** A document an agent made, a copy of one of the person's or a new one, is an agent document wherever a person reads it: in Review, in Docs, in loom's own labels and in the plan's decision 3. "An agent's copy" and "AI document" are retired; `names.spec.ts` holds the viewer's words to it. Code identifiers, paths (`.loom/agents/copies/`), endpoints and JSON fields keep their names.
