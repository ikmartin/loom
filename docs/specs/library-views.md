# What the library's views ask of the backend

**Nothing on this page is built.** It specifies every read and every write the viewer's four views make once the library is rebuilt as [`docs/design/library.md`](../design/library.md) and [`nodes.md`](nodes.md) describe it: what each is given, the shape of what comes back, where the answer comes from, and what it may cost. The views are the sixth round of their mock-up, which the author settled on 2026-11-21, kept at [`docs/design/mockups/library-round-6/`](../design/mockups/library-round-6/README.md) with his marks and the rulings made after it; a screen is cited by its name in the prototype's strip (1, 1 thumbs, 2 choose, 4f, 7a search, 11b), and where a ruling changed a screen, this page follows the ruling. The backend builds to this page, and the viewer is built against fixtures shaped as it says until each read exists. About a node file `nodes.md` wins; about what the viewer is sent, this page. A paragraph that begins **Open** marks a place where the mock-up shows something the design or the node format cannot yet answer, with a proposal; §9 lists them by number.

## 1. Ground rules

Two principles of the design (`library.md`, "Scale") govern every read.

- **The viewer is sent what it is showing, and no more.** Nothing of the rebuilt library is in the manifest. A view asks for what is on its screen, a list of works, a work's outline, a result and what it uses, the rows of one Review list, and is sent that; what is folded or scrolled away is asked for when it opens.
- **Nothing is made before it is asked for.** A work's survey, its page text and word boxes, a thumbnail, a node's place on its page, a node drawn by TeX: each is made the first time a read needs it and kept by the hash of what it was made from, so it is made once.

Three of the views' rules reach the backend. No id and no command is drawn, so every answer carries the words a row is drawn with beside the ids it is addressed by. Nothing not yet checked reads as checked, so every status is computed from the evidence records on the node's current hash, and none is stored. No control sends the person to another view, so every read is answered for the view's own place: a result that points into another work opens that work in a Library tab, and a document is shown over Review, not in Docs.

**Sizes.** Costs are stated at the sizes in use: a library of 300 works; a work of 60 results; a Review of 30 to 40 rows; a web of some thousands of nodes, the drafts' results and the library's together. A cost is a budget measured with `scripts/bench` (never a stopwatch inside a test, `docs/contributing.md`), and, where one can be stated, a structural claim a test holds: what the read must not open or run.

**Sources.** Each answer says where it comes from:

| source | what it is |
| --- | --- |
| index | the node index loom derives from `.loom/library/nodes/` and the tag log: SQLite with full-text search, under `.loom/cache/` |
| evidence | records of acts on nodes, each naming a node's hash: digested (by whom, how), transcription verified, Lean observed, attested; corrections proposed; requests for a paper |
| scan | the scan of the person's documents the publisher already holds: their results, labels, numbers, citations, edges, fragments, the cite labels of their last compile (`tex/aux.py`, `read_cite_labels`) and the acceptance ledger |
| tasks | agent tasks: what was asked of an agent, and whether a session is working on it |
| store | the stored documents, by hash, and what is derived from them when first asked: a TeX source's survey (§3.2), page text, word boxes, thumbnails, nodes' places |
| annotations | the annotation log: notes, marks drawn on pages, agents' questions |
| changes | the change ledger and the compile state (`write-api.md`, `changes` and `compiles`) |
| lean | what loom observed when it ran Lean, fenced (`library.md`, "Formalization"); not built before the formalization phase |

## 2. Conventions

**Transport.** A read is `POST /_api/<name>` with a JSON body and a JSON answer, as `locate` and `compare` are: a handler in its family's module under `loom/src/loom/render/endpoints/`, listed in that module's `READS`, so the publisher does not rebuild after it, with the token and the checks every request to `/_api` takes (`write-api.md` §3), and a case in `cases_<family>.py`. The names follow `reserved.md`'s prefixes: `library-` for the library, `review-` for Review, `formal-` for formalization; the Web's reads take a prefix of their own, `web-`, and the notes' read is `notes`, which `reserved.md` gains when they are built. Each is named in `GET /_api`'s `capabilities` once it is served, and a viewer that does not find one draws nothing that needs it (`write-api.md` §1). Rendered content is never in an answer (`write-api.md` §2): a draft's result is drawn from its fragment, whose path an answer gives, a change from fragments marked as `compare` marks them, and a library node from its LaTeX, which the viewer draws (§3.4).

**Bytes.** What never changes once made is a `GET` at a content address, as `/build/` is: no token, since pdf.js and an `<img>` fetch by URL and send none, served with `Cache-Control: immutable` and, as everything outside the viewer's bundle is, `Content-Security-Policy: sandbox` and `X-Content-Type-Options: nosniff` (`write-api.md` §3). A hash in an address is its 64 hexadecimal digits, without the `sha256:` an answer's field carries. `GET /_api/library/pdf/<hex>` is a stored PDF by its `pdf` hash; `GET /_api/library/thumb/<hex>.png` its first page (§3.1); `GET /_api/library/drawn/<node-hex>-<macros-hex>.svg` a node drawn by TeX, named by its own hash and its macros node's (`none` for a work with none), drawn only through an `<img>`, since it is TeX's output from a source nobody at loom wrote (§3.4).

**Freshness.** Every answer carries `gen`, the library's generation: a number the publisher raises whenever anything a read on this page answers from changes, a node file, the tag log, an evidence record, a task, a mark, an annotation, a stored document, or what the scan gives these reads (results, labels, numbers, citations, edges), but not a publish that changes none of these, so a compile does not set every open view reading again. The stream (`GET /_api/stream`) gains an event `library` carrying `{"gen": N}` each time it is raised. A view asks again for what it shows when it hears one; a read given `"since": N` while the generation is still N answers `{"gen": N, "unchanged": true}` and does no other work. A node file an agent's command writes outside the publisher raises it too, so the publisher's watcher follows `.loom/library/` and `.loom/records/`. The obligations in `README.md` that make the manifest the viewer's only index and its change the only signal widen, once this is built, to these reads and this event.

**Names.** `ref` is a reference's id; `node` any node's id; `key` a draft result's key as the manifest names it, its id, or the qualified key of one with no label; `result` either a node or a key, since a library stem and a draft's id are minted from one namespace and never equal; `item` a result of a TeX source's survey (§3.2); `doc` a document's path; `row`, `mark`, `task`, `question`, `correction`, `citation`, `observation` and `undo` opaque ids a write is given back. Ids are for addressing and are never drawn. Whatever the viewer draws comes with its words:

