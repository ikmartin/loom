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
| `owner` | `person`, `copy`, `work` | optional; whose it is to put right. Absent means `person`. |
| `fixes` | list of `{label, command, act?}` | optional; commands that would resolve it, `act` the ones a viewer may do itself |

Viewers group by what is wrong, filter by severity and code, and link locations and keys. A viewer renders unknown codes generically and never fails on one.

**[decided]** `class` says what kind of problem a diagnostic is. `latex` is a problem in a document's LaTeX that an author would recognise: a document whose last compile failed or finished with errors, what TeX meets in a document's compile, such as a reference to nothing, an id defined twice, a file missing or included twice, or a document never closed, and a circle among the dependencies the person's statements declare, which no block says yet, and a document gone with annotations on it, which no page of notes says yet; and a link in one of the person's Markdown files that goes nowhere, the same fault as a reference to nothing. `model` is the publisher's model of the corpus: the hygiene of ids, `\uses`, links, agents' copies, records and the publisher's own macros, which an agent keeps. `internal` is the publisher's own difficulty or the integrity of its records: a digest's problems, a text TeX refused that no compile makes, a history edited by hand. A viewer's problems page and its lists of a key's diagnostics show a person `latex` alone, their own before an agent's copy's; where a viewer reads a particular code to say something in its own place (a block with no proof, a quilt with no document, a work with no copy to read, a permission file out of date), it reads it whatever its class. The publisher's lint shows every class, since agents' audits rest on the model's codes and the publisher's records on the internal ones. Each code has a class, said in its entry below; where a code's instances differ, the publisher says each one's. A diagnostic with no class, or with one a viewer does not know, is `latex`, so a viewer filtering by class hides nothing a publisher did not classify.

**[decided]** `severity` is `error` for a fault in what TeX compiles or in the publisher's records. A problem of the publisher's model that never stops TeX is a `warning` at most, so that what counts errors, a lint's exit, an agent's first look and a server's start line, counts only what is one. What a gate refuses is decided by code, not by grade: loom will not adopt an agent's copy, nor linearize a document, over a new diagnostic of a code that was an error before the grades followed what TeX does (`scan/diagnostics.py`, `GATED`), at any grade but info, so a regrade changes what is said and never what loom lets through.

**[decided]** `subject` separates what is wrong with the corpus's text from what is wrong with the publisher's own record of it. They are different kinds of work, and a viewer may group them apart; a viewer that ignores the field loses nothing.

**[decided]** `owner` says whose a diagnostic is to put right (plan 0.25.3). `person` is the author's: their documents, their bibliography, their configuration, the records of their review. `copy` is an agent's: every location in an agent's copy, or every key a result of one; the agent puts it right, or the author leaves it out when taking the copy back. `work` is a cited work's: every location in a digest, or every key one of its results. A digest is the publisher's reading of a paper, so a digest's diagnostic is the work's even where the author's text cites the result it is on, and only digesting the work again can mend it. A diagnostic naming both the author's and a copy's is the author's. A viewer puts the author's first and counts only theirs; a viewer that ignores the field shows every diagnostic as the author's, as before the field.

**[decided]** `fixes` are data: each is what an agent does to resolve the diagnostic, a command or an edit described in words. A viewer never runs a command, and among a person's problems it shows none. A fix may also carry `act`, `{endpoint, body}`: the write-API endpoint (`write-api.md`) that does what the command does, and the body to send it. A viewer that serves writes may offer such a fix as a button, through that endpoint and nothing else, and says the endpoint's answer beside it; without a publisher it offers none. The label says what the fix would achieve, so that a reader choosing between two fixes is choosing between outcomes.

**[decided]** Loom sets `act` on three fixes. `loom:undigested-citekey`'s digests the work (`library-update`, `{works: [CK]}`); `loom:agent-permissions-stale`'s rewrites the permission files (`agents-update`); and every diagnostic owned by a work carries "digest CK again" (`library-update`, `{works: [CK], redo: true, steps: ["extract"]}`), except those digesting again does not mend: the renderer's fallback, a dependency cycle (which is the paper's own), and those about the work rather than the digest's text (`loom:missing-package`, `loom:unverified-locators`, `loom:version-mismatch`, `loom:digest-without-bib`, `loom:no-readable-copy`). A digest's id defined twice carries no hand fix, since the person never edits a digest.

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

