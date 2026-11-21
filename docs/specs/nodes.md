# Nodes of the library

**Nothing on this page is built yet.** It specifies the files the library will hold once it is rebuilt: one file for each node, with the ids, the header, the body, and the edges a file may state. What the design is for and why it has this shape is [`docs/design/library.md`](../design/library.md); where the two disagree about a shape, this page wins. Until it is built, `digests.md` specifies what loom writes, and the change that builds this rewrites `digests.md` in the same commit.

A rule marked **[decided]** was settled by the author on 2026-11-20. The others complete the format and are his to change.

## 1. Files

**[decided]** A node is one file, `.loom/library/nodes/<id>.node`, where `<id>` is the node's id (§3). One node, one file; one file, one node.

A file is UTF-8 with line feeds and has three parts in this order:

1. a line that is exactly `+++`;
2. the **header**, a TOML document (§2);
3. a line that is exactly `+++`, and after it the **body** (§4), which runs to the end of the file.

The body is every byte after the line feed that ends the second `+++` line. Nothing in it is quoted or escaped. A file whose body is empty ends with that line feed.

**A node's hash** is `sha256:` followed by the lower-case hexadecimal SHA-256 of the file's bytes, header and body alike. Records name a node's text by this hash.

## 2. The header

**[decided]** The header holds what the source says about the node and nothing else: no Lean, no status, and nothing about who made the file or how.

The keys, in the order loom writes them. A key this table does not name is refused, and so is a key on a kind of node the table does not allow it on.

| key | type | allowed on | meaning |
| --- | --- | --- | --- |
| `schema` | integer | every node, required | The number of this format. It is `1`. It is raised only when the format changes so that a loom that knows the old number cannot read the file, and is never loom's version. |
| `id` | string | every node, required | The node's id (§3), the same as the file's name without `.node`. |
| `taxon` | string | every node, required | What the node is (§5). |
| `number` | string | statements | Its number as the source prints it: `"3.4"`, `"A.2"`. Absent for an unnumbered statement. |
| `title` | string | statements | The name the source gives it, as LaTeX. Absent when it has none. |
| `source` | string | statements, proofs | The id of the reference (§7) this node's text was read from. Absent for a node stated in the quilt and read from no work. |
| `label` | string | statements with a `source` | The source's own label for the statement, when the source is LaTeX and labels it. |
| `pages` | string | statements and proofs with a `source` | The page, or the first and last page joined by a hyphen, as the source numbers its pages: `"13"`, `"12-13"`. |
| `uses` | array of strings | statements, proofs | Ids of the nodes this node's text uses (§9), sorted. Absent when there are none. |
| `mentions` | array of strings | statements, proofs | Ids of the nodes this node's text mentions (§9), sorted. Absent when there are none. |
| `authors` | array of strings | statements and proofs with no `source` | Who states it. |
| `pdf`, `tex` | string | references | The hash, in the form `sha256:` and 64 hexadecimal digits, of the stored PDF and of the stored LaTeX source of this work. Each is absent when loom holds no such document. |

A macros node (§8) has `schema`, `id` and `taxon` only.

## 3. Ids

**[decided]** An id is opaque and permanent. It is not made from a citekey, from the number a paper prints, or from a position in a file. It is minted once and not reused (`source-contract.md` §3.2), and a node's id does not change.

```
stem     := prefix "-" loomlocal            tq-00K3          (source-contract.md §3.1)
id       := stem                            a statement
          | stem "-ref"                     a reference: a work
          | stem "-macros"                  the macros of the work  stem "-ref"
          | stem "-proof" nn                a proof of the statement  stem
anchor   := owner "-eq" nn                  a labelled display inside the node  owner
          | owner "-it" nn                  anything else labelled inside it
owner    := stem | stem "-proof" nn
nn       := [0-9A-Z]{2}                     base 36: 00, 01, …, ZZ
```

**[decided]** The prefix is the quilt's own, as for its other ids. It is not minted at random; a clash between two quilts' prefixes is settled when the two are joined.

