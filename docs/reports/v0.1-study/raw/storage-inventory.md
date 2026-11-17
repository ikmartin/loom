# Storage: what the code keeps under `.loom`, entry by entry (after the study, raw)

A survey of `main` at ef9b647e, made on 2026-11-17 by an agent that only read the code, for `storage.md` beside this file. For each entry: who writes it, who reads it, whether loom's ignore file keeps it on one machine, whether an agent may write it, whether loom can make it again, and what ever deletes it. Line numbers are as of that day. The integrator checked six of its claims against the code afterwards: that a publish prunes `fragments`, `source`, `spans`, `transcripts`, the bodies and the diffs (`render/publish.py`, `render/build.py`); the ignore lines, the journal's among them (`gitignore.py`); what `last-seen.json` is for (`records/lastseen.py`); that the annotation log is copied into `build` before a delete (`records/log.py`); that an agent may write anywhere under `sessions`, `build` and `copies` (`agents.py`); and that no code, on `main` or on the branch the author's server ran, names `build/cache/svg`. The rest is as the agent reported it.

**How to read the table**
- Code paths are relative to `loom/src/loom/`.
- `gi` means `gitignore.py`, and `ag` means `agents.py`.
- Where a row says "refused" with no line, the rule is ag:162-163: anything under `.loom/` outside an agent's places.
- Where a row says "allowed", the rule is ag:160. The agent's places are `sessions/`, `build/` and `copies/` (ag:46).
- Path shorthands:
  - H is the `[quilt] history` directory, by default `.loom/history` (paths.py:37).
  - S is `.loom/digests/storage`.
  - W is one work's folder in the store, `S/<scheme>/<id>`.
  - B is `.loom/build`.

