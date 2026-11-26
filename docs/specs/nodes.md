# Nodes of the library

It specifies the files the library holds: one file for each node, with the ids, the header, the body, and the edges a file may state. What the design is for and why it has this shape is [`docs/design/library.md`](../design/library.md); where the two disagree about a shape, this page wins.

**Built:** reading and writing a file (§1–5), the checks (§11), the index loom derives from the files (§13), the tag log (§14), references and macros nodes made from the works a quilt holds (§7, §8), and statements and proofs digested from a work's TeX source (§6), in `loom/src/loom/library/`.

A rule marked **[decided]** was settled by the author on 2026-11-20. The others complete the format and are his to change.

## 1. Files

**[decided]** A node is one file, `.loom/library/nodes/<id>.node`, where `<id>` is the node's id (§3). One node, one file; one file, one node. Only the files named `*.node` directly in that folder are nodes; anything else there is not read.

A file is UTF-8 with line feeds, holding no carriage return and no NUL, and has three parts in this order:

1. a line that is exactly `+++`;
2. the **header**, a TOML document (§2);
3. a line that is exactly `+++`, and after it the **body** (§4), which runs to the end of the file.

The body is every byte after the line feed that ends the second `+++` line. Nothing in it is quoted or escaped. A body of whitespace alone is empty, and loom writes an empty body as no bytes, so a file whose body is empty ends with that line feed.

**A node's hash** is `sha256:` followed by the lower-case hexadecimal SHA-256 of the file's bytes, header and body alike. Records name a node's text by this hash.

## 2. The header

**[decided]** The header holds what the source says about the node and nothing else: no Lean, no status, and nothing about who made the file or how.

The keys, in the order loom writes them. A key this table does not name is refused, and so is a key on a kind of node the table does not allow it on. A string is never empty and a list never empty: a key with nothing to say is left out.

| key | type | allowed on | meaning |
| --- | --- | --- | --- |
| `schema` | integer | every node, required | The number of this format. It is `1`. It is raised only when the format changes so that a loom that knows the old number cannot read the file, and is never loom's version. |
| `id` | string | every node, required | The node's id (§3), the same as the file's name without `.node`. |
| `taxon` | string | every node, required | What the node is (§5). |
| `number` | string | statements | Its number as the source prints it: `"3.4"`, `"A.2"`. Absent for an unnumbered statement. |
| `title` | string | statements | The name the source gives it, as LaTeX. Absent when it has none. |
| `source` | string | statements, proofs | The id of the reference (§7) this node's text was read from. Every statement and proof has one: the library holds results of works, and a result of the person's own or an agent's belongs in a draft, not the library. A fact from a book the person holds only on paper has the book as its work; a colleague's unpublished note is a work. |
| `label` | string | statements with a `source` | The source's own label for the statement, when the source is LaTeX and labels it. |
| `pages` | string | statements and proofs with a `source` | The page, or the first and last page joined by a hyphen, as the source numbers its pages: `"13"`, `"12-13"`. |
| `found` | string | statements with a `source` | How loom found the statement's `number` and `pages` in its work, where digest did: `words`, its heading identified in the stored PDF by its own words; `place`, by its place between two so identified, which cannot tell two results swapped in print, so the person's check reads it with care; `compile`, with no PDF, the number loom's reading that a compile of the source agreed with. Absent where nothing was found. |
| `anchors` | table of strings | statements, proofs | For each anchor the body defines (§3) whose source prints a number, that number as `\ref` prints it: `{tq-00K3-eq00 = "3.3"}`, which `\eqref` draws "(3.3)". An anchor the source prints no number for is left out. Absent when there are none. |
| `awaiting` | list of strings | statements, proofs | The anchors the body defines whose number loom does not keep yet: a display of the source numbered only by the person's compile, which loom's digest writes here when it writes the node without one and empties once that compile confirms the number into `anchors`: by writing the node again where it is loom's own, and in a node another hand wrote or a person compared by filling in those numbers alone (`evidence/acts.py`, `numbered`, which refuses any other change). No other write sets or clears it: a correction filed or taken is refused where it does (`evidence/acts.py`, `_takeable`). A pointer at such an anchor is drawn with no number. Absent when there are none. |
| `uses` | array of strings | statements, proofs | Ids of the nodes this node's text uses (§9), sorted. Absent when there are none. |
| `mentions` | array of strings | statements, proofs | Ids of the nodes this node's text mentions (§9), sorted. Absent when there are none. |
| `pdf`, `tex` | string | references | The hash, in the form `sha256:` and 64 hexadecimal digits, of the stored PDF and of the stored LaTeX source of this work. Each is absent when loom holds no such document. |