**[decided]** A suffix says what a node is when it is not a statement, and for a proof and a macros node it also says whose: `tq-00K3-proof00` is a proof of `tq-00K3`, and `tq-00A1-macros` holds the macros of `tq-00A1-ref`. This parentage is read from the id and written in no key.

**[decided]** `nn` is given once, the lowest never given under its owner, and not renumbered: removing `tq-00K3-proof00` does not rename `tq-00K3-proof01`, and `00` is not given again.

**[decided]** The parts of a statement, such as the (i) and (ii) of a lemma, have no ids and are not nodes.

An **anchor** is not a node and has no file. It is a place inside a node's body that another body can point at (§4).

## 4. The body

**[decided]** The body is the content only, in LaTeX. A statement's body has no `\begin{lemma}` and no `\end{lemma}`, and a proof's has no `\begin{proof}` and no `\end{proof}`: the taxon, the number and the title are in the header, and loom supplies the heading when it typesets the node. So a body depends on its work's macros (§8) and on no theorem environment its work declared.

**[decided]** A body points at other nodes by their ids.

1. The argument of `\ref`, `\eqref`, `\autoref`, `\pageref`, `\vref`, `\Vref`, `\cref` and `\Cref`, starred or not, is an id or an anchor, or for the last two a list of them. The source's `\ref{def:widget}` is written `\ref{tq-00A4}`.
2. The key of a citation command is the id of a reference. The source's `\cite{Jon19}` is written `\cite{tq-00B1-ref}`.
3. A citation that names one result of another work is written as a reference to that result's node, which is a stub (§6) if the result has not been read. The source's `\cite[Lemma 2.1]{Jon19}` is written `\ref{tq-00B7}`. Loom prints it as a citation with its locator, since the node it points at belongs to another work.
4. A `\label` inside a body is an anchor of that node, and nothing else: the source's `\label{eq:bound}` on a display in the statement `tq-00K3` is written `\label{tq-00K3-eq00}`. The statement's own label is not in the body; it is the header's `label`.

Nothing else in the text is changed by digest: the words, the mathematics, and which referencing command the source used are as the source has them.

A body does not define commands, load packages or input files. Definitions belong to the macros node.

**Every id a body points at is in the header.** Each id that appears in a body by rules 1 to 3, and the owner of each anchor, is in that node's `uses` or in its `mentions`, and in only one of them. Three are exempt: the node itself, the statement a proof is of, and an anchor inside either. The header may list a node the body does not point at, where the text relies on something without a reference to it ("by the previous lemma").

## 5. Taxa

A node's taxon and its id agree:

| id ends | `taxon` | the node is |
| --- | --- | --- |
| `-ref` | `reference` | a work (§7) |
| `-macros` | `macros` | a work's macros (§8) |
| `-proof` and two digits | `proof` | a proof (§6) |
| none of these | anything else | a statement (§6) |

**[decided]** The taxa of statements are an open set, each a word in lower-case ASCII letters and hyphens. Loom writes these where a source gives them: `theorem`, `proposition`, `lemma`, `corollary`, `definition`, `example`, `remark`, `conjecture`, `convention`, `construction`, and `other` where none fits. A reader shows a taxon it does not know as its word.

## 6. Statements, stubs and proofs

**A statement** has a bare stem for its id. Its body is the statement.

**A stub** is a statement whose body is empty: a result known to stand at a place in a work, whose text has not been read. It has a `taxon`, a `source`, and whatever of `number`, `title` and `pages` is known. A stub becomes an ordinary statement when its body is written; its id does not change.

**[decided]** **A proof** is a node of its own, and a statement may have several. Its id is its statement's with `-proof` and two digits, and the statement's file exists. It may have `source`, `pages`, `uses`, `mentions` and `authors`, and has no `number`, `title` or `label`. Its `source` need not be its statement's: a second proof may come from another work, or from nobody's work.

A proof with an empty body is a **pointer**: it says where the proof is and does not copy it. A pointer has `source` and `pages`.

What a statement's text needs is listed on the statement. What an argument rests on is listed on the proof. A statement does not repeat its proofs' lists.

## 7. References

**[decided]** A work is a node. Its id ends `-ref` and its taxon is `reference`.