- a work: `short` ("Smith 2024", "Halberd and Ravel 2021", "Vance et al. 2023"; for an entry that names no author, its title, which for a dropped file is the file's name), `title`, `authors` (surnames, in order), `year`;
- a result: `name`, its taxon's word and its number as its source prints it ("Lemma 3.2", "Definition 2.1"; the word alone when unnumbered), and `title`, its name in the source ("Test lemma"), absent when it has none;
- a document: its path, drawn as its file's name, as the file tree draws it.

A title and authors come from the reference's BibTeX body decoded: braces dropped, accents made characters (`Kova{\v{c}}` is "Kovač"), mathematics kept between `$` for the viewer to draw. Words that are loom's own, a hover card, a legend, an empty state, a confirmation, a task's sentence, are never sent: they are the viewer's, in `arras/src/lib/words/`, a file a view.

**Status.** One vocabulary on every surface (`library.md`, "The views"), two marks a result. A read passes on the status `evidence.md` §5 computes, and the viewer draws it in round six's marks; nothing here computes a status of its own:

| field | values | from |
| --- | --- | --- |
| `paper` | `evidence.md` §5.2's `reading`, `stub`, `unchecked` or `matches`, or `marked` for a place the person marked to digest and nothing read from yet; null for a draft's result and for a survey item not digested | evidence, annotations |
| `lean` | `{"lean", "role", "waiting_on"}` as `evidence.md` §5.2 gives them, `lean` one of `none`, `rerun`, `failed`, `unattested`, `changed`, `waiting`, `formalized` and `role` one of `proved`, `unproved`, `assumed`, `defined`; null while formalization is off for the quilt | evidence |

The viewer draws `matches` as round six's filled circle ("matches the paper"), `unchecked` as the amber ring ("not compared yet"), `stub` as the dotted ring ("not read") and `marked` as the flag ("marked by you"); and `lean` as the filled diamond where it is `formalized` ("formalized") or the half-filled one where it is `formalized` with the role `assumed` ("assumed in Lean"), the amber diamond where it waits on the person: `unattested`, `changed`, or `waiting` with some `why` in `waiting_on` `unchecked` or `unattested` ("Lean accepted, not attested"); and the outlined one otherwise, `waiting` on reading alone among them ("not formalized"). Where a result itself is shown, the Web's focus card, Review's opened row for it and the formalize panel, `waiting_on` is said in words ("not formalized yet: Lemma 2.1 of Okafor 2022 is not compared with its paper"); in a list it is the mark alone. The words are the viewer's; "matches the paper", and "not compared yet" before it, were decided with the author for the person's yes to a transcription. `formalized` holds only when nothing the result rests on in Lean waits on the person (`library.md`, "Digesting and checking"), which `evidence.md` computes as `waiting`.

**A result in a list.** Wherever results are listed (the Web, a neighbourhood, a node's uses, the formalize panel), a result is sent as `ROW`:

```json
{"result": "tq-00K3", "name": "Lemma 3.2", "title": "Test lemma", "taxon": "lemma",
 "source": {"ref": "tq-00A1-ref", "short": "Smith 2024"}, "paper": "unchecked", "lean": null}
```

`source` is `{"doc": "drafting/main.tex"}` for a draft's result. A work's outline is the exception, since it also lists what is not yet a node (§3.2), and so is a Review row (§4.2). A work's results are in paper order: by the place the placement records give, once digesting fills them; until then by the node index's rule, number read naturally (3.2 before 3.10 before A.1) before pages, since a stub has a number and no page (ruled with the node store).

**Who writes.** Every write this page adds is the person's and is refused to a declared agent with `author-only` (403), as the intake's are (`write-api.md` §6); the built writes it uses keep their own rules. An agent changes the web by its own commands (`library.md`, "What an agent can do to the web"). Errors are the write API's: a name that is not there answers 404 with `no-such-` and what it named (`no-such-ref`, `no-such-node`, `no-such-result`, `no-such-row`, `no-such-task`), a request refused on its merits 400, a conflict with the quilt's state 409.

## 3. The Library

### 3.1 The works list (1, 1 thumbs, 1 add, 1 digest, 1c, 1d)

**Drawn.** In the column, the filters All works, Used in your drafts, Not yet compared and No document. Above the list, a search by title or author, `list` and `thumbnails`, `add work…` and `digest…`. The list's columns are Title, Authors, Year and Digested ("11 of 62 · 2 compared"; "3 · 0 compared" for a work held only as a PDF), and from the columns menu Loom has and Used in; any column sorts. A click opens a work in a tab; ⌘-click selects without opening; on a row, `digest…` and a menu of `open its source ↗`, `edit its entry…` and `delete`. Thumbnails draw each work's first page, or "no document".

**Read `library-works`.** Given `{"doc"?: DOC}`; `doc` only from the Docs picker (§6.1). Answers every work:

```json
{"gen": 41, "works": [
  {"ref": "tq-00A1-ref", "short": "Smith 2024", "title": "Widgets and their bounds", "authors": ["Smith"], "year": "2024",
   "holds": {"pdf": "sha256:41b7…", "tex": true},
   "digested": {"statements": 11, "of": 62, "compared": 2, "stubs": 1},
   "used_in": ["drafting/bounds.tex"],
   "link": "https://arxiv.org/abs/2401.01234v2",
   "version": null, "lookup": null, "cited_as": null}
]}
```

- `holds.pdf` is the stored PDF's hash, which addresses its thumbnail and its document, or null; `holds.tex` says loom holds the work's TeX source.
- `digested` is null when nothing of the work is digested. `statements` counts the work's statements that are not stubs, `compared` those whose `paper` is `matches`, `stubs` its stubs, and `of` the results its TeX source holds, from the survey (§3.2), null until a survey exists.
- `used_in` is the documents that cite the work, by an entry key their bibliography resolves to its reference.
- `link` is the work's own page for `open its source ↗`: the entry's `url`, else its DOI's resolver, else its arXiv page; null when it states none.
- `version` is Open 3; `lookup` is null or `{"state": "looking"|"unconfirmed", "identifier": "arXiv 2209.01234v2"}` (1d, below); `cited_as` is null here and is the picker's (§6.1).

Filtering, sorting and searching are the viewer's, over the rows it holds: "Not yet compared" is `compared` less than `statements`; "No document" is no PDF and no TeX source.

From: index (the references and a count of nodes by `source`), evidence (`compared`), scan (`used_in`), store (`holds`, `of`). Cost: one answer of 300 rows, about 60 KB; one grouped query on the index and one pass over the scan's citations, 50 ms warm. It opens no node file, no PDF and no source, and makes no survey.

**Read `GET /_api/library/thumb/<hex>.png`.** The PDF's first page, 360 pixels wide (twice the card's width), made by poppler the first time it is asked for and kept as `.loom/cache/library/thumbs/<hex>.png`. The viewer asks for a card only as it scrolls into view, sixty at first. Cost: the first ask about 0.2 s and 25 KB, then a file read; 300 works keep under 8 MB.

**Open 2.** `of` for a work never opened. "11 of 62" needs the work's survey, which is made when the work is first opened or digested, never for the list. Proposal: a work whose source has no survey yet shows its count without "of".

**Open 3.** "Arden 2025 · second version" (1). Each version is a reference of its own and that two are one paper is a `same` record (`nodes.md` §7). Proposal: `version` is the entry's own `version` field when it has one, else `2` for the later of two references a `same` record joins, which the viewer's words draw as "second version"; nothing is inferred from titles alike.

**Writes.**

- `add work…` opens a panel with `choose files…`, a field for an arXiv number or DOI, and "or drop files anywhere in loom" (1 add). A file chosen goes as a dropped one does (§3.5). A pasted identifier is `library-take` with `{"items": [{"text": "2209.01234"}]}`.
- `digest…` above the list offers `results my drafts use, in every paper (14)` and `everything in the papers I select`; a row's `digest…` is the work's (§3.2). The counts are `library-digest-scopes`; the acts are `library-digest`.
- `open its source ↗` opens `link` in the person's browser; nothing is written.
- `edit its entry…` is `library-entry` (§7). **Open 4.** Round six draws the item and not the editing. Editing rewrites the reference's body and so its hash, which stales every record naming the reference (the inventory's question 20). Proposal: the entry opens as text in the work's tab, and a change rewrites the body; an attestation's closure takes in the statements and definitions a statement uses and leaves references out, since an entry's fields are not what a statement means, so editing an entry stales no attestation.
- `delete` is `library-delete`, answered with an `undo` the column's message offers ("Deleted Smith 2024, with its results and notes"), which `library-restore` takes. Ruled with the spec's merge: deleting a work is never refused. It is one act with one undo: the reference, its macros node, its nodes, and the person's notes and marks on the work go together and `library-restore` puts them back whole; what cites the work then reads as a result whose work is gone (`library.md`, "What this replaces"), and the evidence records stay, naming hashes no file has. How a node of another work that uses one of its nodes stays a valid file (`nodes.md` §11, check 7), and whether gathering makes the reference again from a draft's bibliography, is the references lane's to settle in `nodes.md`.

**The empty library (1c).** A box: "Drop papers here to start your library", "PDFs, TeX sources, or a .bib file", and the same panel as `add work…`. **Open 6**, closed: the intake takes a dropped `.bib`, an entry a row, and a TeX source, a `.tex` file or an archive, besides PDFs and pasted identifiers (`write-api.md` §6); nothing is matched by title or author.

**A work found while the network is off (1d).** Right after a drop, the row reads "arXiv 2209.01234v2 · look it up on arXiv this once?" with `yes` and `not now`; otherwise, "details unconfirmed · look up". The publisher sends `lookup.state` `unconfirmed` for a reference made from an identifier with no look-up, and `looking` while one runs; whether to ask "this once?" is the viewer's, which asks only right after a drop of its own whose row said `unconfirmed`. `yes` and `look up` are `library-look-up`; `not now` writes nothing. **Open 7.** What makes a reference unconfirmed is not a field of its file, which holds no status. Proposal: the intake's record of the act that made the reference says how its details were found (`found_by`, §3.5) and whether they were looked up; the reference reads `unconfirmed` until a look-up's record follows.

### 3.2 A work's tab (2, 2 digest, 2 choose, 3)

**Drawn.** In the column: the title; "Smith · 2024 · PDF and TeX · entry ▸", which shows the BibTeX entry as text; `digest…`; then Contents, the paper's sections with their pages and the results under the section they stand in, each with its marks. A click on a section or a result goes to its place on the page. For a work with its TeX source the outline lists every result of the source, digested or not; one not digested has no mark. For a work held only as a PDF, "Contents, from the PDF's outline", with the person's marks under the section their page falls in, then "Cited, not yet placed": stubs with no place, "not read · locate in PDF", which opens the reader at loom's best guess (`library-find`, §6.2), where the person marks the place (a `to-digest` mark naming the stub, §3.3). A work with no document: "Loom has this work's entry and no document. Drop its PDF anywhere to add it." and `open its source ↗`.

**Read `library-work`.** Given `{"ref": REF}`:

```json
{"gen": 41, "ref": "tq-00A1-ref", "short": "Smith 2024", "title": "Widgets and their bounds", "authors": ["Smith"], "year": "2024",
 "holds": {"pdf": "sha256:41b7…", "pages": 31, "tex": true},
 "entry": "@article{Smi24,\n  author = {Smith, Jane},\n  …\n}",
 "link": "https://arxiv.org/abs/2401.01234v2",
 "outline": {"from": "tex", "state": "ready",
   "sections": [{"section": "s3", "number": "3", "title": "Bounds", "page": 12, "level": 1}],
   "items": [
     {"item": "def:radius", "node": "tq-00K1", "name": "Definition 3.1", "title": "Radius", "taxon": "definition", "section": "s3", "page": 12, "paper": "unchecked", "lean": null},
     {"item": "i41", "node": null, "name": "Remark 3.5", "taxon": "remark", "section": "s3", "page": 13, "paper": null, "lean": null},
     {"item": null, "node": "tq-00K9", "name": "Lemma 8.2", "taxon": "lemma", "section": null, "page": null, "paper": "stub", "lean": null}]},
 "marks": [{"mark": "m-7f3a", "page": 6, "words": "Lemma 2.4. Let ⪯ be a median order…"}],
 "unplaced": [{"node": "tq-00C2", "name": "Theorem 2.3", "paper": "stub"}]}
```

