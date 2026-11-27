// Types mirroring docs/specs/manifest.md. Field names are fixed by the spec; unknown fields are ignored by the viewer, so every interface here is open.


export type Severity = "error" | "warning" | "info";
export type ColorClass =
  | "neutral"
  | "positive"
  | "positive-strong"
  | "warning"
  | "negative"
  | "info"
  | (string & {});

export interface Author {
  /** Who wrote it. */
  kind: "agent" | "person" | (string & {});
  id: string;
  label?: string;
}

export interface Publisher {
  name: string;
  version: string;
}

/** What a corpus has, never what to draw (manifest.md §1). A publisher declares it; `normalise` derives it from the data when a manifest omits it, so everything downstream reads it as present. */
export interface Publishes {
  documents: boolean;
  review: boolean;
  bibliography: boolean;
  discussions: boolean;
}

export interface Corpus {
  name: string;
  root_label: string;
  /** The file the viewer opens on when it remembers no place: `[quilt] home`, else the root README.md; null when there is neither. */
  home?: string | null;
  /** The project root's own directory name, which `files` is a view of; absent from an older publisher. */
  directory?: string;
}

/** An open file changed since the reviewer's look (plan 0.22.8). */
/** One pending change to the person's text (specs/manifest.md §9): an edit made in a file since their look (`edit`), or a suggested edit not yet kept or discarded (`suggested`). Words, not hunks: each run of changed words is one change, its id stable while it stands. Keep makes it what the person has; Discard puts their words back, or drops the suggestion. */
export interface PendingChange {
  id: string;
  kind: "edit" | "suggested" | (string & {});
  /** The file it is in. */
  path: string;
  /** The statement or proof whose text it is in; null for text outside any block. */
  key: string | null;
  /** The person's documents whose text it is part of; empty for a file in none. */
  documents: string[];
  /** The words it takes out, as TeX; '' for words only added. */
  old: string;
  /** The words it puts in, as TeX; '' for words only taken out. */
  new: string;
  /** `new` as the publisher rendered it, where it could. */
  new_html?: string | null;
  /** Who made it, by name; null for an edit made in the file, which no record names. */
  author?: string | Author | null;
  created?: string | null;
  /** What a suggestion's writer says of it. */
  comment_html?: string | null;
  /** The annotation it answers, which Keep resolves. */
  answers?: string | null;
  /** `ready` to keep or discard; `taken` when the text already reads so; `unplaced` with `why`; `on-a-copy` for one on an agent's copy, which comes in with the copy. */
  state: "ready" | "taken" | "unplaced" | "on-a-copy" | (string & {});
  /** Why Keep or Discard is refused, for a change that is not `ready`. */
  why?: string | null;
  /** The block it is drawn in: the block's `data-src`, and a fragment holding the block with every change in it, its old and new words in `span.change[data-change][data-side]`, by its path under the build directory. Null for one not merged into the text. */
  block?: { src: string; fragment: string } | null;
  /** For a change to the text's structure, which no single block holds: the source range of its own words, `PATH:START:END`, by which it is drawn as a marker beside the element holding them. */
  place?: { src: string } | null;
  /** Its patch, by its path under the build directory. */
  diff?: string | null;
}

/** A link a shown file makes (`manifest.md`, Backlinks): where it is written, as written, and what loom resolved it to name. */
export interface Backlink {
  /** The file it is written in. */
  from: string;
  /** Its 1-based line there. */
  line: number;
  /** In a Markdown file or a notebook, the id of the heading above it, where the note opens; '' for none. Absent from an older publisher. */
  at?: string;
  href: string;
  /** What it names: `document`, `node`, `work`, `file`, `annotation`, `session`, `page` or `library`. */
  kind: string;
  /** A document's or file's path, a node's key, a work's reference. */
  key: string;
  /** The place after `#`, without its quoted words. */
  place: string;
  /** The words it quotes; '' for none. */
  quote: string;
}

/** A file of the project the viewer shows, by its quilt-relative path (plan 0.22.7). */
export interface ProjectFile {
  path: string;
  /** What the viewer does with it: a LaTeX document (`document`) or another `.tex` file, a drawn or framed kind, text, or `other`, opened in its application. */
  kind: "document" | "tex" | "markdown" | "html" | "pdf" | "image" | "notebook" | "text" | "other" | (string & {});
  bytes: number;
  /** A Markdown file's or notebook's body as the publisher drew it, by its path under the build directory. */
  body?: string;
  /** What keeps agents from editing it: the deny list's entry as written, or a path loom always protects (`always`); null where agents edit it too, and absent from a publisher that does not say. */
  denied?: { by: string; always: boolean } | null;
}