- Its body is exactly one BibTeX entry, as the person's bibliography has it. The entry's key is the citekey documents cite the work by. No two references have the same entry key.
- Its header has `schema`, `id`, `taxon`, and `pdf` and `tex` where loom holds those documents. It has no `title` or `authors`: they are in the entry.
- **[decided]** Each version of a paper is a reference of its own, with its own entry and its own stored documents. That two references are one paper is a relation (§9), not something a file states.
- A reference whose work has results is the `source` of their nodes. Nothing in the reference lists them.

A document of the quilt, a draft among them, is not a reference and has no node (`docs/design/library.md`, "A draft is not in the library").

## 8. Macros

**[decided]** A work's macros are a node of their own. Its id is the reference's stem with `-macros`, its taxon is `macros`, and the reference `stem-ref` exists. A reference has at most one, and has none when its results need none.

- Its body holds only what is needed to typeset that work's bodies: `\usepackage` lines, and definitions (`\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareMathOperator`, `\DeclarePairedDelimiter`, `\def`, `\let`, and their starred forms).
- It holds nothing that typesets, no `\documentclass`, no `\begin{document}`, no `\input`, and no `\newtheorem`, which no body needs (§4).
- It applies to exactly the nodes whose `source` is its reference, and to no other. Each node is typeset with its own work's macros alone, so two works that define one command differently do not meet.
- A node with no `source`, and a node whose reference has no macros node, uses only what loom's own preamble gives every node.

## 9. Edges

An edge runs from one node to another and has a kind. This is the whole vocabulary.

**Stated in a node's file.**

| kind | written as | means |
| --- | --- | --- |
| source | the `source` key | This node's text was read from that reference. |
| uses | an id in `uses` | **[decided]** This node's text invokes that node. On a statement: the other node is needed to say what the statement means. On a proof: the argument rests on it. |
| mentions | an id in `mentions` | **[decided]** This node's text points at that node without resting on it. |
| parentage | the id's suffix (§3) | This proof is of that statement; these macros are of that reference. |

The target of `uses` and of `mentions` is any node but a macros node. A use or a mention of a whole work, as a bare `\cite` makes, has the reference as its target. Every id a key names is the id of a file that exists; a result not yet read has a stub.

**[decided]** There is no kind for containment or order. Where a node stands in its work, and so the order of a work's nodes, is found by loom and kept with its records.

**Stated in records**, with who said it, when and why, and not in any node's file: that two nodes are the `same` result, that one `generalises` another, that two `contradict`. **[decided]** Nothing is merged, and nothing detects these.

**Read from Lean by loom**, and written by nobody: a declaration `states` a node or part of one; a declaration `supports` a node; a node is `assumed`, stated as an axiom with no proof; one declaration `depends` on another.

The formats of the records, and of what loom reads from Lean, are not specified on this page.

## 10. What a file does not hold

- **Lean.** Declarations live in the quilt's Lean project and name their nodes there.
- **A state.** Whether a node is digested, verified against its source, accepted by Lean or attested is computed from records that name the node's hash (§1).
- **Who made it, when and how.** That is the record of the act.
- **What loom finds again.** A node's place on a page, the order of a work's nodes, what points at a node, and what a statement depends on through its proofs.

## 11. Checks

A file that fails any of these is refused when it is written and reported when it is found:

1. The two `+++` lines are there and the header is valid TOML.
2. `schema` is a number this loom reads.
3. `id` is the file's name without `.node` and matches §3.
4. `taxon` agrees with the id (§5).
5. Every key is one §2 names and allows on this kind of node, with the type §2 gives.
6. A proof's statement exists; a macros node's reference exists; a `source` is the id of a reference that exists.
7. Every id in `uses` and in `mentions` is a node that exists and is not a macros node; none is in both; both are sorted with no id twice.
8. Every id the body points at is in `uses` or `mentions`, with the exemptions of §4; every anchor the body defines is the node's own, and none is defined twice.
9. A reference's body is one BibTeX entry, and no other reference has its key.
10. A macros node's body holds only what §8 allows.
11. A pointer has `source` and `pages`.

## 12. Examples