- `outline.from` is `tex` when loom holds the source, `pdf` when it holds only a PDF, and null with no document. For `tex`, `sections` and `items` come from the survey: an `item` is a result of the source whether or not it is digested, named by its label, else by `i` and its place among the source's results (stable for one source); `node` is the node made from it, or null; a stub of the work that the survey does not hold comes last with `item` null ("not found in its TeX source"). For `pdf`, `sections` is empty: the viewer reads the PDF's own outline from the document it already has (pdf.js), and places the work's nodes that have a place, and its marks, under the section their page falls in; `items` then holds those nodes, with `item` null.
- `outline.state` is `ready`, or `reading` while the survey's compile runs (below).
- `marks` are the person's marks to digest on this work, annotations whose `purpose` is `to-digest` (§3.3), that nothing has been read from yet. `unplaced` is the work's stubs with no `pages` and no place.

From: index, evidence, store (the survey, the stored documents), annotations. Cost: about 15 KB for a work of 60 results; 10 ms once the survey exists. The first open of a work with a TeX source makes its survey.

**The survey.** What a TeX source holds, read once for each source and kept under `.loom/cache/library/survey/<hex>.json` by the source's hash: its sections (number, title, level), its results (taxon, number, title, label, section, the span of the text in the source), each result's page, and the source's definitions. It is what digesting extracts from (`library.md`: "With the TeX source loom knows every result exactly, and can show the ones not yet digested"), so digesting an item is writing its node, not reading the source again. It is made in two steps. Parsing the source, about a second for a paper of 60 results, gives sections, results, taxa, titles, labels, and numbers emulated from the source's counters as `digest/counters.py` emulates them today; the outline answers with these at once, `state: "reading"`, `page` null, and each `name` from an emulated number. A compile of the source, whose `.aux` gives the numbers it prints and the pages, runs as a job, one at a time as library runs do today, and can take minutes; when it is done the outline is `ready` and a `library` event says so. A node's `number` is what the source prints, so `library-digest` on items of a survey still reading answers with its `job` and writes the nodes when the compile is done. Made when the work is first opened or first digested, never for the list; the file under 100 KB.

**Open 8.** Matching the survey to nodes. A node digested earlier is matched to its item by its `label`, else by its printed number and taxon; a stub by printed number. A stub whose number the source does not print is "not found in its TeX source" (4f), most often a citation of another version's numbering (`library.md`'s open question on versions). Proposal: as said, and a stub not found stays a stub; it is never matched by guess.

**Open 9.** A page before the compile. Proposal: until the compile has run, an item's `page` is null and a click on it goes to its section's page, the section found by its heading in the page text; this is navigation, drawn as no mark and written into no node.

The order of a work's nodes is the one §2 gives, ruled with the node store; a node of a work held only as a PDF stands under the section of the PDF's outline its page falls in.

**Read `library-digest-scopes`.** Asked when a `digest…` menu opens. Given `{"ref": REF}` for a work's menu, answers `{"gen", "tex": true, "pdf": true, "used": 2, "marked": 0, "all": 51}`; given `{"all": true}` for the list's, answers `{"gen", "used": 14}`. `used` counts the results the drafts use, through their citations, that are not yet digested (the stubs, and for a work with a survey its items they cite); `marked` the work's marks not yet read; `all` the items of the source not yet digested, or for a work held only as a PDF its page count (2 digest draws "everything in Okafor 2022 (24 pages)"). The count of papers selected is the viewer's. From: scan, index, the marks, the survey. Cost: 10 ms; `all` for a work with a source and no survey starts the survey, and the menu draws that item without its count until the answer comes.

**Write `library-digest`.** `{"refs": [REF…] or "all", "scope": "used"|"marked"|"chosen"|"all", "chosen"?: [ITEM or NODE…]}`, answered `{"gen", "made": 3, "tasks": [TASK…], "job"?: ID}`. `chosen` names the items chosen and, for a stub the survey does not hold, its node. From a work's TeX source loom writes the nodes from the survey: each with an id minted, the stubs its text points at in the same work not yet read, and a record that it was digested mechanically from TeX; a stub chosen that the survey does not hold has nothing to be read from, and stays. A work held only as a PDF gets one agent task (§4.3, `agents`), which waits in Review under Waiting for an agent. `job` is there when the survey's compile must first be done. The menu's foot line, who does the work, is the viewer's words chosen by `holds`. `results I choose…` is the viewer's: checkboxes in the outline on items not digested and on stubs, then `library-digest` with `scope: "chosen"` (2 choose). Cost: writing a node from the survey is a few milliseconds; sixty under a second, under the library's lock, the index following the files that changed. Refused: `no-document` (409) for a work with neither document.

### 3.3 The reader and the digest overlay (2, 3; the same reader in Docs)

**Drawn.** One PDF reader, the same component in the Library and beside a draft in Docs: today's toolbar (Annotate, zoom, the page box, `view`) and annotation tools, its marks and notes. In the Library, `view` also holds "digest marks", the overlay: beside each node of the work on the page, a chip with its paper mark and number, and a bar down the result's margin; a click selects the node and opens it beside the page (§3.4). On a selection, the popup `mark to digest · highlight · note · ask an agent…` (3).

**Reads.**

- The PDF: `GET /_api/library/pdf/<hex>`. pdf.js reads it whole, as today: a paper of 30 pages is 0.3 to 2 MB. **Open 11.** A book of several hundred pages would show its first page late. Proposal: this address answers `Range` requests, so pdf.js fetches the pages in view; not needed at the sizes in use.
- The person's annotations on the work, as today, from the annotation log, keyed by the reference's id (Open 12, closed).
- **`library-places`.** Asked only while the overlay is on, for the pages in view and their neighbours. Given `{"ref": REF, "pages": [12, 13]}`, or `{"node": NODE}` for one node's place (a use followed into another work, a crop in Review, "open at its place"). Answers:

```json
{"gen": 41, "pdf": "sha256:41b7…", "places": [
  {"node": "tq-00K3", "name": "Lemma 3.2", "number": "3.2", "page": 12, "rects": [[72.0, 388.5, 540.0, 470.2]], "paper": "unchecked", "lean": null},
  {"mark": "m-7f3a", "page": 6, "rects": [[70.1, 352.0, 541.3, 401.8]], "paper": "marked"}]}
```

