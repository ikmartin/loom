// The shapes the views read and write for the rebuilt library, as `docs/specs/library-views.md` gives them: what each read answers and each write takes. Ids are for addressing and never drawn; every row carries its words beside them.

/** How a library node's reading of its paper stands (`evidence.md` §5.2, `reading`), or `marked`, a place the person marked to digest and nothing read from yet. */
export type Paper = 'stub' | 'unchecked' | 'matches' | 'marked';

/** How a result's Lean stands, `evidence.md` §5.2's `lean`. */
export type Lean = 'none' | 'rerun' | 'failed' | 'unattested' | 'changed' | 'waiting' | 'formalized';

/** What keeps a result from reading formalized (`evidence.md` §5.2): a node, one of the person's results its Lean assumes, or a citation's key with its locator where it has one; and why. */
export type WaitingOn = ({ node: string } | { label: string } | { cite: string }) & { why: 'stub' | 'unchecked' | 'unattested' | 'unknown' };

/** How a result's Lean stands, as `evidence.md` §5.2 computes it, with its role and what it waits on: `{lean: "none", role: null, waiting_on: []}` where no record names it. */
export interface LeanStatus {
	lean: Lean;
	role?: 'proved' | 'unproved' | 'assumed' | 'defined' | null;
	waiting_on?: WaitingOn[];
}

/** The reading of a library result's paper (`evidence.md` §5.2), null for a draft's result. */
export type Reading = 'stub' | 'unchecked' | 'matches' | null;

/** How a node's text was made (`evidence.md` §3.1). */
export type How = 'extracted' | 'transcribed' | 'read' | 'corrected' | 'written';

/** A content hash as an answer carries it, `sha256:` and 64 hexadecimal digits. */
export type Hash = string;

/** What every answer carries: the library's generation, and, for a read given the current one as `since`, that nothing changed. */
export interface Gen {
	gen: number;
	unchanged?: true;
}

/** A row of the works list (`library-works`, §3.1). */
export interface Work {
	ref: string;
	short: string;
	title: string;
	authors: string[];
	year: string;
	holds: { pdf: Hash | null; tex: boolean };
	digested: { statements: number; of: number | null; compared: number; stubs: number } | null;
	used_in: string[];
	link: string | null;
	version: number | string | null;
	/** A work still being looked up, or made while the network was off; `identifier` is `scheme:value`, the scheme lower-case. */
	lookup: { state: 'looking' | 'unconfirmed'; identifier: string } | null;
	cited_as: string | null;
}

export interface WorksAnswer extends Gen {
	works: Work[];
}

/** A section of a work's outline. */
export interface Section {
	section: string;
	number: string;
	title: string;
	page: number | null;
	level: number;
}

/** An entry of a work's outline: an item of its TeX source's survey, digested or not, or one of its nodes (§3.2). */
export interface OutlineItem {
	item: string | null;
	node: string | null;
	name: string;
	title?: string;
	taxon: string;
	section: string | null;
	page: number | null;
	paper: Paper | null;
	lean: LeanStatus | null;
}

/** A person's mark to digest on a work's page: an annotation of kind `to-digest`. */
export interface DigestMark {
	mark: string;
	page: number;
	words: string;
}

/** One work, for its tab (`library-work`, §3.2). */
export interface WorkAnswer extends Gen {
	ref: string;
	short: string;
	title: string;
	authors: string[];
	year: string;
	holds: { pdf: Hash | null; pages: number | null; tex: boolean };
	entry: string;
	link: string | null;
	outline: {
		from: 'tex' | 'pdf' | null;
		state: 'ready' | 'reading';
		sections: Section[];
		items: OutlineItem[];
	} | null;
	marks: DigestMark[];
	unplaced: { node: string; name: string; paper: Paper }[];
}

/** The counts of a `digest…` menu (`library-digest-scopes`): a work's, or every work's with `all`. */
export interface DigestScopes extends Gen {
	tex?: boolean;
	pdf?: boolean;
	used: number;
	marked?: number;
	all?: number | null;
}

export type DigestScope = 'used' | 'marked' | 'chosen' | 'all';

/** What `library-digest` answers: nodes written now from TeX sources, one agent task a work held only as a PDF, and the survey's job where one must run first. */
export interface DigestDone extends Gen {
	made: number;
	tasks: string[];
	job?: string;
}

/** A rectangle on a PDF page, in points from its top left: x0, y0, x1, y1. */
export type Rect = [number, number, number, number];

