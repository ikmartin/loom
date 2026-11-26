# Diagnostics

A diagnostic is a structured report of something wrong or notable in a corpus. Publishers emit them into the manifest; viewers render the ones a person is shown on a problems page, as badges on the keys they concern, and in header counts.

## 1. Schema

**[decided]**

| field | type | meaning |
|---|---|---|
| `severity` | `error`, `warning`, `info` | how serious |
| `code` | string | stable identifier; reserved (no namespace) or publisher-namespaced (`loom:...`) |
| `class` | `latex`, `model`, `internal` | what kind of problem it is, and so who is shown it. Absent means `latex`. |
| `message` | string | human-readable, one sentence |
| `locations` | list of `{file, line, column?}` | where, zero or more |
| `keys` | list of keys or node ids | what it concerns, zero or more |
| `subject` | `source`, `record` | optional; what the diagnostic is about. Absent means `source`. |
| `owner` | `person`, `copy` | optional; whose it is to put right. Absent means `person`. |
| `fixes` | list of `{label, command, act?}` | optional; commands that would resolve it, `act` the ones a viewer may do itself |

Viewers group by what is wrong, filter by severity and code, and link locations and keys. A viewer renders unknown codes generically and never fails on one.

**[decided]** `class` says what kind of problem a diagnostic is. `latex` is a problem in a document's LaTeX that an author would recognise: a document whose last compile failed or finished with errors, what TeX meets in a document's compile, such as a reference to nothing, an id defined twice, a file missing or included twice, or a document never closed, and a circle among the dependencies the person's statements declare, which no block says yet, and a document gone with annotations on it, which no page of notes says yet; and a link in one of the person's Markdown files to a file, a key or a place in one that is not there, the same fault as a reference to nothing; and an entry of the person's bibliography that loom cannot keep as a work. `model` is the publisher's model of the corpus: the hygiene of ids, `\uses`, links, agents' copies, records and the publisher's own macros, which an agent keeps. `internal` is the publisher's own difficulty or the integrity of its records: a text TeX refused that no compile makes, a library node that fails its checks, a history edited by hand. A viewer's problems page and its lists of a key's diagnostics show a person `latex` alone, their own before an agent's copy's; where a viewer reads a particular code to say something in its own place (a block with no proof, a quilt with no document, a permission file out of date), it reads it whatever its class. The publisher's lint shows every class, since agents' audits rest on the model's codes and the publisher's records on the internal ones. Each code has a class, said in its entry below; where a code's instances differ, the publisher says each one's. A diagnostic with no class, or with one a viewer does not know, is `latex`, so a viewer filtering by class hides nothing a publisher did not classify.

**[decided]** `severity` is `error` for a fault in what TeX compiles or in the publisher's records. A problem of the publisher's model that never stops TeX is a `warning` at most, so that what counts errors, a lint's exit, an agent's first look and a server's start line, counts only what is one. What a gate refuses is decided by code, not by grade: loom will not adopt an agent's copy, nor linearize a document, over a new diagnostic of a code that was an error before the grades followed what TeX does (`scan/diagnostics.py`, `GATED`), at any grade but info, so a regrade changes what is said and never what loom lets through.

**[decided]** `subject` separates what is wrong with the corpus's text from what is wrong with the publisher's own record of it. They are different kinds of work, and a viewer may group them apart; a viewer that ignores the field loses nothing.

**[decided]** `owner` says whose a diagnostic is to put right (plan 0.25.3). `person` is the author's: their documents, their bibliography, their configuration, the records of their review. `copy` is an agent's: every location in an agent's copy, or every key a result of one; the agent puts it right, or the author leaves it out when taking the copy back. A diagnostic naming both the author's and a copy's is the author's. A viewer puts the author's first and counts only theirs; a viewer that ignores the field shows every diagnostic as the author's.

**[decided]** `fixes` are data: each is what an agent does to resolve the diagnostic, a command or an edit described in words. A viewer never runs a command, and among a person's problems it shows none. A fix may also carry `act`, `{endpoint, body}`: the write-API endpoint (`write-api.md`) that does what the command does, and the body to send it. A viewer that serves writes may offer such a fix as a button, through that endpoint and nothing else, and says the endpoint's answer beside it; without a publisher it offers none. The label says what the fix would achieve, so that a reader choosing between two fixes is choosing between outcomes.

