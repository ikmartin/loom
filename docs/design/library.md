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
- **A macros node**: the definitions a work's results are typeset with, one for each work that needs one. They are kept apart from every other work's because two papers define the same command differently, and a web of many papers cannot share one preamble. Forester does the same: a tree of definitions that other trees import.
- **A stub**: a statement known to exist at a place in a work whose text has not been read. A draft that cites Lemma 2.1 of a paper nobody has digested still depends on a node, and the web shows it as known and not yet read.

**The id** is opaque and permanent. It is minted once, it is not reused, and it is not made from a citekey, a printed number or a position, each of which changes. A suffix says what a node is when it is not a statement: `tq-00A1-ref` is a work, `tq-00A1-macros` its macros, `tq-00K3-proof00` a proof of `tq-00K3`. A proof's number is given once and not renumbered, so removing the first proof does not rename the second, and a proof does not move to another statement. Parts of a node, the (i) and (ii) of a lemma, have no ids.

**The file says what the source says, and nothing else.** It is the reading of one place in one work: what kind of thing stands there, its number and name, its text, and what that text points at. It does not hold Lean, since Lean does not compile alone and every step of formalization would then edit a file a person had already checked against the paper. It does not hold a status, since a status written in a file is one anybody could set (P3, P15). It does not hold who digested it or how, which is the record of an act. And it does not hold what loom can find again: the order of a work's nodes and the exact place of each on a page.

**The body is the content only, in LaTeX** (P1). It has no `\begin{lemma}`: the taxon, the number and the name are in the header, and loom supplies the heading when it typesets. So a body needs its paper's macros and not its paper's theorem environments. A body points at other nodes by their ids, `\ref{tq-00A4}` and not `\ref{def:widget}`, so that a node read alone or carried into another quilt still points at something, and two papers that both say `lem:main` do not collide. The source's own label is kept in the header.

**Why this format.** The files are written and read by loom, seldom by hand, so the header is typed and validated, and the body is the text exactly, with no quoting. A LaTeX file with its header in comments cannot hold a list. JSON puts the LaTeX on one escaped line, so any change rewrites the whole body in a diff. Forester's own format was considered and its design is what this takes: an opaque address, one node a file, a small header, everything a node, views computed from links. Its body is its own markup, into which LaTeX goes as a picture, where loom needs words a note can be anchored to; it has no kinds of edge, no evidence and no way to keep two authors' addresses apart; and as a dependency it is another toolchain beside TeX.

**Open.** P5 says the graph is defined by labels and environments, never by paths. It was written of an author's sources, where nothing may be inferred from where a file sits. A library node's id is its file's name by construction, which is a statement and not an inference; P5 takes a sentence saying so when this is built.

