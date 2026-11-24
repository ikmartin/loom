# Evidence and asks

This page specifies two logs loom keeps under `.loom/records/`: the **evidence log**, what someone did to a text (digested it, compared it with its paper, ran Lean on it, attested it), and the **asks log**, what a person asked of an agent and an agent of a person. It wins over `docs/design/library.md` about a shape, as that wins about what a record means. The node files these records speak of are `nodes.md`'s.

What is built: both logs, their formats, their readers and writers (`loom/src/loom/evidence/log.py`, `asks.py`), the diagnostics for a line that cannot be read, what closes an ask (§4.3), the agents' commands (§4.5), and a result's status (§5, `status.py`), a draft's over the drafts' web and a node's over the library's (`web.py`, `DraftWeb` and `LibraryWeb`). Review's lists and their reads and writes (§6, §7, `review.py`) are built for all that needs no node: questions, papers to fetch, Lean statements to attest, accepted and attested results that changed, proposed edits, and what waits for an agent. The Web's reads over the drafts are built (§8, `webview.py`). The lists `cited` and `check`, and the library's results in the Web, wait for the node store's references; nothing writes a record of evidence yet but the tests.

## 1. Files

- `.loom/records/evidence/log.jsonl` (`paths.EVIDENCE_LOG`) and `.loom/records/asks/log.jsonl` (`paths.ASK_LOG`). Both travel with the quilt, and loom deletes nothing in them.
- One JSON object a line, UTF-8, keys sorted, no spaces between tokens, as `json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` writes it. A reader takes any valid JSON.
- Appended under the log's own lock (`loom.locks.locked` on the file) and never rewritten, so two clones' lines merge by keeping both. A writer that must decide from what the log holds takes the lock first and decides under it. A writer starts on a new line when the file does not end in one, so a line a killed writer left half written stays one line that cannot be read, reported, and takes no later record with it.
- A line that cannot be read, is not of a known kind, or lacks or adds a field is skipped and reported (`loom:foreign-evidence`, `loom:foreign-asks`); the rest still loads. Two lines under one id are `loom:repeated-id`, as for the other logs, and only the first is read: a line a merge kept twice moves nothing. A thing's records are ordered by `at`, not by their place in the file.
- A process replays a log once and then reads only the lines appended since (`log.replay`, `asks.replay`); a log replaced by another file, shortened, or whose last bytes read are no longer those bytes is read whole again. A last line with no line feed is read when it is a whole record and read again once ended.
- No agent is to write either file by hand. Both are under `agents.LOOM_DIRS`, so the deny list loom writes for Claude Code refuses its file tools there; nothing refuses a shell's append. What loom's own routes refuse: no command or MCP tool writes a person's kind of record (§3, `log.HANDS`), every reader refuses a kind from a hand that may not write it, and a `person` whose name says it is an agent's (Agent or AI in it, `identity.is_agent`) is refused from either log.

## 2. What a record names

A **subject** is one text by its hash, written `{"<kind>": <name>, "hash": <hash>}` with exactly those two keys. A hash is `sha256:` and 64 lower-case hexadecimal digits.

| kind | name | hash |
| --- | --- | --- |
| `node` | a node's id (`nodes.md` §3) | the node file's bytes (`nodes.md` §1) |
| `label` | a draft's result by its label: the block's id where it has one (an id is a label, `source-contract.md` §3), else its first `\label` | the block's whole text (`web.text_hash`): its region as written, with the blocks nested in it kept and each file it `\input`s read in, its comments removed and every run of white space one space, so a comment or a line broken anew does not change it, and its title, its label and any word of it or of what it holds do |
| `macro` | a command a person defined, without its backslash, as `scan.macros` reads it; an environment a person defined, as `{name}` | its definition's hash (§5.1) |

A record about a label holds for every block of the quilt that bears that label and has that hash: a draft copied to a new file keeps what was said of the results it did not change, and of two blocks bearing one label, the one whose text changed no longer has it. A record about a macro holds wherever a definition with that hash is used. A block with no label has no lasting name, and nothing records about it.

**Who acted**, `by`: `{"kind": "loom"}`, or `{"kind": "person", "name": …}` with the quilt's reviewer name, or `{"kind": "agent", "name": …}` with the name the agent writes as. A person's name that says it is an agent's is refused (§1).

**Ids** are `ev-` (a record of evidence) or `t-` (an ask), the day, and a random token (`records.ids.draw`), so two clones never draw one id. **`at`** is UTC to the second, `2026-11-21T10:02:11Z`.

## 3. The evidence log

Every line has `id`, `kind`, `at` and `by`, and the fields of its kind below and no others. A kind written by one hand only is refused from another.

The records of §3.1 to §3.3 are written by the acts of `loom/src/loom/evidence/acts.py` alone, for every caller, the node store's digest among them: `digested` (how a node's text was made, by the hand that wrote it: its caller passes the hash of the file it wrote, and it is refused `changed` when the file on disk is no longer that text, so a record never names a text another hand wrote since), `check` (a person's `compared`, against the work's document, its PDF else its TeX source, and the node's pages), `propose` (an agent's correction, written at once with `digested` how `corrected` where no person has compared the node's text now, else filed as `proposed`), `take`, `decline`, and `correct` (a person's own body for the node, its header kept, recorded `digested` how `written` and then `compared`, since they have just read it against the page). Each holds the library's lock and then this log's, the one order every writer of both takes, and decides from the node's file now; a node it writes passes the library's checks (`nodes.md` §11). A refusal writes nothing, and says why: `author-only` and `agent-only` for the wrong hand, `no-such-node` for no statement or proof of that id, `changed` when the text is no longer the one shown, `stub` for a node with no text, `no-document` when its work holds no document to read it against, `no-such-proposal` and `closed` for a correction that is not open, and `refused` for a record the log refuses or a file the checks refuse, with their diagnostics.

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

