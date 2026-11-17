# Modes: what a set a person can change would need (after the study, raw)

Asked by the author on 2026-11-16: "Would it be possible to make the mode system more modular? It would be nice to have a "Modes" section of the settings, which displays the default built in modes along with their specification text and the ability to both modify existing modes, delete modes, and add new modes. […] What would be required to make this modular design possible, and are there any desirable features of the present system that the modular design would make IMPOSSIBLE?"

Three agents read the tree without changing it: one the Python core and command line, one the viewer and what reaches an agent's app, one the mode files and the design documents. The tree was `main` at 4adbcdc0 with the viewer's second batch merged, which touches no mode. Line numbers are as of that day. The integrator checked six claims against the code afterwards, and they are marked **checked**; the rest is as the agents reported it.

## Headline findings

- **MODE-1. A mode is text and nothing else.** No code branches on which mode is in force: no flag, permission, zone, record field, validation or default hangs on one (**checked**: the only comparisons with a mode's name are the membership tests below). What an agent may run and where it may write is enforced in code whatever a mode says (`AGENT_COMMANDS` in `loom/src/loom/ai/layout.py`, the protected places in `loom/src/loom/agents.py`). The one rule a mode's text may loosen is where its own changes go, which `rules.md` allows.
- **MODE-2. Editing a mode already works.** A quilt holds its own copies under its `.loom/ai/modes/`, and the quilt's copy wins over the shipped one (`mode_text` in `ai/orient.py`, **checked**). An edit reaches `loom ai mode`, `loom ai orient`, the MCP prompt and its description on the next call. `loom upgrade` keeps an edited file and writes the new version beside it as `<name>.md.new` (`upgrade_layer` in `ai/layout.py`, **checked**); `loom doctor` reports it.
- **MODE-3. The set is a list in code.** `MODES` in `ai/layout.py` names the nine and fixes their order (**checked**). A file not on the list is inert, and `loom ai mode` and the MCP server's `get_prompt` refuse the name (`cli/ai.py`, **checked**; `mcp/server.py`). A deleted file falls back to the shipped text at once, and `loom upgrade` and `loom ai init` write it again (**checked**), so a delete does not stick.
- **MODE-4. The viewer has nothing of modes.** The manifest carries no list of modes and no mode's text; its only mode data is `annotation_types[].modes`, which modes use each annotation type, computed from the `{type:ID}` placeholders. The file tree hides paths that start with a dot, so `.loom/ai/` is never shown, and an agent is refused writing there (`LOOM_DIRS` in `agents.py`, **checked**).
- **MODE-5. Modes travel with the quilt, and nothing shows a change to one.** The copies are committed, not ignored. A co-author's edit to a mode becomes what this person's agent is told, and its "When it fits" line goes into the server's instructions. This is true today; a Settings page makes it easy, and an added mode is one an agent reaches for unasked. The write path met the same shape and ruled that nothing a quilt carries is trusted (`docs/design/writes.md`); decision 10 keeps Lean's switch on the machine for the same reason.
- **MODE-6. No document takes a position on a mode a person adds.** The design says a person may edit a mode in place (`docs/design/agents.md`, `docs/design/invariants.md`); the refusal of an unlisted file was written to retire one mode, not as a stance. The modes study decided "no new modes now" for the shipped set.

## Where the set is fixed

| where | what it does | what a changeable set needs |
|---|---|---|
| `MODES`, `ai/layout.py` | The list and its order; what init and upgrade track | A registry read from the folder, shipped modes first |
| `mode_index` and `modes_using`, `ai/orient.py` | The index from each "When it fits" line; which modes use each annotation type | The same loops over the registry |
| `ai mode`, `cli/ai.py`; `prompts`, `get_prompt`, `mcp/` | Refuse a name not on the list | Refuse a name not in the registry; this membership test is also all that stops a name such as `../x` reaching a path |
| `upgrade_layer` and the version file, `ai/layout.py` | A missing file is written again; entries are keyed by file name alone | A record of which shipped modes the person removed or hid, and whether each file is shipped, edited or added; a mode named `rules`, `orientation` or `formatting` would collide with those documents' entries |
| `doctor.py` | Warns of a deleted or stale mode | Tell hidden from missing |
| `cli/library/state.py` | The library's next step names ingest mode | Hidden, not deleted, while loom's own output names it |
| The mode files and `rules.md` | Five modes cite another by name | A placeholder for a mode's name, or a warning before a delete, as Settings › Annotations warns before deleting a type a mode uses |
| `mcp/server.py` | Builds its instructions once at start and sends no `list_changed` | A refresh, or a plain statement that a running agent learns of a new mode when it restarts |
| Tests | Pin nine names, their order, each file's first lines and `review.md`'s content (`test_ai_layer.py`, `test_mcp_server.py`), and which modes use which type (`loom/tests/fixture/manifest.json`) | The shipped set stays pinned; a person's mode is checked at save instead |

`docs/specs/reserved.md` reserves the mode name `formalize` for a shipped mode to come and has no prefix for mode endpoints.

## What the Settings section needs, by step

1. **Show.** A manifest part listing each mode with its name, its "When it fits" line, its text, and whether it is shipped, edited, or has a newer version waiting beside it (a function in `ATTACH`, `render/parts/agents.py`, the field in the viewer's types, `docs/specs/manifest.md`); a section in `arras/src/lib/shell/settings/` (the catalogue's entries and the branch in `Settings.svelte`). Nothing is written, so no trust question is opened, and MODE-5's blind spot closes: a person can read what their agent is told, a co-author's edit included.
2. **Edit and reset.** Endpoints to save one mode and to put one back to the shipped text, for the author only, refusing a declared agent as `settings-save` and `types-save` do; a case for each in the family's test cases and a row in `docs/specs/write-api.md`, the names reserved first. The screen can follow Settings › Annotations: a list and a detail, a draft that follows the quilt while unchanged, a confirm, a restore. A per-mode reset must keep the version file consistent. The `.new` file upgrade already writes is what a "see what changed" view would read.
3. **Add and delete.** The registry and everything in the table above; a rule for names (a pattern, the reserved names, safe as a file name and as a prompt's name); a check at save that each command a mode cites is one an agent may run, as a test checks for the shipped ones; the index kept within what agent apps keep of the server's instructions (4,096 characters in Claude Code, 512 in Codex, the nine lines being about 1,500); and, once Attach writes each mode as a skill in the agent's app, those files written again when the set changes.

Annotation types are the nearest thing loom has: the quilt's presets, added, edited, deleted and restored in Settings. Three things do not carry over. They are one TOML file, where modes are a file each with a hash kept for each. Their defaults apply only when the file is missing, so a deleted type stays deleted, where a mode falls back file by file. And an agent may edit the types' file, where `.loom/ai/` is protected.

## What a changeable set costs

| property today | under a changeable set |
|---|---|
| An upgrade corrects every mode an agent can reach for | **Lost** for a mode a person wrote or edited: loom can flag it, not mend it. Already given up for an edited mode. |
| "Review mode" means one thing to two co-authors, and to the author helping a pilot | Kept only if an edited mode is marked as edited, to the agent and in diagnostics, or if a shipped name always means the shipped text and an edit makes a copy |
| A mode loom retires disappears from every quilt | Kept only with each file's origin recorded |
| A shipped mode's text cites only commands that exist | Kept for a person's mode only with the check at save, and again at upgrade and in doctor |
| Loom owns the names, `formalize` among them | Kept only if reserved names are refused |
| The boundary on what an agent may change | Unaffected |
| No agent edits a mode | Kept if `.loom/ai/` stays protected and saving is the author's act |

## The decision left open

Whose the modes are. **The quilt's**: one meaning for everyone on it, at the price of MODE-5, which then needs a change that arrives by a pull to be shown to the person before their agent uses it. **The person's**, kept outside the quilt as decision 10 keeps Lean's switch: no such channel, and co-authors diverge. The two can be layered, loom's under the quilt's under the person's. Steps 1 and 2 are the same either way for the shipped nine; step 3 is where the choice is built.