/** Where an annotation on a work's PDF stands (`library-places`, §3.3): its page and a rectangle a line. */
export interface AnnotationPlace {
	annotation: string;
	page: number;
	rects: Rect[];
}

/** A node's place on its page, which joins `library-places` with the digest; round six's fixture answers it. */
export interface NodePlace {
	node: string;
	name?: string;
	number?: string;
	page: number;
	rects: Rect[];
	paper: Paper;
	lean?: LeanStatus | null;
	/** The words of loom's copy the page does not have where it stands, found as its place is: what the check names beside the page; [] where every word is there. */
	lacks?: string[];
}

export type Place = AnnotationPlace | NodePlace;

export interface PlacesAnswer extends Gen {
	pdf: Hash;
	places: Place[];
}

/** A result wherever results are listed (§2, "A result in a list"; `evidence.md` §8): `title` null where it has none, `paper` and `reading` null for a draft's result, `lean` how it stands in Lean. */
export interface Row {
	result: string;
	name: string;
	title: string | null;
	taxon: string;
	source: { ref: string; short: string } | { doc: string } | null;
	paper: Paper | null;
	reading: Reading;
	lean: LeanStatus | null;
}

/** What a body points at, drawn in the pointer's place: a result's name and number and its mark, or an anchor's number; `work` marks a result of another work, drawn as a citation with the result as its locator. */
export interface Point {
	name?: string;
	number?: string;
	page?: string;
	work?: string;
	paper?: Paper | null;
}

/** A node beside its page, or a card (`library-node`, §3.4). */
export interface NodeAnswer extends Gen {
	node?: string;
	hash?: Hash;
	name: string;
	title?: string;
	taxon: string;
	work: { ref: string; short: string; pdf: Hash | null };
	pages?: string;
	digested: { how: How; by: string; at: string } | null;
	paper: Paper | null;
	lean?: LeanStatus | null;
	body?: string;
	macros?: { node: string; hash: Hash; body: string } | null;
	points?: Record<string, Point>;
	uses?: Row[];
	mentions?: Row[];
	proofs?: { node: string; source: { ref: string; short: string } | null; pages: string; pointer: boolean }[];
	used_by?: { docs: string[]; nodes: number };
}

/** Where loom finds words on a work's pages (`library-find`): its one guess, a page it opens at. */
export interface FindAnswer extends Gen {
	pdf: Hash;
	hits: { page: number; rects: Rect[] }[];
	pages: number;
}

/** A write's answer, beyond `gen`. */
export interface WriteDone extends Gen {
	[key: string]: unknown;
}

// ---- Review (`docs/specs/library-views.md` §4; which rows each kind holds, and the asks' shapes, are `evidence.md`'s) ----

/** A kind of row waiting for the person; the tasks waiting for an agent are `agents`, apart from these. */
export type ReviewKind = 'accepted-changed' | 'questions' | 'attested-changed' | 'cited' | 'check' | 'attest' | 'fetch' | 'edits';

/** What the column counts (`review-counts`): a row once whatever it holds; a draft the rows that concern it. */
export interface ReviewCounts extends Gen {
	everything: number;
	kinds: Partial<Record<ReviewKind, number>>;
	agents: number;
	drafts: { doc: string; n: number }[];
}

interface RowBase {
	/** Made from what the row is about, so it stays the same while that waits and an open row stays open. */
	row: string;
	/** The drafts it concerns. */
	docs: string[];
}

/** A text drawn in a body: a fragment of the build, by its path, a change in it marked as a pending change's is (`span.change[data-side]`). */
export interface Statement {
	fragment: string;
}

export interface AcceptedChangedRow extends RowBase {
	kind: 'accepted-changed';
	key: string;
	name: string;
	doc: string;
	reading: Reading;
	lean: LeanStatus;
}

/** The place an ask is tied to (`evidence.md` §4.1), by ids: a node, a draft's label, a block of a document, a work or one of its pages, or a document. The viewer looks each up to name it. */
export interface AskedOn {
	node?: string;
	label?: string;
	block?: { key: string; hash?: string; context?: unknown };
	ref?: string;
	page?: number;
	document?: string;
}

export interface QuestionRow extends RowBase {
	kind: 'questions';
	/** The ask's id, which `review-answer` names. */
	question: string;
	by: string;
	on: AskedOn;
	text: string;
	choices: string[];
	quote: string | null;
	/** The task the asking agent's session was working on when it asked, its work where it names one; null where none. */
	under: { task: string; what: string; on: AskedOn; ref: string | null } | null;
}