/** A landmark: a flat, self-contained copy of a document as it stood when loom recorded a step. It is a document, not a corpus of nodes: nothing in it has an identity. */
export interface CanonDoc {
	path: string;
	stem: string;
	title: string;
	fragment: string;
	hash: string;
	/** The step that wrote it, `0002`, when the history knows; a file dropped into the canon directory by hand has none. */
	step?: string;
	name?: string;
	message?: string;
	when?: string;
	/** The macro set to typeset it with: a landmark renders with its own preamble's macros, whatever the drafting documents have since become. */
	macros?: string;
	/** The live document its step was about, where the history's moves have taken it; absent when no live document leads to it. */
	in?: string;
	/** The act it was kept at, besides recording one by hand: `adopt` or `sync` (before taking changes in), `keep` (an edit kept in Changes), `undo` (the text an undo set aside), `restore` (the text a restore replaced). Absent for a version the author recorded or imported. */
	kept_for?: 'adopt' | 'sync' | 'keep' | 'undo' | 'restore' | (string & {});
	/** The step's action: `import` for the paper as received, `stamp` for every other version. */
	action?: string;
	/** Why it cannot be put back into its document, in the person's words; '' when it can. */
	cannot_restore?: string;
}

/** A version of one file no document's version holds (a bibliography, a figure, a file no document reads), kept when an update from Overleaf wrote over it or a restore replaced it; oldest first in `history.files`. */
export interface HistoryFile {
	path: string;
	/** Its bytes by hash, which `history-restore` takes as `version`. */
	version: string;
	when: string;
	actor?: string;
	/** The act it was kept at: `sync` (before an update from Overleaf) or `restore` (the bytes a restore replaced). */
	kept_for?: string;
	message?: string;
	/** `text` (UTF-8), `image`, or `other`. */
	kind: 'text' | 'image' | 'other';
	bytes?: number;
	/** Its bytes, published under the build directory; absent when the history lacks them. */
	kept?: string;
	/** Whether the file holds these bytes now. */
	same?: boolean;
	/** A text's unified diff from the version to the file now, under the build directory. */
	diff?: string;
	/** Why it cannot be put back, in the person's words; '' when it can. */
	cannot_restore?: string;
}

/** One line of the history, as Review › History lists it: what was done, when, by whom, and to what. */
export interface HistoryAct {
	action: string;
	when: string;
	actor?: string;
	/** A step's number, for the acts that are steps. */
	step?: number;
	/** The file it was done to (a keep, an undo, a page written, a text put back). */
	path?: string;
	/** The files a whole keep took in. */
	paths?: string[];
	/** The document it concerns, as it is now named. */
	in?: string;
	/** A step's landmark: a `canon` entry's path. */
	landmark?: string;
	message?: string;
	hunks?: number[];
	kept_for?: string;
	copy?: string;
	page?: string;
	/** A text by its hash: what an undo or a put-back replaced (`from`) and wrote (`to`). */
	from?: string;
	to?: string;
	/** A version a restore put back, by its landmark's file name. */
	version?: string;
	/** The line of a box set in the viewer, and the state it was set to. */
	line?: number;
	done?: boolean;
}

/** One step of the history: an import, a stamp, an agent document's copy or an adoption. */
export interface HistoryStep {
	step: number;
	action: string;
	name: string;
	when: string;
	actor?: string;
	message?: string;
	/** The document the step concerns, as the ledger names it; absent for a stamp of the whole quilt. */
	document?: string;
	/** That document where it is now, when it is still live. */
	in?: string;
	/** The landmark the step kept, a `canon` entry's path. */
	landmark?: string;
}

export interface Master {
  path: string;
  title: string;
  default: boolean;
  fragment: string;
  engine?: string;
  compiled?: string;
  pdf?: string;
  numbering_known?: boolean;
  /** The local files it loads beside its text: its preamble's packages, class and inputs, then the bibliographies it names; absent where none. */
  loads?: string[];
  /** An agent document's source document, where the history's moves have taken it. */
  copy_of?: string;
  scope?: {kind: string; key?: string; title?: string; keys?: string[]};
  scope_keys?: string[];
  context_when?: string;
  context_changed?: boolean;
  context_only?: boolean;
  context_document?: string;
  closed?: boolean;
  closed_at?: string;
  closed_annotations?: Annotation[];
  closed_keys?: string[];
  macros?: string;
}