| path | holds | written by | read by | gitignore | agent | derived | deleted / pruned |
|---|---|---|---|---|---|---|---|
| `.loom/state.toml` | acceptance ledger | records/ledger.py:89 append_rows, only through cli/review.py:88 write_acceptance | records/store.py:23, since.py:326, scan/alloc.py:20 | not ignored | refused (ag:55) | not derived | never |
| `.loom/annotations/log.jsonl` | annotation events | records/log.py:30 append, :105 append_new; writes.py:632 Act.log | records/log.py:190 replay, since.py:269, scan/alloc.py:29 | not ignored | refused | not derived | records/log.py:38 delete |
| `.loom/edits/log.jsonl` | suggested edits and outcomes | records/edits.py:81 append_new, :533 discard; pending.py:560 via Act.log | records/edits.py:92 replay, since.py:223 | not ignored | refused | not derived | never |
| `.loom/ai/**` (orientation, rules, formatting, modes/, README, .loom-modes-version, *.md.new) | agent instructions and the hashes of what shipped | ai/layout.py:274 init_layer, :301 upgrade_layer | ai/orient.py:34, ai/layout.py:143 | not ignored | refused | partly (shipped text, ai/layout.py:124; edits kept) | never |
| `.loom/retired/**` | sources set aside by atomize | cli/paper.py:644 _atomize | cli/paper.py:584, render/watch.py:45 | not ignored | refused | not derived | never |
| `.loom/sessions/index.jsonl` | session events | sessions.py:84 append_event | sessions.py:66, render/watch.py:118 | not ignored | refused (ag:158) | not derived | lines removed by cli/session.py:301 _purge_index |
| `.loom/sessions/active` | id of the active session | sessions.py:217 set_active | sessions.py:207 active | not ignored | allowed | not derived | sessions.py:222 |
| `.loom/sessions/<id>/inbox.jsonl` | transcript | mailbox.py:231 post | mailbox.py:73, render/build.py:345, since.py:383 | not ignored | allowed | not derived | cli/session.py:283 (`--purge`) |
| `.loom/sessions/<id>/run.log` | command log | cli/build_cmds.py:40 log_run, mcp/server.py:334 _log | render/threads.py:69, ai/orient.py:247 | not ignored | allowed | not derived | cli/session.py:283 |
| `.loom/sessions/<id>/*` (other files) | the agent's own files | agents only | render/threads.py:62 | not ignored | allowed | not derived | cli/session.py:283 |
| `.loom/sessions/*/attached.json`, `*/cursors/` | unknown | nothing | nothing | ignored (gi:26-27) | allowed | unknown | never |
| `.loom/copies/<n>.tex` | agent documents | cli/history_cmds.py:130 _draft_ai, adopt.py:892 refresh; agents | scan/source.py:40, scan/scan.py:130 | not ignored | allowed | not derived | never |
| `.loom/since/<slug>.json` | where each agent last looked | since.py:106 write_marker | since.py:91 | ignored (gi:24) | refused | not derived | never |
| `.loom/since/deleted.jsonl` | deletions still to be reported to an agent | since.py:140 note_deletion | since.py:124 | ignored (gi:24) | refused | not derived | pruned by since.py:118-121 |
| `.loom/looked/<who>.json` | a person's last look, each path mapped to a text hash | looks.py:65 _write | pending.py:175, render/pending.py:493, render/endpoints/changes.py:16 | not ignored | refused | not derived | never |
| `.loom/annotation-types.toml` | annotation types | cli/quilt.py:180, cli/upgrade.py:34, records/types.py:330 save_types | records/types.py:193, ai/orient.py:71 | not ignored | allowed (ag:48) | partly (defaults) | never |
| `.loom/serve.json` | server's port, pid and token | render/serve.py:130 | render/serve.py:162, render/compiles.py:205 | ignored (gi:23) | refused | not derived | render/serve.py:994 stop |
| `.loom/review-decisions.json` | per-reviewer pending rows | review_queue.py:40 _write | review_queue.py:89 rows_for | not ignored | refused | not derived | rows pruned by review_queue.py:231 |
| `.loom/review-origins.json` | where each taken-in block came from | review_origins.py:29, called from adopt.py:725 and sync.py:114 | review_queue.py:100, sync.py:72 | not ignored | refused | not derived | never |
| `.loom/review-observations.json` | first date each cause was seen | records/store.py:492 _observe_causes | same | not ignored | refused | not derived | pruned each scan, records/store.py:516 |
| `.loom/adoption-decisions.json` | adoption choices | adopt.py:1072 decide | adopt.py:1013 | not ignored | refused | not derived | never |
| `.loom/source-sync.json` | pairing with a document workspace | sync.py:93 | sync.py:65, :193 | not ignored | refused | not derived | never |
| `.loom/last-seen.json` | every key's last text | records/lastseen.py:48 | records/lastseen.py:33 | ignored (gi:25) | refused | partly (old texts are lost) | never |
| `.loom/.gitignore` | loom's ignore lines plus the person's | gitignore.py:68, cli/quilt.py:178 | gitignore.py:54, doctor.py:704 | not ignored | refused | partly (lines above OWN, gi:39) | never |
| `.loom/format`, `live/`, `incoming/`, `formal/*`, `digests/suggested.jsonl` | **reserved** (paths.py:51): nothing writes them | nothing | nothing | not ignored | refused (ag:52-57) | n/a | never |
| `.loom/digests/<ck>.tex` | a work's digest | refs/build.py:703, refs/proposals.py:356, :368 | scan/source.py:35, render/manifest.py:397 | not ignored | refused | partly (refs/build.py:720) | refs/added.py:216 |
| `.loom/digests/<ck>.proposed.tex` | proposals written as LaTeX | refs/proposals.py:322 | scan/source.py:35, records/store.py:378 | not ignored | refused | derived from results.json | refs/proposals.py:327; refs/added.py:216 |
| `.loom/digests/<ck>.results.json` | results, anchors and states | refs/proposals.py:154 save_results, cli/library/agent.py:218, cli/library/upkeep.py:350 | refs/proposals.py:135, refs/check.py:33, cli/ai.py:511 | not ignored | refused | not derived | refs/added.py:216 |
| `.loom/digests/<ck>.proposals.jsonl` | proposal events | refs/proposals.py:166 | refs/proposals.py:174 | not ignored | refused | not derived | refs/added.py:216 |
| `.loom/digests/bibliography.bib` | the quilt's bibliography | refs/scan.py:887, refs/added.py:73, :139 | scan/scan.py:307, cli/_quilt.py:91, mailbox.py:316 | not ignored | refused | partly (gathered, refs/scan.py:375) | entries removed by refs/added.py:139 |
| `.loom/digests/unreadable.json` | ignore and forget declarations | refs/unreadable.py:104 declare | refs/unreadable.py:59, render/manifest.py:400 | not ignored | refused | not derived | never |
| `.loom/digests/links.jsonl` | relations between results | refs/links.py:83, refs/proposals.py:612 | refs/links.py:66, records/store.py:867 | not ignored | refused | not derived | lines removed by refs/links.py:145 |
| `.loom/digests/links-removed.jsonl` | relations that were removed | refs/links.py:157 | nothing | not ignored | refused | not derived | never |
| W`/paper.pdf` | stored PDF | refs/fetch.py:329, :408, refs/scan.py:867 | refs/pages.py:427, refs/anchoring.py:66 | ignored (gi:28) | refused | not derived | refs/added.py:237 |
| W`/src/` | stored LaTeX source | refs/fetch.py:308, refs/scan.py:874 | cli/library/agent.py:274, digest/extract.py:405 | ignored (gi:29) | refused | not derived | refs/fetch.py:373; refs/added.py:237 |
| W`/src.json` | the source's identifier | refs/fetch.py:340 | refs/fetch.py:368 | not ignored | refused | not derived | refs/added.py:237 |
| W`/fetched.json` | download record | refs/fetch.py:416 | nothing | not ignored | refused | not derived | refs/added.py:237 |
| W`/pages/*.txt`, W`/sections.json` | page text and section map | refs/pages.py:449, :459 write_map | refs/search.py:138, refs/pages.py:472, :498 | not ignored | refused | derived from paper.pdf | refs/added.py:237 |
| S`/copied.json` | copy ledger | refs/scan.py:544 record_copy, :529 drop_copies | refs/scan.py:517, refs/check.py:114 | not ignored | refused | not derived | entries removed by refs/scan.py:529 |
| S`/cache/boxes/…` | word boxes and page rotations | refs/pages.py:228, :281, :316 | same, refs/anchoring.py:105 | ignored (gi:30) | refused | derived from paper.pdf | refs/scan.py:865 |
| S`/cache/resolve/` | identifier lookup responses | refs/resolve.py:235 | refs/resolve.py:224 | ignored (gi:30) | refused | derived (network) | never |
| H`/ledger.jsonl` | history: steps and moves | history/ledger.py:431, history/acts.py:87 via Act.log, cli/quilt.py:177 | history/ledger.py:391, scan/alloc.py:24 | not ignored | refused (ag:164) | not derived | never |
| H`/texts/<hex>.{tex,md,bin}` | texts stored by content hash | records/snapshots.py:17, writes.py:56 store | records/store.py:325, render/versions.py:131, writes.py:82 | not ignored | refused | not derived | never |
| H`/NNNN-<name>/` | step folders (versions, landmarks) | history/steps.py:175 write_step | history/ledger.py:156, scan/scan.py:213 | not ignored | refused | not derived | only when an act is rolled back: adopt.py:886, sync.py:848 |
| H`/draft-context/<d>/` | paper files captured for a section draft | section_drafts.py:142 | section_drafts.py:209, :236 | not ignored | refused | not derived | never |
| H`/closed-drafts/<d>/` | a closed draft, frozen | draft_lifecycle.py:40 close_draft | draft_lifecycle.py:170 | not ignored | refused | not derived | never |
| H`/writes.jsonl` | write journal | writes.py:318 | writes.py:322, pending.py:256 | ignored (gi:32)* | refused | not derived | never |
| H`/writes-index.json` | journal index | writes.py:372 | writes.py:360 | ignored (gi:33)* | refused | derived from writes.jsonl | never |
| H`/writes.lock`, `**/*.loom-tmp` | lock and temporary files | writes.py:548, :71, :375 | writes.py:264 | ignored (gi:34-35)* | refused | n/a | temporary files: writes.py:78, :385 |
| B`/manifest.json` | the viewer's manifest | render/publish.py:105, called from render/build.py:626 and render/endpoints/sync.py:160 | viewer, draft_lifecycle.py:81, render/endpoints/review.py:30 | ignored (gi:22) | allowed | derived | never |
| B`/fragments/**` | rendered fragments | render/build.py:220 fragment_path, then publish | viewer, draft_lifecycle.py:108 | ignored | allowed | derived | pruned by render/publish.py:108 (prefixes at render/build.py:619) |
| B`/source/` | each key's LaTeX | render/build.py:201 | viewer | ignored | allowed | derived | pruned (same) |
| B`/spans/` | span sidecars | render/build.py:74 | viewer | ignored | allowed | derived | pruned (same) |
| B`/transcripts/` | transcript pages | render/build.py:345 | viewer | ignored | allowed | derived from inbox.jsonl | pruned (same) |
| B`/files/` | Markdown and notebook bodies | files.py:404 | viewer | ignored | allowed | derived | pruned (same) |
| B`/changes/` | diffs of suggested edits | render/pending.py:516 | viewer | ignored | allowed | derived | pruned (same) |
| B`/svg/` | figures and pictures TeX drew | render/assets.py:30, :67 | viewer, draft_lifecycle.py:115 | ignored | allowed | derived | never |
| B`/compiles.json` | the server's compile state | render/serve.py:880 | render/compiles.py:199 | ignored | allowed | not derived | render/serve.py:985 |
| B`/<doc>/` (paths.py:115) | latexmk output | tex/runner.py:289, called from cli/build_cmds.py:94 and render/serve.py:837 | tex/aux.py:66, render/canon.py:130, render/manifest.py:271 | ignored | allowed | derived | scratch run folders: tex/runner.py:347 |
| B`/<doc>/html/` | TeX4ht HTML | tex/tex4ht.py:381 | render/fromhtml.py:61 | ignored | allowed | derived | replaced whole, tex/tex4ht.py:458-462 |
| B`/closures/` | closure documents and their compiles | cli/build_cmds.py:60, :94, :427 | latexmk | ignored | allowed | derived | never |
| B`/uploads/<sha>/` | PDFs dropped on the viewer | render/endpoints/library.py:146 | same, :154 | ignored | allowed | **not derived** | refs/added.py:240 |
| B`/adoption/<token>.json` | saved adoption preview | adopt.py:645 prepare | adopt.py:693 | ignored | allowed | derived (inspect again) | never |
| B`/incorporation-review/<token>.json` | saved incorporation preview | incorporation_review.py:62 | incorporation_review.py:133 | ignored | allowed | derived | never |
| B`/draft-previews/<d>/` | a section draft compiled in its paper | section_drafts.py:236 | section_drafts.py:257, viewer | ignored | allowed | derived | never |
| B`/compare/` | comparison renderings | render/compare.py:127 | viewer | ignored | allowed | derived | never |
| B`/crops/` | page crops around a mark | records/crops.py:35, :153 | mcp/server.py:266, mailbox.py:390 | ignored | allowed | derived | never |
| B`/agent/<session>/` | MCP results too long to return | mcp/server.py:318 _keep | the agent | ignored | allowed | derived (run again) | never |
| B`/<SESSION>/` (e.g. `s-2026-11-09-0001`) | agent's intermediates | agents only (assets/ai/orientation.md:28) | the agent | ignored | allowed | not derived | never by loom |
| B`/annotations-before-delete.jsonl` | copy of the annotation log made before a delete | records/log.py:81 | nothing | ignored | allowed | not derived | overwritten at each delete |
| B`/ids.lock` | lock for drawing ids | cli/_quilt.py:54 | nothing | ignored | allowed | n/a | never |
| B`/cache/fragments.json` | fragment hash index | render/build.py:628 | render/build.py:453 | ignored | allowed | derived | entries dropped at render/build.py:620-623 |
| B`/cache/snippets/` (+`pictures/`) | TeX snippets | render/snippets.py:264-270 | render/fragments.py:223, render/fromhtml.py:391 | ignored | allowed | derived | `*.failed` removed by render/build.py:450 (`--force`) |
| B`/cache/previews/` | previews of changes | render/changes.py:74 | render/changes.py:49 | ignored | allowed | derived | render/build.py:450 (`--force`) |
| B`/cache/spans/` | span cache | render/build.py:181, :188 | render/build.py:139 | ignored | allowed | derived | never |
| B`/cache/boxes/files/` | word boxes for PDFs outside the store | records/marks.py:314 | same | ignored | allowed | derived | never |
| B`/cache/refound/` | re-found mark positions | records/marks.py:443 | same | ignored | allowed | derived | never |
| B`/cache/svg` | unknown: nothing in this checkout names it | none | none | ignored | allowed | unknown | never |

