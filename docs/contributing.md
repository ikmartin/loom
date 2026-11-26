# Contributing

For anyone, person or agent, changing loom or its viewer. What loom is and why lives in `docs/design/`; the viewer interface lives in `docs/specs/`, which wins on shapes; what is not done is in `docs/work-queue/README.md`.

## The repository

One repository: loom, and its viewer in a codebase of its own, each with its own build and tests; the viewer ships inside loom. A change that crosses them is one branch and one pull request.

| directory | what it holds |
|---|---|
| `loom/` | the CLI, Python, built with `uv` |
| `viewer/` | the viewer, Svelte, built with `npm` |
| `docs/` | the design, the specs, the work queue, the plans, frozen history |
| `demos/` | the committed example quilts, rebuilt by `demos/build.py` |
| `scripts/` | `verify`, `regen`, and the documentation checks `verify` runs (`scripts/checks/`) |

To set up: `uv tool install -e ./loom` puts this checkout's `loom` on your PATH; `uv sync` in `loom/` makes `loom/.venv`, which the viewer's write and reading suites serve with; `npm ci` and `npx playwright install chromium` in `viewer/`. A session in a worktree of its own does the `uv sync` and the `npm ci` there, so that what it tests is its own tree and not the main checkout's.

The workspace's documents and loom are GPL-3.0-or-later; the viewer AGPL-3.0-or-later; `loom.sty` and the demo quilt MIT (`loom/src/loom/assets/LICENSE`), so they can travel with a paper.

## Verifying

`scripts/verify` is the one verification command, and CI runs it and nothing else, one lane per workflow (`loom.yml`, `viewer.yml`, `docs.yml`). It ends by printing the branch's latest CI runs; read them.

- `scripts/verify` (`fast`): the everyday lane, while working. loom's ruff, format check, mypy and unit tier; the viewer's svelte-check and vitest; the work queue, principles, hard-wrap, words and machine-path checks. It judges only what the change did: nothing in it compares the working tree with git or a committed generated file with its generator, so a file not yet added, or a generated file left for whoever merges (see "Working in parallel"), does not fail it.
- `scripts/verify full`: before a commit. Adds the checks `fast` leaves out (loom's tests marked `tree`: the tracked-file guard, and every test that reads a committed generated file as it stands, which are the quilts, tool list and command reference against their generators, the generated quilts' expected lint and doctor on the demo; the fixture copies; the vendored bundle), loom's TeX tier, whether the pages the served suites read are what a fresh compile makes, a viewer build, the three Playwright suites and the figure script.
- `scripts/verify paper`: the paper tier, by hand, with `LOOM_PAPER_FIXTURES` naming a directory holding `0805.2065/` and `1709.09864/`. Never in CI.
- `scripts/verify client`: the real-client tier, by hand, after a change to what loom generates for an agent client. It runs Claude Code against the generated settings and spends on the account of whoever runs it, so it never runs in CI.
- `--only loom|viewer|docs`: one lane, when a change touches one codebase or only documents.
- `--steps "pytest tex"`: named steps whatever their tier; CI runs the TeX tier this way, and on `main` the `tree` tests.
- `--workers N`, or `VERIFY_WORKERS=N`: how many test workers the run may use in all. The machine is shared, so by default a run takes half the cores less the load already on it, and never fewer than two; loom's pytest and the Playwright suites divide what it takes. A Playwright suite started by hand reads the same variable.

The docs lane runs `docs/work-queue/check.py` and the checks in `scripts/checks/`, each runnable alone and printing the command that fixes what it finds.

## How the tests work

