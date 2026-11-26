# Invariants

An invariant is a rule loom keeps because breaking it once caused a real failure that a simpler design would bring back; each entry gives the rule, the failure, the test that holds it and the old decision records, and its heading is the name a change cites it by. An invariant changes only by a dated line added to its entry (`**2026-11-02.** What changed.`), explained in the commit message; there is no other decision log.

## The author's authority

### The author's acts refuse any agent, whatever name it declares

**Rule.** The author's acts (`accept`; `library verify`, `discard`, `ignore`, `add`, `import` and `drop`; `session delete --purge`; `ai delete`; `changes --keep` and `--discard`; `sync publish --push` and `sync incorporate`) refuse a declared agent name, and under an agent marker refuse any name (K5). `refuse_under_agent` is the guard.

**Why.** In the first study an agent verified its own proposal and loom named the author as verifier, since the name came from git, which the agent's shell shares. Later, `accept --author …` and `refs verify --author …` from an agent's shell were accepted.

**Guard.** `loom/tests/unit/test_writer.py::test_every_act_that_is_the_authors_or_destroys_refuses_under_an_agent_marker`, `loom/tests/unit/test_writer.py::test_the_authors_verbs_refuse_a_declared_agent_whatever_shell_it_is_in`

**Record.** DR-185, DR-203, DR-325-ikmartin

**2026-11-21.** Today's library is deleted with its commands (plan 0.32, the library's phase 2): of its acts on the command line only `loom library add` stays, and over the write API the author's library writes are `library-take`, `-answer`, `-undo`, `-unfile`, `-look-up`, `-entry`, `-delete`, `-restore` and `-upgrade`, each refusing a declared agent (`author-only`, 403), which the write API's cases for each hold. The rule is unchanged.

### The network is the person's to allow

**Rule.** Loom looks works up and fetches them only under `[library] online = true` or a run the person allows: `--online` in a terminal of their own, or "Allow and run" in the viewer, which sends `online` with `library-update`. Neither is written anywhere. Under an agent marker `--online` is refused without the standing consent, and `library-update` refuses a declared agent, so an agent never grants itself the network.

**Why.** Looking a work up tells a service what the person is reading, and a fetch brings files into their quilt; that is consent only they can give, and an agent asking for it on their behalf is exactly the case to stop.

**Guard.** `loom/tests/unit/refs/test_library_store.py::test_online_is_refused_under_an_agent_without_standing_consent`, `loom/tests/unit/render/test_write_api.py::test_each_endpoint_writes_and_refuses_over_the_wire[library-update]`

**Record.** DR-193; plan 0.24.1