A macros node (§8) has `schema`, `id` and `taxon` only.

**Loom's form.** Loom writes a header one way: the keys in the table's order, one `key = value` a line, a list on one line (`uses = ["tq-00B7", "tq-00K3"]`), a table on one line with its keys in order (`anchors = {tq-00K3-eq00 = "3.3"}`), and each string a basic string (`"…"`), except a string with a backslash and no `'` or control character, which is a literal string (`'The \emph{widget} bound'`) so that LaTeX reads as LaTeX. A file in this form reads and writes back byte for byte. A header in any other valid TOML form is read and never refused, and is written in loom's form the next time loom writes the node, which changes its hash as any edit does.

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

**[decided]** `nn` is given once and not renumbered: removing `tq-00K3-proof00` does not rename `tq-00K3-proof01`, and `00` is not given again. It is given as `source-contract.md` §3.2 gives a stem, one past the largest seen under its owner in the library's files, the tag log, the annotation log, the acceptance ledger and git history, so a number removed and seen nowhere since can be given again, as a stem can.

A stem is minted by `source-contract.md` §3.2 from everything that section counts together with the library's files and the tag log, since the library and the author's sources share the prefix; `loom id --next` counts the library's too. A stem names a statement, with its proofs, or a work, with its macros, never both: `tq-00A1` and `tq-00A1-ref` are not both nodes.

**[decided]** The parts of a statement, such as the (i) and (ii) of a lemma, have no ids and are not nodes.

An **anchor** is not a node and has no file. It is a place inside a node's body that another body can point at (§4).

## 4. The body

**[decided]** The body is the content only, in LaTeX. A statement's body has no `\begin{lemma}` and no `\end{lemma}`, and a proof's has no `\begin{proof}` and no `\end{proof}`: the taxon, the number and the title are in the header, and loom supplies the heading when it typesets the node. So a body depends on its work's macros (§8) and on no theorem environment its work declared.

**[decided]** A body points at other nodes by their ids.