\* gi:32-35 are written from `paths.HISTORY` rather than the `[quilt] history` setting. A history moved elsewhere therefore has its journal lines unignored, which contradicts paths.py:36.

### (a) Entries written by more than one module
- The annotation log is written by records/log.py:30 and :105 (called from cli/review.py:493-780 and records/carry.py:62) and by writes.py:632.
- The edit log is written by records/edits.py:81 and :533, and by pending.py:560.
- H`/ledger.jsonl` is written by history/ledger.py:431, history/acts.py:87 and cli/quilt.py:177.
- `state.toml` has one writer function, cli/review.py:88, but four callers: cli/review.py:350, review_queue.py:210, incorporation_review.py:188 and refs/proposals.py:608. So paths.py:45 ("written only by `loom accept`") is stale.
- `review-origins.json` is written from adopt.py:725 and sync.py:114.
- `annotation-types.toml` is written by cli/quilt.py:180 and :220, cli/upgrade.py:34, and records/types.py:353 (called from render/endpoints/annotations.py:172).
- `copies/` is written by cli/history_cmds.py:191, adopt.py:998 and agents.
- `run.log` is written by cli/build_cmds.py:53 and mcp/server.py:349.
- `results.json` is written by refs/proposals.py:154, cli/library/agent.py:218 and cli/library/upkeep.py:350.
- `<ck>.tex` is written by refs/build.py:703 and refs/proposals.py:356 and :368.
- `bibliography.bib` is written by refs/scan.py:889 and refs/added.py:99 and :195.
- W`/paper.pdf` is written by refs/fetch.py:329 and refs/scan.py:867.
- `manifest.json` is written from render/build.py:626 and render/endpoints/sync.py:160.
- H`/texts/` is written by records/snapshots.py:17 and writes.py:56, under two naming schemes.