**2026-11-21.** `library-update` and `--online` on the library's runs are gone with today's library (plan 0.32, the library's phase 2), and so are the two guards named above. The person's allowance is now `online` on `library-take`, `library-answer` and `library-look-up`, for that one act and written nowhere; those writes refuse a declared agent, and `loom library add` reads an unset quilt as offline. Guards: `loom/tests/unit/render/test_write_api.py::test_each_endpoint_writes_and_refuses_over_the_wire[library-take]` and `[library-look-up]`. The rule is unchanged.

### Identity is never stored in the quilt

**Rule.** The person acting is named by `--as`, then their own user config, then git, and never by anything the quilt tracks. An `[author]` table in `config.toml` identifies nobody.

**Why.** DR-189 made the quilt's tracked `config.toml` settle whom its records name, so cloning a quilt made Bob review and accept under Alice's name.

**Guard.** `loom/tests/unit/test_personal_acceptance.py::test_local_identity_settings_and_missing_identity`

**Record.** DR-189 (reversed), DR-304-luisa

### A passing check is never called verification

**Rule.** The test that a quotation is on its page is "the anchor check", and a proposal that passes it is checked. "Verified" is only the state the author's act produces: loom never prints it for a check, and never hands an agent the author's verify command (P15).

**Why.** `refs propose --help` said "verified against the page", and an agent then told its author "All 13 verified" of thirteen proposals nobody had read.

**Guard.** `loom/tests/unit/test_refs_layer.py::test_propose_does_not_hand_an_agent_the_authors_verb`

**Record.** DR-183

**2026-11-21.** Proposals, `refs propose` and the author's `library verify` are gone with today's library (plan 0.32, the library's phase 2), and so is the guard named above. The rule stands for what records a check of a node against its paper, the evidence lane's; until a test there holds it, it has no guard.

### Overlooking is never accepting

**Rule.** In a copy's or a pull's review every mathematical item starts pending, and only an explicit Accept records an acceptance. Incorporating the source accepts nothing; an item never visited, an item held, and an unchanged proof under a revised statement all stay pending.

**Why.** No incident is recorded. A pull's review applies a coauthor's pull whole, so the short path is to accept what was applied, which would record as read every item the author scrolled past.

**Guard.** `loom/tests/unit/test_adopt.py::test_incoming_explicit_acceptance_keeps_unvisited_dependents_pending`

**Record.** DR-314-luisa, DR-316-luisa

## Agents and configuration

### One table says what an agent may run, and everything else refuses

**Rule.** `AGENT_COMMANDS` in `loom/src/loom/ai/layout.py` is the only list of what an agent may run. The MCP server's tools, the Claude and Codex permission files in both variants, and the list in `.loom/agents/instructions/rules.md` are generated from it. The server's prompts and resources run only commands from it that read. Under an agent marker every other command refuses before reading anything, so a new command is the author's until admitted.

**Why.** The rules' Never section and the permission file were two hand-kept deny lists, and they drifted: `loom upgrade` was in neither, and the alias `loom canonise` walked past the deny on `loom canonize`.

**Guard.** `loom/tests/unit/test_ai_layer.py::test_the_allow_list_and_the_permission_file_cannot_disagree`, `loom/tests/unit/test_ai_layer.py::test_codex_is_given_the_same_policy_as_claude`, `loom/tests/unit/test_mcp_tools.py::test_the_tools_are_the_agent_commands_and_none_of_the_authors`, `loom/tests/unit/test_mcp_resources.py::test_every_command_a_prompt_or_resource_runs_is_an_agent_command_that_only_reads`

**Record.** DR-154, DR-173, DR-333-ikmartin

### Loom never runs a command the quilt carries

**Rule.** Configuration that names a command for an agent's app is generated on the machine that runs it and never committed. `loom ai init` writes the MCP client files (`.mcp.json`, `.codex/config.toml`, `.gemini/settings.json`, `.cursor/mcp.json`) with this machine's absolute paths, and they are gitignored. `ai init` writes over no client file that git tracks or that holds anything but loom's server, and `loom doctor` fails when git tracks one.

**Why.** No incident is recorded. While `loom serve` ran the agent command when a message waited, a tracked one would have let cloning and serving someone's quilt run whatever they committed. A client reading a committed config file runs it the same way (`claude -p` loads a project `.mcp.json` without asking).

**Guard.** `loom/tests/unit/test_clients.py::test_every_client_file_is_gitignored`, `loom/tests/unit/test_clients.py::test_a_client_file_git_tracks_is_not_written`, `loom/tests/unit/test_doctor.py::test_a_client_file_git_tracks_fails`

**Record.** DR-273-ikmartin

**2026-10-26.** Loom starts no agent (plan 0.20.1): `ai/ai-config.toml`, `[ai] launch` and the launcher are gone, and with them this rule's two guards and the unchecked `.claude/settings.json` a launched turn was given.

**2026-10-28.** The client files live in the quilt, gitignored, rather than being passed to the client by name. Only Claude Code takes a file by name; every other app reads one in the project or in the person's home. So the guard moved from where the file is to whether git tracks it (plan 0.21.6).

**2026-11-10.** The rule covers TeX tooling too, at the author's word (plan 0.29). `latexmk` runs with `-norc`, because a `latexmkrc` is a Perl program, one in a quilt ran on every compile, and the author's own adds `-shell-escape`, which let any document's `\write18` run a command. Since `loom serve` compiles every document a change reaches, and `loom library update` compiles every fetched paper, either was a quilt's command run unasked. TeX4ht runs on a copy outside the quilt with an empty home, from which a `.mk4` build file and a `.make4ht` configuration, both Lua, and a `tex4ht.env`, which names the commands `t4ht` runs, are removed. Guards: `loom/tests/tex/test_compile_runs.py::test_neither_a_quilt_s_latexmkrc_nor_a_write18_runs_with_shell_escape_in_the_home_rc`, `loom/tests/tex/test_tex4ht.py::test_nothing_a_quilt_carries_for_tex4ht_runs`.

### Generated agent configuration is tested against the real client

**Rule.** A change to what loom generates for an agent client (permission files, Codex rules, MCP client files) is tried with the client itself, run as a person starting an agent in the quilt would run it (`claude -p --settings …`), before it ships. Unit tests check only the shape loom believes right.

**Why.** The permission file's `Write` rules passed every unit test and were never enforced: Claude Code matches only `Edit` rules to paths. Then root-relative allows passed too, but under `--settings` a leading `/` means `.claude/`, so every write a launched agent made was refused.

**Guard.** The opt-in `client` tier, run by hand with `scripts/verify client` and never in CI, since it spends on the account of whoever runs it:
- `loom/tests/client/test_claude.py::test_a_launched_claude_writes_where_the_quilt_lets_it_and_not_where_it_protects`;
- `::test_a_launched_claude_runs_the_agents_loom_commands_and_not_the_authors`, on both variants;
- `::test_a_claude_attached_over_mcp_writes_as_its_agent_and_runs_no_authors_command`, on the MCP variant.

`loom/tests/client/test_codex.py` and `test_gemini.py` try the server each app's file names, and skip where the app is not installed. Neither has run yet.

**Record.** DR-275-ikmartin, DR-343-ikmartin

**2026-10-26.** Launch commands are gone with launching (plan 0.20.1); the client tier runs `claude -p` itself, as a person starting an agent in the quilt would.

**2026-11-01.** The boundary test writes an open file, the agent's copies, a directory `[agents] deny` names and one of loom's records, in the mode that accepts edits, since outside the protected paths whether the client asks is the person's setting (plan 0.22.6).

**2026-11-04.** The MCP variant allows the agent's commands in a shell beside the tools, since a server that could not start left an agent with no loom at all. The client tier now tries those commands on both variants, and no longer asserts that an agent attached over MCP ran no `loom` in a shell.

### Where an agent may write is one table, which loom's own commands enforce in every client

**Rule.** `loom/src/loom/agents.py` holds the boundary: the agent's own places (the sessions, its copies and its scratch, under `.loom/agents/`), what is always protected (loom's records under `.loom/`, the history, `config.toml`, the research state), and the person's `[agents] deny`. Every loom command that writes a path an agent chose refuses an agent a protected one by its one predicate, and Claude Code's permission file is rendered from its tables. Every `.loom/` path loom names is an agent's place or protected.

**Why.** Only Claude Code's file can refuse an edit by path, so a boundary kept only there held for one client of four. And a record added under `.loom/` without a deny of its own would be open to an agent's edits, since the agent's places sit beside the records there and a deny on `.loom/` would beat their allows.

**Guard.** `loom/tests/unit/test_paths.py::test_every_path_under_loom_is_an_agents_place_or_protected`, `loom/tests/unit/test_destination.py::test_an_agent_is_refused_what_the_quilt_protects_and_a_person_is_not`, `loom/tests/unit/test_ai_layer.py::test_the_deny_list_is_rendered_into_the_permission_file_beside_what_is_always_protected`

**Record.** Plan 0.22.6

**2026-11-02.** The viewer's Settings edits `[agents] deny` and rewrites Claude Code's permission file to it, each only on the author's act: `settings-save` and `agents-update` refuse a declared agent like every other author act over the API (plan 0.23).

**2026-11-11.** `.loom/records/annotation-types.toml` is the one file of loom's under `.loom/` that an agent may edit (`AGENT_FILES`): a type's instructions are written for agents, and an agent asked to write one should not need the person to paste it in (plan 0.30, decision 4). Guarded by `loom/tests/unit/records/test_types.py::test_an_agent_may_edit_the_types_but_nothing_else_of_loom_s`.

**2026-11-17.** The agent's places are `.loom/agents/sessions/`, `.loom/agents/copies/` and `.loom/agents/scratch/`, and no longer what loom derives, which loom may delete at any moment and which the viewer is served from; `.loom/` holds a folder for each kind (plan 0.32, decision 18). Guarded by `loom/tests/unit/test_paths.py::test_every_path_lies_in_the_folder_of_one_kind` beside the guard above.

### Agent instructions name only commands the agent may run

**Rule.** The orientation, the rules and the mode files tell an agent to run only commands in `AGENT_COMMANDS`; an author's command appears in them only where the text says it refuses the agent.

**Why.** The orientation told agents to run `loom linearize`, which the permission file denied and which, had it run, would have superseded the spine and every file it inlined and reassigned `main`.

**Guard.** `loom/tests/unit/test_ai_layer.py::test_every_command_the_agent_is_told_to_run_is_allowed`

**Record.** DR-155

### An agent deletes nothing from a session's directory

**Rule.** An agent never deletes a file in a session's directory, since an annotation or a message may point at it. Its scripts, backups and staging files go in its scratch, `.loom/agents/scratch/<session>/`, and the permission file denies `Bash(rm *)`.

**Why.** An agent tidying a session cluttered with its own intermediates tried to `rm` a file one of its own annotations pointed at. A shell permission cannot be confined to one directory, so the fix was a separate place for intermediates.

**Guard.** `loom/tests/unit/test_ai_layer.py::test_an_agent_is_never_allowed_to_delete`

**Record.** DR-315-ikmartin

**2026-11-17.** The scratch moved out of `.loom/build/`, which loom may delete, to `.loom/agents/scratch/<session>/`, which stays on one machine (plan 0.32, decision 18).

### Upgrade never destroys an author's edit

**Rule.** `loom upgrade` and `loom ai init` keep one line of loom's in `CLAUDE.md`, `AGENTS.md` and `GEMINI.md`, replacing the other variant's line where it stands, and touch nothing else there. An edited mode file or orientation is kept, with the shipped text written beside it as `.new`; an edited `loom.sty` is kept as `loom.sty.old` before it is replaced. `.loom/records/annotation-types.toml` is written only where there is none.

**Why.** Upgrade wrote `CLAUDE.md` and `AGENTS.md` whole whenever they differed from the shipped copy, so an author who had added instructions lost them, and an edited orientation was overwritten with no warning and no backup.

**Guard.** `loom/tests/unit/test_ai_layer.py::test_root_files_carry_one_line_and_keep_the_authors`, `loom/tests/unit/test_ai_layer.py::test_upgrade_preserves_edited_modes`, `loom/tests/unit/test_ai_layer.py::test_upgrade_keeps_an_edited_loom_sty_as_old_and_says_so`

**Record.** DR-151, DR-170, DR-333-ikmartin

**2026-11-11.** The annotation types file joined the rule (plan 0.30, decision 4): it is the person's from the moment `loom init` writes it, so upgrade adds it to a quilt that lacks it and never rewrites it. Guarded by `loom/tests/unit/records/test_types.py::test_init_writes_the_defaults_listed_and_upgrade_keeps_an_edited_file`.

### Where the person is looking is never written down

**Rule.** The place a viewer tab reports to `loom serve` (`here`) is held in the server's memory and nowhere else: no file under the quilt, no log line, no build output. `GET /_api/here` serves it only with the server's token and to its own origin, and stopping the server forgets it.

**Why.** Where a person is reading, and the words they selected, are where they are, not a record of anything they did (P2). Written down, they would be committed by the next `git add`, or read by whoever opens the quilt after them.

**Guard.** `loom/tests/unit/render/test_here.py::test_the_place_is_held_in_memory_and_served_only_with_the_token`

**Record.** plan 0.21.8

## Records, history and sync

### Posting to an inbox takes a lock

**Rule.** `post` holds an exclusive lock on the session's `inbox.jsonl` from reading the last sequence number to appending the new event, so two writers never draw the same number.

**Why.** `post` read the last number and appended with nothing between, which was harmless while one party wrote at a time and a race once an agent could answer while the author typed in the viewer.

**Guard.** `loom/tests/unit/test_transcript.py::test_two_writers_never_draw_the_same_number`

**Record.** DR-265-ikmartin

### Drawing an id takes a lock

**Rule.** Whatever draws an id from what it can see holds an exclusive lock from the read to the write, in the command itself, so the lock holds across shells, servers and the viewer alike (`loom/src/loom/locks.py`). What is drawn against a log is drawn under a lock on that log: an annotation's, a session's and a link's id, a step's number, a message's sequence number. A node id has no one file to draw from, so `loom new`, `loom fork` and `loom history restore` hold `.loom/local/ids.lock` from before their scan until their file is written, as `loom draft` and `loom stamp` do for the step they plan. A step planned from a history the ledger has since moved past is refused before anything is written. `loom new` also creates its file exclusively, so it never overwrites what no lock could stop: a person saving at that moment, or a filesystem with no locks, on which loom says so and goes on (P13).

`loom import`, `loom linearize` and incorporating an agent document hold no lock while they draw node ids, since a compile, a prompt or a preview stands between the draw and the write. They write those ids into a document, never into a file the id names, so a collision is two definitions of one id, which is reported and overwrites nothing (P13). `loom id` says ids and reserves none: `--next` prints one, and a patch or a labelled copy holds them only once the author puts it in a document.

**Why.** A study of `loom mcp` beside `loom` in a shell, on copies of the demo, with writers started at the same moment. Two `loom new` calls both reported success with one file written in ten trials of twelve, a node silently lost; through two servers, sixteen calls reported success and eight files existed. Two `loom annotate` calls drew one id in ten trials of twelve, so a reply to that id could not say which annotation it meant. A lock inside one server had hidden this from any agent with one server.

**Guard.** `loom/tests/unit/test_parallel_writers.py::test_parallel_new_each_make_a_file_of_their_own_or_refuse_cleanly`, `loom/tests/unit/test_parallel_writers.py::test_parallel_annotate_gives_every_annotation_its_own_id`, `loom/tests/unit/test_parallel_writers.py::test_parallel_steps_each_draw_a_number_of_their_own`, `loom/tests/unit/test_mcp_server.py::test_two_servers_on_one_quilt_never_lose_a_node`

**Record.** The study of 2026-11-04.

**2026-11-05.** "What is numbered in a log" became "what is drawn against a log", because an annotation's, a note's, a session's and a link's id stopped being a number (the next entry). The lock is unchanged: a draw still reads what the log holds so as not to repeat it, and this rule keeps writers on one machine apart, where the next keeps clones apart.

### A record's id is drawn, never counted

**Rule.** An annotation's, a session's and a link's id ends in a token drawn at random (`loom/src/loom/records/ids.py`), so two clones that write apart draw two ids. Nothing reads an order out of a token. Two records that still reach a log under one id are reported as `loom:repeated-id`, and loom changes neither (P13).

**Why.** Two clones of a quilt, each writing on one day and merged keeping both sides of git's conflict. Each clone's first annotation that day was `0001`, so `loom ai annotations` listed two under one id, a reply could not say which it meant, and `loom lint` said nothing. A note or a session under a shared id was worse: the reader kept the last, so the earlier one left every view with no word. A link's count held no day, so it shared an id on any day, and undoing either removed both.

**Guard.** `loom/tests/unit/records/test_record_ids.py::test_two_clones_merge_into_records_each_with_an_id_of_its_own`, `loom/tests/unit/records/test_record_ids.py::test_lint_reports_two_records_under_one_id`

**Record.** The study of 2026-11-05.

### Resolving a name never creates anything

**Rule.** One resolver turns a `--session` value into a session. A value that matches nothing, or several, is an error that says what it saw, and nothing on disk changes; making a session is an act of its own.

**Why.** A second resolver took a run's name as a path and created that directory, which then shadowed the real run in every later lookup. The beta experiment lost nineteen findings this way: `loom ai findings` said "no findings yet", and nothing was an error.

**Guard.** `loom/tests/unit/records/test_run_resolution.py::test_an_unmatched_session_is_an_error_and_never_a_path`

**Record.** DR-167

### A write that says nothing is refused

**Rule.** A reply with no message, an edit that changes nothing, and an edit to an empty body are refused with a non-zero exit and write nothing. A bare resolution, and an annotation whose type does not stay open until resolved, a highlight with nothing said among them, stay legal.

**Why.** `--reply` and `--resolve` read their one argument as a target, so the author's answers to findings were filed as `body: ""`, with exit 0 and no warning. Loom's own fixture generator did it twice, and the synthetic quilt shipped two empty replies nobody saw.

**Guard.** `loom/tests/unit/records/test_review_commands.py::test_a_verb_that_answers_nothing_is_refused`

**Record.** DR-171

### Review records are appended, never rewritten

**Rule.** Every review event is one line appended to `.loom/records/annotations/log.jsonl`, and an annotation's state is the replay of its events. The one rewrite is a deletion, which removes an annotation's events and its replies' under the log's lock, in place, so no append lands between its read and its write. The history ledger and a session's inbox are appended the same way (P2).

**Why.** Records were files rewritten whole. When an agent resolved its own finding, the parent and the writer were two copies of one file and the second write clobbered the resolution, which is the case an agent hits on every re-check.

**Guard.** `loom/tests/unit/records/test_review_commands.py::test_a_run_resolves_its_own_annotation`

**Record.** DR-147 (the annotation log, 2026-09-18; a second DR-147 is about base paths)

**Changed 2026-11-11** (plan 0.30, decision 7, approved by the author): deleting an annotation removes it from the log instead of appending a discard, since a record nobody can see is not worth keeping. The clobbering this invariant records cannot recur, because a deletion holds the same lock every append takes and rewrites the file in place.

### A re-check edits a finding; it does not reply to it

**Rule.** A finding that still stands is restated with an `edited` event, which supersedes its body and keeps the earlier one in the log. A reply is for talking to the author.

**Why.** Before `edited` existed a re-check could only reply, and three passes over a finding that still stood left it wearing three restatements of itself.

**Guard.** `loom/tests/unit/records/test_recorded.py::test_an_edit_restates_the_finding_against_the_text_as_it_is_now`

**Record.** DR-147 (the annotation log, 2026-09-18)

### The log's columns use underscores, and a line that does not read is reported

**Rule.** Log lines carry `reply_to`, and an annotation's type as `type`, the id of one in the types file. A line whose type is not an id, a malformed id, or a reply to nothing is reported as `loom:foreign-annotations`, never silently defaulted. A type the quilt no longer lists is no problem, since a type is a label and the annotation keeps the look it was drawn in.

**Why.** The only written column list, in plan 0.10, spelled `annotation-kind` and `reply-to`. A log written from it lost its kind and its parent on every line and said nothing, because a missing kind silently became `objection`.

**Guard.** `loom/tests/unit/records/test_hostile_log.py::test_a_type_that_is_not_an_id_is_reported`, `loom/tests/unit/records/test_hostile_log.py::test_a_reply_to_nothing_is_reported`

**Record.** DR-165

**2026-11-11.** `annotation_kind` gave way to `type` (plan 0.30, decision 4). A line with no type is an untyped annotation rather than a defaulted one, so the silent default this records has nowhere to recur.

### Printing a patch records nothing

**Rule.** `loom revert` prints a patch and writes nothing to the history; applying the patch is the author's act. The same holds for any command that prints a patch (K4).

**Why.** `loom revert` appended a revert to the history every time it printed a patch, applied or not, with `--json` and with nothing to change, so four runs left four reverts of a file that never changed.

**Guard.** `loom/tests/unit/history/test_commands.py::test_revert_prints_a_patch_and_records_nothing`

**Record.** DR-326-ikmartin

### The index is written last

**Rule.** What points at other files is written after them: a history step's version files before its ledger line, and every build fragment, written beside its target and renamed into place, before `manifest.json`, itself written by rename.

**Why.** No incident is recorded. An interrupted step must leave a directory nothing refers to, not a ledger line naming files that do not exist; and arras reloads when the manifest changes, so a manifest written first would name fragments that are not there yet.

**Guard.** `loom/tests/unit/history/test_commands.py::test_a_step_is_written_whole_before_the_ledger_line_that_names_it`, `loom/tests/unit/render/test_build.py::test_the_manifest_is_renamed_into_place_after_every_file_it_publishes`

**Record.** DR-83, DR-134

**2026-10-26.** Both orderings are now tested, each failing when its order is reversed.

### No step is recorded beside an interrupted one

**Rule.** A step directory no ledger line names, left by a step interrupted before it was recorded, is reported by `loom history verify` as `loom:history-interrupted` with the command that removes it; every command that records a step (stamp, draft, import, adopt) refuses while one is there, writes nothing, and names that command. Loom removes nothing itself (P13).

**Why.** The test that proved a step's files are written before its line found that `history verify` never reported the directory such an interruption leaves, that retrying the stamp crashed on it with a traceback, and that a stamp under another name wrote a second directory with the same step number.

**Guard.** `loom/tests/unit/history/test_commands.py::test_a_step_is_never_recorded_beside_an_interrupted_one`

**Record.** Commit `3310c343`.

### A write to a person's file is journalled first and keeps the bytes it replaces

**Rule.** Keep, Discard, restoring a version or a set-aside text, a tick and Settings write a person's file only through the door (`loom/src/loom/writes.py`, `docs/design/writes.md`): under one lock that every loom process takes, every decision made again under it, the bytes the act replaces stored and a `begin` line in the journal before any file, and the file refused if it no longer holds what the act read. A write a crash cut short is finished or undone by the next act, never left half done; one whose file the person changed since is reported and left (P13). A file that is not UTF-8 is never spliced, and a path outside the quilt is never written, by an act or by recovery, whatever a journal says.

**Why.** The v0.1 safety study, on copies of real quilts (`docs/reports/v0.1-study/raw/safety.md`): a save made during Keep was lost; two Keeps at once wrote one edit twice or lost one; a crash between the write and its record let the next Keep write the edit again; Keep and restore rewrote Windows line endings and Discard in such a file corrupted it; restore overwrote a file it kept nowhere; Settings kept nothing first and left `config.toml` readable by its owner alone; put-back wrote outside the quilt.

**Guard.** `loom/tests/unit/test_write_safety.py::test_a_save_made_while_keep_runs_moves_the_edit_with_it`, `loom/tests/unit/test_write_safety.py::test_two_keeps_in_one_file_at_once_both_land_once`, `loom/tests/unit/test_write_safety.py::test_a_keep_cut_short_anywhere_writes_the_edit_once`, `loom/tests/unit/test_write_safety.py::test_keep_leaves_line_endings_alone`, `loom/tests/unit/test_write_safety.py::test_discarding_an_agents_edit_in_a_crlf_file_gives_back_its_bytes`, `loom/tests/unit/test_write_safety.py::test_restoring_a_version_keeps_every_file_it_overwrites`, `loom/tests/unit/test_write_safety.py::test_saving_settings_keeps_the_config_first`, `loom/tests/unit/test_write_safety.py::test_putting_back_a_text_never_writes_outside_the_quilt`, `loom/tests/unit/test_write_safety.py::test_an_edit_in_a_file_that_is_not_utf8_is_never_written`, `loom/tests/unit/test_writes.py::test_the_journal_names_the_act_before_any_file_is_written`, `loom/tests/unit/test_writes.py::test_a_crash_between_two_files_is_undone_whole`, `loom/tests/unit/test_writes.py::test_a_commit_cut_short_puts_back_only_a_file_that_still_holds_what_loom_wrote`, `loom/tests/unit/test_writes.py::test_recovery_never_deletes_a_file_whose_text_before_the_store_lacks`, `loom/tests/unit/test_writes.py::test_a_real_process_killed_after_the_journal_is_settled_by_the_next`, `loom/tests/unit/test_writes.py::test_recovery_never_writes_a_file_outside_the_quilt`, `loom/tests/unit/test_writes.py::test_recovery_never_appends_a_record_to_a_file_outside_the_quilt`

**Record.** The study's spike of the door (`docs/reports/v0.1-study/raw/spike-door.md`); plan 0.32, the Safe workstream, steps 1 to 3.

### A suggested edit is judged at its own place

**Rule.** An insertion, and a replacement that adds words beside its quote, reads as written in only where Keep would write it; any other replacement only once its quote no longer stands in its block (`records/edits.py`, `taken_how`). An insertion, and a replacement that adds words beside its quote, is placed only while the words recorded beside its place when it was suggested still stand there, and a replacement of a whole body only while that body reads as it did (`place`). An edit on a key named by its place in its file goes only to the block that its text, the line above it and its quoted words point to, never to whatever block now holds the place (`store.filed_on`, `place`). An edit's quote, the source's own words, is found again only as written, never as the page prints it (`selectors.find_written`). Otherwise it is unplaced, and Keep writes nothing (`docs/design/writes.md`, "Where an edit goes").

**Why.** The v0.1 safety study (`docs/reports/v0.1-study/raw/safety.md`): a short suggestion the person typed in and touched was written a second time; one placed past a block's `\end{…}` and typed in was written again on every press; a phrase standing anywhere in its block, or a replacement trimming its quote to a part of it, read as kept with nothing written; and an answer suggested on the third of three empty answers was written into the second once a problem was put in before them.

**Guard.** `loom/tests/unit/test_write_safety.py::test_a_short_edit_written_in_and_touched_is_not_written_twice`, `loom/tests/unit/test_write_safety.py::test_a_short_edit_written_in_at_the_foot_of_a_body_and_touched_is_not_written_twice`, `loom/tests/unit/test_write_safety.py::test_an_edit_placed_after_its_blocks_end_is_not_written_twice`, `loom/tests/unit/test_write_safety.py::test_keeping_an_insertion_writes_it_even_when_its_words_stand_elsewhere_in_the_block`, `loom/tests/unit/test_write_safety.py::test_a_replacement_that_trims_its_quote_is_written`, `loom/tests/unit/test_write_safety.py::test_a_whole_body_replacement_is_written_only_over_the_body_it_was_suggested_on`, `loom/tests/unit/records/test_edits.py::test_a_replacement_whose_quote_was_rewritten_goes_nowhere_though_it_reads_like_a_plain_word_further_on`, `loom/tests/unit/test_write_safety.py::test_a_suggestion_at_the_foot_of_a_file_whose_text_all_belongs_to_its_section_is_written_once`, `loom/tests/unit/test_write_safety.py::test_an_edit_on_a_block_named_by_place_stays_on_that_block`, `loom/tests/unit/test_write_safety.py::test_an_answer_typed_into_a_block_named_by_place_is_not_written_again_once_a_block_is_put_in_before_it`, `loom/tests/unit/records/test_edits.py::test_a_phrase_suggested_beside_the_very_words_that_already_stand_there_is_not_read_as_taken`, `loom/tests/unit/records/test_edits.py::test_an_edit_on_a_block_named_by_place_that_has_changed_goes_there_only_by_its_quote`

**Record.** The door's spike (`docs/reports/v0.1-study/raw/spike-door.md`, DOOR-5 and DOOR-15) and `raw/check-labels.md`; plan 0.32, the Safe workstream, the door's step 4.

### The undo of a Keep takes out only what that Keep wrote

**Rule.** The undo of a Keep (`pending.unkeep`) writes only at the place its Keep wrote, established exactly: the file holds that Keep's after bytes, or the words and the 32 characters either side, taken across the same Keep's other splices and with a file's edge among them counted, stand once in that Keep's after text and once in the file and are carried over unchanged by what the two texts share or by a diff of what they do not (`writes.place_in`). It never searches the file for like words, never writes where the region stands twice, and where the place is not established it refuses and writes nothing (`changed-since`); every other byte of the file is kept. It undoes only a Keep this machine's journal holds, never one that wrote nothing, never from a journal line that fails recovery's guard or whose splices the stored texts do not bear out, and it keeps a version of each document it changes first. A kept edit is opened again only with its words taken out (`records.edits.discard` refuses it); a restore, a put-back or a Discard opens one again only where it puts back the very bytes its Keep replaced, or the words its Keep replaced at their place with the Keep's words nowhere in the file, and records an edit kept only where its words stand at their place (`pending.follow_words`).

**Why.** The v0.1 safety study (`docs/reports/v0.1-study/raw/safety.md`, SAFE-9 and SAFE-1): there was no one-step undo of Keep, and the viewer's undo of a Keep opened the record and left the words in the file, so the next Keep wrote them a second time.

**Guard.** `loom/tests/unit/test_undo.py::test_a_keep_is_undone_in_one_step_with_the_exact_bytes_back`, `loom/tests/unit/test_undo.py::test_an_undo_in_a_crlf_file_gives_back_its_bytes`, `loom/tests/unit/test_undo.py::test_an_undo_keeps_what_changed_elsewhere_in_the_file_since`, `loom/tests/unit/test_undo.py::test_an_undo_refuses_once_the_words_beside_what_it_wrote_changed`, `loom/tests/unit/test_undo.py::test_an_undo_refuses_where_its_words_and_their_neighbours_stand_twice`, `loom/tests/unit/test_undo.py::test_an_undo_never_takes_a_twins_words_after_the_person_swaps_two_alike_blocks`, `loom/tests/unit/test_undo.py::test_an_undo_after_typing_at_a_files_end_beside_its_words_refuses`, `loom/tests/unit/test_undo.py::test_an_undo_after_typing_at_a_files_start_within_its_neighbours_refuses`, `loom/tests/unit/test_undo.py::test_an_undo_of_edits_kept_side_by_side_never_writes_in_another_block`, `loom/tests/unit/test_undo.py::test_an_undo_never_takes_the_persons_own_like_words_from_another_block`, `loom/tests/unit/test_undo.py::test_an_undo_never_takes_out_another_keeps_like_words`, `loom/tests/unit/test_undo.py::test_words_a_keep_joined_onto_one_line_come_back_in_the_files_line_ending`, `loom/tests/unit/test_undo.py::test_an_undo_splices_in_nothing_its_texts_do_not_hold`, `loom/tests/unit/test_undo.py::test_a_restore_never_opens_an_edit_whose_words_stand_elsewhere`, `loom/tests/unit/test_undo.py::test_discarding_a_change_that_brings_a_kept_edits_words_back_records_it_kept`, `loom/tests/unit/test_undo.py::test_a_keep_that_wrote_nothing_is_not_undone`, `loom/tests/unit/test_undo.py::test_a_save_made_while_the_undo_keeps_its_version_survives_and_nothing_is_undone`, `loom/tests/unit/test_undo.py::test_a_save_made_between_the_undos_plan_and_its_version_survives`, `loom/tests/unit/test_write_safety.py::test_a_seeded_sequence_with_the_undo_of_keeps_among_its_writes_keeps_the_persons_text`, `loom/tests/unit/test_undo.py::test_a_kept_edit_is_opened_again_only_by_the_undo_of_its_keep`, `loom/tests/unit/test_undo.py::test_a_restore_that_takes_a_kept_edit_out_opens_it_again`, `loom/tests/unit/test_undo.py::test_a_restore_leaves_kept_an_edit_whose_words_the_person_changed_beside`, `loom/tests/unit/test_undo.py::test_a_restore_of_the_very_bytes_a_keep_replaced_opens_its_edit_again`

**Record.** The door's spike (`docs/reports/v0.1-study/raw/spike-door.md`, DOOR-14); plan 0.32, the Safe workstream, the door's step 5.

### Two definitions of one id leave it conflicted

**Rule.** When an id is defined twice, by two files or within one, the id has no text and no winner; `duplicate-id` names every file, and whatever needs the text (accept, annotate, closure, stamp, revert) refuses until one definition goes.

**Why.** Picking one by walk order publishes a copy chosen by filename while a closure inlines the other, records acceptances against a text nobody chose, and lets an agent edit one copy while the other silently disagrees. Later, `loom inline` defined every id twice and reported "Identity test: pass".

**Guard.** `loom/tests/unit/scan/test_conflicts.py::test_two_files_defining_one_id_leave_it_conflicted`, `loom/tests/unit/scan/test_conflicts.py::test_two_copies_in_one_file_are_conflicted_too`, `loom/tests/unit/render/test_canon.py::test_a_conflicted_key_is_published_with_no_text`

**Record.** DR-135, DR-326-ikmartin

**2026-10-26.** Two definitions within one file are conflicted too. The later one used to hold the id silently; the only fix offered is a fresh id (`loom id --next`), since forking splits documents, not one file. Commit `becf7258`.

### Sync never writes to the quilt's own repository

**Rule.** Loom's Git runs only in the sync directory the record names, the person's clone of the workspace. `sync init` refuses a directory that is the quilt's own repository or a worktree of it, holds a quilt, follows a remote of the quilt's own repository however that is spelled, or sits inside one of loom's own directories; `sync publish --push` refuses a workspace that holds a quilt.

**Why.** `sync init` defaulted to `--remote origin --branch main`, usually the quilt's own repository, and `sync publish --push` then replaced that branch with the source-only projection, removing `config.toml`, `ai/` and `.loom/` from what a coauthor pulls.

**Guard.** `loom/tests/unit/test_sync.py::test_sync_init_refuses_the_quilt_s_own_upstream_however_it_is_spelled`, `loom/tests/unit/test_sync.py::test_init_refuses_the_quilt_s_repository_and_loom_s_own_directories`, `loom/tests/unit/test_sync.py::test_publish_push_refuses_a_workspace_that_holds_a_quilt`, `loom/tests/unit/test_sync.py::test_the_quilt_s_own_repository_is_never_touched`, `loom/tests/unit/test_sync.py::test_the_sync_directory_s_files_and_branch_are_never_touched`

**Record.** DR-326-ikmartin, DR-333-ikmartin

**2026-10-31.** Loom no longer clones the workspace into `.loom/workspace/`. The person clones it into a directory of their own and names it with `sync init DIR`, and loom runs Git there as it did in its clone, moving only its own refs and the remote's branch (plan 0.22.2). The guards moved to pairing: what used to be one URL check now covers the directory itself.

## The library

### A digest records what it was read from

**Rule.** A digest's `extracted-from` names the artifact its statements were read from, apart from `published-as`, the work the bibliography cites; a fetched source records the identifier it was fetched on. When the two differ, `loom:unverified-locators` says so.

**Why.** Preprints fetched into the directory named for the published DOI were labelled by that directory, so 11 of the study's 16 digests claimed the DOI and the version warning never fired; one gave the preprint's Theorem 3.4, which is the published Theorem 3.5 with a different conclusion.

**Guard.** `loom/tests/unit/test_refs_layer.py::test_a_source_fetched_on_a_preprint_id_says_so_in_the_digest`, `loom/tests/unit/test_digest.py::test_unverified_locators_when_the_artifact_and_the_cited_work_differ`

**Record.** DR-109, DR-181

**2026-11-21.** Digests are gone with today's library (plan 0.32, the library's phase 2), and so are the guards named above. A version of a paper is now a reference of its own holding its documents by hash (`docs/specs/nodes.md` §7), so what a node was read from is the document its reference holds; the rule has no guard until the digest that writes nodes (phase 3) names one.

