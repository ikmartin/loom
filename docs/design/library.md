# The library as a web of results

**Decided with the author on 2026-11-20 and not built yet** (see [README](README.md#decided-not-yet-built)). This document is the design of the library as it is to be rebuilt: what it is for, what a node is, how nodes are joined, how evidence about them is kept, and how formalization stands on it. The shape of the files is [`docs/specs/nodes.md`](../specs/nodes.md), which wins over this document about a shape, as this one wins about what a thing means. Until it is built, the library section of [`model.md`](model.md#the-library) and `docs/specs/digests.md` describe what loom does.

## What it is for

A quilt grows as its author works. References accrue, each brings results the author uses, compares and builds on, and with digests and Lean those results can be joined into a slowly growing web of mathematics. The library is where that web is kept: in the author's words, "a literal library organized as a graph rather than in stacks of shelves", which shows what rests on what and what has been formally verified.

There are two ways of looking at one body of nodes. **By work**: the papers and books, as a reference manager lists them, each with the results read from it. **By dependency**: a result, what it uses, and what uses it. Neither is a second store; they are two indexes of the same nodes.

Two uses decide the design.

- **First, and built for the pilot: an author formalizes a draft.** The author gives loom a draft. Loom digests the results of other works that the draft depends on, and nothing more. The author's agent then formalizes the draft in Lean with those outside results assumed, so that no effort goes into proving mathematics that is already published.
- **Later: a publisher keeps a web of what it holds.** An open publisher digests each paper it receives into one growing web, of the size of the Stacks project. A submitter who used loom hands over their digests, so the publisher need only run the Lean again. Nothing is built for this now. What it needs later should be additions, almost without exception: the core of the library, which is the node, its edges and its evidence, should not have to change for it.

Two words are kept apart throughout. **To digest** is to make a node from mathematics in paper form, a TeX source or a PDF. It is not to formalize: a digested node says nothing in Lean. **To formalize** is to state a node in Lean and, for the author's own results, to prove it. Works in the library are digested, and almost never proved.

The library is a home for stable works. A draft is not in it; see [below](#a-draft-is-not-in-the-library).

## Nodes

Everything in the library is a **node**: one file, named by its id, with a small typed header and one text as its body. One mechanism serves every kind (P4).

- **A statement**: a theorem, a lemma, a definition, an example, a convention. Its taxon says which, and the set of taxa is open. Its body is the statement.
- **A proof**: a node of its own, a child of the statement it proves. A statement may have several, since two papers prove one lemma differently and an author may add an argument of their own. Read from a TeX source its body is the proof as written; read from a PDF it may be a pointer, the pages and no text, until someone asks for it to be transcribed.
- **A reference**: a work. Its body is the work's BibTeX entry as the author's bibliography has it. Each version of a paper, the preprint and the journal's, is a reference of its own, as a bibliography already treats them; that two references are one paper is a relation recorded later, like any other.
- **A macros node**: the definitions a work's results are typeset with, one for each work that needs one, taken whole from the work's source the first time it is digested; a definition nothing uses costs nothing, and nobody has to ask later whether one is already there. They are kept apart from every other work's because two papers define the same command differently, and a web of many papers cannot share one preamble. Forester does the same: a tree of definitions that other trees import.
- **A stub**: a statement known to exist at a place in a work whose text has not been read. A draft that cites Lemma 2.1 of a paper nobody has digested still depends on a node, and the web shows it as known and not yet read.

**The id** is opaque and permanent. It is minted once, it is not reused, and it is not made from a citekey, a printed number or a position, each of which changes. A suffix says what a node is when it is not a statement: `tq-00A1-ref` is a work, `tq-00A1-macros` its macros, `tq-00K3-proof00` a proof of `tq-00K3`. A proof's number is given once and not renumbered, so removing the first proof does not rename the second, and a proof does not move to another statement. Parts of a node, the (i) and (ii) of a lemma, have no ids.

**The file says what the source says, and nothing else.** It is the reading of one place in one work: what kind of thing stands there, its number and name, its text, and what that text points at. It does not hold Lean, since Lean does not compile alone and every step of formalization would then edit a file a person had already checked against the paper. It does not hold a status, since a status written in a file is one anybody could set (P3, P15). It does not hold who digested it or how, which is the record of an act. And it does not hold what loom can find again: the order of a work's nodes and the exact place of each on a page.

**The body is the content only, in LaTeX** (P1). It has no `\begin{lemma}`: the taxon, the number and the name are in the header, and loom supplies the heading when it typesets. So a body needs its paper's macros and not its paper's theorem environments. A body points at other nodes by their ids, `\ref{tq-00A4}` and not `\ref{def:widget}`, so that a node read alone or carried into another quilt still points at something, and two papers that both say `lem:main` do not collide. The source's own label is kept in the header.

**Why this format.** The files are written and read by loom, seldom by hand, so the header is typed and validated, and the body is the text exactly, with no quoting. A LaTeX file with its header in comments cannot hold a list. JSON puts the LaTeX on one escaped line, so any change rewrites the whole body in a diff. Forester's own format was considered and its design is what this takes: an opaque address, one node a file, a small header, everything a node, views computed from links. Its body is its own markup, into which LaTeX goes as a picture, where loom needs words a note can be anchored to; it has no kinds of edge, no evidence and no way to keep two authors' addresses apart; and as a dependency it is another toolchain beside TeX.

**Open.** P5 says the graph is defined by labels and environments, never by paths. It was written of an author's sources, where nothing may be inferred from where a file sits. A library node's id is its file's name by construction, which is a statement and not an inference; P5 takes a sentence saying so when this is built.

**Open.** A node with no source, something stated in the quilt and read from no work, is specified only as far as a list of authors. What it is for, and whether a note that became durable is one, belongs with the notes beyond annotations in [`model.md`](model.md#notes).

## A draft is not in the library

A draft changes daily, and the library is for what is stable. So a draft's results are read live from the draft, as loom reads them today, and are not copied into node files. They are not shown in the Library. Where a draft's results and the library's are seen together is the Web ([below](#the-views)), in which a draft's result has the shape of a node, the draft as its source, and no file. When a paper is finished and the author gives its source to the library on purpose, it is digested like any other work.

A draft's result still needs a name that lasts, because a Lean declaration and the author's attestation point at it. That name is its label in the source. This is the question anchoring calls label keys, and the answer here is yes.

A draft's edges into the library come from what it cites. `\cite[Lemma 2.1]{Jon19}` in a proof is a use of one result of one work; if that result has no node yet it gets a stub. This is how the library grows by loom's own hand: only what a draft depends on, one step out (P14). Everything further is the author's choice, made in the Library view: digest this paper, read this result, check this transcription.

A label names its result across the whole quilt, not in one file, so a draft copied to a new file keeps what was said of the results it did not change (decided with the author, 2026-11-20).

A statement of a draft with no label has no lasting name. Anchoring finds it again by the text beside it, and loom writes no label for it (decided with the author, 2026-11-20): where an act needs the name, as asking to formalize a result does, loom says that the result needs a label first, and the author adds it to his source by hand.

## Digesting and checking

Loom calls no model (P9), so three hands digest, and each can do different things.

- **Loom alone** does what is certain: a reference for each entry of a bibliography, a stub for each cited result, and the statements of a work whose TeX source it holds, extracted exactly. By its own hand it digests only what a draft depends on. It fetches a paper's TeX source itself where the entry names an arXiv number, and the network is allowed unless the person turns it off (the author, 2026-11-20), since exact extraction is the fast and trustworthy way and how often it is open decides how much is left to agents.
- **An agent**, asked, does what needs reading: transcribing a statement from the pages of a PDF, which loom checks is on the page it names, and working out which result a citation with no number relies on. An agent can also find a fault in a digest loom made, and propose a node or a correction from a work's source.
- **The person** chooses what is digested beyond the least, checks a node against its paper, and attests.

**From a PDF alone loom digests nothing and marks nothing by guess** (the author, 2026-11-20). Its reading of a PDF is as likely wrong as right, and a wrong mark costs a person more than no mark. With only a PDF, what stands on the page is what is known: the nodes that exist and the places the person marked. Loom's one guess is where it already is: when a person asks to locate a result, the paper opens at loom's best guess and the person places it. With the TeX source loom knows every result exactly, and can show the ones not yet digested.

**The person's tools are in the Library.** A work is digested by a scope: what my documents use, what I marked, or the whole work; the list of works offers the same for all of them. On a paper, a **digest overlay**, switched on from the view menu and off by default, marks which results are digested and checked, digested and not checked, stubs, and marked for digestion; a mark opens its node beside the page, and the person marks a place to have it digested. Where a work has only a PDF, digesting it is a task for an agent (below).

**Checking is the approval, and it does not gate a node's existence.** A node an agent or loom made exists and reads as not checked (P15). What is gated is what rests on it: nothing is attested on a node nobody checked, and a result that assumes such a node in Lean does not read formalized until the node is checked and its Lean statement attested. The work is not held back: an agent may be asked to formalize a result that rests on an unread or unchecked one, and the request says what will keep the result from reading formalized. One thing stops a request, a result with no label, which the author adds by hand (the integrator's ruling with the mock-up's sixth round, 2026-11-21, put to the author and not objected to). A correction proposed to a node the person already checked waits as a proposal, and the checked text stands until it is taken.

**The check shows the node and the paper in one place**: the paper at the node's place beside the node, which the person switches between rendered and plain, since only the plain text shows its macros and the ids it points at. So every node is made with its place recorded; a node whose place is unknown cannot be checked quickly. Three things keep the queue of checks usable if agents fill it: what a draft rests on comes first; checks are grouped by work, one row for a paper and not forty; and a node extracted from TeX source says so, since loom can confirm that mechanically and it needs a glance where a transcription from pages needs a reading.

**Agent tasks.** Some work is an agent's by nature, and a person asks for it when no agent is there. What was asked waits in **agent tasks**: digest this work, read these stubs, answer this question on a passage. It is a stack an agent may take from, not a harness: nothing is assigned, ranked or scheduled. An agent that attaches is told what is open; one launched to work through the tasks does so, and one launched for something else need not, though it may offer. A task is tied to a place, shows when a session is working on it, closes by what it produces, and is withdrawn by deleting it. Most of it is computed from records, the stubs asked to be read and the questions not yet answered, and only the asking is recorded (P3). A question a person addresses to an agent is a task; a question to themselves or a coauthor is not.

**What an agent can do to the web** is a small set of commands, the same in a shell and over MCP. To read: a node with its neighbours, what a node uses and what uses it, a search by work, taxon, number, text or tag, what a draft rests on, and the stubs. To write: fill a stub, propose a node at a place, propose a correction, and mark a reference as a mention. An agent writes no node file by hand, and loom checks each write.

**Tags** (the author, 2026-11-20). A tag is a record about a node, said by someone, and not part of its file, so that tagging changes no node's hash. Tags are kept as a log under the quilt's records, one line for each tag put on a node or taken off it, with who and when, as annotations are, and a node's tags are computed from it. They are free words, made lower-case when written, and the ones in use are offered before a new one is coined; a person takes off any tag, an agent only its own. A search reads them from the index loom derives, which is rebuilt from the files and the logs at will and kept up in the background, together with the words of a statement, its taxon, number, work and standing, and what it uses. A work's subject is read from its bibliography entry, and the results that use one definition are found by that edge, so neither needs a tag. Tags are for what neither gives: what an agent learned as it read, and a person's own order. They are not on the pilot's first path.

## Edges

An edge runs from one node to another and has a kind. The vocabulary is small and closed, and each word means one thing.

**Three are written in a node's file, because the source says so.**

- **source**: this node's text was read from that work.
- **uses**: this node's text invokes that node. In a statement, the other node is needed to say what the statement means: a definition, a notation, a convention. In a proof, the argument rests on it.
- **mentions**: this node's text points at that node without resting on it: "see also", "compare".

To these is added **parentage**, read from the id and written nowhere: a proof is of its statement, and a macros node is of its work.

A dependency is written on the node whose text makes it. A proposition depends on a lemma through its proof, and a statement with two proofs may rest on different things by each, so the proof lists what the argument uses and the statement lists what the statement needs. What a proposition depends on is a question asked of both. There is no edge for containment: reading a work opens its PDF, and the order of a work's nodes is where each stands in it.

**Three are written in records, because someone asserts them**: that two nodes are the **same** result, that one **generalises** another, that two **contradict**. Loom has these today as relations, each with who said it and why. Nothing is merged silently, and nothing detects that two nodes are one; that is a later piece, and these words are kept for it.

**Four are read from Lean by loom and written by nobody**: a declaration **states** a node, or part of one; a declaration **supports** a node, serving its proof without being a node; a node is **assumed**, stated as an axiom with no proof behind it; and one declaration **depends** on another.

What is true of a node is kept apart from the kinds of edge. "Depends on something unproved" is an edge and a fact about its far end, and is found by a question, not stored as a kind.

**Open.** A `\ref` in a proof does not say whether it is a use or a mention. Digest reads it as a use and marks a plain comparison as a mention; that is a reading of the text, as the taxon is, and checking a node against its source covers it. Whether a mechanical digest may mark a mention at all, or only an agent and a person, is not decided.

## Evidence

Nothing about a node's standing is stored as a verdict. It is computed from records of what someone did, each naming the node's text by its hash, so that a change to the text makes what was said of the old text stale (P3, P15).

- **Digested**: by whom, from what, and how, mechanically from TeX or by an agent from pages.
- **Transcription verified**: a person compared the node with its place in the source and found it faithful. This says nothing about the mathematics.
- **Lean observed**: loom ran the check itself, and records what it ran, on which versions of the node and of the Lean project, and what Lean said: the declarations, the axioms each used, the kernel's replay.
- **Attested**: a person says the Lean statement means what the node says.

So a node is known in three ways that are not confused with one another: by the literature, where it is published; by the person, who has read it, accepted it, or attested to it; and by the machine.

**An attestation holds for a statement together with everything it uses.** Take a definition, "a widget is a compact set with property P", and a proposition that uses it, "every widget is bounded". The author attests that a Lean theorem says what the proposition says. If the definition is later corrected to "a closed set with property P", the proposition's own words have not changed and it now claims something else. So an attestation names the statement and every node its statement uses, and what those use in turn, and goes stale when any of them changes. Notation that a work's macros typeset and no node defines has a row of its own in what is attested, and attesting does not wait for it to be digested.

## Formalization

**Stating and proving are two things.** The author's own results are stated in Lean and proved. A result of the library that a draft rests on is stated in Lean and not proved: it is **assumed**. An assumed statement still has to be written in Lean, which means its definitions have to be, and a wrongly stated assumption makes whatever is proved from it worthless; so it is attested like any other. Lean reports exactly which assumptions each theorem used, and loom reads the honest claim off that report: this theorem is verified relative to these results. Where Mathlib already has a result, a declaration in the quilt's own project states the node and its proof is one line.

**There are two webs, and one is a contraction of the other.** Lean works in finer pieces than a person does: in loom's trial of one proposition, loom's graph supplied about a third of the nodes and a fifth of the edges of the Lean development. So Lean's graph is not copied into the library. Each node is stated by one or more declarations, together, with no ids for the parts; auxiliary declarations support a node and are not nodes; and Mathlib is the ground everything stands on. A declaration names its node by a marker in the Lean source, as Mathlib tags declarations with Stacks project tags, and loom reads the markers when it runs the check.

This lets loom compare the two webs. A use the paper claims and Lean did not need, or a dependency Lean used that the paper never mentions, is worth showing the author.

The Lean lives in the quilt's Lean project and not in a node. In the Library a node's page shows them together: the statement, the paper open at its place, the Lean statement as Lean prints it, and the evidence.

Loom runs the check itself, fenced, so that "Lean accepted this" is something loom saw (decisions 10 and 16 of `docs/plans/0.32-v0.1.md`; `docs/reports/v0.1-study/raw/fence-trial.md`). The formalization skills need not be used as they are: the library becomes their record of what depends on what and of which statements are fixed, which in the trial were separate files that broke the quilt. Their audit of a statement against its source and their search of Mathlib before proving are kept.

**Open.** What a person is shown between "an agent proposes this formalization" and "formalized": whether a node reads "Lean accepted, not attested", and what a result reads when its proof rests on one not yet proved.

## The views

Four views, each for one kind of work, as the author set them on 2026-11-20 after the first mock-up.

- **Docs** is for drafting and editing. A work still opens beside a document there: the library is a control that opens a compact picker over the view, a list or thumbnails sorted by author or by title, and all notes is a control that opens their page as a tab.
- **The Library** is for works: the list of them, as a reference manager has it, the digestion of each managed work by work, and reading. It has its own tabs, the list of works the leftmost, and a work opens in a tab there. It repeats some of Docs on purpose: Docs is made for writing and the Library for reading. The reader of a PDF is the same in both, with the same notes and marks.
- **The Web** is the one place where nodes are navigated, what rests on what, across the whole quilt, a draft's results and the library's alike, by a scope the person chooses: the library alone, a draft alone, a draft with what it depends on, or everything. It has a form in lists and a drawn form of a neighbourhood. A drawing of the whole web is wanted later.
- **Review** is everything waiting for the person's decision, in one list: edits an agent proposes to their text, what changed in their own text, nodes to check and corrections to nodes, formalizations to attest, questions an agent asks, and problems in their own text. It is needed because nothing unchecked may look checked (P15), so one place must list what is unchecked. Agent tasks, everything waiting for an agent, is a part of it and does not stand beside it.

**A control in one view does not send the person to another** (the author, 2026-11-20: it "makes it unclear where you've ended up and makes the state of loom seem chaotic and unpredictable"). Whatever is started in a view opens and completes there, in place, in a panel or in a tab of that view; only the views' own names change view. So a result is checked where it is being read, the node beside its place on the page, and in Review a row to check opens in place and shows the same. Inside the Library a result that points into another work opens that work at its place, in a Library tab; following dependency from node to node is the Web's.

**Less is shown by default.** The first mock-up was noisy, and it is not to feel like a trading terminal (V6).

**One vocabulary says how a thing stands**, on every surface: one shape for the reading of the paper and another for Lean, filled for a person's yes, a colour for what waits on a person, an outline for nothing yet.

**Open.** The word for a node a person has compared with its paper. "Checked" was read as possibly meaning the mathematics, or Lean.

**Open.** What the control for orphaned things in Docs holds: notes whose document is gone, files no document reads, or both.

## Scale, and moving between quilts

The library is built so that it can reach the size of the Stacks project and so that a library can pass from one quilt to another, though neither is built now.

- **One node a file**, so that two people do not conflict on different nodes.
- **An index loom derives**, under `.loom/cache/`, so that no command reads every file.
- **A node is drawn in the browser** (the author, 2026-11-20), with TeX run only for what a node needs it for, such as a diagram, and that result kept by the node's hash. A person's documents stay TeX's own output: that was chosen for speed and for faithfulness, after earlier versions of loom drew a paper's source in the browser very unfaithfully. A node's body is short prose and mathematics, the easy case, and it is to work well and fast or not be used; so it is compared with TeX's output on real statements before anything rests on it.
- **Nothing is made before it is asked for** where that is possible: a node is typeset when it is first shown, a work's pages are read when it is opened, and the index follows the files that changed.
- **The viewer is sent what it is showing, and no more.** Today the server sends the viewer one file listing every node of the quilt whenever anything changes, ten megabytes at the author's 2,354 nodes. For the library the viewer asks instead for what is on screen, a work's results, a node and what it uses, what a draft rests on, and is sent that.
- **A number for the format in every file**, raised only when the format changes, since files travel without the loom that wrote them.
- **Nothing local in a node but its prefix.** A quilt keeps the prefix it has; a clash between two quilts is settled when they are joined.
- **Evidence travels as a claim.** An imported record that Lean accepted a node is a report until the loom that receives it runs the check, which is the reason a publisher runs the Lean again (P15).

## What this replaces

Nothing of today's library is kept because it exists (the author, 2026-11-20). Every page, control, command, record and rule that belongs to the library as built is a candidate to be replaced or removed, a work's Info with its cards of results among them, and what stays, stays on its merits against this design. The old decisions were often made in passing, and this rework is not to be shaped by them. What follows is what is known to go; an inventory of the rest comes before the build is planned.

- **Digests** as one LaTeX file for each work with a record beside it, and ids made from a citekey and the paper's number.
- **The bibliography file as the place loom keeps its own facts.** A work is a node, so its id, its stored copies and its entry are one file; a bibliography for TeX is generated from the references.
- **Work ids made from authors, title and year**, and the piece of 2026-11-20 that pinned them, which was stopped. Its lessons stay as rules: two entries are not one work unless the person says so, an entry a person corrected is not rewritten, and an entry is found where the parser reads it.

The quilt's layout changes under `.loom/library/` alone, so the format number becomes 2. Works and their stored documents are carried into references. Digests are not converted: the author starts fresh. Nothing else of the old library is carried or kept working: a link written to a work's old id is not honoured, and a quilt whose pages hold such links has them written again once (the author, 2026-11-20: "no need to support an old unreleased link format forever"). An existing quilt may break for this; the product is not held back to spare one.

Two pieces built the same week have a place in the new design, the tray, which is the way a work comes in and now makes a reference, and the tool that places a result in a paper, which records where a node stands. Whether what was built of each is kept, changed or made again is judged like everything else.

**Settled from the inventory of today's library** (the author, 2026-11-20).

- **Deleting a work with results** is one act with one undo, and whatever used those results says they are gone.
- **A work has no overview of its own.** What an agent wants to say of a work, so that later agents find it, is a note on the work, with tags.
- **An entry that states no identifier is not matched to one by loom's own search.** A candidate is offered as a question and nothing is taken without an answer.
- **A paper an agent cannot fetch is asked of the person.** An agent often cannot download what a person on a university's network can. What it needs then waits in Review as a request with the source's link; the person opens the link, and the paper they drop is matched to the work that was waiting for it, so that fetching several at once costs a click and a drop each and no typing.

**Open.** A person cites the published paper and loom reads the arXiv source, whose numbering may differ. The proposal: two references joined as the same work, the result marked as read from another version, its number unconfirmed until it is checked against the version cited. The author agrees it is a tension and has not settled it.

**A work that names itself is looked up, not typed** (the author, 2026-11-20). Where a dropped paper carries an identifier, in its file's name, in its own metadata or on its first page, the reference's authors, title and year come from that identifier's record, and the person is not asked to type what a look-up would give. Where the quilt does not allow the network, loom asks for that one look-up at the drop, naming the identifier it found; a reference made without it says its details are unconfirmed and offers the look-up later. Loom does not guess an author from a page's text. The case this comes from: on 2026-11-20 the author dropped an arXiv paper, named by its arXiv number, into a quilt with the network off; loom recognised the number and recorded it, took a title and a year from the PDF, looked nothing up, said nothing of the number, and showed an empty field for the author to type.

## What the pilot builds

One path through the model, enough for the first use.

1. The node file and its checks, with the index.
2. References and their macros, made from the works a quilt holds.
3. Digest, as one act for any source, run by loom only on what a draft depends on.
4. The Library view: works, a work's results beside its PDF, a result's page.
5. Formalization on top: declarations that name their nodes, loom's fenced check, assumed results, attestation, and what a theorem is verified relative to.

Waiting: the drawn web, telling that two nodes are one, proofs transcribed from PDFs, the pages for reading in the manner of the Stacks project, the controls that move a library between quilts, and serving at the publisher's size.