1. The argument of a referencing command, starred or not, is an id or an anchor: of `\ref`, `\eqref`, `\autoref`, `\pageref`, `\vref`, `\Vref`, `\vpageref`, `\fullref`, `\nameref`, `\Nameref` and `\autopageref` one; of cleveref's `\cref`, `\Cref`, `\cpageref`, `\Cpageref`, `\labelcref`, `\labelcpageref`, `\namecref`, `\nameCref`, `\lcnamecref` and their plurals a list; of `\crefrange`, `\Crefrange`, `\cpagerefrange`, `\Cpagerefrange`, `\vrefrange` and `\vpagerefrange` each of the two; and of `\hyperref[…]{…}` the one in brackets (`SINGLE`, `LISTS` and `RANGES` in `loom/src/loom/library/body.py`). The source's `\ref{def:widget}` is written `\ref{tq-00A4}`.
2. The key of a citation command is the id of a reference. The source's `\cite{Jon19}` is written `\cite{tq-00B1-ref}`. The citation commands are LaTeX's, natbib's and biblatex's, starred or not, `\cite`, `\citep`, `\citet`, `\citealp`, `\citeauthor`, `\citeyearpar`, `\nocite`, `\parencite`, `\textcite`, `\autocite`, `\footcite`, `\fullcite`, `\citetitle` and their like; biblatex's multicites (`\cites`, `\parencites`, …) read every group of keys, after up to two notes in parentheses (`CITES` and `MULTICITES` in `loom/src/loom/library/body.py`).
3. A citation that names one result of another work is written as a reference to that result's node, which is a stub (§6) if the result has not been read. The source's `\cite[Lemma 2.1]{Jon19}` is written `\ref{tq-00B7}`. Loom prints it as a citation with its locator, since the node it points at belongs to another work.
4. A `\label` inside a body is an anchor of that node, and nothing else: the source's `\label{eq:bound}` on a display in the statement `tq-00K3` is written `\label{tq-00K3-eq00}`. The statement's own label is not in the body; it is the header's `label`.
5. A command named as these are, ending in `ref`, `refs` or `refrange` (or `Ref`, …) or holding `cite` (or `Cite`), that is on none of the lists (`\href` apart) and that the work's macros node does not define is refused, and so is a referencing command whose argument is a command (`\ref\x`): loom cannot read what they point at, and a pointer it cannot read is a pointer it cannot check. One the work's macros define is read as rule 6 says, whatever its definition holds: `\deref` defined as `\mathop{!}` points at nothing and is not refused.
6. A work's own command whose definition in its macros node (§8) holds a referencing command or a citation, as `\newcommand{\eq}[1]{(\ref{#1})}` does, is read as that command with the arguments the body gives it: `\eq{tq-00K3-eq00}` points at `tq-00K3-eq00`, and `\eq{eq:bound}` is refused as `\ref{eq:bound}` is. A definition is followed through the work's other commands as far as they go: with `\newcommand{\via}[1]{\eq{#1}}`, or `\let\via\eq`, `\via{eq:bound}` is refused as `\eq{eq:bound}` is. The definitions read are `\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareRobustCommand`, xparse's `\NewDocumentCommand` and its kin, `\def` and its kin, and `\let` (`wrappers` in `loom/src/loom/library/body.py`). One whose definition holds `\label`, directly or through another, is refused in a body, since the anchor it would define is one loom does not read; the body writes `\label` itself.

Nothing else in the text is changed by digest: the words, the mathematics, and which referencing command the source used are as the source has them. A comment is part of the text and is kept, but nothing in it is read as pointing at anything; nor is anything in verbatim text (`\verb`, and the `verbatim`, `Verbatim`, `lstlisting`, `minted` and `comment` environments). A `\label` may carry cleveref's optional `[type]` before its anchor.

A body does not define commands, load packages or input files. Definitions belong to the macros node.

**Every id a body points at is in the header.** Each id that appears in a body by rules 1 to 3 and 6, and the owner of each anchor, is in that node's `uses` or in its `mentions`, and in only one of them. Three are exempt: the node itself, the statement a proof is of, and an anchor inside either. The header may list a node the body does not point at, where the text relies on something without a reference to it ("by the previous lemma").

## 5. Taxa

A node's taxon and its id agree:

| id ends | `taxon` | the node is |
| --- | --- | --- |
| `-ref` | `reference` | a work (§7) |
| `-macros` | `macros` | a work's macros (§8) |
| `-proof` and two base-36 characters | `proof` | a proof (§6) |
| none of these | anything else | a statement (§6) |

**[decided]** The taxa of statements are an open set, each a word in lower-case ASCII letters and hyphens. Loom writes these where a source gives them: `theorem`, `proposition`, `lemma`, `corollary`, `definition`, `example`, `remark`, `conjecture`, `convention`, `construction`, and `other` where none fits. A reader shows a taxon it does not know as its word.

## 6. Statements, stubs and proofs

**A statement** has a bare stem for its id. Its body is the statement.

**A stub** is a statement whose body is empty: a result known to stand at a place in a work, whose text has not been read. It has a `taxon`, a `source`, and whatever of `number`, `title` and `pages` is known. A stub becomes an ordinary statement when its body is written; its id does not change. Loom makes one at every build, before the build draws its fragments, for each result a draft cites by kind and number (`\cite[Lemma 2.1]{Smi24}`) in a work the library holds that holds no statement of that kind printed with that number (`library/stubs.py`), keyed by work, kind and number; a citation reaches only a held node of its kind and number, and loom corrects no kind. A citation of the work alone, a page or a part of it makes none, and so does a located citation naming several works, which names no single result.