### A proposal is never a dependency

**Rule.** The scan makes no edge to a proposed result from outside its own file, whether by `\cite[postnote]`, `\ref` or `\uses`: `loom:cites-proposed-node` (warning) reports the citation, and verifying the proposal makes it a dependency. So nobody's unchecked statement enters a closure, a closure document or a compile (P15).

**Why.** Every postnote match became an edge, proposals included, so `loom source --closure` and `loom compile KEY` carried statements nobody had vouched for, while `refs/proposals.py` promised, as "a structural guarantee", that a proposal could enter no closure. Found by the review of the relloc quilt on 2026-10-26.

**Guard.** `loom/tests/unit/test_refs_layer.py::test_a_cited_proposal_is_no_dependency_until_it_is_verified`

**Record.** Commit `3f38e7c9`.

**2026-11-21.** Proposals are gone with today's library (plan 0.32, the library's phase 2), and so are `loom:cites-proposed-node` and the guard named above. The failure's lesson stands for the library's nodes, whose state is evidence's: an unchecked node entering a closure is phase 3's to settle, and the rule has no guard until then.

### A document is filed under a work only on the person's word

**Rule.** A PDF or a LaTeX source is filed under a work the library already has only when the person says it is that work: `--for` on the command line, "same work" answered in the viewer, or a PDF dropped on that work that shows nothing against it. A strong match (the identifier the document states as its own, or the entry's whole title with its first author leading the byline or a reference manager's file name) only chooses the work the person is asked about, and an entry that names no author is matched by its identifier alone. A PDF that matches nothing is kept as a work of its own, and the report names the nearest entry. A wrongly filed PDF can be taken off its work, and every filing is undone in one step.