Nine files, verbatim: two works, the macros of the first, a definition, a lemma with its proof, a proposition with its proof, and a stub. Their prefix is `tq`.

A work loom holds a PDF and a LaTeX source of, `tq-00A1-ref.node`:

```
+++
schema = 1
id = "tq-00A1-ref"
taxon = "reference"
pdf = "sha256:41b7c0a9e3f2d5681c94ab07e6d3f81290ce5b47a8d1036f2e9c7b54a0d8e163"
tex = "sha256:9e02f7d4b1a865c3097e4f2ab8d6c1e5730f9a24b6d8c0e1f3a57b92d4c6e801"
+++
@article{Smi24,
  author        = {Smith, Jane},
  title         = {Widgets and their bounds},
  year          = {2024},
  eprint        = {2401.01234v2},
  archivePrefix = {arXiv},
}
```

Its macros, `tq-00A1-macros.node`:

```
+++
schema = 1
id = "tq-00A1-macros"
taxon = "macros"
+++
\usepackage{amssymb}
\newcommand{\Wid}{\mathcal{W}}
\DeclareMathOperator{\diam}{diam}
```

A definition, `tq-00A4.node`:

```
+++
schema = 1
id = "tq-00A4"
taxon = "definition"
number = "2.1"
title = "Widget"
source = "tq-00A1-ref"
label = "def:widget"
pages = "4"
+++
A \emph{widget} is a compact set $W \subset \mathbb{R}^n$ whose boundary lies in $\Wid$.
```

A lemma that uses it and holds an anchor, `tq-00K3.node`:

```
+++
schema = 1
id = "tq-00K3"
taxon = "lemma"
number = "3.2"
title = "Test lemma"
source = "tq-00A1-ref"
label = "lem:test"
pages = "12"
uses = ["tq-00A4"]
+++
Let $W$ be a widget (Definition~\ref{tq-00A4}). Then
\begin{enumerate}
\item $\diam W < \infty$; and
\item for every $x_0 \in W$, each point $x$ of $W$ satisfies
\begin{equation}\label{tq-00K3-eq00}
  |x| \le \diam W + |x_0| .
\end{equation}
\end{enumerate}
```

Its proof, `tq-00K3-proof00.node`:

```
+++
schema = 1
id = "tq-00K3-proof00"
taxon = "proof"
source = "tq-00A1-ref"
pages = "12-13"
uses = ["tq-00A4"]
+++
A widget is compact (Definition~\ref{tq-00A4}), so finitely many unit balls cover it, which bounds its diameter. The second claim is the triangle inequality.
```

A proposition, `tq-00K5.node`:

```
+++
schema = 1
id = "tq-00K5"
taxon = "proposition"
number = "3.4"
title = "Test proposition"
source = "tq-00A1-ref"
label = "prop:test"
pages = "13"
uses = ["tq-00A4"]
+++
Let $W$ be a widget as in Definition~\ref{tq-00A4}. Then $W$ lies in a ball about the origin.
```

Its proof, which uses the lemma and a result of another work, and mentions that work as a whole, `tq-00K5-proof00.node`:

```
+++
schema = 1
id = "tq-00K5-proof00"
taxon = "proof"
source = "tq-00A1-ref"
pages = "13"
uses = ["tq-00B7", "tq-00K3"]
mentions = ["tq-00B1-ref"]
+++
By Lemma~\ref{tq-00K3}, the bound \eqref{tq-00K3-eq00} holds for a fixed $x_0$. The covering estimate of \ref{tq-00B7} then gives the radius. For sets that are not compact see \cite{tq-00B1-ref}.
```

The other work, of which loom holds no document, `tq-00B1-ref.node`:

```
+++
schema = 1
id = "tq-00B1-ref"
taxon = "reference"
+++
@article{Jon19,
  author  = {Jones, Alex},
  title   = {Covering estimates},
  journal = {Journal of Examples},
  year    = {2019},
}
```

And its Lemma 2.1, which the proof above uses and nobody has read: a stub, `tq-00B7.node`:

```
+++
schema = 1
id = "tq-00B7"
taxon = "lemma"
number = "2.1"
source = "tq-00B1-ref"
+++
```