### (b) Entries nothing reads
- `links-removed.jsonl` (refs/links.py:157).
- W`/fetched.json` (refs/fetch.py:416).
- B`/annotations-before-delete.jsonl` (records/log.py:81).
- `sessions/*/attached.json` and `cursors/`: named only at gi:26-27; nothing writes them either.
- B`/cache/svg`: no code names it.
- The five reserved entries (paths.py:51).
- `ids.lock` and `writes.lock`, which are locks only.

### (c) The same content in two entries
- B`/cache/spans/<key>.json` is copied byte for byte into B`/spans/` (render/build.py:139-145).
- A PDF in B`/uploads/` is copied into W`/paper.pdf` when it is filed (refs/scan.py:867). The upload stays until refs/added.py:240.
- H`/closed-drafts/` copies B`/fragments/` and B`/svg/` (draft_lifecycle.py:108-117), and the copy's source (:107).
- `last-seen.json` holds every key's text (records/lastseen.py:3-5).
- B`/source/` holds each key's region of the sources (render/build.py:201).
- B`/transcripts/` re-pages `inbox.jsonl` (render/build.py:345).
- `<ck>.proposed.tex` is rendered from `<ck>.results.json` (refs/proposals.py:322).
- One text can sit in H`/texts/` twice, normalised as `.tex` and raw as `.md` (records/snapshots.py:17-27 vs :35-39).
- H`/draft-context/` copies the paper's files (section_drafts.py:170-190).
- B`/annotations-before-delete.jsonl` copies the annotation log (records/log.py:83).