**Why.** A handbook that named Olsson fifth and shared half the title of his 2003 paper was filed as that paper on those two weak signals, and the real paper was then skipped because the slot was taken. Then a strong match filed silently: an entry made of a journal's masthead, "of Financial" with no author, matched every later paper of that journal on its title alone, and the Cox–Ross–Rubinstein PDF was filed as Glosten and Milgrom's; and a note citing a paper's arXiv id was announced as that paper.

**Guard.** `loom/tests/unit/refs/test_matching.py::test_the_quant_incident_no_longer_reproduces`, `loom/tests/unit/refs/test_intake.py::test_a_pdf_naming_a_work_is_a_question_and_nothing_is_filed_until_answered`, `loom/tests/unit/refs/test_library_store.py::test_a_weak_match_is_not_filed_against_the_entry_and_the_pdf_is_kept_as_a_work_of_its_own`

**Record.** DR-331-ikmartin. 2026-11-04, at the author's request: what is withheld is the filing against the entry, never the PDF. The author could not add revision notes with no DOI, a scanned textbook, or a book whose PDF was refused after its entry was written; a PDF they provide is now always kept. The rule the failure taught is unchanged for a match loom makes on its own; a file name a reference manager wrote now counts as evidence, and an entry naming no author is matched on its whole title. 2026-11-17, agreed by the author (plan 0.32, Library): a strong match no longer files on its own anywhere, the command line asking for `--for` as the viewer asks its one question, after the quant quilt's wrong match; an entry naming no author is matched by its identifier alone, and is still offered when a PDF's own title is its title.