**[decided]** **A proof** is a node of its own, and a statement may have several. Its id is its statement's with `-proof` and two digits, and the statement's file exists. It has a `source`, may have `pages`, `uses` and `mentions`, and has no `number`, `title` or `label`. Its `source` need not be its statement's: a second proof may come from another work.

A proof with an empty body is a **pointer**: it says where the proof is and does not copy it. A pointer has `pages`.

**Digest** (`library/digest.py`) writes a work's results from its TeX source's survey (`library-views.md` §3.2, "The survey"), by loom's hand, each statement with its proofs. A result is written once the survey confirms the number it prints (the stored PDF governs it); its text is the source's as it stands, comments included, with every pointer rewritten as §4 says: a result of the same work becomes that node's id, a stub where it has none; a `\label` in it an anchor of the node, numbered in `anchors` where it labels a display whose number the person's compile confirmed, and named in `awaiting` where no compile has, since without one loom keeps no display's number; the result's own label goes to the header; a `\ref` or `\eqref` of a heading or a display outside every result becomes the number the work prints for it, confirmed, a display's only by the person's compile, so a result pointing at one waits for that compile; a citation the reference's id, or `\ref` of the node of the one result its note locates, a stub where none is read. Every pointer it finds is a use: loom marks no mention, and only an agent's proposal or the person moves a pointer to `mentions`. A work the source cites is the reference stating its identifier as that version, else the one whose entry has its title and year (for a `\bibitem`, its note), else one made from the source's own bibliography, a `\bibitem` as `@misc`, recorded `how` `cited` with the citing work as its `source`. A node is written again only where it is a stub or loom's own extraction that no person compared; any other is kept, a pointer proof among them, beside which the source's proof is written under a new id. After the person's compile, the person's digest fills into a kept node the display numbers it confirms for the anchors in its `awaiting`, and changes nothing else of it, recorded `digested` how `numbered` (`evidence.md` §3.1), where loom gave those anchors from the source as it is held now; the unasked path never does. Each text written is recorded `digested`, how `extracted`, from `{ref, tex}`, and each stub of the work whose number the source does not print, where the PDF or a compile governs its numbers, is recorded `sought` once for each source (`evidence.md` §3). A result waits, saying why, while a number it prints or points at is not confirmed, while it holds another result, while its title points at something, while it uses a command loom cannot read as a pointer or a work's own command wrapping one, while it points into a proof no node holds, while it points by a label the source defines more than once (TeX's `\ref` prints the last, the survey keeps the first), and where the checks refuse it; it leaves no node behind unless another written result points at it. Scope `used` digests the results the drafts cite by number and, from each statement written, the results of the same work its own text points at, never those its proof does: what a draft rests on is a cited result's statement and what that needs to say what it means.

What a statement's text needs is listed on the statement. What an argument rests on is listed on the proof. A statement does not repeat its proofs' lists.

## 7. References

**[decided]** A work is a node. Its id ends `-ref` and its taxon is `reference`.

- Its body is exactly one BibTeX entry, as the person's bibliography has it, standing alone: no `@string`, `@preamble` or `@comment`, and nothing beside the entry, so whatever makes the node expands a source's abbreviations. The entry's key is the citekey documents cite the work by. No two references have the same entry key, compared ignoring case as BibTeX compares them.
- Its header has `schema`, `id`, `taxon`, and `pdf` and `tex` where loom holds those documents. It has no `title` or `authors`: they are in the entry.
- **[decided]** Each version of a paper is a reference of its own, with its own entry and its own stored documents. That two references are one paper is a relation (§9), not something a file states.
- A reference whose work has results is the `source` of their nodes. Nothing in the reference lists them.

**How a reference is made.** Every way a work comes in makes one (`library/references.py`): a file dropped or given to `loom library add` and a pasted text (the intake, `write-api.md` §6); an entry of a bibliography a person's document or a landmark reads, which loom gathers after every build, the publisher's and `loom build`'s, when `loom stamp` or `loom import` makes a landmark, and before `loom library add` takes, and never when the works are read (`library/gather.py`); a quilt made by an earlier loom, brought forward once (`loom upgrade`); and a TeX source dropped alone. Its stem is minted as `loom id --next` mints one (§3). Its documents are kept by hash, a PDF as `.loom/library/documents/<hex>.pdf` and a TeX source as one file, an uncompressed tar of its files with their names sorted and every owner, mode and time fixed, `<hex>.tar`, so the same source hashes alike however it came; `pdf` and `tex` name these hashes. How it was made, from what, and whether its details were looked up are recorded in the library's log (`.loom/records/library/log.jsonl`), never in its file: a reference made from an identifier with no look-up after it is unconfirmed. Gathering makes a reference for an entry key no reference holds, compared ignoring case, leaves alone a key whose work the person deleted until the work is added again, and rewrites a reference it made when its `.bib` entry changes, until someone edits the reference in loom. It writes under the id lock and the library's lock, deciding again under them, and takes neither when nothing is due. An entry the checks refuse is left out, or a reference following it is left as it was, and the rest go on; a build says each such entry to the person at its line (`diagnostics.md`, `loom:bib-entry-refused`). A pasted text and a dropped `.bib` have their `@string` abbreviations written out as gathering writes them.

**What loom fetches and tries unasked.** After every build, `loom serve` tries each work the drafts cite by a result that the library's stubs name, once for what it holds (`library/unasked.py`), one at a time, compiling nothing; a work only a digested proof cites is not tried. Under `[library] online`, a work whose entry states an arXiv number and that holds no PDF has arXiv's PDF fetched, and its source too where it holds neither: one request for each document and none again, naming loom and its version and nothing of the person, the machine or the quilt, each document filed under the work whose entry states the number (the author, 2026-11-20); a refused or failed fetch is recorded as the try's outcome and asked again only when what the work holds changes or the person asks. A work that holds a source is then surveyed and numbered from its stored PDF alone, and scope `used` digested (§6); a work held only as a PDF waits for a reader, an ask being the person's to make; a work holding neither waits for a document. Each try is recorded in the library's log as `tried`, with what the work held, its arXiv number and the printed numbers of its stubs once tried (`on`), what it came to (`outcome`, `digested`, `surveyed`, `waiting` or `failed`) and why, so a work is tried again only once what it holds or the stubs it has change. A try the network being off held back records nothing, and is made again once the network is allowed.

A document of the quilt, a draft among them, is not a reference and has no node (`docs/design/library.md`, "A draft is not in the library").

## 8. Macros

**[decided]** A work's macros are a node of their own. Its id is the reference's stem with `-macros`, its taxon is `macros`, and the reference `stem-ref` exists. A reference has at most one, and has none when its results need none, so a macros node holding nothing is refused.

- Its body holds only what is needed to typeset that work's bodies: package loads (`\usepackage`, `\RequirePackage`, `\usetikzlibrary`) and their options (`\PassOptionsToPackage`), definitions (`\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareRobustCommand`, `\NewDocumentCommand` and its `Renew`, `Provide` and `Declare` forms, `\DeclareMathOperator`, `\DeclarePairedDelimiter` and its `X` and `XPP` forms, `\newenvironment`, `\renewenvironment`, `\def`, `\gdef`, `\edef`, `\xdef`, `\let`, and their starred forms, with `\makeatletter` and `\makeatother` around them; colours, `\definecolor` and `\colorlet`; counters, lengths and conditionals, `\newcounter`, `\numberwithin`, `\newlength` and `\newif`; cleveref's names, `\crefname` and `\Crefname`; fonts and their symbols, `\DeclareMathAlphabet`, `\SetMathAlphabet`, `\DeclareSymbolFont`, `\DeclareMathSymbol`, `\DeclareMathAccent`, `\DeclareFontFamily`, `\DeclareFontShape`, `\DeclareUnicodeCharacter`, `\mathchardef` and `\chardef`; registers, `\newtoks`, `\newdimen`, `\newskip` and `\newcount`; `\newcolumntype` and `\newtheoremstyle`; and a conditional's own `\…true` and `\…false`), and the settings TikZ, tikz-cd, pgfplots and xy-pic take (`\tikzset`, `\tikzcdset`, `\pgfplotsset`, `\SelectTips`, `\xymatrixcolsep`, `\xymatrixrowsep`), `\allowdisplaybreaks`, and any of these inside `\AtBeginDocument{…}` or in the branches of a conditional. A conditional is one item, allowed when each of its branches is and its condition is one loom reads: TeX's own (`\ifdefined\cs`, `\ifx` of two tokens, `\ifcsname … \endcsname`, `\ifnum`, `\ifdim` and `\ifodd` of registers and numbers, `\iftrue`, `\iffalse`, the modes, and `\unless` before any of them) and a flag's (`\newif\ifdraft`'s `\ifdraft`), each to its `\fi` with its `\else` or `\or`; and those taking their branches as groups, `\@ifundefined`, `\@ifdefinable`, `\@ifpackageloaded`, `\@ifclassloaded`, `\@ifpackagewith`, `\IfPackageLoadedTF`, `\IfClassLoadedTF`, etoolbox's `\ifdef`, `\ifundef`, `\ifdefmacro`, `\ifdefempty`, `\ifcsdef`, `\ifcsundef`, `\ifcsmacro`, `\ifbool` and `\iftoggle`, and ifthen's `\ifthenelse` testing booleans and whether a command is defined (`GROUP_CONDITIONALS` beside `ARGUMENTS`). A setting of the page's layout, such as `\setlength{\parindent}{0pt}`, is the document's and not the work's, and is refused. The list is `ARGUMENTS` in `loom/src/loom/library/body.py`, and is widened from real papers.
- It holds nothing that typesets, no text, no `\documentclass`, no `\begin{document}`, no `\title`, no `\input`, and no `\newtheorem`, which no body needs (§4).
- It applies to exactly the nodes whose `source` is its reference, and to no other. Each node is typeset with its own work's macros alone, so two works that define one command differently do not meet.
- A node whose reference has no macros node uses only what loom's own preamble gives every node.