/** A cause of an attestation's going stale (`evidence.md` §5.2): what changed, by its label or node, and its hash then and now, either null. */
export interface Cause {
	changed: { label: string } | { node: string } | { notation: string };
	then: Hash | null;
	now: Hash | null;
}

export interface AttestedChangedRow extends RowBase {
	kind: 'attested-changed';
	result: string;
	name: string;
	doc: string;
	changed: 'statement' | 'used';
	causes: Cause[];
	/** The attestation's record, and when it was made. */
	attestation: string;
	attested_at: string;
	reading: Reading;
	lean: LeanStatus;
	/** The results that rest under this one, each attested again one by one. */
	resting: { result: string; name: string }[];
}

/** A stub a draft cites, in a cited row. */
export interface CitedStub {
	node: string;
	name: string;
	rests: { docs: string[] };
	not_in_source: boolean;
	marked: boolean;
}

/** A work with stubs the drafts cite, or (`citation` set) a citation that names no result. */
export type CitedRow =
	| (RowBase & { kind: 'cited'; ref: string; short: string; holds: { pdf: boolean; tex: boolean }; stubs: CitedStub[]; citation?: undefined })
	| (RowBase & { kind: 'cited'; citation: string; doc: string; key: string; where: string; ref: string; short: string; citekey: string });

/** A digested node to check, in a check row. */
export interface CheckNode {
	node: string;
	name: string;
	/** Its number as its source prints it, which the row puts first ("3.2 Lemma"). */
	number?: string;
	title?: string;
	rests: { docs: string[]; through?: string };
	how: How;
}

/** A work's digested results to check, or (`correction` set) an agent's correction to a node the person compared. */
export type CheckRow =
	| (RowBase & { kind: 'check'; ref: string; short: string; pdf: Hash | null; nodes: CheckNode[]; correction?: undefined })
	| (RowBase & { kind: 'check'; correction: string; node: string; name: string; ref: string; short: string; by: string });

export interface AttestRow extends RowBase {
	kind: 'attest';
	result: string;
	name: string;
	source: { doc: string } | { ref: string; short: string };
	what: 'statement and proof' | 'statement only';
	paper: Paper | null;
	/** The Lean record to attest. */
	record: string;
	reading: Reading;
	lean: LeanStatus;
}

export interface FetchRow extends RowBase {
	kind: 'fetch';
	task: string;
	ref: string;
	link: string;
	want: 'pdf' | 'tex';
	by: string;
	words: string;
}

export interface EditRow extends RowBase {
	kind: 'edits';
	change: string;
	type: 'suggested' | 'edit';
	doc: string;
	key: string;
	where: string;
	/** Who suggested it; null for an edit made in place. */
	by: string | null;
	state: string;
	broke: { line: number; error: string } | null;
}

export type ReviewRow = AcceptedChangedRow | QuestionRow | AttestedChangedRow | CitedRow | CheckRow | AttestRow | FetchRow | EditRow;

/** A task waiting for an agent: what was asked (`evidence.md` §4.1's `what`), where, by ids, and the ask's own fields by its `what`, from which the viewer names it. */
export interface TaskRow extends RowBase {
	kind: 'agents';
	task: string;
	what: string;
	on: AskedOn;
	working: { by: string } | null;
	asked_at: string;
	words?: string;
	nodes?: string[];
	marks?: string[];
	ref?: string;
	scope?: 'uses' | 'marked' | 'chosen' | 'all';
	text?: string;
	quote?: string;
	target?: { label?: string; node?: string };
	differs?: string;
	cites?: string;
	state?: string[];
	prove?: string[];
	assume?: string[];
}

/** One group of the list (`review-list`), in the order the list draws them. */
export interface ReviewGroup {
	kind: ReviewKind | 'agents';
	rows: (ReviewRow | TaskRow)[];
}

export interface ReviewList extends Gen {
	groups: ReviewGroup[];
}

/** An agent's correction's body: the word diff of the two texts, each run kept (`=`), taken out (`-`) or put in (`+`), and when the person compared the text it corrects. */
export interface CorrectionBody {
	compared_at: string;
	runs: ['=' | '-' | '+', string][];
}

/** A row's body's fields, by its kind (`review-row`): accepted-changed's and edits' the text with its change marked. */
export interface RowBody {
	statement?: Statement;
	[field: string]: unknown;
}