**2026-11-21.** The intake is rebuilt on references (plan 0.32, the library's phase 2; the rulings on `library-views.md` Opens 6 and 18): a document is offered as a work the library has only by an identifier it states, never by its title or byline, and filed under it only on the person's answer or a drop on the work's row. The guards named above are gone; the guards are now `loom/tests/unit/library/test_intake.py::test_a_title_alike_is_never_a_match`, `::test_a_pdf_stating_an_identifier_the_library_has_asks_and_is_answered` and `::test_a_drop_on_a_row_is_filed_under_it`.

### Redoing a step keeps what a person verified

**Rule.** `library update --redo` and `library drop` keep every result a person verified: its record, and its text in the digest byte for byte.

**Why.** `loom refs build --force` rewrote a digest from the paper's source and deleted every result the author had verified into it, while `results.json` still said `verified` and `refs recheck` reported nothing moved.

**Guard.** `loom/tests/unit/refs/test_library_store.py::test_redo_keeps_a_verified_result_byte_identical`, `loom/tests/unit/refs/test_library_regrade.py::test_drop_then_redo_keeps_the_authors_verified_text`

**Record.** DR-326-ikmartin, DR-331-ikmartin, DR-333-ikmartin

**2026-11-21.** `library update --redo` and `library drop` are gone with today's library (plan 0.32, the library's phase 2), and so are the guards named above. The rule's reason holds for the digest that writes over nodes a person may have checked (phase 3), and has no guard until then.