`pdf` is the document the rectangles are on, which the reader opens. A node's place is found again, never stored in its file (`nodes.md` §10): its text matched against the words of the page its `pages` names, by the normalisation a quotation is checked under; a stub's place is the mark that names it (below). A node with no place found has no entry. A mark's place is its annotation's, placed as every annotation on a PDF is. Rectangles are in points from the page's top left, as `annotate`'s are. Kept by the node's hash and the PDF's hash. From: index, store (word boxes), annotations. Cost: on the first ask for a page, its word boxes (poppler, about 50 ms a page, kept by the PDF's hash) and a match for each node on it; then 5 ms and 2 KB a page.

The overlay is off until a person turns it on, and the viewer remembers it once they have (ruled with the spec's merge, as `library.md` says; round six draws it on). The backend is the same either way, since places are asked for only while it is on.

**Writes.**

- `mark to digest` is an annotation (ruled with the spec's merge): `annotate` on the work's page, with the same record and the same placing as a highlight on a PDF, so that it is found again on a changed PDF by the one mechanism, and with a purpose of its own, which the lists of notes leave out: `annotate` takes `purpose: "to-digest"`, an optional field of the annotation apart from the person's `type` and from the event's own `kind`, which says who wrote it (built by the evidence lane, `manifest.md` and `evidence.md`); an annotation with no `purpose` is an ordinary note. The column's message ("Marked on page 7, to digest") offers `undo`, which is `delete`. A mark may name the stub whose place it is. Asking for a mark to be read makes a task that names it (`review-task`).
- `highlight` and `note` are `annotate`, as today.
- `ask an agent…` is `review-task` with `{"what": "ask", "on": {"ref", "page"}, "quote", "text", "from", "words": ""}` ("Added to agent tasks: a question on these words"). The field for the question is not drawn in round six; the viewer opens one under the popup.
- The reader reports the person's place with `here`, as today, its item the reference.

### 3.4 A result beside its page (2)

**Drawn.** Beside the page: "Definition 3.1 Radius", "page 12 · extracted exactly from the TeX source", `rendered | plain`, the statement, "Does loom's copy match the paper?" with `yes, it matches` and `no, it differs…`, its Lean mark, and "uses", each use with its mark; a use in another work opens that work in a Library tab at the use's place. An item not digested: "Not digested. Loom has the TeX source, so it can extract this exactly, now." and `digest it`; a stub: "Known from the TeX source and not read." and `digest it`.

**Read `library-node`.** Given `{"node": NODE}`, or `{"ref": REF, "item": ITEM}` for an item of a survey not digested; `"brief": true` leaves out `uses`, `mentions`, `proofs` and `used_by`, for a card (§6.2). Answers:

```json
{"gen": 41, "node": "tq-00K3", "hash": "sha256:…", "name": "Lemma 3.2", "title": "Test lemma", "taxon": "lemma",
 "work": {"ref": "tq-00A1-ref", "short": "Smith 2024", "pdf": "sha256:41b7…"}, "pages": "12",
 "digested": {"how": "extracted", "by": "loom", "at": "2026-11-20T14:02:11Z"},
 "paper": "unchecked", "lean": null,
 "body": "Let $W$ be a widget (Definition~\\ref{tq-00A4}). Then\n\\begin{enumerate}…",
 "macros": {"node": "tq-00A1-macros", "hash": "sha256:…", "body": "\\usepackage{amssymb}\n\\newcommand{\\Wid}{\\mathcal{W}}\n\\DeclareMathOperator{\\diam}{diam}"},
 "points": {"tq-00A4": {"name": "Definition 2.1", "number": "2.1", "paper": "matches"},
            "tq-00K3-eq00": {"number": "3.3"}},
 "uses": [ROW], "mentions": [ROW],
 "proofs": [{"node": "tq-00K3-proof00", "source": null, "pages": "12-13", "pointer": false}],
 "used_by": {"docs": ["drafting/bounds.tex"], "nodes": 1}}
```

- `digested` is the latest `digested` record on this very text, its `how` as `evidence.md` §3.1 has it (`extracted` from the TeX source by loom, `transcribed` from the pages or `read` from a source by an agent, `corrected` by an agent, `written` by a person) and `by` the name of who did it; null for an item not digested.
- `macros` is the work's macros node, which the viewer applies to this node alone; null when the work has none.
- `points` gives, for every id and anchor the body points at, what is drawn in its place: the rendered view draws `\ref{tq-00A4}` as "2.1" and `\eqref{tq-00K3-eq00}` as "(3.3)", and the plain view draws each pointer as a chip with the name and the target's mark. A use in the same work has `source` null in its `ROW`.
- For `{ref, item}`: `{"gen", "name", "title", "taxon", "pages", "work", "digested": null, "paper": null}`, from the survey.

From: index (the node, its edges, its proofs, what uses it), evidence (`digested`, `paper`, `lean`), the node's file (its body), the macros node's file, store (the survey, for an item), scan (the drafts that use it). Cost: two file reads and index lookups, 5 ms, under 8 KB.

"(3.3)" is the number the source prints for a labelled display: the node's header holds it in `anchors`, a table from each anchor defined in its body to the number its source prints (ruled with the node store), and `points` passes it on.

**Open 16.** Ids in the plain view. `library.md` says the plain view shows "the ids it points at"; the rule for the views is that no id is drawn, and round six puts the id in a chip's tooltip. Proposal: the chip names the result and draws its mark; the id appears nowhere, since the chip already shows what the pointer points at.

**Drawing a node.** The viewer draws a node in the browser (`library.md`, "Scale"): its text-mode LaTeX (paragraphs, emphasis, lists, displays) by a small converter of its own, and its mathematics by MathJax, which the viewer already loads, with the work's macros. What it cannot draw, a diagram or an environment it does not know, it asks the publisher for: `GET /_api/library/drawn/<node-hex>-<macros-hex>.svg` is that node typeset by TeX with its work's macros node, made on first ask and kept by both hashes, shown through an `<img>` (§2, "Bytes"). `library.md` requires the browser's drawing to be compared with TeX's on real statements before anything rests on it.

**Writes.**

- `yes, it matches` is `library-check` with `{"node", "hash"}`: a record that the person verified the transcription of the text with that hash. Refused `changed` (409) when the node's hash is no longer `hash`, since the person compared a text that has changed since.
- `no, it differs…` is drawn in round six only as a message ("Correct it here, or ask an agent to"). **Open 17.** Proposal: it opens the plain text for editing in the panel, and a change is `library-correct` with `{"node", "hash", "body"}`: the person's correction, written as the node's new body under `nodes.md` §11's checks, with a record of the act, and checked at once, since the person has just read it against the page; or `ask an agent to` is `review-task` with `{"what": "correct", "on": {"node"}, "text", "from", "words": ""}`.
- `digest it` is `library-digest` with `scope: "chosen"` and the item.

### 3.5 The drop of a paper (1b, 4d, and the column's message)

**Drawn.** A file dragged over any view covers it: "Drop to add to your library.", and only while papers wait for their file, "If it is one of the 3 papers waiting to be fetched, it is attached to that paper." The drop adds it; the column's foot says what happened, with `undo` ("Added Gadget towers, Halberd and Ravel 2021, found by its arXiv number, with its TeX source."); the view does not change, and in the Library the new row is selected.

**Reads.** The number of papers waiting: `review-counts`, its `kinds.fetch` (§4.1), asked when a drag enters the window.

**Writes.** `library-receive` for each file, then `library-take` with `{"items": [{"incoming"}…]}`, or `{"incoming", "for": REF}` for a file dropped on a work's row (in the Library's list, or in Review under Papers to fetch), answered with rows (`write-api.md` §6); the intake's `added` row now makes a reference. For the message, an added row carries `ref`, `short`, `title`, `found_by` (`arxiv`, `doi`, `isbn`, `entry`, `row`, or `none`: what it was known by), `tex` (loom holds or fetched the source) and `unconfirmed` (made from an identifier with no look-up). `undo` is `library-undo`.

Ruled with the spec's merge: nothing is matched by title or author. A dropped file joins a paper that waits for it, or any work, by the identifier it states, or by being dropped on that paper's row; otherwise it is a new work, and the intake asks its one question only where one file answers to several papers.

**Open 19.** The intake's `question` row ("is this one of these works?") and its `cannot` row have no drawing in round six. Proposal: each is a column message, the question with its candidates as choices and "a work of its own", the cannot with its reason; the `arriving` rows keep them across a reload, as today.

**Open 36.** A drop on a quilt that has not said whether loom may use the network: `library-take` refuses it `network-unasked` (409) and the files wait (`write-api.md` §6). Round six draws no such question, and the viewer asks it nowhere. Proposal: the column's message asks it once ("May loom look papers up on the internet?"), the answer is saved with `settings-save` (`library.online`), and the take is made again.

## 4. Review

### 4.1 The column (4, 4 hover)

**Drawn.** "Waiting for you"; `Everything` with its count; the kinds in alphabetical order, each with its count; a rule; `Waiting for an agent` with its count; a rule; "Drafts", each draft with the count of what waits for you that concerns it. A hover card on each is the viewer's words. Ruled with the spec's merge, beyond round six: one quiet line at the column's foot, `Record`, opens today's Record pages inside Review, read as today; and an incoming pull, where a quilt has one, shows under the kinds as today's component draws it, from the manifest's `incoming`. Problems are on their document, in Docs.

**Read `review-counts`.** Given `{"doc"?: DOC}`; Everything, the kinds and the agents are counted for that draft where one is given, as the column shows them while a draft is chosen, and the drafts always each:

```json
{"gen": 41, "everything": 29,
 "kinds": {"accepted-changed": 6, "questions": 2, "attested-changed": 2, "cited": 4, "check": 5, "attest": 2, "fetch": 3, "edits": 5},
 "agents": 6,
 "drafts": [{"doc": "drafting/main.tex", "n": 20}, {"doc": "drafting/bounds.tex", "n": 9}]}
```

A row counts once whatever it holds (Smith 2024's nine results to check are one row); a draft counts the rows that concern it, and a row may concern two. From: what `review-list` gathers, without its bodies. Cost: 20 ms, under 1 KB. The drop cover reads `kinds.fetch`, and the column's foot, which is the frame's, reads the task a session is working on from `review-list` with `kind: "agents"`.

### 4.2 The list (4)

**Drawn.** Under `Everything`, a group for each kind, folding, with its count, then a rule and `Waiting for an agent`, folded; a kind alone when the column chooses it; a draft filters each. A row draws its marks, its words, a quiet line at the right and a chevron, and opens in place. The groups under `Everything` are ordered by who is waiting, as ruled after round six drew them alphabetically: agents' questions, papers to fetch, cited results to digest, digested results to check, Lean statements to attest, then the rest in the column's order (accepted results that changed, attested results that changed, proposed edits). The column stays alphabetical.

**Read `review-list`.** Given `{"kind": "all"|KIND|"agents", "doc"?: DOC}`; answers `{"gen", "groups": [{"kind": KIND, "rows": [RROW…]}]}`, the groups in the order above. An `RROW` is `{"row", "kind", "docs": [DOC…]}` with the fields of its kind (§4.3) and no body; a field that names a kind of its own is never called `kind`, which is the row's. A row's id is made from what it is about (`check:tq-00A1-ref`, `edits:c-1a2b3c4d`), so it stays the same while that thing waits and an open row stays open across a new generation. Within a kind: what a draft rests on first, then by work and paper order; questions and tasks oldest first. Cost: 30 to 40 rows, under 20 KB, 50 ms; it opens no PDF, runs no TeX, and reads a node's body only where a row's words need one.

**Read `review-row`.** Given `{"row": ROW_ID, "node"?: NODE}`, asked when a row opens, and with `node` when a cited result's `locate…` opens; answers `{"gen", "row", …}` with the body of its kind (§4.3). Cost: 30 ms and under 30 KB, plus a page's word boxes the first time a crop needs them.

**The evidence lane's spec governs Review's data.** Which rows each kind holds, and the shapes of questions, tasks and requests for papers (its log of asks, `.loom/records/asks/log.jsonl`), are the evidence lane's, written in `docs/specs/evidence.md` (ruled with the spec's merge); where that page and this section disagree about them, that page wins and this one is corrected in the same change. This section says what each row needs in order to be drawn. Its kinds' names are `evidence.md`'s; its ask kinds are this page's (`read`, `digest`, `ask`, `correct`, `restate`, `which-result`, `formalize`), with `question` and `paper` for an agent asking the person.

### 4.3 The kinds

Each kind below: what its row draws, the fields it needs, its body, its writes. The names are the kinds' keys, never drawn. A statement drawn in a body is a fragment, by its path; a change is drawn from fragments marked as `compare` marks them.

**`accepted-changed`: Accepted results that changed (4).** A row: "main.tex · Lemma 3.3". Fields `{"key", "name", "doc"}`. Body: `{"statement": {"fragment"}}`, the block's fragment with what changed since it was accepted merged in and marked as a pending change's words are (`span.change[data-side]`, old words struck and new ones marked), which is how round six draws it; and `accept`. Write: `review-accept` with `{"reviewer", "keys": [KEY]}`, as built. From: scan, the acceptance ledger; which of its `unresolved` rows are listed is `evidence.md`'s.

**`questions`: Agent questions (4 question).** A row: "Claude Code asks, digesting Okafor 2022: your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?". Fields `{"task", "by": "Claude Code", "on": {"digesting"?: SHORT, "ref"?, "short"?, "page"?, "node"?, "doc"?, "key"?, "name"?}, "text", "choices": ["both", "only the proposition"]}`: `task` the ask's id; `on` the ask's place with the words it is drawn with, and `digesting` the work a digest ask names that the asking agent's session had taken when it asked, where there is one. The row's words are built from `on` ("digesting Okafor 2022", "on main.tex, Theorem 3.4", "on Okafor 2022, page 7"). Body: none read; the choices as buttons, a field "or answer in your own words", `send`. Write: `review-answer` with `{"task", "choice"?, "words"}`, `choice` the number of one of its choices counted from 0 and `words` the person's own (empty with a choice alone), as `evidence.md` §4.2's `answered`; the agent reads it in `loom tasks`. From: the evidence lane's asks, `question` kind, which may name a place as an annotation does; its shape is `evidence.md`'s.

**`attested-changed`: Attested results that changed (4i, 4j).** Rows: "main.tex · Corollary 3.5", "its statement changed since you attested it, 20 Nov"; "main.tex · Definition 3.7, Connected", "changed since you attested it · 2 results rest on it". Fields `{"result", "name", "title"?, "doc", "attested_at", "changed": "statement"|"used", "resting": 2}`. Body, in three steps: what was attested, `{"then": {"fragment"}, "at", "lean"}`, `lean` the declaration as Lean prints it; how it reads now, `{"now": {"fragment"}}`, what changed since the attestation merged in and marked as a pending change's words are; and the question. For a definition, below it, the results resting on it, each `{"result", "name", "statement": {"fragment"}, "lean", "attested_again": false}`, each opening to the same question. The body carries `observation`, the observation the attestation was of. Writes: `still states it` is `formal-attest` with `{"result", "observation"}`, an attestation of the same declarations on the current hashes; `ask an agent to restate` is `review-task` with `{"what": "restate", "on": SUBJECT, "target": SUBJECT, "differs": "", "from", "words": ""}`. From: evidence (an attestation names the statement's hash and the hash of every node its statement uses, transitively, `library.md` "Evidence"), lean, scan. Not built before formalization.

**`cited`: Cited results to digest (4f, 4h).** A row a work: "Okafor 2022 · Theorem 2.3 and Corollary 4.2", "PDF only · main.tex rests on both"; "Smith 2024 · Lemma 8.2", "not found in its TeX source · bounds.tex rests on it". Inside, a row a stub, "Theorem 2.3", "main.tex rests on it", with `ask an agent to read it` and `locate…`. Over the kind, `ask an agent to read all 4`. Fields `{"ref", "short", "holds", "stubs": [{"node", "name", "rests": {"docs": [DOC…]}, "not_in_source": false, "marked": false}]}`. Opening `locate…`, the body: the draft's sentence that cites it, `{"cite": {"doc", "key", "where": "Section 1", "fragment", "nth": 2}}`, the fragment of the block that holds it and which of its citations it is, from which the viewer cuts the sentence and marks the citation; beside it, a find bar filled with the result's name and what loom found, `{"find": {"query": "Theorem 2.3", "hits": [{"page": 6, "rects": […]}], "pages": 24}}` ("these words are on page 6 · 1 of 2 · next ›", or "not in the PDF's text · page 1 of 31"), and the page drawn by the reader, the hit highlighted as the reader's find highlights; the person selects the passage and marks it ("Marked on page 6. An agent reads it from there."), which is a `to-digest` mark naming the stub with `node` and then, in the same gesture, the ask to read the stub. A citation that names no result is a row of its own: "main.tex · the proof of Theorem 3.4 cites Okafor 2022 without naming a result", fields `{"citation", "doc", "key", "where": "the proof of Theorem 3.4", "ref", "short", "citekey": "Oka22"}`, body the sentence (as above), what to add with an example in the person's own key, `ask an agent which result`, `only a mention`, and `see it in main.tex`. Writes: `review-task` with `{"what": "read", "on": {"node"}, "nodes": [NODE…], "from", "words": ""}`, after a mark naming the stub, a task for each stub; `annotate` of kind `to-digest` naming the stub; `review-task` with `{"what": "which-result", "on": {"citation"}, "cites": REF, "from", "words": ""}`, the publisher writing the citation as the block it stands in (`evidence.md` §4.1), whose answer comes back as a proposed edit; `library-mention` with `{"citation"}`. From: index (stubs), scan (the citations, the blocks that hold them, what rests on them), store (the find, the survey), the evidence lane's asks, annotations. Which stubs are listed is `evidence.md`'s.

**Open 22.** Naming a citation. `only a mention` must be remembered across edits of the draft, and a citation has no id. Proposal: `citation` is the document, the key cited and the words around the citation, found again as an annotation's quote is, and `library-mention` records it under `.loom/records/library/`; a citation so marked makes no stub and leaves the list.

**`check`: Digested results to check (4 check).** A row a work: "Smith 2024 · 9 results", "bounds.tex rests on one"; "Arden 2025 · Theorem 5.1", "transcribed by an agent · main.tex rests on it". Inside, a row a node, "3.2 Lemma · Test lemma", "bounds.tex rests on it, through Proposition 3.4"; the first not yet compared opens: a line on how it was made ("extracted exactly from the TeX source, so compare it at a glance", or "transcribed by Claude Code from page 21, so read it closely"), the node with `rendered | plain`, "Does loom's copy match the paper?", and beside it the paper cropped at its place, "Smith 2024, page 12". Fields `{"ref", "short", "pdf", "nodes": [{"node", "name", "number", "title", "rests": {"docs": [DOC…], "through"?: "Proposition 3.4"}, "how": "extracted"|"transcribed"|"read"|"corrected"|"written"}]}`, `number` as the source prints it, which a node's row puts first ("3.2 Lemma · Test lemma"). A node's body is `library-node` (§3.4); the crop is `library-places` with `{node}`, drawn by the reader clipped to the place with lines above and below. `through` is the first result on a shortest path from a draft's result to the node, when no draft uses the node directly. A correction is a row of its own, "Arden 2024 · a correction to Definition 1.2", "proposed by Claude Code": fields `{"correction", "node", "name", "ref", "short", "by"}`, body `{"compared_at", "runs": [["=", "The \\emph{cycle space} …"], ["-", "of the divergence map"], ["+", "$\\mathcal{Z}(Q)$ of …"]]}`, the word diff of the two LaTeX bodies, which the viewer draws as it draws a node, "The text you compared on 18 Nov stands until you take this.", `take` and `decline`. Writes: `library-check`; `library-correction-take` and `library-correction-decline` with `{"correction"}`. From: index, evidence (how each was digested, verified records, corrections), scan (what rests on it), store (places). Order (`library.md`, "Digesting and checking"): what a draft rests on first, grouped by work, one row for a paper. Cost of `through`: a breadth-first walk up the reversed uses from the work's nodes, 5 ms.

**Open 23.** Whether taking a correction checks the node. Proposal: yes, a record of the person's verification on the new hash, since the person read the change against the text they had compared; the panel says so in its line.

**`attest`: Lean statements to attest (6).** Rows: "main.tex · Lemma 3.3", "statement and proof"; "Smith 2024 · Proposition 3.4", "statement only", with its paper mark. Fields `{"result", "name", "title"?, "source", "what": "statement and proof"|"statement only", "paper"}`; the row's Lean mark is the amber diamond, since every row of the kind waits for the person's word. A library node is listed only once its paper is `checked`, since nothing is attested on a node nobody checked (`library.md`, "Digesting and checking"). Body: the whole statement as the draft has it, then part by part what was written, the Lean that states it and the agent's reading; folded, "It uses Definitions 2.1 and 2.3, which you attested on 12 Nov." and "3 supporting declarations serve the proof. Lean accepted them; they are not what you attest."; the agent's note of a difference; "Does the Lean say what you wrote?" with `yes, I attest it` and `no, it differs…`; and a line saying what yes covers. Body shape:

```json
{"observation": "o-3c1e…",
 "statement": {"fragment": "fragments/nodes/rl-0033.html"},
 "parts": [{"part": "(i)", "draft": "if $\\operatorname{supp} w$ is a forest, then $w = 0$;", "lean": "theorem Weighting.IsBalanced.eq_zero_of_isForest …", "reading": "If $w$ is balanced and …", "by": "Claude Code"}],
 "notation": [{"part": "supp", "draft"?: "…", "lean": "Function.support w", "reading": "…", "from": "statement"|"macros"}],
 "uses_attested": [{"result", "name", "title"?, "at"}],
 "supporting": ["Weighting.exists_leaf_of_isForest", "Weighting.IsBalanced.restrict", "Quiver'.cycleSign_mul_self"],
 "difference": {"by": "Claude Code", "text": "…"}}
```

`draft` and `reading` are LaTeX, drawn as a node is, with the document's macro set. Writes: `formal-attest` with `{"result", "observation"}`, naming the statement's hash and every node its statement uses, refused `unchecked` (409) on a library node not checked and `changed` (409) when the observation is no longer the latest; `no, it differs…` is `review-task` with `{"what": "restate", "on": SUBJECT, "target": SUBJECT, "differs", "from", "words": ""}`. From: lean (the declarations, as Lean prints them, the axioms each used, the supporting declarations), evidence, scan. Not built before formalization. **Open 24.** `parts`, `reading` and `difference` are the agent's account of its formalization, which no record yet holds. Proposal: the agent's request to have a result attested is a record of its own, with these fields, naming the observation loom made; loom checks that each declaration it names is one Lean accepted in that observation.

**`fetch`: Papers to fetch (4).** A row: "Jones 2019 · Covering estimates", with `open its page ↗`; it does not open. Fields `{"task", "ref", "short", "title", "link", "by", "docs"}`, `task` the `paper` ask's id. Writes: none but a file dropped on the row, which is `library-take` with `for` (§3.5). From: the evidence lane's asks, `paper` kind (`library.md`: what an agent cannot fetch "waits in Review as a request with the source's link"); its shape is `evidence.md`'s.

**`edits`: Proposed edits (4, 12).** Rows: "main.tex · proof of Theorem 3.1", "proposed by Claude Code"; "bounds.tex · Lemma 2", "bounds.tex has not compiled since this edit (line 14)". Fields `{"change", "type": "suggested"|"edit", "doc", "key", "where", "by", "broke": {"line": 14, "error": "Undefined control sequence"} or null}`. Body: `{"statement": {"fragment"}}`, the block's fragment with the change merged in and marked as a pending change's words are; `keep` and `discard`, or for an edit made in place `keep` and `undo the edit`, with "Claude Code made this edit in place. bounds.tex has not compiled since: the command it adds is not defined (line 14)."; `see it in main.tex`. Writes: `change-keep` and `change-discard`, as built. From: changes. An agent copy's adoption is a proposed edit too, redrawn as one and kept or discarded with today's `adopt-` writes (ruled with the spec's merge). Which changes are listed is `evidence.md`'s. **Open 26.** `broke`. Proposal: an agent's edit made in place has `broke` when its document's last compile failed, or made a PDF with errors, after the edit, and the line TeX stopped at (`compiles`, `last.at`) lies in the lines the edit wrote; `error` is TeX's message, which the viewer's words turn into a sentence for the errors it knows and show as it is otherwise.

**`agents`: Waiting for an agent (4).** A row: the task in words ("Digest the 2 places you marked in Okafor 2022", "Read Theorem 2.3 of Okafor 2022", "Answer, on main.tex, proof of Theorem 3.4: does the count need the median order?"), "Claude Code is working on it" or "waiting", and `delete` on hover. Fields `{"task", "what", "docs", "on": {…}, "text"?, "working": {"by": "Claude Code"} or null, "asked_at"}`, `what` the ask's (`evidence.md` §4.1). The sentence is the viewer's, built from `what` and `on`, which carries the names its words need:

| what | made by | `on` | drawn as |
| --- | --- | --- | --- |
| `digest` | `library-digest` on a work held only as a PDF | `{ref, short, scope, count}` | "Digest the 2 places you marked in Okafor 2022", "Digest the whole of Vance et al. 2023" |
| `read` | `review-task`, alone or after a mark naming the stub | `{nodes, names, short, marks?}` | "Read Theorem 2.3 of Okafor 2022" |
| `ask` | `review-task` from a selection, on a work's page or a draft's text | `{ref, short, page, quote}` or `{doc, key, name, quote}` | "Answer, on main.tex, proof of Theorem 3.4: " and the person's `text` |
| `correct` | `review-task` from a node | `{node, name, short}` | "Correct Lemma 3.2 of Smith 2024: " and the `text` |
| `restate` | `review-task` from an attestation | `{result, name, doc}` | "Restate the Lean of Corollary 3.5 of main.tex" |
| `which-result` | `review-task` from a citation | `{citation, doc, where, short}` | "Say which result of Okafor 2022 the proof of Theorem 3.4 cites" |
| `formalize` | `formal-ask` | `{result, name, doc, assume}` | "Formalize Theorem 3.4 of main.tex" |

Write: `review-task-delete` with `{"task"}`, which withdraws it (`library.md`: a task "is withdrawn by deleting it"). From: the evidence lane's asks, whose record, closing and taking by a session are `evidence.md`'s. Round six also lists tasks no write on this page makes ("Transcribe the second proof of Proposition 3.4 of Smith 2024, from Halberd and Ravel 2021, pages 22–23", "Check the macros of Smith 2024 against its preamble"): an ask whose `what` the viewer does not know is drawn with the `text` it carries.

### 4.4 See it in a document (4 see it)

**Drawn.** `see it in main.tex` lays the document over Review, read only, at the result ("read only here; edit it in Docs"), until its close button. **Reads.** The document's rendering as Docs reads it today, from the manifest and its fragments, scrolled to the row's `key`; nothing new.

## 5. The Web

### 5.1 Scope and form (7a, 7b)

**Drawn.** In the column, Scope: `the library`, `a draft` (with a choice of draft), `a draft and what it rests on` (with a choice of draft), `everything`; Form: `list` and `graph`. Every Web read takes `{"scope": "library"|"draft"|"deps"|"all", "doc"?: DOC}`:

- `library`: every statement and stub of the library (not its proofs, references or macros);
- `draft`: the results of one draft, as the scan reads them;
- `deps`: the results of one draft and every result they use, by statement or by proof, transitively;
- `all`: every draft's results and the library's.

### 5.2 The list (7a, 7a draft)

**Drawn.** A search, "23 results", and `by document | by status`. By document under `a draft and what it rests on`: "main.tex", the draft's results; "library results main.tex uses", a row for each work, open, with its results under it. Under `everything`: "your drafts", a row for each document, and "library", a row for each work, both folded, then "and 295 works with no results digested". Each result draws its marks, name and title, its source where it is not under its source's row, and, on the person's own results not formalized, a box to choose it for the formalize panel; with any chosen, a bar "3 chosen · formalize… · clear".

**Read `web-list`.** Given the scope, `"sort": "document"|"status"`, and `"open"?: [DOC or REF…]`:

```json
{"gen": 41, "count": 23, "sections": [
  {"head": "draft", "doc": "drafting/main.tex", "rows": [ROW]},
  {"head": "uses", "doc": "drafting/main.tex", "groups": [{"group": "tq-00A1-ref", "short": "Arden 2024", "title": "Cycle spaces of finite quivers", "n": 5, "rows": [ROW]}]}],
 "undigested": 295}
```

`head` is `draft`, `uses` ("library results main.tex uses"), `drafts` ("your drafts") or `library`. A group's rows are sent only when it is open: open by default under `uses`, folded under `drafts` and `library`, and a group opened later is `web-group` with the scope and `{"group": DOC or REF}`. A `ROW` here gains `"choose": true` on the person's results not formalized. By status, `{"gen", "count", "rows": [ROW…], "more": 0}`, ordered not read, not compared, Lean accepted and not attested, not formalized, matches the paper, assumed, formalized, then paper order, two hundred at a time with `"offset"`. From: scan, index, evidence, lean. Cost: `deps` at the showcase's size about 40 rows; `all` at thousands of nodes sends groups only, about 350 of them in 40 KB, and a group of 60 rows is 10 KB; the closure of a draft is a walk over the index's uses from its results, 20 ms at thousands.

### 5.3 Search (7a search)

**Drawn.** "find a result, or words in it"; hits as rows, each with the words of its statement around the match, the match highlighted.

**Read `web-search`.** Given the scope and `{"q": "polynomial", "limit": 50}`; answers `{"gen", "count", "hits": [{"row": ROW, "snippet": {"before": "…eightings of $Q$ of height at most $h$ is a ", "match": "polynomial", "after": " in $h$ of degree …"}}]}`. It matches a result's number, name and title, its work's short name and title, and the words of its statement; a hit in the statement carries the words around it from the statement's LaTeX, cut at spaces outside mathematics, which the viewer draws as it draws a statement. A hit on the number or name comes before one in the text. Library nodes are searched in the index's full-text table, which gives where the match stands; the drafts' results in the scan's statements, the words today's `search` entries hold. Only results in the scope. Cost: 100 ms at thousands, at most 50 hits.

### 5.4 The focus (7a)

**Drawn.** A trail of the results followed, the viewer's. A card: the name and title, the source, its marks with their words, its statement, and one line: "Verified relative to Proposition 2.1 of Arden 2024, which is assumed.", or "Verified, relative to Mathlib alone.", or "Not formalized. It rests on Lemma 5.7 Arden 2024, …" (7a search); folded, "proofs, Lean, and its record"; and `formalize…` on the person's results not formalized. Under or beside it: "What its statement uses", "What its proof uses", "What uses it", each a list of rows, with "and 2 outside this scope".

**Read `web-focus`.** Given the scope, `{"result": RESULT, "more"?: true}`:

```json
{"gen": 41, "row": ROW,
 "statement": {"fragment": "fragments/nodes/rl-0031.html"},
 "relative_to": [ROW],
 "rests_on": [ROW],
 "more": null,
 "uses": {"statement": [ROW], "proof": [ROW], "outside": {"statement": 0, "proof": 0}},
 "used_by": {"rows": [ROW], "outside": 0, "more": 0}}
```

- `statement` is a draft's result's fragment, which the viewer fetches as Docs does, or for a library node `{"body", "macros", "points"}` as `library-node` gives them; null for a stub, which loom knows only by its number.
- `relative_to` is, for a formalized result, the assumed results its Lean theorem rests on, read off the axioms Lean reported it used and the nodes their declarations state; an empty list is "relative to Mathlib alone"; null when it is not formalized.
- `rests_on` is, for a result of the person's not formalized, the results it uses directly that are not read or not compared.
- `more`, sent only when the fold is opened: `{"proofs": [{"where": "main.tex, Section 3" or {"ref", "short", "pages"}, "uses": [ROW]}], "lean": ["Showcase.rank_cycleSpace"], "record": [{"act": "lean-accepted"|"attested"|"verified"|"digested", "by": "you", "at"}]}`.
- `used_by.rows` is at most 50, `more` the rest, for a definition much used.

From: scan, index, evidence, lean. Cost: 20 ms, under 10 KB.

**Open 27.** "What its proof uses" for a statement with two proofs. Proposal: the union of what its proofs use, each row saying which proof only when there are two or more.

### 5.5 The graph (7b)

**Drawn.** Four columns: two steps back, what it uses, the focus, what uses it; a solid line for a use by a statement, a dashed one for a use by a proof; a column of more than six draws five and "and 3 more · in the list"; the focus's card under the graph at full width.

**Read `web-graph`.** Given the scope and `{"result": RESULT}`; answers `{"gen", "focus": ROW, "excerpt": "rank 𝒵(Q) = |A(Q)| − |V(Q)| + c", "columns": {"back": [ROW], "uses": [ROW], "used_by": [ROW]}, "more": {"back": 0, "uses": 0, "used_by": 0}, "edges": [{"from": RESULT, "to": RESULT, "proof": false}]}`, the edges only among what is drawn, each `from` a result that uses `to`, and `excerpt` the statement's first line in plain words, as search indexes them. The card under it is `web-focus`. Cost: 20 ms.

## 6. Docs

What Docs draws of the library is the picker, a work beside a draft with a citation's card, the notes tab, the Lean marks in a draft's margin, the markers in a Lean file and the formalize panel. The file tree, the documents and their changes read the manifest as today; the tree is today's product's, "did not compile" under a document's PDF row among it (ruled after round six), and no other mark of a problem is added to it.

### 6.1 The picker (8a)

**Drawn.** Over Docs: a search, "300 works", `list` (Title, Authors, Year, and the label the draft cites it by, "[1]", with "main.tex cites it as [1]" on hover) or `thumbnails`, sorted by title, authors or year; a click opens the work beside the draft. **Read.** `library-works` with `{"doc"}`, whose `cited_as` is that label, read from the document's last compile as the build already reads it (`tex/aux.py`, `read_cite_labels`), null for a work the document does not cite or a document not compiled; and the thumbnails of §3.1. Open 28 asked for this label and is closed: the build has it.

### 6.2 A work beside a draft, and a citation's card (8, 8c)

**Drawn.** The reader of §3.3 beside the draft, without the digest overlay. A hover on a citation in the draft, "[1, Proposition 2.1]", shows a card: "Proposition 2.1", "Arden 2024 · page 1", its marks, the statement, and `open at its place`; on a stub, "Theorem 2.3", "Okafor 2022", "Loom knows this result only by its number. Nobody has read it.", `locate in PDF` and `ask an agent to read it`.

**Reads.** A citation's target is the node the scan resolved it to. This changes `dialect.md` §2.8, whose `span.cite` carries no target: once this is built, its `data-target` names a library node or a stub, every locator having one (Open 29), and `dialect.md` changes with it. The card is `library-node` with `{"node", "brief": true}`. `open at its place` opens the work beside the draft at `library-places` with `{node}`. `locate in PDF` opens it at loom's best guess, `library-find`, given `{"ref", "q": "Theorem 2.3"}` and answering `{"gen", "pdf", "hits": [{"page", "rects"}], "pages": 24}` from the stored page text by the normalisation a quotation is checked under; this is the one guess `library.md` allows, a page loom opens at, never a mark. Cost: 30 ms for a paper of 30 pages once its page text is read, about a second the first time.

**Writes.** The person selects the result's passage and marks it, a `to-digest` mark naming the stub (§3.3); `ask an agent to read it` is `review-task` with `{"what": "read", "on": {"node"}, "nodes": [NODE], "from", "words": ""}`, naming the mark where there is one.

**Open 29.** A citation whose locator names a result the work's source does not print. Proposal: a stub, as for any locator (`library.md`: "if that result has no node yet it gets a stub"), listed in Review as "not found in its TeX source".

### 6.3 The notes tab (8b, 8b work)

**Drawn.** A tab "All notes", 760 pixels wide whatever its sort: `sort by work | date` and "show orphaned notes (2)". By work: "Orphaned · their document is gone, or their words are not found" first, each note with `place it again` and `delete`; then a group for each document and each work, with its count, its latest notes and "6 more". A note draws its type's colour, the words it is on, its text, who wrote it and when, and its tags ("summary"); a click on a placed note opens it at its place, in Docs.

**Read `notes`.** Given `{"sort": "work"|"date", "orphaned": true, "group"?: DOC or REF or "orphaned", "offset"?: N}`. By work, `{"gen", "orphaned": 2, "groups": [{"group": {"doc"} or {"ref", "short"} or "orphaned", "n": 9, "notes": [NOTE…], "more": 6}]}`, three notes a group; by date, `{"gen", "notes": [NOTE…], "more": 11}`, twenty at a time; `group` with `offset` sends the rest of one. A `NOTE` is `{"annotation", "color", "quote", "message", "by": "you" or the agent's name, "at", "tags": [], "at_place": {"doc", "key"} or {"ref", "page"} or null, "was"?: "old-intro.tex, deleted 14 Nov"}`; `message` is the annotation's text as the log holds it, drawn as the viewer draws annotations today, and `at_place` is null for an orphan. From: annotations; orphaned are those whose words are not found, whose document is gone, or whose PDF was replaced. Cost: hundreds of notes, under 20 KB, 20 ms. The tab needs no part of the manifest's annotations.

**Writes.** `place it again`: the person clicks where the note belongs or selects its words, `place` with `{"annotation", "target", "quote"?, "page"?, "rects"?}`. `delete` is `delete`, as built. **Open 30.** Today's `edit` moves only a mark drawn on a PDF page. Proposal: `place`, beside `annotate` and `edit`, anchors a note again on any target by its quote, or on a page by its region, and records that it was placed again.

**Open 31.** Tags on a note. Annotations have a type and no tags; `library.md` says what an agent wants to say of a work is "a note on the work, with tags". Proposal: an annotation gains `tags`, written by `annotate`; "summary" in 8b is such a tag. As for a node's tags (ruled with the node store), a tag keeps the case it was typed in, two equal ignoring case are one tag, and it is shown as first written.

### 6.4 Lean marks in a draft's margin (8, 11a)

**Drawn.** Once formalization is on for the quilt, beside each result of the draft its Lean mark, its hover "not formalized · formalize…", a click opening the formalize panel; `view` hides them. **Read `formal-marks`.** Given `{"doc"}`; answers `{"gen", "on": true, "marks": {"rl-0031": "formalized", "rl-0034": "not"}}`. From: lean, evidence, scan. Cost: 10 ms, under 5 KB. **Open 32.** What turns formalization on for a quilt. Proposal: `reserved.md`'s `formal-enable`, on this machine, with a Lean project loom checks; with `on: false` neither the marks nor the panel are drawn, and every `lean` field on this page is null.

### 6.5 The markers in a Lean file (11d)

**Drawn.** A Lean file of the quilt's project opened in Docs, each line that names a node, `@[loom "thm:rank"]`, with "names Theorem 3.1 of main.tex" beside it. **Read `formal-markers`.** Given `{"path"}`; answers `{"gen", "markers": [{"line": 7, "result": "rl-0031", "name": "Theorem 3.1", "doc": "drafting/main.tex"}]}`, or for a marker that names nothing `{"line", "result": null}`. From: lean, the markers loom reads when it runs the check (`library.md`, "Formalization"), and the scan. Cost: 5 ms. Not built before formalization.

### 6.6 The formalize panel (11a, 11b; from the Web, 11c, 11e)

**Drawn.** A large panel over the view, reached from a Lean mark in Docs, from the bar of chosen rows in the Web, or from `formalize…` on the Web's card: "Formalize Theorem 3.4 · main.tex"; the target, or targets, in full as the draft has them; one sentence, "To formalize this, an agent will state 3 definitions in Lean, prove 2 of your lemmas, and assume 4 results from your library."; two headed parts, each shown only when it has something in it: `Stops the request`, a result with no label, which the person labels by hand and which is the one thing that stops it, and `Before it reads formalized`, a cited result nobody has read, a digested result not yet checked against its paper, and a Lean statement waiting to be attested; `To state`; `To prove`, each with `prove | assume for now`; `To assume`, with "not read yet" or "not checked yet"; `Already formalized`, folded; the button ("ask an agent to formalize Theorem 3.4", or "add a label to Definition 3.2 first"), and "It becomes one task in Review, under Waiting for an agent."; each item's statement one click away. Round six drew one part, "Needed first"; the ruling after it splits it in two, so that a heading never says the opposite of the line under it.

**Read `formal-plan`.** Given `{"targets": [KEY…], "assume": [KEY…]}`, `assume` the person's results chosen "assume for now":

```json
{"gen": 41,
 "targets": [{"key": "rl-0034", "name": "Theorem 3.4", "title": "Bounded balanced weightings", "doc": "drafting/main.tex", "statement": {"fragment": "fragments/nodes/rl-0034.html"}}],
 "state": [ROW], "prove": [ROW], "assume": [ROW], "formalized": [ROW],
 "stops": [ROW],
 "before": [{"why": "not-read", "results": [ROW]}, {"why": "not-checked", "results": [ROW]},
            {"why": "attest", "results": [ROW]}, {"why": "attested-changed", "results": [ROW]}]}
```

A `ROW` in `assume` gains `"why": "not-read"|"not-checked"|null`, and one in `prove` `"assume": true|false`. `stops` is `Stops the request`, and `before` is `Before it reads formalized`, each group named by why it is there; an empty one is not drawn. The plan, by the rules round six draws, as ruled:

1. Each target is to be proved, unless the person chose to assume it for now.
2. From a result to be proved, every result it uses is reached, by its statement and by its proof; from one assumed or a definition to be stated, only what its statement uses.
3. A result reached that is formalized is in `formalized` and is not followed. One of the person's that Lean accepted and that waits for attestation is in `before` as `attest`, one that changed since it was attested as `attested-changed`, and neither is followed. A definition or a convention not formalized, the person's or the library's, is in `state`. Another of the person's is in `prove`. Another of the library's is in `assume`, and also in `before` when it is a stub (`not-read`) or not compared (`not-checked`).
4. A target, or a result in `state` or `prove`, with no label is in `stops`. It is the only thing that stops the request.

The sentence's counts are the lists' lengths, and the sentence is the viewer's. A statement one click away is `library-node` with `brief` for the library's, the fragment for the person's. From: scan (the person's results, their labels and uses), index (the library's uses), evidence and lean. Cost: a walk over the targets' closure, 50 ms at thousands, under 20 KB.

**Write `formal-ask`.** `{"targets": [KEY…], "assume": [KEY…]}`, answered `{"gen", "tasks": [TASK…]}`, one task a target, refused `needs-label` (409) naming each result without one (`library.md`: "loom says that the result needs a label first, and the author adds it to his source by hand"). Nothing in `before` refuses it: an unread or unchecked library result does not stop a request to formalize, and only keeps the result from reading formalized (`library.md`, "Digesting and checking").

## 7. The writes

Every write the views make, in one place. "Built" marks one that exists today.

| write | body | answer | what it does |
| --- | --- | --- | --- |
| `library-receive`, `library-take`, `library-answer`, `library-undo` | as `write-api.md` §6 | rows | built; the intake, its `added` row now making a reference, with `found_by`, `tex` and `unconfirmed` (§3.5) |
| `library-look-up` | `{ref}` | `{gen, ref}` | looks up, once and with the network, the identifier the reference states, and writes its details from the record found, unless the person corrected the entry; `no-identifier` (409), `unreachable` (409) |
| `library-entry` | `{ref, bibtex}` | `{gen, ref}` | replaces the reference's body with one BibTeX entry (Open 4); `bad-entry` (400), `key-taken` (409) |
| `library-delete` | `{ref}` | `{gen, undo}` | deletes the work as one act, never refused (§3.1) |
| `library-restore` | `{undo}` | `{gen, ref}` | puts back what one delete took; `changed` (409) when something has since taken its place |
| `library-digest` | `{refs, scope, chosen?}` | `{gen, made, tasks, job?}` | §3.2; `no-document` (409) |
| `library-check` | `{node, hash}` | `{gen}` | the person's record that the transcription with that hash matches its paper; `changed` (409) |
| `library-correct` | `{node, hash, body}` | `{gen, hash}` | the person's correction of a node, checked at once (Open 17); refused with the checks' diagnostics (400), `changed` (409) |
| `library-correction-take`, `library-correction-decline` | `{correction}` | `{gen}` | takes or declines a correction an agent proposed (Open 23) |
| `library-mention` | `{citation}` | `{gen}` | remembers a citation as a mention (Open 22) |
| `review-answer` | `{task, choice?, words}` | `{gen}` | answers an agent's question, `choice` counted from 0; `evidence.md` §4.2's `answered` |
| `review-task` | `{what, on, from, words, …}` | `{gen, task}` | asks an agent (§4.3, `agents`): `read`, `digest`, `ask`, `correct`, `restate`, `which-result`, each with its own fields; an `asked` line of the evidence lane's log, `evidence.md` §4.1, whose `by`, `id`, `at` and `to` loom writes |
| `review-task-delete` | `{task}` | `{gen}` | withdraws a task |
| `formal-ask` | `{targets, assume}` | `{gen, tasks}` | a task for each target; `needs-label` (409) |
| `formal-attest` | `{result, observation}` | `{gen}` | the person's word that the Lean statement says what the result says, naming the hashes it covers; `unchecked`, `changed` (409) |
| `place` | `{annotation, target, quote?, page?, rects?}` | `{gen}` | anchors a note again (Open 30) |
| `annotate`, `delete`, `here`, `settings-save` | as `write-api.md` | | built; `annotate` gains `purpose`, `to-digest` for a mark to digest (§3.3), which may name a stub |
| `change-keep`, `change-discard`, `review-accept` | as `write-api.md` | | built |

## 8. Costs at the sizes in use

| read | answer | budget | it must not |
| --- | --- | --- | --- |
| `library-works` | 300 rows, about 60 KB | 50 ms | open a node file, a PDF or a source; make a survey |
| thumbnail | about 25 KB | 0.2 s first, then a file | be made for a card not scrolled into view |
| `library-work` | about 15 KB for 60 results | 10 ms with a survey | compile in the request; the survey's compile is a job |
| `library-digest-scopes` | under 1 KB | 10 ms | make a survey except to count `all` |
| `library-places` | 2 KB a page | 5 ms, 50 ms a page first | be asked while the overlay is off |
| `library-node` | under 8 KB | 5 ms | read any file but the node's, its macros node's and, for an item, the survey |
| `library-find` | under 2 KB | 30 ms, about 1 s first | guess a mark |
| `review-counts` | under 1 KB | 20 ms | read a body |
| `review-list` | under 20 KB for 40 rows | 50 ms | open a PDF or run TeX |
| `review-row` | under 30 KB | 30 ms | |
| `web-list`, `web-group` | 40 KB at most | 20 ms | send a folded group's rows |
| `web-search` | 50 hits | 100 ms | |
| `web-focus`, `web-graph` | under 10 KB | 20 ms | send the fold unasked |
| `notes` | under 20 KB | 20 ms | |
| `formal-marks`, `formal-markers` | under 5 KB | 10 ms | |
| `formal-plan` | under 20 KB | 50 ms | |

The manifest carries nothing of the library (`library.md`, "Scale").

## 9. Open questions

| n | where | question | proposal, in a line |
| --- | --- | --- | --- |
| 1 | §2 | the word for a person's yes to a transcription | closed: "matches the paper", decided with the author |
| 2 | §3.1 | "of 62" for a work never opened | no "of" until the work has a survey |
| 3 | §3.1 | "second version" | the entry's own field, else the later of two references a `same` record joins |
| 4 | §3.1 | editing an entry rewrites the reference's hash | allowed; attestations do not cover references |
| 5 | §3.1 | what deleting a work removes | closed: never refused; one act, one undo; the references lane settles the files that used it |
| 6 | §3.1 | a dropped `.bib` or TeX source | closed: the intake takes both (`write-api.md` §6) |
| 7 | §3.1 | "details unconfirmed" | the intake's record of how the details were found |
| 8 | §3.2 | matching the survey to nodes, and a stub the source lacks | by label, else printed number and taxon; never by guess |
| 9 | §3.2 | an item's page before the survey's compile | null; a click goes to its section |
| 10 | §3.2 | order and sections of a work held only as a PDF | closed: §2's order, ruled with the node store; sections by the PDF's outline |
| 11 | §3.3 | long PDFs | `Range` on the PDF's address, later |
| 12 | §3.3 | annotations on a work keyed by identifier | closed: keyed by the reference's id, which the carry-over re-keys them to |
| 13 | §3.3 | the overlay's default | closed: off, remembered once turned on |
| 14 | §3.3 | where a mark to digest is kept | closed: an annotation whose `purpose` is `to-digest` |
| 15 | §3.4 | anchors' printed numbers | closed: the header key `anchors`, ruled with the node store |
| 16 | §3.4 | ids in the plain view | a named chip; no id |
| 17 | §3.4 | "no, it differs…" | the person corrects in place, checked at once, or asks an agent |
| 18 | §3.5 | a drop meant for a paper waiting to be fetched | closed: by its identifier or by being dropped on its row; nothing matched by title or author |
| 19 | §3.5 | the intake's question and cannot rows | column messages |
| 20 | §4.3 | an agent's question with choices | closed: the evidence lane's asks, `evidence.md` |
| 21 | §4.3, §6.2 | whether marking a stub's place asks for it to be read | closed: the viewer makes the mark and the ask in one gesture |
| 22 | §4.3 | naming a citation for "only a mention" | its document, key and surrounding words, found again as a quote is |
| 23 | §4.3 | whether taking a correction checks the node | yes |
| 24 | §4.3 | the agent's account of a formalization (parts, readings, a difference) | a record of the agent's, checked against loom's observation |
| 25 | §4.3 | where a request for a paper is kept | closed: the evidence lane's asks, `evidence.md` |
| 26 | §4.3 | "has not compiled since this edit" | the last failed compile's line inside the edit's lines |
| 27 | §5.4 | what a statement's proofs use, with two proofs | the union, each row naming its proof |
| 28 | §6.1 | "[1]", the label a draft cites a work by | closed: `read_cite_labels` gives it |
| 29 | §6.2 | a citation of a number the source does not print | a stub, "not found in its TeX source" |
| 30 | §6.3 | placing a note again | `place` |
| 31 | §6.3 | tags on a note | annotations gain `tags`, kept in the case typed, equal ignoring case being one |
| 32 | §6.4 | formalization on for a quilt | `formal-enable`, with a Lean project loom checks |
| 33 | §6.6 | requesting a formalization over unchecked results | closed: ruled after round six, allowed; the gate is on what reads formalized |
| 34 | §4.2 | Review's kinds against `library.md`'s list | closed: `evidence.md` writes the rule for each kind |
| 35 | §4.3 | where a task is recorded and how a session takes one | closed: the evidence lane's asks, `evidence.md` |
| 36 | §3.5 | a drop before the quilt has said whether loom may use the network | the column's message asks once |