A reference's macros node is made when the reference first holds a TeX source, and made again when its source changes (`library/macros.py`): from the source's main file, the one declaring its class, up to `\begin{document}`, every item this section allows is taken whole, as the source wrote it and in its order; a local `.sty` or `.tex` file the preamble loads is read in its place, a package's file between `\makeatletter` and `\makeatother`, and a `\usepackage` is kept for a package the source does not hold, or holds in a file over a megabyte, which is no file of definitions, before what its other packages define. A conditional is kept whole, a local file a branch loads read in its place, when its branches hold only what this section allows; otherwise it is left out, and a comment in the node says so and why, since a definition in it may be one a body needs. Everything else is left out, the class among it, and with the class the packages it loads itself (`amsart`'s `amsmath`, which `\DeclareMathOperator` needs): loom's own preamble, which every node is typeset with, is to give those **(not built yet)**, and until it does a node made from such a source does not typeset under `article` alone. A preamble defining nothing this section allows makes no node, and a reference whose source is taken off loses its macros node.

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

**[decided]** There is no kind for containment or order. Where a node stands in its work, and so the order of a work's nodes, is found by loom and kept with its records (not built yet; until then the index orders a work's statements by their numbers, §13).

**Stated in records**, with who said it, when and why, and not in any node's file: that two nodes are the `same` result, that one `generalises` another, that two `contradict`. **[decided]** Nothing is merged, and nothing detects these.