export interface NumberEntry {
  number: string;
  page?: number;
}

export interface Node {
  name?: string;
  /** An agent document's node: the plain key it corresponds to, `zk-0001` for `zk-0001-ai`. Whole-quilt views leave such nodes out. */
  derived_of?: string;
  draft_macros?: string;
  /** A derived node's base: the version of its plain key it began from, and that version's hash as `data-hash` takes it (`math`), so compare can tell a node changed on both sides. */
  base?: { key: string; step: number; hash: string; math?: string };
  id: string;
  kind: "environment" | "section" | "proof" | (string & {});
  /** Sections only: the sectioning depth, 1 for \section. A contents list stops at a chosen depth with it. */
  level?: number | null;
  taxon: string;
  style?: string;
  title?: string;
  aliases: string[];
  author?: string[];
  created?: string;
  tags: string[];
  file: string;
  src: [number, number];
  fragment: string;
  numbers: Record<string, NumberEntry>;
  reached_by: string[];
  parent: Record<string, string>;
  children: string[];
  proofs: string[];
  external: boolean;
  /** Why this block may be relied on; unclassified blocks need an author choice in the drafting source. */
  basis?: 'expository' | 'local-proof' | 'cited-result' | 'assumption' | 'open-claim' | 'unclassified';
  basis_reason?: string;
  inline_proof?: boolean;
  /** The files that each define this id, when two do. The id is then `conflicted`: it has no text, and loom reports both rather than choosing. */
  conflict?: string[];
  /** On a block of basis `cited-result`, the postnote its title cites the result with; null when it cites none. */
  locator?: string | null;
  incomplete: string[];
  state: string;
  derived: Record<string, boolean>;
}

export interface Cause {
  identity?: string;
  label?: string;
  owner?: string;
  kind: string;
  id?: string;
  via?: string;
  citation?: string;
  when?: string;
  diff: string | null;
  current_fragment?: string;
  current_macros?: string;
  comparison?: {
    accepted: string;
    current: string;
    current_macros?: string;
    accepted_macros: string;
    accepted_spans: [number, number][];
    current_spans: [number, number][];
  };
}

/** An update from Overleaf as the manifest keeps the last one: when, how many files, whose changes Review lists, how many only the person made, each change outside a result, and the results changed here that it wrote over. */
export interface OverleafUpdate {
  when: string;
  files: number;
  by: string[];
  own: number;
  /** `place` one of `preamble`, `between`, `removed`, `not-a-document`. */
  places: { file: string; place: string; by: string[] }[];
  here: string[];
}

/** The manifest's `overleaf` (`docs/specs/manifest.md`): `folder` the quilt folder the project is kept in, `main` its main document's quilt path, `link` the project's page in Overleaf, `waiting` Overleaf holds text not yet taken in, `ask_me` ask again who the person is there, `problem` the code of what the last reach of Overleaf could not do. */
export type OverleafState =
  | { paired: false }
  | { paired: true; folder: string; main: string; link: string; waiting: boolean; last: OverleafUpdate | null; ask_me: boolean; problem: string | null };

export interface AdoptionReview {
  kind: 'adopt';
  copy: string;
  source: string;
  label: string;
  fingerprint: string;
  /** Each result the copy changes: `class` is new, proposal-only, removed, separate-result, merged (both sides changed it and their edits fall apart line by line, `merged` the text), or conflict (their edits clash: shown, never offered). `proposed_key` is the copy's own key for it, which names it. */
  changes: {key: string; name: string | null; class: string; current: string; proposed: string; merged?: string; offered?: boolean; proposed_key?: string | null; math_changed: boolean; incoming_macros: string; local: string | null; incoming: string | null; documents: string[]; affected: {key: string; citation: string | null}[]}[];
  document_changed: boolean;
  document_conflict: boolean;
  document_diff: string;
  document_comparison?: {local: string | null; incoming: string | null; current: string; proposed: string; incoming_macros: string};
  scope?: {kind: string; title?: string};
  preamble_changed?: boolean;
  preamble_conflict?: boolean;
  preamble_current?: string;
  preamble_proposed?: string;
  choices: {keys: string[]; document: boolean; preamble?: boolean; kept?: string[]; revision?: number; invalidated?: string[]};
  issues: string[];
}

