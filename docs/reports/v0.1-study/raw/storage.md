# Storage: what `.loom` holds, and a model for it (after the study, raw; a draft for the author to mark)

Asked by the author on 2026-11-17, after reading through relloc's `.loom` and looking at its server's memory: the folder is "cluttered and un-intuitive … hacky, laid out without purpose, a big jumble of stuff, much of which appeared potentially redundant"; that `biber` unpacks itself per folder while build directories are never pruned is "completely awful … old build resources should be cut and killed whenever possible"; and "I think the RAM, disk, and directory organization issues all point to a need for a redesign, not an optimization of the existing design."

Measured the same day by the integrator on relloc (the author's quilt: 0.4 MB of TeX, five documents, about 2,500 blocks) and on a copy of it. The code is `main` at ef9b647e unless said; the author's own server ran an older branch whose tokenizer and layout are the same. Nothing in relloc was changed. The scripts were in a scratch directory and are not kept; the numbers a later session needs are here. What the code writes, reads and deletes, entry by entry, is `storage-inventory.md` beside this file, an agent's survey of which the integrator checked six claims.

## Headline findings

- **STOR-1. Relloc is 3.4 GB on disk, and about 3.3 GB of it is scratch or derived.** What must be kept is about 100 MB: the library (68 MB), the agents' sessions (26 MB), the history (6.5 MB), the copies and the annotations.
- **STOR-2. Only what the viewer is served is ever pruned.** A publish removes the fragments, sources, spans, transcripts, bodies and diffs it did not keep (`render/publish.py`). Nothing removes anything else that is derived: the cache, the compile folders, the pictures in `build/svg`, the saved previews of an adoption or a draft, the crops, the comparisons. `.loom/build/cache` holds 89,586 files in 787 MB, written on seventeen different days since 12 October: each change to a block, and each change to loom's rendering code (FAST-8 in `spike-speed.md`), makes new keys and leaves the old files. One warm rebuild read 1,157 of them. That count is a floor and not the live set, since a rebuild that re-renders nothing reads little; the live set is what the build's own index names. Compile folders stay when their document moves: `R6`, `draft5`, `examples`, `examples-shared` and `drafting-ai` are all from before their documents were moved, and the author found a PDF of 27 October there while looking for today's.
- **STOR-3. Agents' scratch lies inside the folder loom defines as rebuildable, and holds 2.5 GB.** `paths.py` says of `.loom/build`: "Everything loom can rebuild; deletable at any moment." The orientation tells agents that `.loom/build/SESSION/` is theirs for intermediates. Loom cannot rebuild what an agent put there, and nothing limits or removes it. In relloc 2.2 GB of it is eleven unpacked copies of `biber`, about 200 MB each: agents ran `loom compile` with their temporary folder set inside their build folder (their notes: "`loom compile`, with `TMPDIR` in `B/genus/integrate/tmp/`"; why they did was not found), and `biber`, which TeX Live ships as a bundle that unpacks itself, unpacks into whatever temporary folder it is given. The machine's ordinary copy exists once, in the system's temporary folder. `biber` takes a folder of loom's choosing through `PAR_GLOBAL_TMPDIR` (checked with TeX Live 2024's). Two more things under `build` cannot be rebuilt: the files a person dropped on the viewer and has not filed (`build/uploads`), and the copy of the annotation log that loom makes before a delete (`build/annotations-before-delete.jsonl`). And the boundary lets an agent write anywhere under `build` (`agents.py`, `AGENT_PLACES`), the manifest and the fragments the person reads among it.
- **STOR-4. `.loom` holds five kinds of thing at one level, and `build` holds four.** Records, the library, the agents' things, this machine's state and derived files sit side by side, and relloc's ignore file needs nine patterns to say which stay on one machine. `build` mixes what the viewer is served, a compile folder for each document, a cache, and the agents' scratch.
- **STOR-5. The same 0.4 MB of TeX is kept six ways.** `build/source` (13 MB, one file for each block), `build/fragments` (34 MB, the HTML of each block), `manifest.json` (10 MB), `last-seen.json` (3.0 MB), the history (6.5 MB) and the copies.
- **STOR-6. A build folder mirrors its document's path, so a document under `.loom` compiles into `.loom/build/.loom/…`.** The rule keeps two documents of one name apart (`paths.document_name`). Applied to an agent's copy at `.loom/copies/examples-shared.tex` it gives `.loom/build/.loom/copies/examples-shared/`, and 35 files named `examples-shared.pdf` lie under `build` in all.
- **STOR-7. One build holds about 380 MB of memory, and each save adds about 37 MB.** A trace of one build: 294 MB held, 179 MB of it tokens (917,000 objects of 195 bytes, 34 bytes for each character of source), with a cache of the last 256 whole texts keeping every saved version. The fix is its own piece of Speed's; the Fast gate now carries the line.
- **STOR-8. Almost none of this is an old layout.** One folder is: no code names `build/cache/svg` (1,415 files, 20 MB, last written on 10 November), on `main` or on the branch the author's server ran. Two of the ignore file's patterns, a session's `attached.json` and `cursors`, name things nothing writes. Every other name in relloc's `.loom` is one today's code uses, and the waste is what was never pruned. One oddity besides: `looked/the-synthetic-quilt.json`, a reader's record under a test fixture's name.
- **STOR-9. The history holds copies of derived files, and several names mean two things.** A closed draft's folder copies its fragments and pictures out of `build`, and a section draft's context copies the paper's files (the survey, list c). `LEDGER` names three files, `INDEX` two and `CACHE` two; "copies", "incoming", "snapshot", "boxes" and "files" each mean two things (list d). The name freeze wants these settled with the layout.
- **STOR-10. The journal's ignore lines follow the default place of the history, not the setting** (the survey's note on `gitignore.py`; not checked beyond those lines). If so, a history that `[quilt] history` puts elsewhere has its journal travel with the quilt, which the design of the write door says it must not. Safe's to look at.

## What relloc holds today

| entry | size | files | kind |
|---|---|---|---|
| `build/s-*`, three sessions' folders | 2.5 GB | 44,781 | agents' scratch |
| `build/cache` (`previews`, `snippets`, `svg`, `spans`) | 787 MB | 89,586 | derived |
| `digests` | 68 MB | 3,408 | library |
| `build/fragments`, `source`, `svg`, `manifest.json`, `files`, `spans`, `transcripts` | 72 MB | 6,250 | derived: what the viewer is served |
| `sessions` | 26 MB | 514 | agents' |
| compile folders: `build/drafting`, `build/.loom`, and five of documents since moved | 22 MB | 170 | derived |
| `build/uploads` | 8.5 MB | 4 | this machine: files dropped and not yet filed |
| `history` | 6.5 MB | 373 | record |
| `build/adoption`, `closures`, `draft-previews`, `incorporation-review` | 4.7 MB | 138 | derived |
| `last-seen.json` | 3.0 MB | 1 | this machine's state: the last text seen for each block, kept so that an annotation's words can be frozen when the text under it changes |
| `copies`, `annotations`, `ai`, `since`, the decision files, `looked`, `serve.json` | 1.7 MB | 34 | records, agents' and this machine's, mixed |

## The model

Five kinds. Every entry is one of them, and its folder says which. "Travels with the quilt" means it is shared when the quilt is shared through git, with a co-author or with another machine. What does not travel stays on the disk where it is: it is not deleted there, and it is never fetched or added again there. A quilt that is not in git, as relloc is not, shares nothing either way.

| kind | what it is | who writes | travels with the quilt | deleted |
|---|---|---|---|---|
| **Records** | What the person and loom decided or said: annotations, suggested edits, versions, decisions, the ledger, the annotation types, formal evidence, the format number | Loom only | Yes | Never by loom |
| **The library** | Other people's documents and what was drawn from them | Loom, and agents through loom's commands | The digests yes, the stored documents no | When the person removes a work |
| **The agents' places** | What agents are told; what they write for the person to read (sessions, copies); their scratch | Agents, within the boundary; loom for what they are told | All but the scratch | Scratch expires; a copy goes when taken or discarded |
| **This machine's state** | The server's address, who is attached, each agent's marker, the write journal, dropped files not yet filed | Loom only | No | Each by its own rule, and all of it small |
| **Derived** | Anything loom can make again: what the viewer is served, compile folders, rendered blocks | Loom only | No | Swept after every build; the whole folder may be deleted at any moment |

Four rules follow.

1. **What stays on one machine is said by folder names.** Two folders and the scratch, in place of nine patterns.
2. **A derived file is named by the build as it stands, or it goes.** After a build that succeeds, loom removes every derived file the build's index does not name, and the compile folder of every document no longer in the quilt. The test is what the index names and not what the build read.
3. **Nothing an agent writes lies in a folder loom may delete.** Scratch is a place of its own, with a limit and an expiry, and what an agent is told says that anything the person should keep is a session file or a copy.
4. **A tool unpacked for the machine is unpacked once, for the machine, outside any quilt.** `biber` first: loom gives every TeX run it starts one folder for it, and the settings it writes for an agent let the agent's runs use the same one.

## The layout proposed

```
.loom/
  format            the layout's number, written for the first time
  records/          annotations, edits, history, decisions, ledger, annotation types, formal
  library/          today's digests
  agents/
    instructions/   today's ai/
    sessions/
    copies/
    scratch/SESSION/    this machine; expires
  local/            serve.json, since/, live/, the journal, incoming/, last-seen.json, the annotation log's copy before a delete
  cache/
    site/           what the viewer is served
    tex/NAME-HASH/  one compile folder for each document
    blocks/         rendered blocks, by key
```

Three things do not move by a rename alone. The history sits wherever `[quilt] history` puts it, and only its default changes; the journal, which lives in it today and stays on one machine, moves out to `local`. A document's name is its path, so moving `copies` renames every agent's document and the records made on it must follow. And the boundary changes with the folders: an agent writes in `agents/` and no longer anywhere under what is derived.

## What it costs

- **Every open branch conflicts**, since each names places through `paths.py`, the ignore rules and what agents are told. It is therefore a stage of its own, between waves A and B.
- **The author's two quilts are moved once**, their records compared before and after. No other quilt exists, so nothing is migrated for anyone else; the format number is what a later change will read.
- **A sweep after an upgrade removes the older loom's files**, so going back to that loom costs a cold build again.
- **An agent's scratch can expire under a person who wanted something from it.** Rule 3 is the answer, and it has to be said to agents plainly.

## Not in this model

The build itself: that every save scans every file again, rebuilds a 10 MB manifest and sends it whole is why a save on relloc takes 18 to 21 s, and FAST-10 sizes what changing it takes. The sweep leans on the build having an index of what it made, which is the same record an incremental build needs, so the two are designed together and built apart. The decision files merged into one record: a change of record format, which rides with the one Safe makes for anchoring. And the library's inner arrangement, which is Library's.

## Settled by the author (2026-11-17)

- **An agent's scratch** is removed fourteen days after its session's last write, and `loom doctor` reports a session over 500 MB before anything is removed.
- **Sessions are kept**, and a person can delete one, in Settings, as a conversation is deleted in an agent's app.
- **No earlier generation of the cache is kept**, so going back to an older loom costs a cold build.
- **Relloc and quant are moved once, by hand, with the author**, and not by a step of `loom upgrade`.
- **`biber` is unpacked once for the machine.**
- **Loom keeps its hands off git.** The author: "Loom writes a gitignore file that ignores the minimal set of things, the set of things which a user would never want to commit anyways, and it doesn't hide anything that would cause confusion or annoyance that the user would expect to be committed." So loom forbids nothing; its ignore file names what is derived, what is this machine's, and an agent's scratch, and the person overrides any line below its marker, as they can today. The token that authorises writes, and any switch that grants power, leave the quilt for the machine's own place, so that committing the whole directory leaks and grants nothing; and whatever stays on one machine inside the quilt is never trusted when it arrives from elsewhere (decision 12). With no ignore file at all, three things would go wrong: derived files and scratch committed, hundreds of megabytes changing with every build and in conflict on every pull; one machine's facts shared as everyone's (the server's address, who is attached, where each agent last looked, the journal); and the token, with whatever lets an arriving quilt act on the machine that opens it.
- **A document's PDF opens and saves from the document.** Today the only way to it is a small `PDF` link in the file tree under the document's own row, and for an agent's copy under the copy, which is itself under the document it copies; nothing on the document's page or its toolbar opens it, and nothing in the viewer saves it (the author: "there is no way to save it through the Loom viewer"). Legibility's.
- **The top level of a quilt is the person's.** The author: "the top level should be fully controlled by the human." An agent with nowhere to write there asks, the first time it needs a place, for a folder to be made ("create folder `ai-misc/` in quilt?"), and the person grants it with one click. With three amendments the author accepted: the yes is given in the viewer, where loom knows it is the person's, since an agent that could report the answer could grant itself a place; loom proposes the folder's name and the person may change it; and a no leaves the agent its own place under `.loom/agents/`, so that a request is never left with nowhere to go. The third leans on work the plan has and has not built. The viewer does not show an agent's things through the hidden folder but lists them by kind: today the column has a heading "Agent documents" for an agent's copies, and a file an agent writes in its session is listed with that session. A new document that copies nothing, a summary say, has no such place yet and would be found only through its session; it needs the list decision 3 describes, an AI document in the file tree with "Take into my document" on it (Review, wave C). So the request for a folder does not ship before that list does. An agent's copies stay inside `.loom`; the folder at the top is separate and the person's to grant.
- **Stored papers are committed like anything else.** Loom's ignore file stops naming them. The author, on the risk of a publisher's PDF reaching a public repository: it "is the responsibility of the user, not of loom. Git doesn't stop you from doing this for example, loom shouldn't either"; and on a switch in Settings for it: "loom shouldn't butt in where it doesn't have to, you're over-designing." A person who wants them kept out writes the line themselves. The repository's own example quilts are regenerated to the new layout in any case.

## Still open

Nothing in the model. Beside it: whether the build's first cut is agreed (Speed's row in the plan).
