# Loom

Loom is a local application for mathematical research: a person reads, annotates and decides in its viewer, arras, and their own AI agent works beside them through loom's commands. This directory is their design: what they are for, the principles they follow, the model they share, how agents take part, and the invariants that must not be lost. It replaces the design book, whose decision records are frozen in [`decision-records-frozen.md`](decision-records-frozen.md); the book itself is deleted, and git history keeps it.

## What loom is for

Mathematicians do not finally care whether a theorem is true so much as understand why it is. Loom is a tool for building that understanding at every stage of research, from learning a field to submitting a paper, and it uses AI to deepen it. It treats mathematics as a graph of addressable statements: your drafts, the papers and books you read, and the questions you are working on. Anything a person or an AI says about that mathematics attaches to the statement it concerns and can be found from there, so that the connections in your head have a counterpart you can follow.

Most of research is provisional, and loom lets it stay that way. As in a Zettelkasten, conversations and half-formed ideas are fleeting notes: one gesture to leave, asking nothing of anyone afterwards, so forgetting one costs nothing. What proves worth keeping is distilled into durable notes, about the literature or in your own words, that are atomic, linked, and found from the mathematics they concern.

AI-written mathematics and documents are welcome in loom and will be a large part of research. Loom's part is a clear boundary around what an AI may change, so that the person keeps control of their own text and of how they work. Loom calls no model and stays useful with none present; it is built to be excellent with one, from any provider, including local models (P9). It assumes as little as possible about who you are, what stage you are at, or whether you have a draft or a problem at all. And it never lets a claim that nobody has checked look checked.

A person uses loom as an application: they launch it, open a quilt or start one, drag in papers and drafts, and read, annotate and decide in the viewer. They need no command line, and loom is not a text editor: they write in their own editor, or on Overleaf. An agent uses loom through its commands, in a shell or over MCP. The viewer's controls, the commands and the MCP tools are surfaces over one set of operations. Much of this is [not built yet](#decided-not-yet-built): today a person still starts loom, makes a quilt and sets up an agent from a terminal.

## Three people

Every design decision is tested against three people. A feature that serves none of them does not belong; one that serves one and costs another needs a reason.

**The Learner** is a graduate student reading literature openly, with no draft and no research question. They need to read papers and books through loom, see how results in different works relate, ask an AI to clarify a concept or build an example of a definition, and keep what they learn attached to the statement it is about. Today loom gives them a library of the works they add, each with the PDF and TeX source they hold, annotations on a page of a work, and their own files (Markdown, HTML, notebooks, PDFs) in the project's tree, opened on a front door they name. The rest is not built yet: the Library view, a quilt that is a library rather than a paper, results read from a work, and notes attached to any result.

**The Explorer** is a researcher with a concrete question, working examples and trying proofs. They need to record attempts, claims and dead ends against the question, find out quickly whether something is known, see which steps are still open, and turn an attempt that works into a statement. Today loom gives them nodes, `\incomplete` steps, the graph and agent documents to draft in. A problem page that remembers what was tried is not built yet.

**The Author** has a draft and is proofreading, expanding and checking it before submission. They need review that lands on the text, their own annotations as a working list, an audit of every dependency and citation, acceptance that goes stale when anything underneath changes, and a record of what was submitted. Loom serves the Author well today; this is where it began.

## Judging a change

Before building something, answer three questions:

1. **What friction does it add, for which of the three people, and what does it buy them at that moment?** A step that buys nothing is removed, defaulted or never introduced (P14).
2. **Could it let something unchecked look checked?** Whether a claim has been checked, and by whom, must stay visible (P15).
3. **Does it work with no AI present, and with any AI?** Loom calls no model, and no vendor is assumed (P8, P9).

These are warning signs. Each is a reason to think again, not an automatic veto:

- it needs syntax beyond `\uses`, `\incomplete` and `\nest`;
- it asks for configuration where the preamble already says the answer;
- it writes to an author's file outside an incorporation the author chose (P7);
- it creates a second source of truth, or stores a state that could be computed (P3);
- it makes a person type a command for something a control could do, or makes an agent need the viewer for something a command could do;
- it only makes sense with a model in the loop, or needs an API key;
- it names a directory for a property loom can compute;
- it reinvents something LaTeX already has.

## How this design changes

The design is still being discovered, and this directory records current thinking, not a contract. When building something teaches you that the design is wrong, change the design in the same change and say why in the commit message. Three things differ in how they change:

- **Invariants** (`invariants.md`) change deliberately. Each records a failure that happened; changing one adds a dated line to its entry saying what changed and why.
- **Principles** (`principles.md`) change by editing them, with the reason in the commit message. A principle's name is permanent: a retired principle keeps its heading, marked retired, so that citations still resolve.
- **Everything else** is current thinking. Edit it as you learn.

Two markers keep the text honest:

- A paragraph that begins **Open.** states a question that is not decided, beside the design it affects. The work queue (`docs/work-queue/`) holds deferred work, each item with a trigger; it does not hold design questions.
- **(not built yet)** marks something decided and not yet implemented, and links to the list below. Nothing unbuilt may read as built.

## Decided, not yet built