/** A block of the person's not freshly accepted: why it waits, and why loom cannot accept it, if it cannot. */
export interface UnresolvedReview {
  key: string;
  /** `earlier-change`: its acceptance went stale; `adopted` or `incoming-pull`: taken in; `never-accepted`: no acceptance yet. */
  cause: 'incoming-pull' | 'adopted' | 'earlier-change' | 'never-accepted';
  source_label?: string;
  contribution?: string;
  pull: string;
  changed_text: boolean;
  /** Null means an older sync record has no post-pull baseline. */
  local_changed?: boolean | null;
  /** Why loom cannot accept it, as an agent reads it, naming a directive and keys; '' when it can. The viewer words `refusal_code` instead. */
  refusal: string;
  /** The same reason as a code, '' when it can be accepted; absent from an older publisher. */
  refusal_code?: '' | 'not-yours' | 'incomplete' | 'open-claim' | 'unclassified' | 'unidentified';
  /** The person's own notes on a block marked incomplete, in their TeX; absent from an older publisher. */
  incomplete?: string[];
}

export interface Acceptance {
  author: string;
  date: string;
  fresh: boolean;
  causes?: Cause[];
}

export interface Reviews {
  /** Open annotations by type id. */
  open: Record<string, number>;
  detached: number;
}

export interface Key {
  review_fragment?: string;
  review_macros?: string;
  key: string;
  node: string;
  kind: "statement" | "proof" | (string & {});
  ordinal?: number;
  file: string;
  src: [number, number];
  hash: string;
  incomplete: string[];
  state: string;
  acceptance?: Acceptance;
  acceptances?: Acceptance[];
  reviews: Reviews;
  uses: string[];
  closure: string[];
  previous_key_match: string | null;
  /** The step whose recorded text this key's current text is, when it is one: what "text of @2" is built from. */
  version?: { step: string; name?: string };
  conflict?: string[];
}

export interface Region {
  key: string;
  container: string;
  in: string;
  label: string;
  numbers: Record<string, NumberEntry>;
  src: [number, number];
}

export interface Edge {
  from: string;
  to: string;
  kind: "statement" | "proof" | "prose" | (string & {});
  via: string;
  src?: { file: string; line: number };
}

/** A declared relation between two nodes that is not a dependency: it never enters a closure, a bundle, or a staleness computation (specs/manifest.md §16). */
export interface Relation {
  kind: "see" | (string & {});
  from: string;
  to: string;
}

export interface InclusionNode {
  key: string;
  via?: string;
  file?: string;
  shift?: number;
  children: InclusionNode[];
}

export interface StateLabel {
  label: string;
  color: ColorClass;
  modifier?: boolean;
}

export interface States {
  labels: Record<string, StateLabel>;
  derived: Record<string, StateLabel>;
}

/** How an annotation is drawn: one of the nine colours, a style, a thickness in whole pixels and an opacity in percent. */
export interface Look {
  color: string;
  style: 'underline' | 'highlight' | 'strike';
  weight: number;
  opacity: number;
}

/** A type an annotation may carry: a label with a look, whether its annotations stay open until resolved, and instructions for agents. */
export interface AnnotationType {
  id: string;
  name: string;
  look: Look;
  open: boolean;
  instructions: string;
  /** The modes whose text names this type. */
  modes?: string[];
}