**2026-11-26.** One exception, the author's choice ("Okay i") on 2026-11-26: after the person's compile of a work's source, digest fills the display numbers that compile confirmed into the anchors a checked node holds waiting for them (`awaiting`), and changes no other byte of it, recorded `digested` how `numbered`; the person's `compared` on the text before holds on the text after (`evidence.md` §3.1). Why: without a compile loom keeps no display's number, so a node a person checked before compiling would otherwise wait for its numbers for good, or lose their check to get them, and a number confirmed by their own compile is nothing they read against the page. The act refuses any other change (`acts.only_numbers`), and nothing but the person's digest after their compile reaches it. Guards: `loom/tests/unit/library/test_digest.py::test_the_person_s_compile_numbers_a_compared_node_and_its_check_holds`, `::test_a_corrected_node_is_numbered_alike`, `::test_numbering_refuses_any_change_beyond_the_numbers`, `::test_no_agent_and_no_unasked_digest_reaches_numbering`.

### A paper outside the quilt is compiled from a clean copy

**Rule.** Importing a paper and extracting a cited work's source compile a scratch copy of the paper's directory without its build products (a `.bbl` stays only when there is no `.bib`). latexmk never runs in the paper's own directory.

**Why.** latexmk rewrites `.bbl` and `.fdb_latexmk` in its working directory even under `-outdir`. On the author's relative localization paper, an editor's leftovers made it run bibtex where the paper uses biber, the import refused a paper that compiles, and the run rewrote the author's own `.bbl`.

