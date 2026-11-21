# Evidence and asks

This page specifies two logs loom keeps under `.loom/records/`: the **evidence log**, what someone did to a text (digested it, compared it with its paper, ran Lean on it, attested it), and the **asks log**, what a person asked of an agent and an agent of a person. It wins over `docs/design/library.md` about a shape, as that wins about what a record means. The node files these records speak of are `nodes.md`'s.

What is built: both logs, their formats, their readers and writers (`loom/src/loom/evidence/log.py`, `asks.py`), the diagnostics for a line that cannot be read, and a draft's result's status (§5, `status.py`, over the drafts' web, `web.py`). A library node's status waits for the node store, and Review's lists are not built yet; nothing yet writes a record but the tests.

## 1. Files

- `.loom/records/evidence/log.jsonl` (`paths.EVIDENCE_LOG`) and `.loom/records/asks/log.jsonl` (`paths.ASK_LOG`). Both travel with the quilt, and loom deletes nothing in them.
- One JSON object a line, UTF-8, keys sorted, no spaces between tokens, as `json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` writes it. A reader takes any valid JSON.
- Appended under the log's own lock (`loom.locks.locked` on the file) and never rewritten, so two clones' lines merge by keeping both. A writer that must decide from what the log holds takes the lock first and decides under it.
- A line that cannot be read, is not of a known kind, or lacks or adds a field is skipped and reported (`loom:foreign-evidence`, `loom:foreign-asks`); the rest still loads. Two lines under one id are `loom:repeated-id`, as for the other logs.
- No agent writes either file by hand: both are under `agents.LOOM_DIRS`, so a quilt's permission files refuse it.

## 2. What a record names

A **subject** is one text by its hash, written `{"<kind>": <name>, "hash": <hash>}` with exactly those two keys. A hash is `sha256:` and 64 lower-case hexadecimal digits.

| kind | name | hash |
| --- | --- | --- |
| `node` | a node's id (`nodes.md` §3) | the node file's bytes (`nodes.md` §1) |
| `label` | a draft's result by its label: the block's id where it has one (an id is a label, `source-contract.md` §3), else its first `\label` | the block's own text as the acceptance ledger hashes it (`records.locate.block_hash`): each child cut out and stood for by its marker, normalised (`scan.hashing.normalize`), so a line that is only a comment, spaces at a line's end and extra blank lines do not change it, and its title, its label and a comment at the end of a line do |
| `macro` | a command a person defined, without its backslash, as `scan.macros` reads it | its definition as `scan.macros.parse_macros` reads it (§5.1) |

A record about a label holds for every block of the quilt that bears that label and has that hash: a draft copied to a new file keeps what was said of the results it did not change, and of two blocks bearing one label, the one whose text changed no longer has it. A record about a macro holds wherever a definition with that hash is used. A block with no label has no lasting name, and nothing records about it.

**Who acted**, `by`: `{"kind": "loom"}`, or `{"kind": "person", "name": …}` with the quilt's reviewer name, or `{"kind": "agent", "name": …}` with the name the agent writes as.

**Ids** are `ev-` (a record of evidence) or `t-` (an ask), the day, and a random token (`records.ids.draw`), so two clones never draw one id. **`at`** is UTC to the second, `2026-11-21T10:02:11Z`.

## 3. The evidence log

Every line has `id`, `kind`, `at` and `by`, and the fields of its kind below and no others. A kind written by one hand only is refused from another.

### 3.1 `digested`: how a node's text was made

`on` a statement or a proof node; `how`; `from`, the work and its stored document read, as `{ref, pdf | tex, pages?}`, or null for a node a person wrote from no document.

| `how` | by | means |
| --- | --- | --- |
| `extracted` | loom | read mechanically from the work's TeX source |
| `transcribed` | an agent | read from the pages of a PDF |
| `read` | an agent | read from a TeX source, by reading |
| `corrected` | an agent | an agent's correction to a node no person had compared |
| `written` | a person | written or edited by hand |

A stub needs no record: it reads as a stub by its empty body.

```json
{"at":"2026-11-21T10:02:11Z","by":{"kind":"loom"},"from":{"ref":"tq-00A1-ref","tex":"sha256:3b4ea141a571256761f0c16139130d7a4ede1d99bb97d151f5a4b4fbca59bd1e"},"how":"extracted","id":"ev-2026-11-21-k2m9xq","kind":"digested","on":{"hash":"sha256:409a44fa2e6f1148d759dac9d5799bc3d3d7932b865838f3dc0e8492683e631b","node":"tq-00K3"}}
{"at":"2026-11-21T11:40:03Z","by":{"kind":"agent","name":"Claude Code"},"from":{"pages":"21","pdf":"sha256:5e92c2a617e6600c731a614660507a9bb48e86bbebf49175062bb63ef73565c0","ref":"tq-00B1-ref"},"how":"transcribed","id":"ev-2026-11-21-7rw3fd","kind":"digested","on":{"hash":"sha256:d4847a0726046231167ef74c11d148a29371dd768d21f77e8f0938792c84fa66","node":"tq-00B7"}}
```

### 3.2 `compared`: a person found a node faithful to its paper

`on` a statement or a proof node; `with`, the document compared against, `{ref, pdf | tex, pages?}`. Only a person. It is what the viewer words "matches the paper", and says nothing of the mathematics.

```json
{"at":"2026-11-21T14:12:40Z","by":{"kind":"person","name":"A. Author"},"id":"ev-2026-11-21-q4hn8c","kind":"compared","on":{"hash":"sha256:409a44fa2e6f1148d759dac9d5799bc3d3d7932b865838f3dc0e8492683e631b","node":"tq-00K3"},"with":{"pages":"12","pdf":"sha256:5e92c2a617e6600c731a614660507a9bb48e86bbebf49175062bb63ef73565c0","ref":"tq-00A1-ref"}}
```

### 3.3 `proposed` and `declined`: a correction to a compared node

An agent's correction to a node a person has compared waits as `proposed`: `on` the node at the text it corrects, `bytes` the whole new file, `why` the agent's reason. Only an agent. It is open while the node still has the hash it names and no `declined` names it. The person declines it with `declined`: `proposal` its id, `why` (may be empty). Taking it writes the node and records `compared` on the new text, so it needs no record of its own: the node then has the proposal's bytes.

```json
{"at":"2026-11-21T15:01:09Z","by":{"kind":"agent","name":"Claude Code"},"bytes":"+++\nschema = 1\nid = \"tq-00A4\"\ntaxon = \"definition\"\nnumber = \"2.1\"\ntitle = \"Widget\"\nsource = \"tq-00A1-ref\"\nlabel = \"def:widget\"\npages = \"4\"\n+++\nA \\emph{widget} is a closed set $W \\subset \\mathbb{R}^n$ whose boundary lies in $\\Wid$.\n","id":"ev-2026-11-21-c8vz2a","kind":"proposed","on":{"hash":"sha256:151ca0e359d959ae7cef44e514938b850b887dd8f82951c218e88ff54c25461a","node":"tq-00A4"},"why":"page 4 has closed, not compact"}
{"at":"2026-11-21T16:20:00Z","by":{"kind":"person","name":"A. Author"},"id":"ev-2026-11-21-d0e5mt","kind":"declined","proposal":"ev-2026-11-21-c8vz2a","why":""}
```

### 3.4 `lean`: what loom ran and what Lean said

Only loom writes it, when it runs the check itself (`docs/design/library.md`, "Formalization"); nothing writes it yet.

- `on`: the result checked, a node or a label, at the hash it had.
- `project`: `{root, toolchain, mathlib, manifest}`, the Lean project's folder, its toolchain, the Mathlib revision and the hash of `lake-manifest.json`.
- `files`: every Lean file loom read, by path from the quilt's root, with its hash.
- `declarations`: each with `name`; `kind` (`theorem`, `def`, `axiom`, `structure`, `inductive`, `instance`, `abbrev`, `opaque`); `role`, `states` a result or `supports` one; `names`, the node or label its marker names (`{"node": …}` or `{"label": …}`, null for a declaration that only supports); `statement`, the hash of its statement as the marker delimits it; `axioms`, as Lean reports them; `sorry`.
- `assumed`: each library node, with its hash, stated as an axiom that the result rests on: the result is verified relative to these.
- `uses`: each result named by the marker of a declaration the result's declarations depend on, with its hash then. This is the map from Lean back to the paper, which finds a definition the statement reaches only through a macro.
- `replay`: `{tool, exit, output}`, the kernel's replay with its output kept.
- `ok`: Lean's verdict on the whole, and `errors`, a list of messages, where it failed.

```json
{"assumed":[{"hash":"sha256:d4847a0726046231167ef74c11d148a29371dd768d21f77e8f0938792c84fa66","node":"tq-00B7"}],"at":"2026-11-21T17:30:12Z","by":{"kind":"loom"},"declarations":[{"axioms":["Classical.choice","Quot.sound","propext"],"kind":"theorem","name":"Showcase.balanced_eq_zero_of_isTree","names":{"label":"lem:balanced"},"role":"states","sorry":false,"statement":"sha256:a872ffc36134baa29fd3e06d72ec803a51381cbd8a4098b5d90a150a6118ca37"},{"axioms":[],"kind":"def","name":"Quiver'.Connected","names":{"label":"def:connected"},"role":"states","sorry":false,"statement":"sha256:e608a6cadda37922163752ae109258a5bbc3ba4149e769e71e430d62cc49976c"}],"files":{"lean/Showcase/Balanced.lean":"sha256:9fcbee8cecede5392dcd690d71c6f21eea2d2ff7146a39217fa89c303c9555d8","lean/Showcase/Quiver.lean":"sha256:f0bb0301829286d526b964fcd377bfc46505925b37a23918e5154448081344a4"},"id":"ev-2026-11-21-l3an9e","kind":"lean","ok":true,"on":{"hash":"sha256:744b4c900c1908b82e08a2c65d2d1b551cdb30398fbf85e6675b721e7088b8c5","label":"lem:balanced"},"project":{"manifest":"sha256:67fa2287e7b8307aea7e9a6a681a9e329a089094dc47fbda219b071a24c866af","mathlib":"9d581dfff2e41de989072ea63abf3daf69311520","root":"lean","toolchain":"leanprover/lean4:v4.36.0"},"replay":{"exit":0,"output":"","tool":"leanchecker"},"uses":[{"hash":"sha256:fbcd6c18fb0435659158ad60c4811450da454537d67f3681785718ad4d53959a","label":"def:connected"}]}
```

### 3.5 `attested`: a person's word that the Lean says what the result says

Only a person. Two forms.

**On a result**, a statement node or a label: `lean`, the id of the `lean` record the person was shown; `statements`, each stating declaration's name with its statement's hash as shown; `closure`, every node and label the statement uses and what those use in turn, with the `lean` record's `uses` added, each at the hash shown; `rulings`, `{asked, answer}` for each question the paper never settled that the person answered (a list, often empty). Whether it still holds is judged on these contents, not on the `lean` id.

```json
{"at":"2026-11-21T18:05:44Z","by":{"kind":"person","name":"A. Author"},"closure":[{"hash":"sha256:fbcd6c18fb0435659158ad60c4811450da454537d67f3681785718ad4d53959a","label":"def:connected"},{"hash":"sha256:72bbc7f881e65639a1e4250896aa96c3dfe334cdc32ad708a0aad51436b80759","label":"prop:tree"},{"hash":"sha256:d4847a0726046231167ef74c11d148a29371dd768d21f77e8f0938792c84fa66","node":"tq-00B7"}],"id":"ev-2026-11-21-z6pq1w","kind":"attested","lean":"ev-2026-11-21-l3an9e","on":{"hash":"sha256:744b4c900c1908b82e08a2c65d2d1b551cdb30398fbf85e6675b721e7088b8c5","label":"lem:balanced"},"rulings":[],"statements":{"Quiver'.Connected":"sha256:e608a6cadda37922163752ae109258a5bbc3ba4149e769e71e430d62cc49976c","Showcase.balanced_eq_zero_of_isTree":"sha256:a872ffc36134baa29fd3e06d72ec803a51381cbd8a4098b5d90a150a6118ca37"}}
```

**On a macro**, with no other field: the person read this notation's definition once, as part of attesting a result that uses it. It holds wherever that definition is used, until the definition changes, so each command a person defined costs one look in all, not one for every statement that uses it. Commands of LaTeX itself and of packages are never attested.

```json
{"at":"2026-11-21T18:05:44Z","by":{"kind":"person","name":"A. Author"},"id":"ev-2026-11-21-n0t4x1","kind":"attested","on":{"hash":"sha256:82c642a324596da88d68ff67580fd61bbae8a996651c6cd5e12f28a21075fa69","macro":"Zcyc"}}
```

### 3.6 `sought`: loom looked for a stub's result and did not find it

`on` a stub; `from`, the work's TeX source read, `{ref, tex}`; `found`, always false (a result found is digested). Only loom.

```json
{"at":"2026-11-21T10:02:12Z","by":{"kind":"loom"},"found":false,"from":{"ref":"tq-00A1-ref","tex":"sha256:3b4ea141a571256761f0c16139130d7a4ede1d99bb97d151f5a4b4fbca59bd1e"},"id":"ev-2026-11-21-9sm2kd","kind":"sought","on":{"hash":"sha256:d4847a0726046231167ef74c11d148a29371dd768d21f77e8f0938792c84fa66","node":"tq-00B7"}}
```

### 3.7 `mention`: a citation that names no result is only a mention

The person's word that a citation of a work with no result named in it is a mention and rests on nothing. `block`, the citing block as a note names its block: its `key`, the `hash` of its text and its `context` (`records.locate.context_of`), found again by `records.locate.follow`; `cites`, the reference; `undo`, true to take an earlier one back. Only a person. It holds while that block still cites the work with no locator.

```json
{"at":"2026-11-21T18:30:00Z","block":{"context":{"after":{"gap":1,"hash":"sha256:511c96ceb7174affc0b103d8fbbb33384196d849f1eeb3c2e9da6145053ae9d3"},"before":{"gap":1,"hash":"sha256:8f9d61fac39402898f831bfec31c774438bb77be6a0cbd47c83cf53d31858372"},"copies":1,"documents":["drafting/main.tex"],"kind":"proof","twin":false},"hash":"sha256:b5a45e5f4685d21700a0c4f00c2d7a11872c7f5f4a22a6cdf9525d36c2a66a90","key":"thm:main/proof"},"by":{"kind":"person","name":"A. Author"},"cites":"tq-00B1-ref","id":"ev-2026-11-21-m1nt0b","kind":"mention","undo":false}
```

## 4. The asks log

A stack an agent may take from, not a harness: nothing is assigned, ranked or scheduled, and no agent is woken. The log records the asking and what was said afterwards; whether an ask is still open is computed from what exists, never recorded.

### 4.1 `asked`

Every `asked` line has `event` (`asked`), `id`, `at`, `by`, `what`, `to` (`agent` or `person`), `on`, `from` and `words`, and the fields of its `what`.

- `on` is the place it is tied to, one of: `{"node": …}`; `{"label": …}`; `{"block": {key, hash, context}}`, a block of a person's document as a note names one (§3.7); `{"ref": …}` or `{"ref": …, "page": n}`, a work or one of its pages; `{"document": path}`.
- `from` lists the drafts it was asked for, so that Review can show only what concerns one draft.
- `words` are the person's or the agent's own, often empty.

| `what` | to | asked by | its fields |
| --- | --- | --- | --- |
| `read` | agent | person | `nodes`: the stubs to read |
| `digest` | agent | person | `ref`; `scope`: `uses`, `marked`, `chosen` or `all`; `nodes` where the scope names results, `marks` (the ids of the person's annotations of kind `to-digest` on the work's pages) where it names marks |
| `ask` | agent | person | `text`, the person's question; `quote`, the words it is on, where they selected some |
| `correct` | agent | person | `text`, what the person says differs; `on` is the node |
| `restate` | agent | person | `target`, a node or label subject; `differs`, what the person says the Lean gets wrong |
| `which-result` | agent | person | `cites`: the work a citing block cites with no result named; `on` is that block |
| `formalize` | agent | person | `target`; `state`, `prove`, `assume`: the subjects of each part of the boundary |
| `question` | person | agent | `text`; `choices`, up to 6 distinct strings of at most 200 characters; `quote`, the words it is on |
| `paper` | person | agent | `ref`; `link`, the http or https address it could not fetch from; `want`, `pdf` or `tex` |

The names are those of `library-views.md` §4.3, so the viewer draws an ask by its `what`.

```json
{"at":"2026-11-21T09:00:00Z","by":{"kind":"person","name":"A. Author"},"event":"asked","from":["drafting/main.tex"],"id":"t-2026-11-21-7h3qfw","nodes":["tq-00B7"],"on":{"node":"tq-00B7"},"to":"agent","what":"read","words":""}
{"at":"2026-11-21T09:20:02Z","by":{"kind":"agent","name":"Claude Code"},"event":"asked","from":["drafting/bounds.tex"],"id":"t-2026-11-21-pq0d4n","link":"https://doi.org/10.1000/example.2019.17","on":{"ref":"tq-00B1-ref"},"ref":"tq-00B1-ref","to":"person","want":"pdf","what":"paper","words":"The publisher's page asks for a login."}
{"at":"2026-11-21T09:31:10Z","by":{"kind":"agent","name":"Claude Code"},"choices":["both","only the proposition"],"event":"asked","from":["drafting/main.tex"],"id":"t-2026-11-21-w2c6ga","on":{"page":7,"ref":"tq-00C2-ref"},"text":"Your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?","to":"person","what":"question","words":""}
```

### 4.2 What is said of an ask afterwards

Each names its ask by `task`.

| `event` | by | its fields | means |
| --- | --- | --- | --- |
| `took` | an agent, on an ask to an agent | `session`, its loom session | it is working on it |
| `done` | an agent, on an ask to an agent | `made`, the ids of what it produced | what it produced, which loom checks |
| `answered` | the one an `ask` or a `question` was asked of | `words`, and for a `question`, `choice`, the number of one of its choices | the answer: a choice, words, or both |
| `withdrawn` | a person, or the agent that asked | | the ask is withdrawn; this is deleting it |

A person withdraws any ask and an agent only its own; an agent's withdrawal of another's is skipped and reported. An event may stand above its ask in the file, as a merge can leave it.

```json
{"at":"2026-11-21T09:04:31Z","by":{"kind":"agent","name":"Claude Code"},"event":"took","session":"s-2026-11-21-a8k2rx","task":"t-2026-11-21-7h3qfw"}
{"at":"2026-11-21T12:00:40Z","by":{"kind":"person","name":"A. Author"},"choice":1,"event":"answered","task":"t-2026-11-21-w2c6ga","words":"and note that 2.5 is only a remark"}
{"at":"2026-11-21T12:10:00Z","by":{"kind":"person","name":"A. Author"},"event":"withdrawn","task":"t-2026-11-21-7h3qfw"}
```

## 5. Status

A result's status is computed from the evidence and the texts now, and never stored (`loom/src/loom/evidence/status.py`). It is asked of a node by its id, or of a draft's block by its key; a record about a label speaks for each block that bears the label with that text, so two blocks bearing one label can stand differently.

The function is built and answers for a draft's results now; it answers for a node of the library once the node store gives it the texts of the library (`LibraryWeb`), which is not built yet.

### 5.1 What it reads

- **The text now**: a node file's hash, or a block's label and the hash of its own text (§2).
- **Its closure**: what the statement uses and what those use in turn. For a draft's result, the targets of its statement's references, through a display to the block that holds it (`Dependencies.review_targets`), each by its label and the hash of the block it resolves to in a document that reads the result; a result with no label is left out, since nothing could name it. For a node, its statement's `uses` that are statements, stubs included, and not works or proofs (with the node store). A label two blocks bear with two texts, neither in a document that reads the result, resolves to nothing.
- **Its notation**: each command a person defined that the statement or any text of its closure uses, from the preamble of a document that reads the result or the macros node of the node's work, by its definition's hash: SHA-256 of `[kind, name, args, default, body]` as compact JSON (`json.dumps(…, ensure_ascii=False, separators=(",", ":"))`), as `scan.macros.parse_macros` reads the definition, so a comment or a space inside it does not change it. Loom's own commands (`\uses`, `\incomplete`, `\nest`) and the commands of LaTeX and of packages loom does not read are never rows.
- **Whether a Lean record still stands**: every Lean file it names still has the hash it recorded. A change anywhere in such a file makes it stand no more, which sends loom to run the check again and never lets a stale record count.
- **The acceptance ledger**, for a draft's result, through the resolver every record uses (`records.store`).

### 5.2 What it says

| field | values | |
| --- | --- | --- |
| `reading` | `stub`, `unchecked`, `matches`; none for a draft's result | a node: `stub` with an empty body; `matches` when a person's `compared` names its hash now; else `unchecked`, with `compared_before` when one named an earlier text |
| `how`, `sought`, `proposal` | | the latest `digested` on this very text; a `sought` on it; an open `proposed` on it |
| `lean` | `none`, `rerun`, `failed`, `unattested`, `changed`, `formalized` | below |
| `role` | `proved`, `unproved`, `assumed`, `defined` | from the Lean record on the text now: the stating declaration is a theorem with no `sorry`, one with a `sorry`, an axiom, or a definition |
| `relative_to` | subjects | the record's `assumed`: what its proof is verified relative to |
| `causes` | `{changed, then, now}` | for `changed`: each subject whose hash is no longer the one attested, `now` null where it no longer resolves |
| `unattested_notation` | command names | rows of its notation no person has attested in their definition now |
| `accepted` | `fresh`, `changed`, none | a draft's result the reviewer accepted, from the ledger |

`lean`, where the **standing** records are the `lean` records on this result whose Lean is unchanged, the **latest** is the last of them, and the **current** is the latest when it is on the text now:

1. `none`: no `lean` record on this result at all.
2. `rerun`: records, but none standing.
3. When the person's last attestation on this result names the latest record's statements (the Lean is what they attested):
   - `changed` when it no longer holds: its subject's hash, a member of its closure, or a row of notation the person attested in an earlier definition differs now;
   - else `rerun` when there is no current record (the text changed and the person said the Lean still states it, so loom runs it on the text now);
   - else `failed` when the current record's `ok` is false;
   - else `unattested` while a row of its notation was never attested;
   - else `formalized`.
4. Otherwise (never attested, or attested of a statement the Lean no longer has): `rerun` with no current record, `failed` when its `ok` is false, else `unattested`.

A row of notation is attested once, in its definition, and holds wherever that definition is used: a changed definition is looked at once, and every result using it holds again once it is. A changed definition of a result's closure is not: each result resting on it is attested again, one by one.