export interface Annotation {
  id: string;
  author: Author;
  created: string;
  /** What it is about: a key in the corpus; a work, by its reference, which `work` repeats, with `page` the page of its PDF, none for the whole work; or a project PDF, with `file` its path and `page`. */
  target: { key: string; hash: string; work?: string | null; page?: number | null; file?: string | null };
  /** The document a claim about a node is read in, as a master path; null for the node wherever it appears. Drawn in that document, listed on the node's page, absent elsewhere. */
  in?: string | null;
  /** On a cited work's page, anchored through its store: `text` when the quotation is located in the page's committed text, `box` when a drawn rectangle is the record. Null for one that records its own place (`rects`). */
  basis?: "text" | "box" | null;
  /** On a PDF page, where it stands now, in points from the page's top left: its words found again on a changed file. */
  rects?: number[][] | null;
  /** A drawing's points, x, y, x, y… per stroke, in points from the page's top left. */
  strokes?: number[][] | null;
  /** The tool it was drawn with: `pin`, `ink`, `text`, `box`, `oval` or `arrow`; null for one on words, which its look's style draws. */
  mark?: string | null;
  /** What it is for beside a note: `to-digest`, the person's mark asking that a result on a work's page be read, which no list of notes holds; null on a note. */
  purpose?: 'to-digest' | null;
  /** On a mark to digest, the stub it locates, by its node's id; null where it names none. */
  node?: string | null;
  /** Where one taken in from a PDF's own annotations came from. */
  origin?: { by?: string; subtype?: string; color?: number[]; ref?: string; sha?: string } | null;
  /** The reference of the PDF's own annotation it stands for, while the file is the one it was taken from: the viewer leaves that one undrawn. */
  hides?: string | null;
  /** The id of one of the quilt's `annotation_types`, or null for an untyped annotation. A type deleted since leaves an id no type has. */
  type: string | null;
  /** The whole look to draw it with, whatever its type now says. */
  look: Look;
  /** The comment as written, in Markdown, which an editor starts from; `body_html` is it rendered. Absent from a publisher that does not say. */
  body?: string;
  body_html: string;
  status: "open" | "resolved";
  in_reply_to: string | null;
  /** Whether the text this was written against can still be produced: the current text, or a version the publisher kept. */
  recorded?: boolean;
  anchored: boolean;
  detached: boolean;
  quote?: string;
  /** Why it was resolved, when it was. */
  resolved_why?: string | null;
  /** The version it was written on, for one whose words are gone (`detached`) and whose version is kept (`recorded`): that version's hash, its key's text as it was with every annotation on it marked (`fragment`, under the build directory), and whether an empty `mark.annotation.gone` stands where its words were in the text now (`at`). */
  version?: AnnotationVersion | null;
  /** For one carried onto new words when a change was kept: the words it was written on, and the change that replaced them. */
  earlier?: { quote: string; change: string } | null;
  /** On a PDF page that is not the one it was written on: true when its words, or the words its drawing stands beside, were found again on the changed file, `target.page`, `rects` and `strokes` being where it stands now. A changed PDF keeps no version, so there is nothing else to open. */
  refound?: boolean | null;
  /** A drawing's place beside the first word under it, `[dx, dy]` in points, by which it is found again on a changed file. */
  gap?: number[] | null;
  /** On a cited work whose source loom holds: where its words are in that source, the work's own TeX. */
  source?: { path: string; bytes: number[]; exact: string } | null;
}

/** The version an annotation was written on (specs/manifest.md §9). */
export interface AnnotationVersion {
  hash: string;
  fragment: string;
  at: boolean;
}

/** A suggested edit (specs/manifest.md §9.2): words a writer proposes to put in place of a quote, beside it or for it, which the person keeps or discards. */
export interface SuggestedEdit {
  id: string;
  author: Author;
  created: string;
  target: { key: string; hash: string };
  /** The words it replaces, or stands beside; with none, the key's body. */
  quote: string | null;
  /** What it puts in; '' with `replace` deletes the quoted words. */
  with: string;
  /** `with` as the publisher's converter renders it in the context of its key; null when it could not be. */
  with_html: string | null;
  /** `replace` takes exactly the quote's place, `after` and `before` go right beside it. */
  placement: string;
  comment: string | null;
  comment_html: string | null;
  /** The annotation it answers, or null. */
  answers: string | null;
  status: 'open' | 'kept' | 'discarded';
  /** Why it was discarded, when it was. */
  why: string | null;
}

export interface Attachment {
  name: string;
  kind: string;
  path?: string;
  count?: number;
}

/** One session as the selector shows it. The id is the address and never changes; the title is the author's and may. */
export interface SessionRow {
  id: string;
  title: string;
  /** What the sitting is for, in the author's words; '' when never stated. */
  purpose?: string;
  /** `open`, `closed`, or `deleted` — a tombstone, which the publisher does not send. */
  state: "open" | "closed" | (string & {});
  created: string;
  /** When the current round opened: what "changed since last time" is measured from. */
  opened: string;
  rounds: number;
  /** Whether this is the publisher's own default for writes made at a terminal. The viewer never reads it: a write names its session (plan 0.13.1). */
  active: boolean;
  /** The last event in this session's inbox. A client that has fallen behind knows it has by comparing its own. */
  seq?: number;
  /** When it was last written in: the newest of its logged commands, its annotations and notes, and its transcript's last message; '' when nothing was. */
  last?: string;
}