**Guard.** `loom/tests/unit/test_paper.py::test_import_leaves_the_paper_directory_and_no_scratch_behind`

**Record.** DR-186

**2026-11-21.** Extracting a cited work's source is gone with digests (plan 0.32, the library's phase 2); importing a paper is unchanged, and so is the guard.

## Rendering and the viewer

### A transcription is judged against the page itself

**Rule.** Where the author verifies a proposed result, the viewer shows the PDF page itself at the anchor, quotation marked, beside the rendering, and names the rendering's words the quotation lacks. The text layer is shown only as what the anchor check read.

**Why.** The text layer drops sub- and superscripts and keeps one `X` for a stack and its space. In the study three wrong renderings passed every text check, one moving a hypothesis from the space to the stack, and the author, editing against page text, twice deleted the paper's own words.

**Guard.** `arras/tests/e2e/review-views.e2e.ts::a transcription is judged against the page itself: the paper's page at the result's place, washed there, beside loom's copy, with the copy's words the page lacks named, and the page's text layer never shown`

**Record.** DR-179, DR-201

**2026-11-21.** The viewer's review of proposals is gone with today's library (plan 0.32, the library's phase 2), and so is the guard named above. The rule is the Library view's check of a node against its paper (`docs/specs/library-views.md`, `check`), built in its own change, and has no guard until then.

**2026-11-21.** The Library view's check holds it, on round six's fixture until the digest serves it (phase 3): the paper's page drawn at the result's place, beside loom's copy, with the words of the copy the page lacks named from the place's `lacks` (`library-views.md` §3.3). The guard above is its test. The rule is unchanged.

### A mark never splits a formula

**Rule.** An annotation's mark takes a formula whole or not at all: a quote inside a displayed formula marks the whole display, and no tag is ever placed inside `\(…\)`.

**Why.** A mark's tag inside `\(…\)` stopped MathJax reading the formula at all, and a quote that crossed markup fell back to a bar down its block's left edge, which read as punctuation in the text.

**Guard.** `loom/tests/unit/render/test_marks.py::test_a_quote_inside_a_formula_never_puts_a_tag_inside_it`, `loom/tests/unit/render/test_marks.py::test_a_quote_around_math_takes_the_formula_whole`

**Record.** DR-244-ikmartin

### A served quilt publishes what a cold build of the same files publishes

**Rule.** Whatever `loom serve` keeps from one build for the next, on disk or in memory, is looked up by everything it is made from, so after any sequence of saves, writes through the viewer and compiles the server's site is the one a build from cold makes of the same files. Most of what the server keeps in memory is in `scan/memo.py`'s memos: what a scan derives from a file's text, and what a build makes from its scan, each keyed by everything it is made from and let go once no build asks for it. Three things no key can name are guarded as well: a rendering made while TeX failed for the machine's sake (a run that stopped saying nothing, one out of time), or while a converter that can read a PDF here failed on a figure, is kept for no later build, as no cache on disk remembers such a failure (`render/uses.py`, `passing`), and a section draft's key names what decides whether a PDF figure converts here (`render/assets.converters`: `pdftocairo`, `dvisvgm`, `mutool`, and the Ghostscript `dvisvgm` is given), so a machine that cannot convert one keeps its draft until that changes; one whose cache files or pictures have gone from disk is made again; and a build after one in another process, a `--force` in a terminal among them, forgets everything first.

Two differences are known and allowed: the blank space two runs of TeX over one text may leave in a page, and a fragment a build with no TeX published as its source, which a later build with TeX keeps until `--force` (plan 0.32, the author's queue, 44 and 40). Three more are known, all older than this rule, and not yet mended or allowed: two runs of TeX over one text also differ by a space either side of a tag, a no-break space for a space, and a picture's name, which follows the order TeX drew its glyphs in; a Review preview's section number depends on what else TeX made in the same run; and a fragment outside a section draft made while no tool converted its figure keeps it unconverted until its text changes or a build is forced. A file `kpsewhich` found is believed while the file it named is there, and a name it did not find is asked about again at the first scan ten seconds or more after it was last asked (`scan/expand.py`, `AGAIN`), whatever way the file arrives: until then a server calls missing a file that has just arrived, which a cold build finds, and a server at rest scans nothing, so a file that arrives while nothing changes is called missing until the next save.

**Why.** A key that leaves out one input serves an old result with no error. A section's fragment key left out the text an included file holds after its node, so a save showed the section without the new words (2026-11-17), and the speed spike found keys without page numbers safe only for the commands it listed.

**Guard.** `loom/tests/unit/render/test_served_is_cold.py::test_a_server_after_saves_notes_an_acceptance_and_a_compile_publishes_what_a_cold_build_does`, and for each memo a test that changes each input alone: `loom/tests/unit/render/test_memos.py`, `loom/tests/unit/test_adopt.py::test_a_side_of_a_comparison_is_shaped_once_and_again_when_any_input_changes`, `loom/tests/unit/test_section_drafts.py::test_a_section_draft_is_rendered_once_and_again_when_any_input_changes`; for the three things no key names, the tests in `test_section_drafts.py` of a draft rendered while TeX failed for the machine's sake, with a figure no tool converted and after a converter arrived, after a forced build in another process, and with the site or the snippet cache removed, `loom/tests/unit/render/test_refused.py`, which says which failures are the machine's, and `loom/tests/unit/scan/test_memo.py::test_a_build_empties_every_memo_when_another_process_built_since`

**Record.** Plan 0.32, Speed's row; `docs/reports/v0.1-study/raw/spike-speed.md`, FAST-9 and FAST-10

### Every write to the viewer's server carries a token

**Rule.** `loom serve` refuses a POST unless it is `application/json`, carries the `X-Loom-Token` the server keeps outside the quilt and serves to the viewer, and names no Origin but this server. This is CSRF protection, not a login.

**Why.** No incident is recorded. A browser blocks a cross-origin response but never the request, so without the token any page the author had open could POST into the quilt and create, resolve or discard annotations.

**Guard.** `loom/tests/unit/render/test_write_api.py::test_a_write_without_the_token_is_refused_over_the_wire`, `loom/tests/unit/render/test_write_api.py::test_the_write_api_refuses_a_post_from_another_page`

**Record.** DR-203

**2026-11-17.** The token is kept in the machine's place, outside the quilt and keyed by its path (`loom/src/loom/machine.py`), no longer in `.loom/serve.json`, so a quilt committed or copied whole carries none (plan 0.32, decision 18). The rule is unchanged.

### A page the quilt holds never runs as the viewer

**Rule.** `loom serve` sends everything but the viewer's own bundle, which is every file under `/build/` and `/digests/storage/` and every JSON answer, with `Content-Security-Policy: sandbox` and `X-Content-Type-Options: nosniff`, so a page there runs no script and has an opaque origin. `GET /_api` gives the token only to a request that no browser says came from another page (`Origin`, `Sec-Fetch-Site`). Over the API, `review-accept` refuses a declared agent, like the author's other acts there (K5).

**Why.** Found 2026-10-30 by reading the code for the open-quilt study, and reproduced before it was fixed. An agent writes the build output, served at `/build/`, and an HTML or SVG page it left there ran as the viewer when the author opened it, for instance from a link in a transcript. The page read the token from `/_api` and posted a write naming no author, which the publisher takes for the author's own click; an acceptance posted that way was recorded as the author's. The token kept other sites out but not a page served from the viewer's own origin.

**Guard.** `loom/tests/unit/render/test_write_api.py::test_a_page_the_quilt_holds_is_served_with_no_origin_of_the_viewers`, `loom/tests/unit/render/test_write_api.py::test_the_token_is_served_only_to_the_viewers_own_origin`, `loom/tests/unit/render/test_write_api.py::test_each_endpoint_writes_and_refuses_over_the_wire` (`review-accept`), `loom/tests/unit/render/test_files_served.py::test_a_shown_file_is_served_sandboxed_on_the_viewers_origin`, `loom/tests/unit/render/test_files_served.py::test_an_html_page_runs_on_the_frames_origin_with_the_bridge_and_nothing_of_looms`, `arras/tests/e2e-write/origin.e2e.ts`, `arras/tests/e2e-write/files.e2e.ts`, `loom/tests/unit/test_raw_html.py`, `arras/tests/e2e/files.e2e.ts`

**Record.** `docs/reports/open-quilt-study.md`

**2026-11-02.** The project's shown files are served sandboxed on the viewer's origin too, at `/_files/`. An HTML file the viewer frames runs on a second loopback origin, the frames origin, where its scripts and embedded players work: that origin serves shown files and nothing of loom's, answers only its own host, and is refused by the write API like any other page, so a framed page still never runs as the viewer (plan 0.22.7).

**2026-11-04.** The frames origin also answers `/.loom/files.json`, the sorted paths of the shown files, because a page that had to hard-code file names silently missed new ones. It adds only names of what that origin already serves, and a framed page still cannot write (plan 0.27).

**2026-11-04.** A Markdown file may hold HTML, which the viewer draws in its own page rather than a frame so that links, mathematics and quoting keep working there. So the publisher writes that HTML back out through an allowlist with everything escaped, and a frame in it loads only an `https:` address, sandboxed, which is never the viewer's origin. A click on a `javascript:` address written with a space or a control character, which a formula's `\href` can carry, is now refused too.

**Open.** The rule above holds for what loom renders, not for what an agent edits after it. What loom derives, `.loom/cache/`, is not among an agent's places, so loom's commands and Claude Code refuse an agent an edit there; but the other apps leave that list to the agent, and the boundary is not a security boundary (`agents.md`). The viewer inserts a body or a manifest's `body_html` as it reads them, so one edited there directly runs as the viewer and can read the token (reproduced 2026-11-04 against a real `loom serve`, with a handler in a file's body under what was then `.loom/build/files/`, now `.loom/cache/site/files/`). A `Content-Security-Policy` on the viewer's own page that refuses inline script, or a viewer that filters what it inserts, would close it; document fragments reach the page the same way.

**2026-11-21.** `/digests/storage/` is gone with today's library (plan 0.32, the library's phase 2); a work's documents are served by hash at `/_api/library/pdf/<hex>` and `/_api/library/thumb/<hex>.png`, sandboxed as `/build/` is, which `test_a_page_the_quilt_holds_is_served_with_no_origin_of_the_viewers` holds, and `origin.e2e.ts` plants its page there, as a stored PDF, in place of `/digests/storage/`. The rule is unchanged.