**Read from Lean by loom**, and written by nobody: a declaration `states` a node or part of one; a declaration `supports` a node; a node is `assumed`, stated as an axiom with no proof; one declaration `depends` on another.

The records of evidence and what loom reads from Lean are specified in `evidence.md`; the records of `same`, `generalises` and `contradict` are not specified yet.

## 10. What a file does not hold

- **Lean.** Declarations live in the quilt's Lean project and name their nodes there.
- **A state.** Whether a node is digested, verified against its source, accepted by Lean or attested is computed from records that name the node's hash (§1).
- **Who made it, when and how.** That is the record of the act: for a reference, the library's log (§7).
- **What loom finds again.** A node's place on a page, the order of a work's nodes, what points at a node, and what a statement depends on through its proofs.

## 11. Checks

A file that fails any of these is refused when it is written and reported when it is found. A write is of one node or of several at once, checked as a whole, each file against the others and the library, so results that point at each other go in together; it is refused whole for its own files' failures, for two of its ids equal ignoring case, and, as a write of nodes new to the library, when one's id is there already. It is placed whole too: every file is on the disk before any takes its place, an interruption takes out what the write had placed, and a write a killed process left part way is rolled back by the next write, so the library holds all of a write or none of it. What it breaks in another file, as when it removes an anchor another body points at, is reported when that file is checked. Each failure is an error said under its check's code (`diagnostics.md`, "The library's nodes"), named here in brackets.