export interface Thread {
  id: string;
  kind: "session" | (string & {});
  title: string;
  created: string;
  participants: Author[];
  targets: string[];
  attachments: Attachment[];
  /** The session's command log, a line each: what was run, and the keys and files it names, a moved document under where it is now. */
  log: { time: string; command: string; names?: ({ key: string } | { path: string })[] }[];
  discarded: boolean;
}

export interface Location {
  file: string;
  line: number;
  column?: number;
}

/** What an agent does to resolve a diagnostic: a command, or an edit said in words. Nothing in the viewer runs anything, and a person's problems show none. */
export interface Fix {
  label: string;
  command: string;
  /** A fix a viewer may do itself, as a button: the write-API endpoint and the body to send it. */
  act?: { endpoint: string; body: Record<string, unknown> };
}

export interface Diagnostic {
  severity: Severity;
  code: string;
  message: string;
  locations: Location[];
  keys: string[];
  fixes?: Fix[];
  /** What the diagnostic is about: the source, or loom's own record of it. Absent means `source`. */
  subject?: "source" | "record" | (string & {});
  /** Whose it is to fix: the person's, or an agent's copy's. Absent means the person's. */
  owner?: "person" | "copy" | (string & {});
  /** What kind of problem it is: in a document's LaTeX, a failed compile among them; in loom's model of the quilt, an agent's to keep; or loom's own difficulty. Absent means a document's LaTeX. */
  class?: "latex" | "model" | "internal" | (string & {});
}

export interface Taxon {
  style: string;
  slug: string;
  count: number;
}

/** A page loom keeps, the research state (plan 0.21.3): a reading, never a source. */
export interface Page {
  path: string;
  hash: string;
  body_html: string;
  /** Who last wrote it through loom, and when; absent when nobody has. */
  by?: { kind: "agent" | "person" | (string & {}); id: string };
  when?: string;
  /** Changed by hand since the last write through loom, or never written through it. */
  edited_since: boolean;
  links: { broken: { href: string; why: string }[]; moved: { href: string; key: string }[] };
}

export interface Macro {
  name: string;
  args: number;
  body: string;
}

export interface SearchEntry {
  key: string;
  title: string;
  taxon?: string;
  kind?: string;
  aliases?: string[];
  tags?: string[];
  excerpt?: string;
}

/** An agent app with a file in the quilt that starts loom's server, and whether it does. */
export interface AgentClient {
  key: string;
  label: string;
  file: string;
  set_up: boolean;
  /** What a person runs to set it up, from the publisher; empty when it is set up. */
  command: string;
}

/** What the quilt's configuration holds and what follows from it, for Settings (plan 0.23). */
export interface QuiltSettings {
  /** The `table.key` names Settings may change, and the ones it only shows. */
  editable: string[];
  read_only: string[];
  quilt: { name: string; main: string; home: string; prefix: string; engine: string; history: string; research_state: string };
  library: { online: boolean };
  /** `dir`: where New note puts a note, '' for the default folder `default` names. Absent from an older loom's manifest. */
  notes?: { dir: string; default: string };
  /** `codes`: every diagnostic code that can be silenced. */
  lint: { disable: string[]; codes: string[] };
  agents: {
    deny: string[];
    protected: string[];
    /** Whether the quilt has an agent layer, and how its agents reach loom. */
    layer: boolean;
    variant: 'mcp' | 'shell' | null;
    /** Whether Claude Code's permission file lags the deny list. */
    stale: boolean;
    command: string;
    clients: AgentClient[];
    /** How far the deny list holds for the apps set up here, one sentence: which cannot edit there, which are only asked; '' without an agent layer. */
    holds?: string;
  };
  warnings: string[];
}

/** An agent app the write API's `agents-setup` sets up, and whether the quilt is set up for it (specs/manifest.md, Agents). */
export interface AgentApp {
  key: string;
  label: string;
  set_up: boolean;
}