An agent's correction to a node a person has compared waits as `proposed`: `on` the node at the text it corrects, `bytes` the whole new file, `why` the agent's reason. Only an agent. It is open while the node still has the hash it names and no `declined` names it. The person declines it with `declined`: `proposal` its id, `why` (may be empty). Taking it writes the node and records `compared` on the new text, since the person read the change against the text they had compared (the views spec's Open 23), so it needs no record of its own: the node then has the proposal's bytes. A correction to a node no person has compared on its text now is never filed: it is written at once, recorded `digested` how `corrected`.

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

The person's word that a citation of a work with no result named in it is a mention and rests on nothing. `block`, the citing block as a note names its block: its `key`, the `hash` of its text and its `context` (`records.locate.context_of`), its key read as the records read a stored key (`evidence.web.blocks_named`, over `ScanResult.node_named` and `records.locate.shared_label`), so a mention written on a statement's place key holds once a label keys it, and one on a label a copied draft defines again holds for each copy; `cites`, the reference; `undo`, true to take an earlier one back. Only a person. It holds while that block still cites the work with no locator.

```json
{"at":"2026-11-21T18:30:00Z","block":{"context":{"after":{"gap":1,"hash":"sha256:511c96ceb7174affc0b103d8fbbb33384196d849f1eeb3c2e9da6145053ae9d3"},"before":{"gap":1,"hash":"sha256:8f9d61fac39402898f831bfec31c774438bb77be6a0cbd47c83cf53d31858372"},"copies":1,"documents":["drafting/main.tex"],"kind":"proof","twin":false},"hash":"sha256:b5a45e5f4685d21700a0c4f00c2d7a11872c7f5f4a22a6cdf9525d36c2a66a90","key":"thm:main/proof"},"by":{"kind":"person","name":"A. Author"},"cites":"tq-00B1-ref","id":"ev-2026-11-21-m1nt0b","kind":"mention","undo":false}
```

## 4. The asks log

A stack an agent may take from, not a harness: nothing is assigned, ranked or scheduled, and no agent is woken. The log records the asking and what was said afterwards; whether an ask is still open is computed from what exists, never recorded.

### 4.1 `asked`

Every `asked` line has `event` (`asked`), `id`, `at`, `by`, `what`, `to` (`agent` or `person`), `on`, `from` and `words`, and the fields of its `what`.

- `on` is the place it is tied to, one of: `{"node": …}`; `{"label": …}`; `{"block": {key, hash, context}}`, a block of a person's document as a note names one (§3.7); `{"ref": …}` or `{"ref": …, "page": n}`, a work or one of its pages; `{"document": path}`.
- `from` lists the drafts it was asked for, so that Review can show only what concerns one draft.
- `words` are the person's or the agent's own, often empty. Words, a question's text and its choices hold no control character but a line feed or a tab.
- An agent's ask may carry `session`, the loom session it was asked in, by which loom tells one conversation's asks from another's under the one name an app declares. Loom takes it from the transport, never from an argument: over MCP the conversation's session, which the server sets in the command's environment (`LOOM_MCP_SESSION`); in a shell, which binds nothing, the quilt's active one. The refusal holds over MCP, where the transport is loom's. In a shell no transport is loom's: the variable is the shell's to set, so an agent with a shell can act as another conversation, as a name declared in a shell is taken at its word (`docs/design/agents.md`); there the session guards against mistakes, not against an agent that means to.
- An agent's ask of the person may carry `under`, the task its session was working on when it asked (`asks.working_on`: the last ask to an agent that session took, neither withdrawn nor said done), taken from the session as the session is, never from an argument; Review's row names it, so the person reads what the agent was doing when it asked.

| `what` | to | asked by | its fields |
| --- | --- | --- | --- |
| `read` | agent | person | `nodes`: the stubs to read; `marks`, the person's marks to digest that show where (`manifest.md`, annotations' `purpose`), each of which may name the stub it locates (`node`) |
| `digest` | agent | person | `ref`; `scope`: `uses`, `marked`, `chosen` or `all`; `nodes` where the scope names results, `marks` (the ids of the person's marks to digest on the work's pages, annotations whose `purpose` is `to-digest`, `manifest.md`) where it names marks: `marked` needs `marks`, `chosen` needs `nodes` |
| `ask` | agent | person | `text`, the person's question; `quote`, the words it is on, where they selected some |
| `correct` | agent | person | `text`, what the person says differs; `on` is the node |
| `restate` | agent | person | `target`, a node or label subject; `differs`, what the person says the Lean gets wrong |
| `which-result` | agent | person | `cites`: the work a citing block cites with no result named; `on` is that block |
| `formalize` | agent | person | `target`; `state`, `prove`, `assume`: the subjects of each part of the boundary |
| `question` | person | agent | `text`; `choices`, up to 6 distinct strings of at most 200 characters; `quote`, the words it is on |
| `paper` | person | agent | `ref`; `link`, the http or https address it could not fetch from, with no name or password in it; `want`, `pdf` or `tex` |

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
| `done` | an agent, on an ask to an agent | `made`, the ids of what it produced: nodes or suggested edits | what it produced |
| `answered` | the one an `ask` or a `question` was asked of | `words`, and for a `question`, `choice`, the number of one of its choices | the answer: a choice, words, or both |
| `withdrawn` | a person, or the agent that asked | an agent's may carry `session` | the ask is withdrawn; this is deleting it |