1. The two `+++` lines are there, the file is UTF-8 with line feeds, and the header is valid TOML. [`loom:node-unreadable`]
2. `schema` is a number this loom reads. [`loom:node-schema`]
3. `id` is the file's name without `.node` and matches §3; and, when loom writes it, no other node's id equals it ignoring case, since a file system blind to case holds one file for both. [`loom:node-id`]
4. `taxon` agrees with the id (§5). [`loom:node-taxon`]
5. Every key is one §2 names and allows on this kind of node, with the type §2 gives, and no string, list or table is empty; every key of `anchors` and every entry of `awaiting` is one of the node's own anchors, and none is in both. [`loom:node-key`]
6. A proof's statement exists; a macros node's reference exists; a `source` is the id of a reference that exists; and a stem is not both a statement's and a work's (§3). [`loom:node-parent`]
7. Every id in `uses` and in `mentions` is a node that exists and is not a macros node; none is in both; both are sorted, in code-point order, with no id twice and not the node itself. [`loom:node-edge`]
8. Every id the body points at is in `uses` or `mentions`, with the exemptions of §4; every argument of a referencing command is an id or an anchor, and every citation's key a reference's id; no command is named as a pointer that loom does not read (§4, rule 5); every anchor the body defines is the node's own, and none is defined twice; every anchor the body points at is defined by its owner, where the owner has text; and every anchor `anchors` numbers or `awaiting` names is defined by the body. Nothing in a comment or verbatim text is read. [`loom:node-body-ref`]
9. A reference's body is one BibTeX entry standing alone, with a key and no abbreviation unexpanded but a month's (`jan` to `dec`, which BibTeX's styles define), and no other reference has its key, ignoring case. [`loom:node-bibtex`]
10. A macros node's body holds only what §8 allows, and something; a failure names the command. [`loom:node-macros`]
11. A statement or a proof has a `source`, a stub and a pointer among them, whoever wrote it; a pointer has `pages`. [`loom:node-incomplete`]

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

A lemma that uses it and holds an anchor, which the paper prints as (3.3), `tq-00K3.node`:

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
anchors = {tq-00K3-eq00 = "3.3"}
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

## 13. The index

Loom answers questions of the library from an index it derives, `.loom/cache/library/nodes.sqlite3` (SQLite, with FTS5 for words), and not by reading every file. Nothing makes it before it is asked for. Each time it is opened it is brought up to date: a file whose size, modification time, change time and inode are as they were is not read again, unless it was written within two seconds of the last update, since a change in the same tick leaves them as they were; the tag log is replayed when it changed. It holds the readable nodes only; a file that fails a check reading it takes (1 to 5) is left out, and the checks report it. An index of another version, one missing a table, or one SQLite cannot read, is made again, and so is one removed while a process holds it open (a sweep of the cache), at that process's next update; it can be made again at will.

It answers: a node by its id, and a reference by its entry's key; the number the source prints for an anchor; a work's nodes in the paper's order, each statement followed by its proofs; what a node uses and mentions, and what uses and mentions it; a statement's proofs; the stubs, of one work or all; and a search. A work's order is the place loom records for each node (§9), and until that is built its statements' numbers read naturally (3.2, 3.10, A.1), then the first page.

A search returns statements, stubs among them. Words are compared ignoring case and accents, with compatibility forms made plain and case folded in full, so `strasse` finds Straße and `finite` the ligature in ﬁnite, and the letters that are letters of their own rather than a letter with an accent (ø, ł, đ, ħ, ı, ŧ, ð, æ, œ, þ) as their ASCII spellings, so `ostergaard` finds Østergaard and `lukasiewicz` Łukasiewicz; a run of Chinese or Japanese characters is one word, found by its start. Every word must match among a statement's name (its taxon and number, "lemma 3.2"), title, work and text, and the last word may be the start of a longer one; a word shaped like a printed number with a dot (`3.4`, `A.2`) matches a number exactly. Each hit says where it matched, `name` (its name or title), `text`, `proof` or `work`, and a hit in the text or a proof carries the words around the match from that LaTeX, cut at spaces outside mathematics, the match being the whole word it starts, and inside a formula the whole formula; in a formula longer than 160 characters the match is the line of it that holds the word (to a line feed or `\\`), cut to 160 characters around the word when the line is longer still, with nothing around it but "…". Hits on the name come first, then the rest by how well they match. A statement's work is its reference's key, authors, title and year. In a statement's title, its text and its work alike, TeX's accents and named letters are read as the characters they print (`M\"uller`, `M{\"u}ller` and `Mu` with a combining diaeresis all as Müller, `{\o}` as ø) and a brace group of plain letters as its letters (`{K}ova\v{c}` as Kovač), so `muller` and `kovac` find every way of writing them; what is shown, a title or a snippet's match, is as the file writes it, case and accents kept. Its text is its body with comments, the arguments of `\ref`, `\cite` and `\label`, environments' names and a short list of commands that carry no meaning (`emph`, `mathbb`, `left` and their like) left out; any other command's name is a word, so `Hom`, `alpha` and `otimes` find the statements that use them. A search may be limited to a work, a taxon or a tag, and may look in proofs as well, where a statement found by a proof's words alone is marked with that proof.

The index keeps a **generation**, a number raised by every update that puts a node in, takes one out or changes one, or changes the tags on one, and by nothing else: not a file touched and unchanged, not a file that does not read, not a tag written again. It never goes back: it outlives the index made again at will, and an index made from nothing starts it from the clock, in milliseconds. A publisher that keeps a generation of its own for the views (`library-views.md` §2, "Freshness") raises it whenever this one moves.

## 14. Tags

A tag is a record about a node, said by someone, and not part of its file, so tagging changes no node's hash (`docs/design/library.md`, "Digesting and checking"). Tags are a log, `.loom/records/tags/log.jsonl`, only ever appended to, one JSON object a line for each tag put on a node or taken off it:

| key | holds |
| --- | --- |
| `event` | `tag` or `untag` |
| `node` | the node's id |
| `tag` | the tag as written |
| `by` | who, by name |
| `kind` | `person` or `agent` |
| `at` | when, as `2026-11-21T09:00:00Z` |

A tag is written composed (Unicode's NFC), stripped, each run of whitespace inside it one space, and in the case it was typed: a subject code such as `14A20` stays as it is. It is one to 64 characters with no control character; a tab or a line feed typed in it is whitespace, and any other control character, the separators `\x1c` to `\x1f` and `\x85` among them, is refused. Two tags equal ignoring case are one tag, shown as it was first written in the log. A tag is on a node whose file is named exactly its id; an id in another case is not that node, though a file system blind to case opens its file. A node's tags are replayed from the log: a tag is on a node while anyone who put it there still has it there. A person's untag takes a tag off for everyone; an agent's takes off only its own, and an agent asking to take off a tag it did not put on is refused. Only a node in the library is tagged, and a tag or untag that would change nothing writes nothing. A line that is neither a tag nor an untag is skipped, and said as `loom:foreign-tags`; the rest of the log still loads. A line cut short, as a crash in the middle of writing it leaves one, is ended before the next is written, so it costs that line alone.