### (d) Names used for two different things
- `LEDGER` means three files: `state.toml` (paths.py:46), `ledger.jsonl` (history/ledger.py:19) and `copied.json` (refs/scan.py:514).
- `INDEX` means `sessions/index.jsonl` (sessions.py:24) and also `writes-index.json` (writes.py:26).
- `CACHE` means `last-seen.json` (records/lastseen.py:24) and also B`/compare` (render/compare.py:27).
- `LIVE` means a reserved directory (paths.py:55) and also a list of TeX Live mirror URLs (tex/private.py:74).
- `TEXTS` means the `texts/` directory (history/ledger.py:20) and also `texts.json` (tex/tex4ht.py:35).
- "incoming" means files dropped on the viewer (paths.py:56, reserved; real drops go to B`/uploads`, render/endpoints/library.py:105) and also a pull's incoming revision (sync.py:506, :698).
- "snapshot" means the `texts/` store (records/snapshots.py) and also a closed-drafts folder (draft_lifecycle.py:125).
- "boxes" exists under both B`/cache/` and S`/cache/` (records/marks.py:314, refs/pages.py:245).
- "files" means B`/files/` (files.py:28) and also B`/cache/boxes/files/`.
- Folders named after a session exist in two places: B`/agent/<session>/` (mcp/server.py:320) and B`/<SESSION>/` (orientation.md:28).
- "copies" means `.loom/copies/` (paths.py:28) and also the store's copy ledger, `copied.json` (refs/scan.py:513).

### Other things I noticed
- ag:45 says an agent writes in "its session's directory", but ag:158-161 allows all of `.loom/sessions/` except `index.jsonl`, including `active` and other sessions' folders.
- paths.py:13 says `build/` is "deletable at any moment", which is not true for `uploads/`, `annotations-before-delete.jsonl` or the agents' `<SESSION>/` folders.