**[decided]** Loom sets `act` on two fixes: `loom:agent-permissions-stale`'s, which rewrites the permission files (`agents-update`); and `loom:write-left`'s, which settles the write as it stands (`write-settle`, `{act: ID}`) after the viewer shows `write-settle-preview`'s words.

## 2. Reserved codes

**[decided]** These describe any inclusion tree and link graph over nodes. Any publisher may emit them; a viewer may give each a specific affordance. They cannot be disabled by a publisher's lint configuration.

| code | severity | class | meaning | viewer affordance |
|---|---|---|---|---|
| `duplicate-id` | error, or warning | latex, or model | the same identifier is defined by two nodes | link both locations; show the id as conflicted wherever it appears |
| `dangling-link` | error, or warning | latex, or model | a link to no node or region | mark the source |
| `missing-include` | error | latex | an inclusion names a file that does not exist | link the site |
| `double-inclusion` | error | latex | one node under two parents in one root | link both paths |
| `inclusion-cycle` | error | latex | a node includes itself through a chain | list the cycle |
| `unreachable` | info | model | a node or file no root reaches (loom: loose) | filter |

**[decided]** `duplicate-id` is an error of class `latex` where one root's inclusion tree reaches two of its definitions, since a compile of that root reads both; where no root reaches two of them, as when two roots each define it once or a file no root reaches holds one, it is a warning of class `model`. `dangling-link` is an error of class `latex` for a reference a root's compile reads, which prints `??` there; a link TeX never reads (loom's `\uses`, which prints nothing, a `% !LOOM see:` relation, or any link in a file no root reaches) is a warning of class `model`.

**[decided]** A publisher may leave a doubly-defined identifier with no text and the state `conflicted` (manifest §3, §8) rather than choosing between the definitions. A viewer renders that state like any other the manifest declares.

## 3. Loom codes

**[decided]** Namespaced `loom:`. Severity and class in parentheses. All except those marked fixed can be silenced with `[lint] disable`.

Source and structure:

- `loom:environment-spans-files` (warning, model): a theorem-like environment opens in one file and closes in another. A `\begin{document}` that no file the document reads closes is an error of class `latex`, the fault TeX stops on at the document's end.
- `loom:line-anchoring` (warning, model, fixed): a `\begin` or `\end` of a theorem-like environment is not alone on its line; reported by `import`, `id` and `atomize`.
- `loom:unknown-environment` (warning, model): a theorem-like environment the preamble closure does not declare, as loom reads it; fix with `% !LOOM environment:`. A class or package loom does not read may declare it, and an environment TeX itself lacks stops the compile, which `loom:compile-failed` reports.
- `loom:unattached-proof` (warning, model): a `proof` neither adjacent to a node nor referencing one.
- `loom:multi-target-proof` (warning, model): a proof's optional argument references several nodes; attached to the first.
- `loom:reference-to-loose` (error and latex for a `\ref` in a master's compile, which prints `??` there; warning and model for a `\uses`, which prints nothing; info and model in loose files): a reference to a node the master does not reach. A master reaches what it includes and what the documents it names in `\externaldocument{…}` (`xr`, `xr-hyper`) define, the argument matched by its file name's stem among the masters.
- `loom:duplicate-label` (error and latex where one master's compile reads both definitions, else warning and model, as `duplicate-id` in §2): a non-id label defined twice anywhere in the quilt.
- `loom:macros-unloaded` (error, model): `\uses`, `\incomplete`, or `\nest` used in a master that carries neither loom's macro block nor `\usepackage{loom}` with a `loom.sty` beside it, so TeX meets an undefined control sequence.
- `loom:macro-shadowed` (warning, model): the preamble defines one of the three names outside loom's macro block and `loom.sty`.
- `loom:macros-missing` (error, model): a live document loads `\usepackage{loom}` with no `loom.sty` beside it and none on the TeX path, so it does not compile; `loom doctor` gives the patch that puts loom's macro block in its place.
- `loom:taxon-conflict` (warning, model): two masters declare different taxa for one environment.
- `loom:unknown-directive` (warning, model): a `% !LOOM` key not in the inventory.
- `loom:invalid-name` (warning, model): a `% !LOOM name:` outside a node, empty, or given twice in one node, where the last is used.
- `loom:unlabelled-node` (info, model): a theorem-like environment without an id.
- `loom:positional-proof-key` (info, model): a node with more than one unlabelled proof.
- `loom:unexpected-proof` (info, model): a proof attached to a block explicitly classified as definition, assumption, or open claim.
- `loom:missing-proof` (warning, model): a local-proof block with no proof and no `\incomplete`, regardless of TeX style.

Arras displays this diagnostic on the block with a link to its row in a working-document Review tab. It does not change the recorded acceptance state.
- `loom:needs-classification` (warning, model): a live theorem-like block whose basis is unknown or whose signals conflict; add `% !LOOM basis:` inside it after deciding what the block asserts.
- `loom:misplaced-basis` (warning, model): a `% !LOOM basis:` directive outside a theorem-like block; it cannot classify a whole file or a proof.
- `loom:equation-in-proof-referenced` (warning, model): another node references an equation inside this node's proof.
- `loom:uses-missing` (info, model): a `\ref` in a proof not listed in `\uses`.
- `loom:uses-unused` (info, model): a `\uses` entry the proof's text never mentions.
- `loom:see-redundant` (info, model): a `% !LOOM see:` item that names the node it is written in, or that repeats a relation already declared on that node.
- `loom:dependency-cycle` (warning, latex): statement dependencies form a cycle; breaks settledness. The person is shown it until a block says it.
- `loom:snippet-failed` (warning, internal): TeX refused a text no compile makes (a node no document reaches, a landmark's, a preview) or a diagram, which shows as its source; naming the text's opening words, where it stands, and TeX's first complaint. Not raised where TeX does not run (`--no-compile`, no `make4ht`).
- `loom:closure-failed` (error, internal): a key's closure document did not compile; first LaTeX error attached; `loom check --closures` prints it under this code.
- `loom:atomize-target-exists` (warning, model, fixed): atomize would overwrite a file.
- `loom:import-outside-tree` (warning, model): import found a file outside the paper directory and did not copy it.
- `loom:non-utf8-source` (warning, latex): a scanned file was not UTF-8 and was decoded as Mac Roman or Latin-1 (DR-47).
- `loom:unknown-theoremstyle` (warning, internal): a `\theoremstyle` other than plain, definition, or remark; treated as plain (DR-46).
- `loom:taxon-name-macro` (info, internal): a `\newtheorem` display name is a macro the closure does not define; the environment name is used (DR-46).
- `loom:main-not-found` (warning, model): `[quilt] main` names a file that is not a master; the first master is used.
- `loom:main-unset` (info, model): `[quilt] main` is unset and the quilt holds several documents, so none is the default; choosing one by its path would be arbitrary. With one document, that one is the default and nothing is said.
- `loom:unknown-config-key` (warning, model): `config.toml` has a table or key outside the inventory of 4.2; it is ignored (M7).

Review:

- `loom:retired-ledger-key` (info, model): a ledger row whose key no longer exists and whose text no block holds either (a row on a key named by place goes with its text, `records.store.Records.placed`).
- `loom:detached-annotation` (info, model): annotations whose selectors no longer match, with a count per key.
- `loom:previous-key-match` (info, model): an acceptance row matches the text of a differently keyed proof.
- `loom:foreign-annotations` (warning, internal): a line of `.loom/records/annotations/log.jsonl` that is not a review event, or of `.loom/records/edits/log.jsonl` that is not a suggested edit's; it is skipped and the rest of the log still loads. An annotation whose `purpose` this loom does not know is read as a note and reported the same way.
- `loom:foreign-evidence` (warning, internal, subject `record`): a line of `.loom/records/evidence/log.jsonl` that is not a record of one of its kinds with that kind's fields (`evidence.md` §3), naming its line and what is wrong; it is skipped and the rest of the log still loads, so a result it would have spoken of reads as though it had never been written.
- `loom:foreign-asks` (warning, internal, subject `record`): a line of `.loom/records/asks/log.jsonl` that is not an ask or one of its events, an event naming an ask the log does not hold, or one its hand may not say (an agent withdrawing another's ask); it is skipped and the rest still loads.
- `loom:repeated-id` (warning, internal, subject `record`): a line of the annotation log, the suggested edits' log, the session index, the evidence log or the asks log that gives a second record an id another record already has, usually a line a hand-resolved merge kept twice. One per line, naming both lines and the edit that clears it; nothing is dropped or renumbered.
- `loom:annotation-types` (warning, internal, subject `record`): `.loom/records/annotation-types.toml` is not TOML, so the default types are used, or one of its types cannot be read and is skipped, naming what is wrong with it; info when there is no file, so the defaults are used and `loom upgrade` writes them. Annotations keep their own look either way, so nothing is drawn differently.

Gathering, which makes a work of each entry of a bibliography the person's documents and landmarks read (`nodes.md` §7), after every build:

- `loom:bib-entry-refused` (warning, latex): an entry loom cannot keep as a work, so it makes none of it, or keeps the work it made of the entry as it was before the entry changed; the rest are gathered. On the line the entry begins at, in the `.bib` that writes it (in the document, for a `\bibitem`), naming the entry by its key and saying what in it to change, such as an abbreviation no `@string` in that file defines and the field it stands in. It is the person's, in their own file, and they are told nowhere else; it is said by every build until the entry is put right.

The library's nodes, each a failure of one of the checks of [`nodes.md`](nodes.md) §11 in a file of `.loom/library/nodes/`, said of that file with its line where it has one and the node's id as its key. Loom makes these when it checks the store and refuses a write that would make one; no command, lint or doctor reports them yet (not built yet).

- `loom:node-unreadable` (error, internal, subject `record`): check 1. The file's fences are not where §1 puts them, it is not UTF-8, it holds a carriage return or a NUL, or its header is not TOML. No node is read from it, so what names it names nothing.
- `loom:node-schema` (error, internal, subject `record`): check 2. The file has no `schema`, or one this loom does not read.
- `loom:node-id` (error, internal, subject `record`): check 3. The file is not named by an id of §3, or its `id` is not its name; or, as loom writes it, its id equals another node's ignoring case, or the write makes only new nodes and the id is in the library already.
- `loom:node-taxon` (error, internal, subject `record`): check 4. The taxon does not agree with the id (§5): a reference's, a macros node's and a proof's is its kind's word, and a statement's is a word of lower-case letters and hyphens other than those three.
- `loom:node-key` (error, internal, subject `record`): check 5. A key §2 does not name, one not allowed on the node's kind or, for `label`, `pages` and `authors`, with or without a `source`, or a value not of its type, an empty string or an empty list among them; or an `anchors` key that is not one of the node's own anchors, or one given two numbers.
- `loom:node-parent` (error, internal, subject `record`): check 6. A proof whose statement, or a macros node whose reference, is not in the library; a `source` that is not a reference in it; or a stem that names both a statement and a work.
- `loom:node-edge` (error, internal, subject `record`): check 7. An id in `uses` or `mentions` that is not in the library or is a macros node; one in both; or a list not sorted, holding an id twice, or holding the node itself.
- `loom:node-body-ref` (error, internal, subject `record`): check 8. The body points at a node it lists in neither `uses` nor `mentions`, the node itself, a proof's statement and their anchors apart; gives a referencing command an argument that is neither an id nor an anchor, or a citation a key that is no reference's id; defines a label that is not one of its own anchors, or one twice; or points at an anchor its owner, a node with text, does not define; uses a command named as a pointer is (ending in `ref`, `refs` or `refrange`, or holding `cite`, either case of their first letter) that loom does not read and its work's macros do not define; points or cites wrongly through its work's own command that wraps `\ref` or `\cite`, or defines a label through one that wraps `\label`; or numbers in `anchors` an anchor the body does not define. A comment and verbatim text are not read.
- `loom:node-bibtex` (error, internal, subject `record`): check 9. A reference's body is not one BibTeX entry standing alone (an `@string`, `@preamble` or `@comment`, text beside the entry, an entry with no key, or one using an abbreviation other than a month's), or its key is another reference's, compared ignoring case.
- `loom:node-macros` (error, internal, subject `record`): check 10. A macros node holds nothing, or text, or a command that neither loads a package nor defines one (the list is `library/body.py`'s `ARGUMENTS`), at its top level, in `\AtBeginDocument`, or in a branch of a conditional; or a conditional whose condition loom does not read or that no `\fi` ends (`nodes.md` §8); the message names the command.
- `loom:node-incomplete` (error, internal, subject `record`): check 11. A pointer, a proof with no text, without `source` or `pages`; or a stub, a statement with no text, without `source`.
- `loom:foreign-tags` (warning, internal, subject `record`): a line of `.loom/records/tags/log.jsonl` that is neither a tag nor an untag. It is skipped and the rest of the log still loads.
- `loom:foreign-library-acts` (warning, internal, subject `record`): a line of `.loom/records/library/log.jsonl` that is no act on a work. It is skipped and the rest of the log still loads.

Compiles:

- `loom:compile-failed` (error, latex, fixed): a document's last compile made no PDF, stopped by a TeX error. Read from the log its compile folder holds, which every whole compile of it leaves, the server's and `loom compile`'s, so it goes when the document next compiles; a compile cut short leaves no log there. An error is a `!` line TeX follows with its context, which it does after every error it reports. On the document's key; TeX's line belongs to the file it was reading, so the location is that file and line where the file is one the person can open in the viewer, their own `.tex`, `.sty`, `.cls` or `.bib`, and there is none where it is TeX's own, loom's or the compile's (a `.bbl`, an `.aux`). The message gives TeX's first error, with the macro an undefined control sequence names and, where it is not the document, the file TeX was reading. It is an error while the log is newer than every file the document reads (the document, what it inputs, its local styles), and a warning once one of them has changed since, its message saying it is from the last compile, before that change: until the next compile, what it says may be mended already.
- `loom:compile-errors` (error, latex, fixed): a document's last compile made its PDF though TeX reported errors; said, placed and aged as `loom:compile-failed` is, with how many.

Links in Markdown files: each link and image source of a shown Markdown file, read off the page the viewer draws of it and judged by the resolver every `quilt:` and `cited:` link answers to, so that lint and the page agree on what a link reaches. A link in code or mathematics is none, and another site's address is not followed. One per link, on the file and line that wrote it. A link to a file, a key or a place in one that is not there is class `latex`, the class of a reference to nothing in a document: the person sees it in their own text and can put it right by hand, a shown file is the person's whoever wrote the link, and no place an agent owns is shown. A link to a work by an identifier no work of the library states is class `model`, which an agent mends with `loom link`.

- `loom:link-target-missing` (warning, latex): a link names nothing the viewer shows: a file that does not exist, is hidden, is a folder or lies outside the quilt, a LaTeX file by its path, or a key, annotation or session the quilt does not hold; or, in the research state, a result gone since the page was written through loom, which its page lists among its broken links.
- `loom:link-place-missing` (warning, latex): a link reaches what it names and not the place in it: a heading the Markdown file or notebook does not have, matched exactly as the viewer matches an id, a heading of the file's own, a line past a text file's end, a place in a PDF that is not `page=N`, or a key the document or node does not hold.
- `loom:link-work-unknown` (warning, model): a `cited:` link names no identifier (`doi`, `arXiv`, `MR` or `zbMATH`), or one no work of the library states. Carries `loom link CITEKEY`, which prints the work's link as it is named now: by the first identifier its entry states, else as `quilt:` and its reference.

Interface:

- `arras:manifest-unreadable` (error, fixed): emitted by the viewer when `manifest.json` is not valid JSON.

It is listed here so the code is reserved, and it is in the **viewer's** namespace rather than a publisher's: a diagnostic a viewer raises about a manifest is the viewer speaking, and naming it `loom:` said that loom had complained about something loom never saw. So loom emits `loom:interface-version` (error, internal, fixed) nowhere; it stays registered so that the code is never reused.

### The workbench and the record

**[decided]** These concern loom's own record of the quilt and carry `subject: "record"` except where noted.

- `loom:superseded-file` (info, model): a document a conversion replaced; it defines nothing until `loom live`.
- `loom:history-missing` (error, internal): a step directory or one of its files is gone.
- `loom:history-edited` (error, internal): a version file, a preamble, or a step's document — a landmark, or a copy step's source — does not hash to what the ledger recorded.
- `loom:history-corrupt` (error, internal): a ledger line cannot be read, or a step number does not follow the last.
- `loom:history-interrupted` (warning, internal): a step directory no ledger line names, left by a step interrupted before it was recorded; nothing reads it, and every command that records a step refuses until it is removed.
- `loom:dangling-ancestry` (warning, internal): a `fork`, `revert`, `restore` or `copy` line names a step, a landmark or a version the history no longer resolves.
- `loom:id-reused` (warning, model, subject `source`): an id the history retired is defined again with a text the history never recorded.
- `loom:node-recovered` (info, model, subject `source`): an id the history retired is defined again with a text it did record.
- `loom:no-live-document` (info, model, subject `source`): the quilt holds no LaTeX document of the person's, so it defines no nodes. With a landmark, it carries the fix that starts one from the newest, `loom history restore NAME --to FILE`. With none, it is raised only where the quilt shows no Markdown file, notebook or HTML page of the person's beyond the README.md and the agents' instruction files loom writes at its root, since a quilt of lessons or notes is being worked on in its files; its message then says a document may be written anywhere in the quilt, and it carries `loom import FILE` (a paper being written) and `loom library add FILE` (a paper being read). A viewer's page for a quilt with nothing to read shows these fixes.
- `loom:derived-id-in-person-document` (warning, model, subject `source`): one of the person's documents defines or cites an agent document's derived id; the message names the plain id to use.
- `loom:agent-document-unrecorded` (warning, model, subject `source`): a document in `.loom/agents/copies/` that no `copy` step made, so it can be neither adopted nor refreshed; carries the fix `loom draft DOC --ai NAME.tex`, DOC the default document.
- `loom:plain-id-in-agent-document` (warning, model, subject `source`): a plain id defined in an agent document, where every id is derived; carries the fix `loom id --next`, whose id takes `-ai`.
- `loom:agent-permissions-stale` (warning, internal): `.claude/settings.json` is not what `[agents] deny` and this loom make it, so Claude Code holds agents to an older boundary than loom's own commands do; carries the fix `loom upgrade`.
- `loom:home-missing` (warning, model): `[quilt] home` names a file the viewer does not show — missing, or hidden — so the viewer opens on the root README.md or the default document instead (plan 0.22.7).
- `loom:write-left` (warning, latex, subject `source`): a write the journal records on the person's files (a Keep, an undo, a Discard, a restore, a put-back, a tick, a save of Settings) that recovery could neither finish nor undo, since a file of it changed since, the history lacks a text it names, or its journal line cannot be trusted; one per act, at its first file. The message says what the journal records, never who began it: each file as the act left it, as before it, or neither, by the digests the line records; that both texts are kept in the history only when the store holds them; and in plain words what makes it go, with no command and no id: each file reading exactly as before the act or as the act left it, which putting back the version History kept just before the act does where it kept one, or, where the history lacks a text, only each file reading as the act left it. A line recovery cannot trust, such as one that came with a copied folder, is said with no file and no place, since its paths are not believed. It stands until the act is settled. Its one fix, "settle it as it stands", carries `act` `{endpoint: "write-settle", body: {act: ID}}`, which a viewer offers as its control after showing `write-settle-preview`'s words, and the command `loom doctor --settle ID`; the act's id is in those alone (`docs/design/writes.md`, "Settling as it stands").
- `loom:document-gone` (warning; latex where annotations are on the document, else model): a drafting document that acceptance rows or annotations name is gone, and the history records no move that leads to a live document. One per document, named by the last path the history knows for it, counting the rows and annotations that name it, with its rows' keys in `keys` and `loom mv OLD NEW` as its fix (DR-297-ikmartin). Where annotations are on it the message leads with them (`3 annotations are on drafting/old.tex, which is gone; …`) and the class is `latex`, so a person's problems page says it, a warning that counts in no exit; one that only acceptance rows name is `model`.

## 4. Adding a code

**[decided]** A new loom code is added here with a severity and a one-line meaning before it is emitted. A new reserved code is added on both sides at once, since the viewer may give it an affordance.