### Loom opens only documents in their application

**Rule.** `POST /_api/open` opens an application by a plain name, or a shown file whose suffix is on `loom.files.OPENABLE` (notebooks, spreadsheets, office documents, Anki packages, audio, video, books) and that has no executable bit. Any other file, a hidden one, and a name that could be a path or an option are refused.

**Why.** An agent may write nearly anywhere in the quilt, so it can write a file and a link to it that the person clicks. A click that opened a script, a `.command` or an application bundle would run the agent's code as the person.

**Guard.** `loom/tests/unit/test_files.py::test_loom_opens_an_application_or_a_document_and_never_a_file_that_runs_code`, `loom/tests/unit/render/test_files_served.py::test_open_is_the_persons_click_and_never_runs_code`

**Record.** Plan 0.22.7

### Undo writes a person's file only on their act, with what it replaces kept first

**Rule.** `loom changes --discard` and the API's `change-discard` write a change's old words back into an open file only when the person asks, never an agent (K5), and store the file's text now in the history's texts before writing, with a ledger line naming the change. A file new since the look is removed the same way.

**Why.** Since plan 0.22.6 agents edit open files in place, and Review's Your Changes is where the person keeps or throws away what they did. An undo is loom writing a person's file, which P7 allows only on the person's act and only with the old text kept, so a wrong undo can itself be undone from the history.

**Guard.** `loom/tests/unit/test_pending.py::test_keeping_one_change_leaves_the_other_and_discarding_writes_it_back_with_a_version_kept`, `loom/tests/unit/test_pending.py::test_keeping_and_discarding_are_the_authors`, `loom/tests/unit/render/test_write_api.py::test_each_endpoint_writes_and_refuses_over_the_wire` (`change-discard`)

**Record.** Plan 0.22.8

**2026-11-12.** Edits in place wait in Your Changes only where the quilt tracks them, `[review] track_edits`, off by default (plan 0.31): the person was asked to keep edits they had just made themselves. Where a quilt does not track them there is no in-place change to discard; the rule holds where it does, and its guards run with tracking on.

**2026-11-21.** The look is always kept and `[review] track_edits` is gone (plan 0.32): an edit in place waits in Your Changes in every quilt, and its guards run as every quilt now does.

**2026-11-12.** Undo became Discard, per change cut by words rather than per hunk, and covers suggested edits too (plan 0.30, decision 11); what it writes and what it keeps first are unchanged.

### A note's fading is computed, never stored

**Rule.** Whether a note has faded is computed each time the manifest is published, from its age (more than 14 days), whether it is kept, and whether an annotation, a message, the research state or a kept note links to it. Nothing records that a note faded, and nothing deletes one.

**Why.** P3: a state stored is a state that goes stale. A note linked tomorrow must come back without anyone writing that it did.

**Guard.** None since 2026-11-11.

**Record.** Plan 0.22.8

**2026-11-11.** Retired with notes (plan 0.30, decision 1): a note is an annotation whose type is listed in Notes, and an annotation never fades. P3 still holds for what replaced it, since whether an annotation is open is computed from its type.