A person withdraws any ask and an agent only its own: one asked under its name, and where the ask names a session, in that session. Both, since neither alone tells one conversation: every conversation of one app declares one name, and every agent in a shell shares the quilt's active session. An agent's withdrawal of another's is skipped and reported. An event may stand above its ask in the file, as a merge can leave it.

Loom's commands refuse to say what an ask as it stands cannot take (`asks.closed_for`): nothing of a withdrawn ask, no second answer, a `done` that names nothing made, and a `took` of a task another session that is live now has taken.

```json
{"at":"2026-11-21T09:04:31Z","by":{"kind":"agent","name":"Claude Code"},"event":"took","session":"s-2026-11-21-a8k2rx","task":"t-2026-11-21-7h3qfw"}
{"at":"2026-11-21T12:00:40Z","by":{"kind":"person","name":"A. Author"},"choice":1,"event":"answered","task":"t-2026-11-21-w2c6ga","words":"and note that 2.5 is only a remark"}
{"at":"2026-11-21T12:10:00Z","by":{"kind":"person","name":"A. Author"},"event":"withdrawn","task":"t-2026-11-21-7h3qfw"}
```

### 4.3 What closes an ask

An ask is open until what it asked for exists, whoever made it; an agent's `done` says what it made and closes nothing by itself. Computed each time it is asked (`asks.standing`), never written:

| `what` | closed when |
| --- | --- |
| `read` | every stub it names has a body |
| `digest` | every node it names has a body; for marks, until loom finds a node's place on a page, the nodes a `done` names exist with bodies |
| `ask`, `question` | it is answered |
| `correct` | a `digested` or a `proposed` on the node is written after it |
| `restate` | loom observes the target's Lean after it, standing (§5.1), with statements other than the person's last attestation's |
| `which-result` | the person says only a mention (§3.7) of that block and work, or an agent files a suggested edit on that block after it; the block's key, the mention's and the edit's each read as the records read a stored key (§3.7), so one block under its place key and its label key is one |
| `formalize` | loom observes the target's Lean after it, standing, and Lean accepts it |
| `paper` | the work holds the document wanted, read from the store |

Every ask is closed once withdrawn. One that a node would close stays open while nothing can say of the node; the library's web (`LibraryWeb`) is what says it, and is the asks' web where no draft is read. An ask taken (`took`) is **working** while an agent server alive now (`presence.live`) is in the session that took it, and waiting otherwise, so a session that has ended does not look busy.

### 4.4 A dropped paper