- loom's tests run loom through `loom/tests/helpers.py`, in process with exceptions let through, so a crash surfaces as a traceback. A test asserts one exit code (`ok`, `exits`, `refused`), never a set of them.
- The fake TeX toolchain (`loom/tests/fake_latex/fake_tex.py`) exists only in the directory `loom/tests/conftest.py` makes per session, never on the real PATH. Look up every external tool on PATH so a test can substitute it.
- Every LaTeX compile in a test runs isolated: empty HOME, TEXMFHOME, TEXMFLOCAL, TEXMFVAR and TEXMFCONFIG, no TEXINPUTS, the quilt root as cwd. A test never passes because of a file elsewhere on the machine.
- Fixture quilts are written from `loom/tests/quilts/sources/` by loom's own commands under a fixed clock (`uv run python scripts/gen_quilts.py all` in `loom/`, which `scripts/regen` runs with every other generator); `test_the_checked_in_quilt_is_what_the_generator_writes` compares them byte for byte. Never edit one by hand. The viewer's served suites run no TeX, so the pages TeX makes of the synthetic and showcase quilts' documents are kept in `viewer/tests/pages/` (`uv run python scripts/gen_pages.py` in `loom/`, which needs TeX Live); a change to those quilts' documents, to how loom configures TeX4ht, or to the code that makes a snippet (`tex/tex4ht.py`, `render/normalise.py` and `render/snippets.py`, whose code is in every snippet's name) makes them again, and a page left behind is read as edited since.
- `test_never_modifies_author_files` runs a fixed list of commands that read or record (lint, search, doctor, history, stamp and the like) on every fixture quilt and fails if an author file's hash changes; it runs none that writes a person's text. `test_write_safety.py` is the test of those: it runs sequences of suggestions, hand edits, Keep, Discard, ticks and settings through the write API and checks the person's files after every act.
- Every diagnostic code is in `docs/specs/diagnostics.md` before loom emits it, and some test emits it. `test_all_emitted_codes_are_known` checks only that the fixtures' codes are in loom's table, not that every code is emitted.
- CI sees only committed files, so `loom/tests/unit/test_tracked.py` fails on a shipped file under `loom/src`, `loom/tests/quilts` or `viewer/src` that is untracked or ignored. It is marked `tree`, so it runs in `full`, before a commit, and not while a new file is still being written.
- When loom's pytest runs beside the Playwright suites, `scripts/verify` gives it half the run's workers and splits the rest among the suites: left to themselves each takes every core, and together they starve the reading suite into timeouts.
- `scripts/verify` takes the first slot nothing on the machine holds, so its Playwright servers never meet another worktree's or a suite started by hand; `viewer/tests/sites.ts` says what a slot is. Suites started by hand run in slot 0, so two of them in two checkouts need `VIEWER_SLOT=N` on one.
- A test fails on what happened, never on how busy the machine is. Waits are bounded generously and end as soon as the thing happens (`PATIENCE` in `loom/tests/helpers.py`; `patient` in `viewer/tests/sites.ts`; `testTimeout` in `viewer/vite.config.ts`), so only a real failure spends them. A claim about speed is made structurally, by holding back what must not be waited for and asserting what still arrives (`noPolls` in `viewer/tests/polls.ts`), or timed by `scripts/bench`, never by a stopwatch inside a test; what a served quilt holds across saves is measured by `uv run python scripts/memory.py PATH` in `loom/`, on a copy. loom's tests run with `LOOM_PROGRESS=off`, since how long a command took decides whether it prints progress; a test of the progress line asks for it with the `progress` fixture.

## Construction

The construction principles C1–C5 (`docs/design/principles.md`) govern how the code is built:

- C1, the scanner before everything: nothing else can be tested without it.
- C2, vertical slices: work runs end to end, source to viewer page, not one layer at a time.
- C3, the fixture is the contract's executable form: a change to loom's output regenerates it (`docs/specs/tools/refresh-fixture.sh`); a change to the interface changes it first.
- C4, author files are sacred: the test comes before the command that touches a file.
- C5, one tool in two languages: loom and its viewer each have their own build and tests, the viewer ships inside loom, and `docs/specs/` changes with the code on either side.

## Working in parallel

Several branches are worked on at once, each in a worktree of its own, and one person merges them: the integrator, who is the author or a session he names. What follows keeps their merges from meeting in files nobody wrote.

- **A branch never commits a generated file.** The generated files are the ones `scripts/regen --list` prints: the test quilts with their agent permission files and expected lint, the demo `loom init --demo` writes, the copies under `demos/`, the list of the agent's tools, the command reference, the samples of Review's and the Web's reads and writes, the tables in the list of principles, the pages TeX makes for the viewer's served suites, and the conformance fixture with its two copies. A change that alters what a generator writes leaves the committed files stale on its branch, says so in its pull request, and is still green there: `scripts/verify` (`fast`) and CI on a branch run no check that compares a generated file with its generator.
- **The integrator regenerates after each merge**, with `scripts/regen`, and commits what it changed alone, as "Regenerate after …". `scripts/regen --check` writes nothing and says what is stale; CI runs the same comparisons on `main`.
- **A conflict in a generated path is never resolved by hand.** Take `main`'s side of every such path, finish the merge, and run `scripts/regen`.
- **The two steps that run TeX** (`pages`, `fixture`) print the TeX they ran, and `scripts/regen --no-tex` leaves them out. `pages` is due after a merge that changes the code of `loom/src/loom/tex/tex4ht.py`, `render/normalise.py` or `render/snippets.py` (a comment or a docstring is not code here), and after one that changes the synthetic or showcase quilt's documents: the name of each snippet kept beside the pages takes in the code of those three modules, so such a merge renames every one of them, and the viewer's served suites, which run no TeX, find none until they are regenerated. `scripts/regen --check pages` says whether they are current, and `scripts/verify full` runs it. The fixture is compared with a fresh build by CI's TeX tier, on CI's own TeX.
- **Merges that touch `loom/src/loom/render/`, `scan/` or `tex/` are batched**: each changes the hash every cached page is kept under, so each costs every quilt a full rebuild.
- **A branch does not vendor the viewer**, and neither does `scripts/regen`. The bundle loom ships is vendored at a release, and by CI on `main` (not built yet); until that is built the integrator vendors when `main` is to be used with a changed viewer. A change to the viewer is tried without vendoring (`viewer/CONTRIBUTING.md`).
- **Only the integrator edits the plan a branch works to.** A branch reports in its pull request: what landed, which checks it ran with their output, what it changed outside its own files, whether a regeneration is due, and what it needs decided.

To try a generator's change on a branch, run `scripts/regen` there and leave what it writes uncommitted; `git checkout -- $(scripts/regen --list)` puts the committed files back.

## Where a new thing goes

Each of these has a place of its own, so that two changes made at once do not touch the same lines.

- **An endpoint of the write API** is a handler in its family's module under `loom/src/loom/render/endpoints/` and an entry in that module's `HANDLERS` (and in its `READS`, `NO_REBUILD` or `RECORD_WRITES` where it is one); a case in `loom/tests/unit/render/write_api/cases_<family>.py`; and a row in `docs/specs/write-api.md`. `render/api.py` gathers the families and is not edited for an endpoint of a family it lists. A new family, an endpoint prefix of its own (`web-` is one), is the one change that edits it: its module joins `FAMILIES`, its cases module joins the imports of `loom/tests/unit/render/test_write_api.py`, and its prefix is named in `docs/specs/reserved.md`.
- **An endpoint of the home server** (`loom app`) is a handler in `loom/src/loom/app/server.py`'s `HANDLERS`, a test under `loom/tests/unit/app/`, and a row in `docs/specs/write-api.md` §7.
- **A part of the manifest** is a function in `ATTACH` (`loom/src/loom/render/attach.py`), given the scan, the records, the renderer and the manifest being made. `build()` is not edited.
- **A sentence the viewer says** (a label, a hover card, a tooltip, an empty state, a confirmation, an error line) is an entry in `viewer/src/lib/words/`, in the file of the view that shows it or `frame.ts`, named for the place it shows, with a one-line comment saying where; a component holds none. `scripts/checks/words.py` fails on words in a component's markup, attributes a person sees or hears and string literals in its expressions, handlers, actions and block tags among them, unless the component is on that check's list of those that predate the folder, which only shrinks; it does not read a string in `<script>` used by name, a string in a `.ts` module outside `words/`, a prop other than `label`, other attributes' expressions, a lone lower-case word where it cannot be the value shown, or CSS (its docstring lists these exactly), so those are held by review.
- **What was just done**, a work added, a place marked, a work deleted, is said in the column's message: `message.post(text, undo?)` from `viewer/src/lib/shell/message.svelte.ts`, which the column's foot draws with `undo` where the act can be taken back. `review/Toast.svelte` is today's older way of saying the same, kept where it is used until those surfaces move.
- **A hover card** on a control, as on the view names, is `use:hovercard={{ text, place }}` from `viewer/src/lib/shell/hovercards.svelte.ts`, its words from `words/`; the card shows after the column's delay and is the control's description.
- **A result's status** is drawn by `viewer/src/lib/marks/Mark.svelte`, the one vocabulary of round six's marks, on every surface; `marks/marks.ts` maps the status a read passes on (`docs/specs/evidence.md` §5) to its mark.
- **A read or write of the library's views** (`docs/specs/library-views.md`) is a function in `viewer/src/lib/library/api.ts`, its shapes in `library/types.ts`; until the publisher serves it, round six's fixture answers it (`library/fixtures/`, chosen with `?fixture=round6`), and a view reads through `library/read.svelte.ts`, asking again when the library's generation moves.
- **Review** is `viewer/src/lib/views/review/` with its column in `shell/column/review/`, drawn wherever the source serves `review-list` (the fixture does); where the publisher does not yet, `/review` and the column are today's Your Changes (`review/YourChanges.svelte`) and sections (`ReviewNav`), which go when the evidence lane serves Review's reads. A row's words and marks are `views/review/rows.ts`'s, held by its unit tests.
- **The Web** is `viewer/src/lib/views/web/` with its column in `shell/column/web/`, drawn wherever the source serves `web-list` (the fixture does); where the publisher does not yet, `/web` says so, and today's graph (`/graph`, `lib/graph/`) stands until the Web's reads are served, when it goes. A text a view draws from a fragment is `views/Statement.svelte`, Review's and the Web's.
- **Docs' additions** are `viewer/src/lib/views/docs/` (the picker, a citation's card, the Lean marks) and `lib/formalize/` (the formalize panel, drawn over Docs or the Web by the frame), with two pane items of their own in `workspace/items/`: `ReadingItem` (a work of the library beside a draft, `/reading/<ref>`) and `NotesItem` (All notes, `/notes`). The Library button stands where the library's reads are served; the Lean marks and the panel draw nothing until `formal-marks` says formalization is on.
- **Something the viewer's column draws** is in the child that draws it, under `viewer/src/lib/shell/column/`: the files' shelf, the list of documents, Review's sections, the foot. `Column.svelte` is the frame they stand in. What a child must remember while it is off screen (a shelf open, a filter typed) is kept in a module beside it, since the column takes its children down when it folds. A file dropped on the window is `viewer/src/lib/components/DropZone.svelte`'s to take in.