- **Loom as an application.** Installing with one line is built: `scripts/install.sh` installs loom with its own TeX of one TeX Live year and its own Ghostscript and poppler, which every program loom starts finds first, and a paper that does not typeset still comes in; it then writes Loom in `~/Applications` (Loom Quilts where another app is called Loom), which opens loom's home page. The home page's server is built (`loom app`, `specs/write-api.md` §7): it lists the quilts on this machine, serves each on a port it keeps for good, starts again what the person left open, restarts each after an update, and makes a new quilt that opens on a paper dropped there. Not built: the home page and its drop window in the viewer, which wait for the author's look; connecting an agent from the viewer and seeing that it is connected; and no step that makes a person type a command. See `docs/plans/0.32-v0.1.md`, which also holds what is recommended and not yet decided.
- **Annotating PDFs and reviewing changes as plan 0.30 settled them.** Annotating documents is built: the toolbar and its one popup, the Comments and Notes lists, Quote, Settings › Annotations, and an annotation opening the version it was written on. Not built: the same toolbar on a PDF page, a mark found again on a changed PDF and a crop of it for an agent (0.30.2), and changes reviewed in the document (0.30.3). See `model.md` and `docs/plans/0.30-annotations.md`.
- **Open problems as nodes,** with the attempts, claims and dead ends about them attached as notes.
- **A reader-first library.** Works that are read but not cited are first-class, and nothing the library shows assumes a draft. A work added by hand is a reference like any gathered one; the views that show works wait on the Library view. See `model.md`, "The library".
- **The viewer's four views.** The frame is built: Docs, Library, Web and Review in the column, each with its hover card, as the mock-up's sixth round has them (`mockups/library-round-6/`). The Library view is drawn (the list of works, a work's tab with its outline, the one reader with its digest marks, a result beside its page, the drop of a paper) against that round's fixture, since none of the reads it makes (`docs/specs/library-views.md`) is served yet; the Web, Review's new lists and Docs' picker, notes tab and formalize panel are not built.
- **The library as a web of results.** The library rebuilt as one store of nodes, a file each: statements, proofs, works and their macros, joined by a small closed set of edges, with evidence in records and formalization on top. Built so far: the node file, its checks, the index, the tag log, the references and macros nodes made from the works a quilt holds, the intake that adds a work, the carry-over of an earlier loom's library, the survey of a work's TeX source confirmed by its stored PDF, digest, which writes a work's results as statements and proofs, the stubs the drafts' citations make, the reads the Library's views draw from (`loom/src/loom/library/`), and an agent's commands on the web, `loom library node`, `search`, `uses`, `rests-on`, `stubs`, `work`, `fill`, `propose`, `correct` and `digest`, each an MCP tool. See [`library.md`](library.md) and `docs/specs/nodes.md`.
- **The viewer's words in one place.** Decided with the author on 2026-11-20, so that he can change by hand what the viewer says and know where to look. Every sentence the viewer says (a hover card, a tooltip, an empty state, a legend, a confirmation, an error line) is written in `arras/src/lib/words/`, a file for each view (`docs.ts`, `library.ts`, `review.ts`, `web.ts`) and one for the frame (`frame.ts`); a component holds none. An entry is named for the place it shows (`views.docs.hover`), carries a comment saying where that is, and is written on one line, so the words seen on screen are found by searching for them. They are TypeScript, so a missing entry fails the build. The folder and its check, `scripts/checks/words.py`, are built, with the frame's words first. The check fails on words in a component's markup: text, the words of an attribute a person sees or hears (`title`, `aria-label` and the like), a string literal that reads as words inside an expression there or in an event handler, an action (`use:hovercard`), `data-tip` or a block tag, and, where it can be the value shown, a lone lower-case word; a value tested (`=== 'Escape'`) is never words. It does not read a string in `<script>` used by name, a string in a `.ts` module outside `words/`, a component's prop other than `label`, any other attribute's expression, a lone lower-case word where it cannot be the value shown, or words in CSS, which review holds instead; the check's own docstring lists these exactly. It reads every component but those on its list of the ones that predate the folder, which only shrinks, as the check holds against its base: a base that names no commit fails, and one that holds no list is said rather than passed over. An older surface moves when it is next changed. Not built: a like place for the sentences loom's Python makes (a problem's wording, why a note is on no block).
- **Later:** running code to test claims (not in the next weeks).

## Where things live

| what | where |
|---|---|
| this design | `docs/design/`: this file, `principles.md`, `model.md`, `agents.md`, `invariants.md`, `writes.md`, `library.md` |
| how loom writes a person's file: the lock, the journal, recovery | `docs/design/writes.md` |
| formats: the loom–arras interface, the source contract, the library's nodes, diagnostics | `docs/specs/` |
| commands and their options | `loom <command> --help`, generated into `loom/docs/cli-reference.md` |
| what an agent is given | `loom/src/loom/assets/ai/` (orientation, rules, modes) |
| building, testing, verifying, releasing | `docs/contributing.md` |
| deferred work | `docs/work-queue/` |
| history: the old book's decision records, plans, reports | `docs/design/decision-records-frozen.md`, `docs/plans/`, `docs/reports/` |

Where the design and a spec disagree about a shape, the spec wins; about what a thing means, the design wins. Where either disagrees with the code, one of them is wrong, and the fix is to correct whichever it is.