Nothing here matches a dropped file to a request. The intake files a dropped file under the reference that states its identifier, or under the row in Review it was dropped on, whether or not a request waits for it (the node store's references, `nodes.md` §7); a `paper` ask is closed by the fact that its reference now holds the document it wants, read from the store (§4.3). No call crosses between the intake and this log.

### 4.5 An agent's commands

Each is also its MCP tool, as every agent command is. An agent names itself with `--as`, a name ending in Agent; a person acts in the viewer, and no command here does a person's act.

| command | does |
| --- | --- |
| `loom tasks [--all]` | what is open for agents, each with its place and whether a session is on it; what agents asked of the person that waits, each naming the agent that asked; and each question the person answered that the agent that asked has not seen since its last `loom since`, with the choice and the words; `--all` adds what is closed |
| `loom tasks take TASK` | says its session is working on it (§4.1: over MCP the conversation's, in a shell the active one) |
| `loom tasks done TASK --made ID…` | says what the agent made |
| `loom tasks answer TASK TEXT` | answers a person's `ask` |
| `loom tasks withdraw TASK` | withdraws one of its own asks, in its session (§4.1) |
| `loom ask TEXT --on PLACE [--choice C]…` | asks the person a `question`; PLACE is a draft's label or a block's key, a node's id, a work's id with `:PAGE`, or a document's path, a draft's label first since a draft's id has a node's shape |
| `loom ask --paper REF --link URL [--want pdf\|tex] [TEXT]` | asks the person for a paper it could not fetch |
| `loom evidence NAME` | a result's status and every record and ask about it; NAME is a draft's label or a node's id |

`loom ai orient` says how many asks are open for an agent, how many agents asked of the person and wait, and how many questions are answered and not yet seen by the agent that asked, when any are. `loom since` reports the person's answers to the questions the agent looking asked, each once. Over MCP, `ask`, `tasks take` and `tasks withdraw` act in the conversation's session, which the server sets, and none takes a session argument (`mcp.server.BOUND`).

## 5. Status

A result's status is computed from the evidence and the texts now, and never stored (`loom/src/loom/evidence/status.py`). It is asked of a node by its id, or of a draft's block by its key; a record about a label speaks for each block that bears the label with that text, so two blocks bearing one label can stand differently.

The function is built and answers for a draft's result over the drafts' web (`DraftWeb`) and for a node over the library's (`LibraryWeb`), which reads each statement's and proof's file from the node store; Review and the agents' commands read both together (`Joined`).

### 5.1 What it reads

- **The text now**: a node file's hash, or a block's label and the hash of its whole text (§2).
- **Its closure as it reads now**: what the statement uses and what those use in turn, and what each standing Lean record on its text says its declarations use (`uses`). For a draft's result, the targets of its statement's references (`Dependencies.direct`), a display followed both to the block that holds it (`Dependencies.owners`) and through it to what it refers to, and what a result nested in the statement uses; each by its label and the hash of the block it resolves to in a document that reads the result. A result with no label is left out, since nothing could name it. For a node, its header's `uses` that are statements, stubs included, and not works or proofs, and theirs in turn; a node whose file does not read is no text and is left out. A label two blocks bear with two texts, neither in a document that reads the result, resolves to nothing.
- **Its citations**: each citation in the statement or a text of its closure. One with a locator (`\cite[Theorem 2.1]{key}`) uses one result of a work; one with none (`\cite{key}`) uses some result of the work all the same. Until citations resolve to nodes nothing answers for either, and each waits as `unknown` (§5.2): one with a locator until its node is settled, one with none until it gains a locator or the person says it is only a mention (§3.7), which can be matched to the citation once its key names a work.
- **Its notation**: each command or environment a person defined that the statement or any text of its closure uses, and each that those definitions use in turn, by its definition's hash. A command's is SHA-256 of `[kind, name, args, default, body]` as compact JSON (`json.dumps(…, ensure_ascii=False, separators=(",", ":"))`), as `scan.macros.parse_macros` reads the definition from text with its comments blanked, its default and body with every run of white space one space, so a comment or a line broken inside it does not change it; an environment's, `{name}`, is the same of its optional arguments and its two bodies (`web.environments`). Definitions are read from each document that reads the result, its preamble and its body, or from the macros node of the node's work, which is not read yet: until it is, a node's notation is unknown, and so is that of a draft's result whose closure holds a node, which keeps either from reading `formalized` (§5.2); where documents reading the result define one differently, its row's hash is the hash of their definitions' hashes together, so a change in any of them is seen. Loom's own commands (`\uses`, `\incomplete`, `\nest`) and the commands of LaTeX and of packages loom does not read are never rows.
- **Whether a Lean record still stands**: every Lean file it names still has the hash it recorded. A change anywhere in such a file makes it stand no more, which sends loom to run the check again and never lets a stale record count.
- **The acceptance ledger**, for a draft's result, through the resolver every record uses (`records.store`).

### 5.2 What it says

| field | values | |
| --- | --- | --- |
| `reading` | `stub`, `unchecked`, `matches`; none for a draft's result | a node: `stub` with an empty body; `matches` when a person's `compared` names its hash now; else `unchecked`, with `compared_before` when one named an earlier text |
| `how`, `sought`, `proposal` | | the latest `digested` on this very text; a `sought` on it; an open `proposed` on it |
| `lean` | `none`, `rerun`, `failed`, `unattested`, `changed`, `waiting`, `formalized` | below |
| `role` | `proved`, `unproved`, `assumed`, `defined` | from the Lean record on the text now: the stating declaration is a theorem with no `sorry`, one with a `sorry`, an axiom, or a definition |
| `relative_to` | `{node}` or `{label}` | what its proof in the current record is verified relative to: each result Lean reports it rests on as an axiom (below), and each node the record lists in `assumed` |
| `causes` | `{changed, then, now}` | for `changed`: the result's own text if it changed; each member of the closure as it reads now not attested at its hash now, `then` null for one the attestation never named; each member it named that no longer resolves to that hash, `now` null where it resolves to nothing; each row of notation attested in an earlier definition only |
| `unattested_notation` | command names, or null | rows of its notation no person has attested in their definition now; null when its notation is unknown (§5.1), which reads as rows not attested |
| `accepted` | `fresh`, `changed`, none | a draft's result the reviewer accepted, from the ledger |
| `waiting_on` | `{node, why}`, `{label, why}`, or `{cite, why}` with a citation's key and its locator where it has one | with a current Lean record: each thing that keeps it from reading formalized, `why` being `stub` (a node not read), `unchecked` (a node, the result itself among them, not compared with its paper on its text now), `unattested` (assumed in Lean, or its Lean used by this result's Lean and not stated in its record, and its own Lean statement not attested, or not over all its own Lean rests on) or `unknown` (nothing can say of it yet) |

`lean`, where the **standing** records are the `lean` records with a declaration stating this result (`status.states`) whose Lean is unchanged, the **current** is the last standing one on the text now, and the **latest** is the current where there is one, else the last standing. Later is by `at`, so where a merge puts lines of different seconds decides nothing; records of one second keep the order of the log (`Evidence.about`), so for two records on one result in one second, rare in one clone and met where a merge brings two together, the order of their lines decides. Records and attestations are taken on this block's own text, so two blocks bearing one label with two texts stand apart, and the order of lines on the other text decides nothing here. Lean **proves** the result when the record's `ok` is true, the kernel's replay exited 0, a declaration states it, none has a `sorry`, a result of the person's is not stated as an axiom (the library's are assumed; the person's own are proved), and every axiom the stating declarations report beyond Lean's three (`propext`, `Classical.choice`, `Quot.sound`) is accounted for (`status.assumes`): it is a declaration of the record, of kind `axiom` and role `states`, stating a library node or another of the person's own results, which the person chose to assume for now by attesting the record's statements, that axiom's among them. Any other axiom (a `sorry`'s `sorryAx`, a supporting axiom, an axiom stating nothing) and Lean does not prove it. What it reports it rests on is read from the axioms Lean reports, not from the record's `assumed`; the results so assumed are `relative_to`, the result reads as verified relative to them, and each is gated like any other.

1. `none`: no `lean` record states this result.
2. `rerun`: records, but none standing.
3. When a person's attestation on the text now names the latest record's statements (the Lean is what they attested):
   - `changed` when it no longer holds (`causes`, above);
   - else `rerun` when there is no current record;
   - else `failed` when Lean does not prove it;
   - else `unattested` while a row of its notation was never attested, or its notation is unknown;
   - else `waiting` while `waiting_on` names anything (below);
   - else `formalized`.
4. When no attestation is on the text now but an earlier one names a standing record's statements, and no block bearing the label still has that earlier text (`Web.texts`), `changed`, with the text among its causes: the person said the Lean states the result, and the text has moved since. Where another block still has the attested text, that text is the one attested and this block's is one the person never attested, which reads by rule 5, so one label on two texts never crosses. Where no block keeps it, every block bearing the label reads it as its own earlier text, since no record says which document's block was attested.
5. Otherwise (never attested, or attested of a statement the Lean no longer has): `rerun` with no current record, `failed` when Lean does not prove it, else `unattested`, with `waiting_on` said beside it.

**The gate.** A result reads `formalized` only when Lean proves it on its text now, the person's attestation holds, and every library result under it is settled: each node of its closure as it reads now and of its attested closure is read (not a stub) and compared with its paper on its text now, each statement its Lean assumes (`relative_to`), a library node stated as an axiom or one of the person's results assumed for now, counts to one standard: its own statement attested on its text now (its status holds a person's attestation, nothing changed and its notation attested) over a Lean record that elaborated (`ok` and the replay passed), whether or not that Lean proves it, since its proof is what is assumed; a node read and compared with its paper itself; and every library node its statement uses read and compared and none a stub, every citation it makes answered, what only its proof uses not needed (`status._assumption`); each result whose Lean its current Lean record uses (`uses`) and does not state itself, such as a definition its statement is written in terms of, counts to the same standard, since an attestation holds for a statement with everything it uses, and so on through what that result's own Lean rests on (`status.rested`): a person attests each such Lean once, as a row of notation is attested once. A record does not yet say which of its uses its statements make and which only its proofs, so every one is asked for until a record can say; a result whose Lean is used only inside a proof Lean checked will not be, once it can. An assumption, or a Lean rested on, that comes round to a result already asked of is never settled; a node asked of itself is read and compared with its paper on its text now; and no citation is left that nothing answers for. Status computes this itself, from whatever records exist, and does not trust it to the act that wrote them, so an attestation written by hand over an unread or unchecked result still leaves it short of `formalized`. Between the two, Lean accepted and the attestation holding but a library result under it not yet settled, the result reads `waiting`, and `waiting_on` names each such result and why. Attesting itself waits for the closure's nodes to be read and compared (`formal-attest` refuses them as `unchecked`, §7), so before an attestation `waiting_on` is said beside `unattested` for the request to name what will keep the result from reading formalized. A node no web can say anything of (no file of its id, or one that does not read) settles nothing: under an attestation it is a cause with `now` null, and assumed it waits as `unknown`.

A row of notation is attested once, in its definition, and holds wherever that definition is used: a changed definition is looked at once, and every result using it holds again once it is. A changed definition of a result's closure is not: each result resting on it is attested again, one by one.

## 6. Review's lists

What waits for the person, each kind a rule saying what puts a row in and what takes it out, computed when it is read from the evidence, the asks, the scan and the published manifest, and never stored (`loom/src/loom/evidence/review.py`). A read under the publisher's same scan, with none of the files the lists read changed since (`review.files_read`), answers from what the last read computed (`memo.kept`), all but whether an agent's server is alive, which no file says and every read asks again. A row is what one decision is about: it carries the ids it is addressed by and the fields its words are drawn from, never loom's own words, which are the viewer's.

**A row** is `{row, kind, docs, …}` with its kind's fields. `row` is made from what it is about (`questions:t-2026-11-21-w2c6ga`, `attest:drafting/main.tex#lemma:1`, `edits:e-2026-11-21-k2m9xq`), so it stays the same while that waits. `kind` is the row's kind, and no field of a kind is named `row`, `kind` or `docs`: a kind of its own a row carries is `type` for an edit and `what` for an ask. `docs` are the drafts it concerns: an ask's `from`, the documents that read a result's blocks, a change's documents.

**Ranks.** Under Everything the kinds come in the order of who waits, as the integrator ruled after round six: `questions`, `fetch`, `cited`, `check`, `attest`, then `accepted-changed`, `attested-changed`, `edits`, and what waits for an agent, `agents`, last and apart. The column draws them alphabetically by the viewer's words; that is the viewer's.

**Within a kind**, rows an agent is stopped on until the person acts come first, then rows a draft rests on, then the rest; ties oldest first, by when what put the row in was written.

**A draft** narrows every list and count to the rows whose `docs` hold it; a row may concern two drafts, and counts once in each.

| kind | in | out | fields |
| --- | --- | --- | --- |
| `questions` | an open `question` ask, from an agent to the person | answered, or withdrawn by its agent | `question`, `by`, `on`, `text`, `choices`, `quote`, `under` (the task it was asked under, `{task, what, on, ref}`, or null) |
| `fetch` | an open `paper` ask | withdrawn, or the work holds the document wanted (with the node store) | `task`, `ref`, `link`, `want`, `by`, `words` |
| `cited` | a stub a draft rests on that no open ask covers; a citation of a work that names no result, with no `mention` holding | with the node store, not built yet | |
| `check` | a statement node with a body whose `reading` is `unchecked`; an open `proposed` correction | with the node store, not built yet | |
| `attest` | a draft's result whose `lean` is `unattested` (§5.2), or a library node's whose paper `matches` besides, since nothing is attested on a node nobody checked, and that may be attested now: no node of its closure unread or uncompared, and no citation of a work's result in its statement or its closure that no node answers for (§5.1, its citations); what it assumes in Lean does not hold it back here, only from reading formalized | attested, or Lean restated | `result`, `name`, `source`, `what` (`statement and proof` for a proved theorem, else `statement only`, as a library node always is), `paper` (null for a draft's result, a node's reading of its paper), `record` (the current Lean record's id), `reading`, `lean`. A node's `source` is `{ref, short}`, `short` null until the node store's references give it, and its `docs` are empty until a draft's citations resolve to nodes |
| `accepted-changed` | a result of the person's whose acceptance went stale, as the build publishes the ledger through its own resolver (`manifest.md`, `unresolved` with cause `earlier-change`) | accepted again, or its text back as accepted | `key`, `name`, `doc`, `reading`, `lean` |
| `attested-changed` | a draft's result whose `lean` is `changed`, one row for each result, its id made from the result's block (`attested-changed:KEY`), so a label two documents bear with two texts is two rows | attested again on the text now, or restated | `result`, `name`, `doc`, `changed` (`statement` when its own text or a notation row changed, else `used`), `causes`, `attestation`, `attested_at` (when that attestation was made), `reading`, `lean`, `resting` (the results nested under it, each `{result, name}`; empty where none) |
| `edits` | each change waiting on the person as Review lists it today (`pending.pending`): an agent's suggested edits, and the in-place changes since the person's look in the places agents may edit | kept, discarded or undone | `change`, `type` (`suggested` or `edit`), `doc`, `key`, `where`, `by`, `state`, `broke` (null until a compile's line is read, the views spec's Open 26) |
| `agents` | an open ask to an agent | it produces what it asked for (§4.3), or is withdrawn | `task`, `what` (the ask's `what`), `on`, `working` (`{by}`, the agent whose live session took it last, else null), `asked_at`, and the ask's own fields, none of which replaces one of these |

**How a result stands, in a row.** A row about a result carries how it stands as §5.2 gives it, never a bare word: `reading`, the reading of its paper (null for a draft's result), and `lean`, `{lean, role, waiting_on}`, the Lean word with its role and what keeps it from reading formalized (`status.brief`). So an assumed result reads as assumed, and one that waits on the person says on what. A result no record names stands `{lean: "none", role: null, waiting_on: []}`.

**Nested rows.** In `attested-changed`, a result whose own text and notation are unchanged, its causes all members of its closure, rests under the first of its causes that is a row of its own because its own text or a notation row changed, as one of that row's `resting`; where none is, it is a row of its own. Its causes come in the order status gives them: its closure as it reads now breadth first from the statement, what the statement uses directly before what those use, then what its Lean record says it uses, then the members its attestation named that resolve to another text or to none. A cause names a member by its label and its hash now, so a result rests under the text it reads by that label, never under another text of one label borne in a document that does not read it. So a changed definition is one row, with each result resting on it beneath to be attested again one by one, and every changed result is listed once, as a row or under one.

A result never accepted is not listed, nor a result taken in from an agent's copy or a pull, which the views spec shows as a proposed edit and as the incoming pull. Problems are on their document, in Docs.

## 7. The reads and writes

Endpoints of the write API, in Review's family (`render/endpoints/review.py`; rows in `write-api.md`). The reads change nothing and the publisher does not rebuild after them; the writes change the asks log alone, and the publication that follows builds from the last scan, which tells the viewer something changed. Every write is the person's: a declared agent is refused `author-only` (403), and with no reviewer name `no-reviewer` (409). A write is recorded under the reviewer's name whatever person `author` names; where it names another, the answer's `result` says so (`answered as A. Author, the reviewer`).

| endpoint | sends | answers |
| --- | --- | --- |
| `review-counts` | `{}` | `{everything, kinds: {KIND: n}, agents, drafts: [{doc, n}]}`, `drafts` being the person's documents |
| `review-list` | `{kind?, doc?}`: `all` (the default), `agents` or a kind | `{groups: [{kind, rows}]}`, in rank order with `agents` last, empty groups left out |
| `review-row` | `{row}` | `{row, body}`: for `accepted-changed` the key's published `acceptance` and `review_fragment`; for `edits` the published change; for `attested-changed` `{at}`, when the attestation was made; for `attest` `{observation, statement, parts, notation, uses_attested, supporting, difference}`: the Lean record to attest, the statement (a draft's `{fragment}`, a node's `{body, macros}`, `macros` null until its work's macros are read), each row of its notation `{part, from, attested}` (`from` `preamble` or `macros`; null where its notation is unknown, §5.1), each member of its closure the person attested on its text now `{result, name, at}`, and the declarations of the Lean record that only serve its proof, with `parts` and `difference`, the agent's account, null until an agent's record gives them (the views spec's Open 24); `{}` for the rest. `no-such-row` (404) when nothing waits under that id now |
| `review-answer` | `{question, choice?, text?, author?}` | records `answered` (§4.2) under the reviewer's name; `closed` (409) when answered or withdrawn already, `no-such-task` (404), `refused` (409) for a choice it does not offer |
| `review-task` | `{kind, on, text?, docs?, author?}` | records an ask of an agent and answers `{task}`. `read`: `on.nodes`, `on.marks`; `digest`: `on.ref`, `on.scope`, `on.nodes`, `on.marks`; `ask`: `on.ref` with `on.page`, or `on.key` a block, with `on.quote` and `text`; `correct`: `on.node` and `text`; `restate`: `on.result` a draft's block, and `text`, what differs; `which-result`: `on.key` the citing block and `on.ref`. A formalization is `formal-ask`'s (not built yet). `docs`, its `from`, are paths of the person's documents (the scan's documents whose role is `person`, as `review-counts` lists them), by default the documents that read the place. `bad-field` (400) for a kind it does not make, a field not of the kind's shape, or a `docs` path that is not one of the person's documents, an agent's copy included; `refused` (400) for an ask the log refuses; `no-such-result` (404) |
| `review-task-delete` | `{task, author?}` | records `withdrawn` under the reviewer's name; `closed` (409) when withdrawn already, `no-such-task` (404) |

In formalization's family (`render/endpoints/formal.py`), `formal-attest` `{result, observation, author?}` is the person's word that the Lean statement of `observation`, a `lean` record, says what the result says: `result` a draft's block by its key, asked first, or a node by its id. It records, under the reviewer's name, `attested` on the result's text now with that record's statements and its closure as it reads now (§5.1), each member by its hash now, and an `attested` for each row of its notation not attested in its definition now, which the row showed; a result whose notation is unknown has no rows to attest yet (§5.1). The same word given again, where the latest attestation of these statements on this text names the same closure, writes nothing and answers as the first did. It is refused `no-such-result` (404); `no-lean` (409) when no standing Lean record states the text now, or Lean did not accept the statement; `changed` (409) when `observation` is not the latest standing one on the text now, or a member of the closure resolves to nothing; and `unchecked` (409), naming each, while the result itself if a node, or a library node of its closure, is not read and compared with its paper on its text now, or a citation in it is one no node answers for yet (`evidence/acts.attest`).

`formal-plan` `{targets, assume?}` reads, and changes nothing, what asking an agent to formalize the person's results `targets` comes to (`evidence/plan.py`, the views spec's §6.6). From each target it walks what the result uses, by status's own walk (§8, `rests_on`) for a draft's result and by a node's header for the library's: a target is to prove unless the person chose to assume it for now (`assume`); from a result to prove, what its statement and its proofs use is reached, from one assumed or stated only what its statement uses; a library result is assumed, never proved, so its proofs are not followed. A result reached that has its Lean already, `formalized`, or one of the person's whose Lean waits for their word (`unattested`) or changed since they gave it (`changed`), is not followed: the agent uses that Lean as it is. Of the rest, a definition, notation, convention or construction is to state, another of the person's to prove, another of the library's to assume. A target, or a result to state or to prove, with no label is in `stops`, the one thing that stops the request.

**What stands before** the targets read formalized is the gate's own (§5.2). For a target whose own Lean record stands on its text now and proves it, it is what the gate asks of that record (`status.own_needs`, from the very arguments status gave the gate, or would give it once a `changed` target is attested again), since what the record rests on may be more than the plan as walked now reaches. Otherwise `needs` (`evidence/status.py`) is asked of the Lean the request will make (`plan.asked`): the target stated and proved; each library result to assume, and each result of the person's chosen assumed for now, an axiom of it; each library result to state, and each result reached with its Lean already, used by it; every library result reached, and every node the target's statement uses, read and compared; each citation in it that no node answers for. `needs` gives each thing the gate asks by itself, down through what an attested Lean in turn rests on, and `gate` is its summary, so the list cannot name what the gate does not ask nor leave out what it does. Every one is named once (`plan.needed`), with what is wrong and when it can be done, and a reason the gate gives that the list does not say is refused (`status.WHYS`). `now`, the person's: a library result not read (`not-read`) or not compared (`not-checked`); a label that two texts answer to near the target (`ambiguous`); a label or a library result nothing answers to (`missing`), as a label no block bears or a node the library no longer holds; a Lean statement Lean has accepted on the result's text now that waits for the person's word (`attest`, or `attested-changed` where it was attested before something it uses changed), offered only where `formal-attest` would take it (`acts.attest_refusal`, the act's own check), and otherwise in its place what stands in its way: a member of its closure that reads as no one text (`missing`, or `ambiguous` where two texts answer), a node under it not read or not compared, a citation. `after` the agent's work: a Lean statement with no Lean on its text now that elaborated, which the agent writes or loom runs again, or whose notation cannot be shown yet (a library result's, until its work's macros are read, the target's own included, attested or not), and the target's own until the agent writes it (`attest`); one attested and still asked of because its Lean comes round, through what it rests on, to a result already asked of (`cycle`), which only Lean written otherwise settles. `waiting`, settled by nothing anyone does now: a citation that names no result a node answers for (`cite`), until loom resolves citations to results. The list is empty exactly when the targets read `formalized`; every entry it offers `now` is an act loom takes, on the quilt as the list was made; doing every entry that can be done, round after round, with the target's Lean written as the plan says, makes a target read `formalized` unless a citation or a cycle stands, and leaving any one undone keeps it from it (`tests/unit/evidence/test_plan_gate.py`, over random libraries). It answers `{targets, state, prove, assume, formalized, stops, before}`, each list in the order the walk reached it, a row in `prove` with `assume` and one in `assume` with `why` (how it reads its paper), and `before` as `[{why, when, results}]`, `why` in the order `not-read`, `not-checked`, `ambiguous`, `missing`, `cite`, `attest`, `attested-changed`, `cycle`, with `now` before `after` before `waiting`, an empty group left out. Each of `results` is a row, a citation's `{cite}`, a label's `{label, results}` with a row for each block bearing it, or a node the library holds no result by, `{node}`, and carries `for`, the targets whose plan asks it.

`formal-ask` `{targets, assume?, author?}` records, under the reviewer's name, one `formalize` ask of an agent for each target (§4.1), on its label, from the documents that read it, its `target`, `state`, `prove` and `assume` by subject from that target's own plan, the person's results chosen assumed for now among those to assume, and answers `{tasks}`. While any target's plan has something in `stops` it is refused `needs-label` (409), naming each; loom writes no label (`docs/design/library.md`, "A draft is not in the library"), and nothing unread or unchecked refuses it.

`review-accept` and the proposed edits' endpoints stay as they are. The views spec's `gen`, the library's generation, is the publisher's to keep and is not in these answers yet.

## 8. The Web's reads

The Web is where results are followed, what rests on what, a draft's and the library's alike (`docs/design/library.md`, "The views"). These reads answer it over the drafts' results and the library's statements (`loom/src/loom/evidence/webview.py`, endpoints in `render/endpoints/web.py`, rows in `write-api.md`). Each reads the scan, the published manifest, the evidence and the node store's files, and changes nothing; a read answers from what the last one computed while the publisher's scan is the same object and no log, the manifest, a Lean file a record names or a node file has changed (`evidence/memo.py`). A draft's citation does not reach a library result until citations resolve to nodes, so until then no draft's result is listed as using one.

**A result** of the drafts is a theorem-like block of a document of the person's, named by its key as the manifest names it, and sent as the views spec's `ROW`: `{result, name, title, taxon, source: {doc}, paper, reading, lean}`. `source.doc` is the document whose group it is listed in, else the scope's draft where that reads it, else the first in path order of the person's documents that read it; `name` is its taxon's word and the number the build published for that document (the word alone where it published none), `taxon` that word in lower case, `paper` null for a draft's result, and `reading` and `lean` how it stands, as a Review row carries them (§6): `reading` null for a draft's result, `lean` `{lean, role, waiting_on}` from its status (§5.2), computed only where a record names its label, `{lean: "none", role: null, waiting_on: []}` elsewhere.

**A library result** is a statement node of the node store, a stub among them, named by its id: `{result, name, title, taxon, source: {ref, short}, paper, reading, lean}`, `name` its taxon's word and the number its source prints (the word alone where it prints none), `source.ref` its work, `short` null until the node store's references give it, `paper` and `reading` its reading of its paper (`stub`, `unchecked` or `matches`), and `lean` from its status, computed always. What its statement uses is its header's `uses` that are statements, and what its proofs use their files' `uses`; what uses it is the reverse of both, over the library's statements.

**Scopes.** `library` (the library's statements, stubs among them, by work and then by id), `draft` (one draft's results, in `doc`), `deps` (those and every result they use, by statement or by proof, transitively), `all` (every draft's, then the library's). A scope it does not know, or `draft` and `deps` with no `doc`, is `bad-field`.

**What a result uses** is kept in two: what its statement uses and what each of its proofs uses, each by status's own walk (`web.rests_on`, §5.1), so the Web and status never disagree about what rests on what: the targets of its references, a display followed both to the block that holds it and through it to what it refers to, and what a result nested in it uses; a proof's own statement is left out, since that is what it proves. With two proofs or more, each row of what the proofs use says which (`proof`, from 1), the views spec's Open 27. **What uses it** is the reverse of both.

| read | sends | answers |
| --- | --- | --- |
| `web-list` | `{scope, doc?, sort?, open?, offset?}` | by `document`: `{count, sections, undigested}`; under `draft`, one section `draft` with its rows; under `deps`, that and `uses`, the results the draft does not read, in groups, open; under `all`, `drafts`, in groups, folded unless named in `open`, and `library`, by work, folded unless named in `open`; under `library`, `library` alone. A group of `drafts` is one of the person's documents and holds every result of its section that the document reads, so a result two documents read is in the group of each; a group of `library` is a work, `{group, short, title, n, rows?}`, `short` and `title` null until the node store's references give them. `undigested` is the works of which no result is read: none of its statements has a text. By `status`: `{count, rows, more}`, what waits on the person first (`unattested`, `changed`, `waiting`), then not formalized, then formalized, each in document order, two hundred from `offset`. Either way `count` is the results the scope holds, each once, so the groups' `n` may add to more |
| `web-group` | `{scope, doc?, group}` | `{group, n, rows}`: one document's group, or one work's, as `web-list` counts it and would send it, for a group opened after the list was sent |
| `web-search` | `{scope, doc?, q, limit?}` | `{count, hits: [{row, snippet}]}`: results whose name or title holds the query, first, with `snippet` null, then those whose statement holds it, matched as the node index matches a search (`library.index`, `nodes.md`): every word of the query among the statement's words (`library.index.words`, read from the block as a node's body is, its environment's head and foot, its labels and `\uses` left out), each a whole word and the last also the start of a longer one, case and accents folded, in any order, so `label` or `begin` finds nothing and `poly` finds "polynomial". `snippet` is the index's (`library.index.snippet`): `{before, match, after}`, the first word found as written in the statement's LaTeX, a formula whole, and about sixty characters either side cut at spaces outside mathematics, `…` marking a cut. At most `limit`, 1 to 200, 50 by default |
| `web-focus` | `{scope, doc?, result, more?}` | `{row, statement, relative_to, rests_on, more, uses: {statement, proof, outside: {statement, proof}}, used_by: {rows, outside, more}}`. `statement` is a draft's `{fragment}`, or a library result's `{body, macros, points}`: `macros` null until its work's macros are read, `points` for each id and anchor its body points at (`library.body.pointers`) what is drawn in its place, a result's `{name, number, paper}` and an anchor's `{number}`, the number its source prints. `relative_to` is, for a formalized result, the rows of the results its Lean rests on as axioms (`relative_to`, §5.2), `[]` relative to Mathlib alone, and null otherwise; `rests_on` is, for a result of the person's not formalized, the library results it uses that are not read or not compared, `[]` otherwise. Only what is in the scope is sent, what lies outside counted; `used_by` sends at most fifty. With `more`, `{proofs: [{where, uses}], lean: [declarations], record: [{act, by, at}]}`, a library proof's `where` its work and pages `{ref, short, pages}`, from the records on the result's own text (its subject's hash) alone, as status reads them: `lean` the declarations stating it in its current `lean` record (§5.2, the last standing one on this text), `record` each act on this text. `no-such-result` (404) |
| `web-graph` | `{scope, doc?, result}` | `{focus, excerpt, columns: {back, uses, used_by}, more, edges}`: two steps back, what it uses, what uses it, each column of more than six drawing five and counting the rest in `more`; `edges` `{from, to, proof}` only among what is drawn, `proof` true for a use by a proof alone; `excerpt` the statement's plain words, as `web-search` matches them, at most 200 characters. `no-such-result` (404) |

The views spec's `gen` is the publisher's and is not in these answers yet.