## Rules for every change

- Never edit anything under `~/notes/`. Paper sources, the author's included, are copies under the workspace's gitignored `tests/fixtures/`, never committed, and neither are the quilts `demos/build.py` builds from them.
- Prose is never hard-wrapped: one line per paragraph, in Markdown, docstrings and comments. `scripts/checks/hardwrap.py` enforces it on added lines.
- The repository is public, so nothing committed names a person's machine or holds a secret: no home folder, per-user temporary folder, email address or token, in text or in a binary. Write `~/…`, `/Users/someone/…` or `<scratch>/…` instead. `scripts/checks/machine_paths.py` enforces it on every file git would commit; its `PENDING` list holds the files the author has yet to decide on, and only shrinks.
- Docstrings follow `CLAUDE.md`'s two styles and describe the current state only; review documentation with its ten passes.
- A path loom uses inside a quilt is named once, in `loom/src/loom/paths.py`; `loom/tests/unit/test_paths.py` refuses one spelled out anywhere else.

## How the documents change

The design is still being discovered, and the previous system failed by treating it as a fixed specification. `docs/design/` records current thinking, not a contract. When implementation teaches you something, update the design document in the same change and explain why in the commit message. Open questions belong in the design document beside what they affect; the work queue holds deferred work, not design questions. Only an entry in `docs/design/invariants.md` changes deliberately, with a dated line there.

Every commit message explains the why of its change. `docs/design/decision-records-frozen.md` is frozen history: read it, never extend it.

The work queue, whose mechanical rules `docs/work-queue/check.py` enforces:

- An item is a row in the queue's README and a `WQ-NN-<slug>.md` beside it, with an observable trigger (a measurement crossing a threshold, a capability existing, a dependency landing); its "why deferred" is that trigger inverted.
- The cap is 45 active items; a forty-sixth means promoting, merging or dropping one.
- An item closes by deleting its file and row and adding one line to `closed.md`. Ids are never reused.

## Releases

`loom/docs/RELEASE.md` is loom's release checklist; follow it, not a summary. It stops before publishing: publishing to PyPI is the maintainer's step, never a script's or an agent's. The viewer is not published on its own; it ships as the bundle vendored into loom (`loom/scripts/vendor_viewer.py`).