**[decided]** `duplicate-id` is an error of class `latex` where one root's inclusion tree reaches two of its definitions, since a compile of that root reads both; where no root reaches two of them, as when two roots each define it once or a file no root reaches holds one, it is a warning of class `model`. `dangling-link` is an error of class `latex` for a reference a root's compile reads, which prints `??` there; a link TeX never reads (loom's `\uses`, which prints nothing, a `% !LOOM see:` relation, or any link in a file no root reaches) is a warning of class `model`. A diagnostic in a cited work's digest is `internal` whatever its code (§1, `owner`).

**[decided]** A publisher may leave a doubly-defined identifier with no text and the state `conflicted` (manifest §3, §8) rather than choosing between the definitions. A viewer renders that state like any other the manifest declares.

## 3. Loom codes

**[decided]** Namespaced `loom:`. Severity and class in parentheses. All except those marked fixed can be silenced with `[lint] disable`. A diagnostic that a cited work's digest holds, owner `work`, is `internal` whatever its code: a digest is loom's reading of another paper.

Source and structure:

- `loom:environment-spans-files` (warning, model): a theorem-like environment opens in one file and closes in another. A `\begin{document}` that no file the document reads closes is an error of class `latex`, the fault TeX stops on at the document's end.
- `loom:line-anchoring` (warning, model, fixed): a `\begin` or `\end` of a theorem-like environment is not alone on its line; reported by `import`, `id` and `atomize`.
- `loom:unknown-environment` (warning, model): a theorem-like environment the preamble closure does not declare, as loom reads it; fix with `% !LOOM environment:`. A class or package loom does not read may declare it, and an environment TeX itself lacks stops the compile, which `loom:compile-failed` reports.
- `loom:unattached-proof` (warning, model): a `proof` neither adjacent to a node nor referencing one.
- `loom:multi-target-proof` (warning, model): a proof's optional argument references several nodes; attached to the first.
- `loom:reference-to-loose` (error and latex for a `\ref` in a master's compile, which prints `??` there; warning and model for a `\uses`, which prints nothing; info and model in loose files): a reference to a node the master does not reach; never for a target in a digest file, which is loose by construction (DR-76). A master reaches what it includes and what the documents it names in `\externaldocument{…}` (`xr`, `xr-hyper`) define, the argument matched by its file name's stem among the masters.
- `loom:duplicate-label` (error and latex where one master's compile reads both definitions, else warning and model, as `duplicate-id` in §2): a non-id label defined twice anywhere in the quilt.
- `loom:macros-unloaded` (error, model): `\uses`, `\incomplete`, or `\nest` used in a master that carries neither loom's macro block nor `\usepackage{loom}` with a `loom.sty` beside it, so TeX meets an undefined control sequence.
- `loom:macro-shadowed` (warning, model): the preamble defines one of the three names outside loom's macro block and `loom.sty`.
- `loom:macros-missing` (error, model): a live document loads `\usepackage{loom}` with no `loom.sty` beside it and none on the TeX path, so it does not compile; `loom doctor` gives the patch that puts loom's macro block in its place.
- `loom:taxon-conflict` (warning, model): two masters declare different taxa for one environment.
- `loom:prefix-is-citekey` (warning, model): the quilt's id prefix equals a bibliography key.
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
- `loom:snippet-failed` (warning, internal): TeX refused a text no compile makes (a node no document reaches, a digest's statement, a landmark's, a preview) or a diagram, which shows as its source; naming the text's opening words, where it stands, and TeX's first complaint. Not raised where TeX does not run (`--no-compile`, no `make4ht`).
- `loom:closure-failed` (error, internal): a key's closure document did not compile; first LaTeX error attached; `loom check --closures` prints it under this code and `loom compile` names `loom:missing-package` first when a digest in the closure requires a package the preamble lacks.
- `loom:atomize-target-exists` (warning, model, fixed): atomize would overwrite a file.
- `loom:import-outside-tree` (warning, model): import found a file outside the paper directory and did not copy it.
- `loom:non-utf8-source` (warning, latex): a scanned file was not UTF-8 and was decoded as Mac Roman or Latin-1 (DR-47).
- `loom:unknown-theoremstyle` (warning, internal): a `\theoremstyle` other than plain, definition, or remark; treated as plain (DR-46).
- `loom:taxon-name-macro` (info, internal): a `\newtheorem` display name is a macro the closure does not define; the environment name is used (DR-46).
- `loom:citekey-slug-collision` (warning, model): two citekeys share a digest prefix after slugging (DR-45).
- `loom:main-not-found` (warning, model): `[quilt] main` names a file that is not a master; the first master is used.
- `loom:main-unset` (info, model): `[quilt] main` is unset and the quilt holds several documents, so none is the default; choosing one by its path would be arbitrary. With one document, that one is the default and nothing is said.
- `loom:unknown-config-key` (warning, model): `config.toml` has a table or key outside the inventory of 4.2; it is ignored (M7).

Review:

- `loom:retired-ledger-key` (info, model): a ledger row whose key no longer exists.
- `loom:detached-annotation` (info, model): annotations whose selectors no longer match, with a count per key.
- `loom:previous-key-match` (info, model): an acceptance row matches the text of a differently keyed proof.
- `loom:foreign-annotations` (warning, internal): a line of `.loom/records/annotations/log.jsonl` that is not a review event, or of `.loom/records/edits/log.jsonl` that is not a suggested edit's; it is skipped and the rest of the log still loads.
- `loom:repeated-id` (warning, internal, subject `record`): a line of the annotation log, the suggested edits' log, the session index or the links file that gives a second record an id another record already has, usually a line a hand-resolved merge kept twice. One per line, naming both lines and the edit that clears it; nothing is dropped or renumbered.
- `loom:annotation-types` (warning, internal, subject `record`): `.loom/records/annotation-types.toml` is not TOML, so the default types are used, or one of its types cannot be read and is skipped, naming what is wrong with it; info when there is no file, so the defaults are used and `loom upgrade` writes them. Annotations keep their own look either way, so nothing is drawn differently.

References and digests:

- `loom:unmatched-postnote` (warning, internal): a `\cite[postnote]` that matched no digest node, when a digest for the citekey exists; a digest node's own locator title is exempt (DR-66), and so is a postnote that names a page alone. The citation's element carries `data-unmatched` ([dialect.md §2.8](dialect.md#28-references-and-citations)), which is where a person meets it.
- `loom:cites-proposed-node` (warning, model): a citation, `\ref` or `\uses` names a proposal from outside its own file, which makes no edge until the result is verified (`digests.md` §5).
- `loom:undigested-citekey` (info, internal): a cited key with no digest; the ingest trigger.
- `loom:postnote-from-another-version` (info, internal): a `\cite[postnote]{key}` that `key`'s own digest does not answer, answered by the digest of another version of the work (an entry filed as another document of it, `loom-copy-of`); the edge goes to that version's node. A key counts as digested for `loom:undigested-citekey` when a version of it is.
- `loom:unresolved-work` (info, internal): a cited work whose bibliography entry states no identifier (`doi`, `eprint`, `mrnumber`, `zbl`, or a URL carrying one) and whose document loom does not hold. It can still be digested and still enters the graph; what it cannot do is deduplicate against another corpus's copy or be fetched (DR-109). A work holding its PDF or its LaTeX is silent here, since it wants nothing fetched.
- `loom:unverified-locators` (warning, internal): a digest extracted from a preprint while the bibliography cites a published version, or one that does not say what it was extracted from. Its result numbers and page references are unverified against the document a reader will open (DR-109). The commands that read a digest say the same where it is read (DR-313-ikmartin).
- `loom:version-mismatch` (warning, internal): a digest's source version differs from the bibliography's.
- `loom:missing-package` (warning, internal): a digest requires a package the preamble closure does not load.
- `loom:digest-without-bib` (warning, internal): a digest whose citekey is not in the bibliography.
- `loom:no-readable-copy`: renderable content — a digest file or a recorded result — whose work has no artifact in the store that can be read. **`warning`** where there is no artifact at all, which is the state the invariant is about; **`info`** where loom holds the paper's LaTeX and no PDF, since source is what a statement is checked against and what it lacks is pagination and a page. Never an error: loom cannot fetch without consent, and a build must not fail for want of a document. A work the author has declared unreadable is silent here (DR-198). Class `internal`.

Compiles:

- `loom:compile-failed` (error, latex, fixed): a document's last compile made no PDF, stopped by a TeX error. Read from the log its compile folder holds, which every whole compile of it leaves, the server's and `loom compile`'s, so it goes when the document next compiles; a compile cut short leaves no log there. An error is a `!` line TeX follows with its context, which it does after every error it reports. On the document's key; TeX's line belongs to the file it was reading, so the location is that file and line where the file is one the person can open in the viewer, their own `.tex`, `.sty`, `.cls` or `.bib`, and there is none where it is TeX's own, loom's or the compile's (a `.bbl`, an `.aux`). The message gives TeX's first error, with the macro an undefined control sequence names and, where it is not the document, the file TeX was reading. It is an error while the log is newer than every file the document reads (the document, what it inputs, its local styles), and a warning once one of them has changed since, its message saying it is from the last compile, before that change: until the next compile, what it says may be mended already.
- `loom:compile-errors` (error, latex, fixed): a document's last compile made its PDF though TeX reported errors; said, placed and aged as `loom:compile-failed` is, with how many.

Links in Markdown files: each link and image source of a shown Markdown file, read off the page the viewer draws of it and judged by the resolver every `quilt:` and `cited:` link answers to, so that lint and the page agree on what a link reaches. A link in code or mathematics is none, and another site's address is not followed. One per link, on the file and line that wrote it. Class `latex`, the class of a reference to nothing in a document: a shown file is the person's whoever wrote the link, and no place an agent owns is shown.

- `loom:link-target-missing` (warning, latex): a link names nothing the viewer shows: a file that does not exist, is hidden, is a folder or lies outside the quilt, a LaTeX file by its path, or a key, annotation or session the quilt does not hold; or, in the research state, a result gone since the page was written through loom, which its page lists among its broken links.
- `loom:link-place-missing` (warning, latex): a link reaches what it names and not the place in it: a heading the Markdown file or notebook does not have, matched exactly as the viewer matches an id, a heading of the file's own, a line past a text file's end, a place in a PDF that is not `page=N`, or a key the document or node does not hold.
- `loom:link-work-unknown` (warning, latex): a `cited:` link names no identifier, or one no entry of the library states. Carries `loom link CITEKEY`, which prints the work's link as it is named now: a work that states no identifier and was not filed from its PDF is named by its authors, title and year, so correcting them leaves a link to the old name.

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
- `loom:no-live-document` (info, model, subject `source`): the quilt holds no document of the person's, so it defines no nodes. With a landmark, it carries the fix that starts one from the newest, `loom history restore NAME --to FILE`; with none, its message says a document may be written anywhere in the quilt, and it carries `loom import FILE` (a paper being written) and `loom library add FILE` (a paper being read). A viewer's page for a quilt with nothing to read shows these fixes.
- `loom:derived-id-in-person-document` (warning, model, subject `source`): one of the person's documents defines or cites an agent document's derived id; the message names the plain id to use.
- `loom:agent-document-unrecorded` (warning, model, subject `source`): a document in `.loom/agents/copies/` that no `copy` step made, so it can be neither adopted nor refreshed; carries the fix `loom draft DOC --ai NAME.tex`, DOC the default document.
- `loom:plain-id-in-agent-document` (warning, model, subject `source`): a plain id defined in an agent document, where every id is derived; carries the fix `loom id --next`, whose id takes `-ai`.
- `loom:agent-permissions-stale` (warning, internal): `.claude/settings.json` is not what `[agents] deny` and this loom make it, so Claude Code holds agents to an older boundary than loom's own commands do; carries the fix `loom upgrade`.
- `loom:home-missing` (warning, model): `[quilt] home` names a file the viewer does not show — missing, or hidden — so the viewer opens on the root README.md or the default document instead (plan 0.22.7).
- `loom:document-gone` (warning; latex where annotations are on the document, else model): a drafting document that acceptance rows or annotations name is gone, and the history records no move that leads to a live document. One per document, named by the last path the history knows for it, counting the rows and annotations that name it, with its rows' keys in `keys` and `loom mv OLD NEW` as its fix (DR-297-ikmartin). Where annotations are on it the message leads with them (`3 annotations are on drafting/old.tex, which is gone; …`) and the class is `latex`, so a person's problems page says it, a warning that counts in no exit; one that only acceptance rows name is `model`.

## 4. Adding a code

**[decided]** A new loom code is added here with a severity and a one-line meaning before it is emitted. A new reserved code is added on both sides at once, since the viewer may give it an affordance.