/** `review-row`: the row as it waits now, and its body (`{}` where its kind has none yet). */
export interface ReviewBody extends Gen {
	row: ReviewRow | TaskRow;
	body: RowBody;
}

// ---- the Web (`docs/specs/library-views.md` §5) ----

/** What the Web shows: the library, one draft, a draft and what it rests on, or everything. */
export type WebScope = 'library' | 'draft' | 'deps' | 'all';

/** A row of works or documents in the list, its rows sent only while it is open. */
export interface WebGroup {
	group: string;
	short?: string;
	title?: string;
	doc?: string;
	n: number;
	rows?: Row[];
}

export interface WebSection {
	head: 'draft' | 'uses' | 'drafts' | 'library';
	doc?: string;
	rows?: Row[];
	groups?: WebGroup[];
}

/** `web-list`: by document, its sections; by status, its rows, two hundred at a time. */
export interface WebList extends Gen {
	count: number;
	sections?: WebSection[];
	undigested?: number;
	rows?: Row[];
	more?: number;
}

/** `web-group`: an opened group's rows, as `web-list` counts it. */
export interface WebGroupAnswer extends Gen {
	group: string;
	n: number;
	rows: Row[];
}

/** `web-search`: hits, each with the words of its statement around the match where the match is there, null for a hit on the name or title. */
export interface WebSearch extends Gen {
	count: number;
	hits: { row: Row; snippet: { before: string; match: string; after: string } | null }[];
}

/** A result's text in the focus card: a draft's fragment, or a library node's body as `library-node` gives it. */
export type WebStatement = Statement | { body: string; macros: string | null; points: Record<string, Point> };

/** `web-focus`: the result, its statement, its standing in Lean in rows, and its neighbourhood. */
export interface WebFocus extends Gen {
	row: Row;
	statement: WebStatement | null;
	relative_to: Row[] | null;
	rests_on: Row[];
	more: { proofs: { where: string | { ref: string; short: string; pages: string }; uses: Row[] }[]; lean: string[]; record: { act: string; by: string; at: string }[] } | null;
	uses: { statement: Row[]; proof: Row[]; outside: { statement: number; proof: number } };
	used_by: { rows: Row[]; outside: number; more: number };
}

/** `web-graph`: the four columns' results, what each holds beyond the five it draws, and the edges among them, `from` using `to`. */
export interface WebGraph extends Gen {
	focus: Row;
	excerpt: string;
	columns: { back: Row[]; uses: Row[]; used_by: Row[] };
	more: { back: number; uses: number; used_by: number };
	edges: { from: string; to: string; proof: boolean }[];
}

// ---- the notes tab (`docs/specs/library-views.md` §6.3) ----

/** A note as the notes tab draws it; `at_place` null for one that lost its place. */
export interface Note {
	annotation: string;
	color: string;
	quote: string;
	message: string;
	by: string;
	at: string;
	tags: string[];
	at_place: { doc: string; key: string } | { ref: string; page: number; short?: string } | null;
	was?: string;
}

export interface NotesGroup {
	group: { doc: string } | { ref: string; short: string } | 'orphaned';
	n: number;
	notes: Note[];
	more: number;
}

/** `notes`: by work, the groups, three notes a group; by date, twenty notes at a time; a group asked for with `offset`, its rest. */
export interface NotesAnswer extends Gen {
	orphaned?: number;
	groups?: NotesGroup[];
	notes?: Note[];
	more?: number;
}

// ---- formalization (`docs/specs/library-views.md` §6.4, §6.6) ----

/** `formal-marks`: whether formalization is on for the quilt, and each result of the draft's Lean mark. */
export interface FormalMarks extends Gen {
	on: boolean;
	marks: Record<string, 'formalized' | 'not' | 'attest' | 'assumed'>;
}

/** A result in the formalize panel: a draft's carries its fragment, its statement one click away. */
export type PlanRow = Row & { fragment?: string };

/** `formal-plan`: what an agent would state, prove and assume, what stops the request and what keeps it from reading formalized. */
export interface FormalPlan extends Gen {
	targets: { key: string; name: string; title?: string; doc: string; statement: Statement }[];
	state: PlanRow[];
	prove: (PlanRow & { assume: boolean })[];
	assume: (PlanRow & { why: 'not-read' | 'not-checked' | null })[];
	formalized: PlanRow[];
	stops: PlanRow[];
	before: { why: 'not-read' | 'not-checked' | 'attest' | 'attested-changed'; results: PlanRow[] }[];
}