/** One of the quilt's modes, as its agents are shown them. */
export interface AgentMode {
  name: string;
  /** Its "When it fits" line. */
  fits: string;
  /** The quilt's copy, which an agent reads in place of loom's. */
  path: string;
  /** Whether the quilt's copy is the author's own, differing from what loom wrote. */
  edited: boolean;
  /** The file as a person edits it, the quilt's copy else loom's, each `{type:ID}` as written; absent from an older publisher. */
  text?: string;
  /** Whether `loom upgrade` left a newer version of loom's beside the quilt's edited copy; absent from an older publisher. */
  newer?: boolean;
}

/** How agents are set up in the quilt and what they are told first. */
export interface Agents {
  apps: AgentApp[];
  /** The line loom puts in each app's root file, verbatim; '' with no agent layer. */
  line: string;
  modes: AgentMode[];
}

export interface Manifest {
  reviewer?: { name: string; source: string };
  publisher: Publisher;
  publishes: Publishes;
  generated: string;
  corpus: Corpus;
  masters: Master[];
  canon?: CanonDoc[];
  nodes: Record<string, Node>;
  keys: Record<string, Key>;
  contributions?: AdoptionReview[];
  /** Whether the quilt mirrors an Overleaf project, and how it stands; absent from an older publisher. */
  overleaf?: OverleafState;
  unresolved?: UnresolvedReview[];
  history?: { steps: HistoryStep[]; acts?: HistoryAct[]; files?: HistoryFile[] };
  regions: Record<string, Region>;
  relations?: Relation[];
  edges: Edge[];
  inclusion: Record<string, InclusionNode>;
  states: States;
  annotations: Record<string, Annotation>;
  /** The annotations placed on no block, each by id with the key it was written on, why, and the document it is listed in and opened from; each stays in `annotations`, detached, with `target.key` '', and is counted on no key (specs/manifest.md §9). */
  unplaced?: { id: string; key: string; why: string; document: string }[];
  /** The library's drops that wait on the person, as the intake's rows: each a `question` or a file `received` and not yet taken; empty or absent when none does (manifest.md §1). */
  arriving?: import('$lib/library/api').TakeRow[];
  /** Every suggested edit, by id (specs/manifest.md §9.2). */
  suggested_edits?: Record<string, SuggestedEdit>;
  /** The quilt's annotation types, in its file's order (specs/manifest.md §1). */
  annotation_types?: AnnotationType[];
  /** The plain look: how an annotation with no type that sets no look of its own is drawn (specs/manifest.md §1). */
  annotation_plain?: Look;
  threads: Record<string, Thread>;
  /** Every session the index leaves standing, for the selector: which exists, which loom is writing into, and what round each is on. */
  sessions?: SessionRow[];
  diagnostics: Diagnostic[];
  tags: Record<string, string[]>;
  taxa: Record<string, Taxon>;
  /** The quilt's research state (plan 0.21.3); absent until one is written. */
  research_state?: Page;
  /** Every file of the project the viewer shows, hidden ones left out (plan 0.22.7); absent from an older publisher. */
  files?: ProjectFile[];
  /** Every `quilt:` and `cited:` link the shown files make, raw or bracketed, resolved to what it names, in file and line order; absent from an older publisher. */
  backlinks?: Backlink[];
  /** Every pending change, edits since the reviewer's look and open suggested edits, in each file's order; absent before a first look. */
  changes?: PendingChange[];
  /** The reviewer's look: when it was taken, whose it was carried over from when their name had none, and the places it leaves to the person (the config and each `[agents] deny` entry), where a change is never listed, and how far that holds for the apps set up here. */
  changes_since?: { who: string; when: string; carried?: string; unwatched?: string[]; holds?: string };
  /** The quilt's configuration, for Settings; absent from an older publisher. */
  config?: QuiltSettings;
  /** How agents are set up and what they are told; absent from an older publisher. */
  agents?: Agents;
  macros: { default: Macro[]; sets: Record<string, Macro[]> };
  search: SearchEntry[];
  /** Reserved for work not built yet, which will give each its shape (docs/specs/reserved.md); loom writes none of them. */
  published?: unknown;
  suggested_works?: unknown;
  formal?: unknown;
}

export interface IncorporationMathItem {
  key: string;
  dependencies?: string[];
  name: string;
  reason: string;
  local: {path: string; macros: Macro[]} | null;
  proposed: {path: string; macros: Macro[]};
  unavailable: string;
}
export interface IncorporationMathReview {
  token: string;
  reviewer: string;
  items: IncorporationMathItem[];
}
export interface IncorporationOutcome {
  accepted?: string[];
  pending?: string[];
  acceptance_error?: string;
}
