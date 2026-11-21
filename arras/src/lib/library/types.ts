// The shapes the views read and write for the rebuilt library, as `docs/specs/library-views.md` gives them: what each read answers and each write takes. Ids are for addressing and never drawn; every row carries its words beside them.

/** How a library node's reading of its paper stands (`evidence.md` §5.2, `reading`), or `marked`, a place the person marked to digest and nothing read from yet. */
export type Paper = 'stub' | 'unchecked' | 'matches' | 'marked';

/** How a result's Lean stands, as `evidence.md` §5.2 computes it. */
export interface LeanStatus {
	lean: 'none' | 'rerun' | 'failed' | 'unattested' | 'changed' | 'waiting' | 'formalized';
	role?: 'proved' | 'unproved' | 'assumed' | 'defined';
	/** Each library result that keeps it from reading formalized, and why. */
	waiting_on?: { node: string; why: 'stub' | 'unchecked' | 'unattested' | 'unknown' }[];
}

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

/** A node's place on its page, or a mark's (`library-places`, §3.3). */
export interface Place {
	node?: string;
	mark?: string;
	name?: string;
	number?: string;
	page: number;
	rects: Rect[];
	paper: Paper;
	lean?: LeanStatus | null;
}

export interface PlacesAnswer extends Gen {
	pdf: Hash;
	places: Place[];
}

/** A result wherever results are listed (§2, "A result in a list"). */
export interface Row {
	result: string;
	name: string;
	title?: string;
	taxon: string;
	source: { ref: string; short: string } | { doc: string } | null;
	paper: Paper | null;
	lean: LeanStatus | null;
	choose?: boolean;
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