**Open.** A node with no source, something stated in the quilt and read from no work, is specified only as far as a list of authors. What it is for, and whether a note that became durable is one, belongs with the notes beyond annotations in [`model.md`](model.md#notes).

## A draft is not in the library

A draft changes daily, and the library is for what is stable. So a draft's results are read live from the draft, as loom reads them today, and are not copied into node files. They appear in the web under the same shape as a node, with the draft as their source and with no file. When a paper is finished and the author gives its source to the library on purpose, it is digested like any other work.

A draft's result still needs a name that lasts, because a Lean declaration and the author's attestation point at it. That name is its label in the source. This is the question anchoring calls label keys, and the answer here is yes.

A draft's edges into the library come from what it cites. `\cite[Lemma 2.1]{Jon19}` in a proof is a use of one result of one work; if that result has no node yet it gets a stub. This is how the library grows by loom's own hand: only what a draft depends on, one step out (P14). Everything further is the author's choice, made in the Library view: digest this paper, read this result, check this transcription.

**Open.** A statement of a draft with no label has no lasting name. Anchoring finds it again by the text beside it; whether loom also offers to write a label, through the door and on the author's word (P7), is not decided.

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

**An attestation holds for a statement together with everything it uses.** Take a definition, "a widget is a compact set with property P", and a proposition that uses it, "every widget is bounded". The author attests that a Lean theorem says what the proposition says. If the definition is later corrected to "a closed set with property P", the proposition's own words have not changed and it now claims something else. So an attestation names the statement and every node its statement uses, and what those use in turn, and goes stale when any of them changes.

## Formalization

**Stating and proving are two things.** The author's own results are stated in Lean and proved. A result of the library that a draft rests on is stated in Lean and not proved: it is **assumed**. An assumed statement still has to be written in Lean, which means its definitions have to be, and a wrongly stated assumption makes whatever is proved from it worthless; so it is attested like any other. Lean reports exactly which assumptions each theorem used, and loom reads the honest claim off that report: this theorem is verified relative to these results. Where Mathlib already has a result, a declaration in the quilt's own project states the node and its proof is one line.

**There are two webs, and one is a contraction of the other.** Lean works in finer pieces than a person does: in loom's trial of one proposition, loom's graph supplied about a third of the nodes and a fifth of the edges of the Lean development. So Lean's graph is not copied into the library. Each node is stated by one or more declarations, together, with no ids for the parts; auxiliary declarations support a node and are not nodes; and Mathlib is the ground everything stands on. A declaration names its node by a marker in the Lean source, as Mathlib tags declarations with Stacks project tags, and loom reads the markers when it runs the check.

This lets loom compare the two webs. A use the paper claims and Lean did not need, or a dependency Lean used that the paper never mentions, is worth showing the author.

The Lean lives in the quilt's Lean project and not in a node. In the Library a node's page shows them together: the statement, the paper open at its place, the Lean statement as Lean prints it, and the evidence.

Loom runs the check itself, fenced, so that "Lean accepted this" is something loom saw (decisions 10 and 16 of `docs/plans/0.32-v0.1.md`; `docs/reports/v0.1-study/raw/fence-trial.md`). The formalization skills need not be used as they are: the library becomes their record of what depends on what and of which statements are fixed, which in the trial were separate files that broke the quilt. Their audit of a statement against its source and their search of Mathlib before proving are kept.

**Open.** What a person is shown between "an agent proposes this formalization" and "formalized": whether a node reads "Lean accepted, not attested", and what a result reads when its proof rests on one not yet proved.

## The Library view

The Library is a view of its own, beside Docs and Review. It lists works as a reference manager does. It shows a result on a page of its own: the statement, where it is from, what it uses and what uses it, and its evidence, each a link to follow (V5). And reading a work there opens its PDF at the place, with the work's results to move between, in the manner of the Stacks project's pages. From this view the author digests and verifies what they choose.

A work also still opens beside a document in Docs, from a library control in the column, since a result is mostly wanted in the paper it lives in, next to what is being written.

Drawing the web waits for a second pass. At the size of the author's own quilt the whole graph was unreadable, so the Library answers questions, and draws at most a neighbourhood.

## Scale, and moving between quilts

The library is built so that it can reach the size of the Stacks project and so that a library can pass from one quilt to another, though neither is built now.

- **One node a file**, so that two people do not conflict on different nodes.
- **An index loom derives**, under `.loom/cache/`, so that no command reads every file. The manifest carries every node today, ten megabytes at the author's 2,354; the web is served by question.
- **A number for the format in every file**, raised only when the format changes, since files travel without the loom that wrote them.
- **Nothing local in a node but its prefix.** A quilt keeps the prefix it has; a clash between two quilts is settled when they are joined.
- **Evidence travels as a claim.** An imported record that Lean accepted a node is a report until the loom that receives it runs the check, which is the reason a publisher runs the Lean again (P15).

## What this replaces

- **Digests** as one LaTeX file for each work with a record beside it, and ids made from a citekey and the paper's number.
- **The bibliography file as the place loom keeps its own facts.** A work is a node, so its id, its stored copies and its entry are one file; a bibliography for TeX is generated from the references.
- **Work ids made from authors, title and year**, and the piece of 2026-11-20 that pinned them, which was stopped. Its lessons stay as rules: two entries are not one work unless the person says so, an entry a person corrected is not rewritten, and an entry is found where the parser reads it.

The quilt's layout changes under `.loom/library/` alone, so the format number becomes 2. Works and their stored documents are carried into references. Digests are not converted: the author starts fresh.

Two pieces built the same week are fitted to the new store and not thrown away: the tray, which is the way a work comes in and now makes a reference, and the tool that places a result in a paper, which records where a node stands.

## What the pilot builds

One path through the model, enough for the first use.

1. The node file and its checks, with the index.
2. References and their macros, made from the works a quilt holds.
3. Digest, as one act for any source, run by loom only on what a draft depends on.
4. The Library view: works, a work's results beside its PDF, a result's page.
5. Formalization on top: declarations that name their nodes, loom's fenced check, assumed results, attestation, and what a theorem is verified relative to.

Waiting: the drawn web, telling that two nodes are one, proofs transcribed from PDFs, the pages for reading in the manner of the Stacks project, the controls that move a library between quilts, and serving at the publisher's size.
