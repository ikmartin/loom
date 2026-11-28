// Review's two kinds drawn from the manifest rather than from loom's `review-list`, since their acts are the manifest's: "Results to accept", a row for each block waiting (changed since accepted, or taken in from Overleaf) and one for each adoption of an agent's copy, holding the blocks it took in, the never accepted and the accepted folded beneath; "Proposed edits", a row for each file with edits made in place since the look (holding that file's changes, and a document's those of the files it loads beside its text), for each suggested edit and for each agent's copy. The column counts for them the rows drawn, and a draft narrows them as it narrows every kind.

import type { Key, Manifest, PendingChange, UnresolvedReview } from '$lib/manifest/types';
import type { ReviewKind, ReviewList } from '$lib/library/types';
import { isAgentDocument } from '$lib/manifest/documents';
import { byDocument, pending, type ChangeGroup } from '$lib/review/changes';
import { adoptionsOf } from '$lib/review/proposed';
import { documentsWithBlocks, takenLabel } from '$lib/review/queue';
import { acceptanceOf, type Acceptance, type BlockRow } from '$lib/review/yourChanges';

/** The two kinds drawn from the manifest. */
export const YOURS = ['accepted-changed', 'edits'] as const satisfies ReviewKind[];

export type YoursKind = (typeof YOURS)[number];

/** Whether this kind is drawn from the manifest. */
export const isYours = (kind: string): kind is YoursKind => (YOURS as readonly string[]).includes(kind);

/** The person's documents with blocks to accept, as the accept section offers them: open, read in full, and no agent's. */
export function blockDocuments(m: Manifest): Manifest['masters'] {
	return documentsWithBlocks(
		m,
		m.masters.filter((x) => !x.closed && !x.context_only && !isAgentDocument(x))
	);
}

/** One document's blocks, each once, under the first document that reads it. */
export interface AcceptSection {
	path: string;
	/** The document's file name. */
	file: string;
	/** Its blocks, less those an earlier document lists. */
	a: Acceptance;
}

/** Each document with blocks, its own blocks grouped by why they wait, each block once, under the first document that reads it; one draft's only when given. */
export function acceptSections(m: Manifest, doc?: string | null): AcceptSection[] {
	const seen = new Set<string>();
	const once = <T extends { key: string }>(rows: T[]): T[] => rows.filter((b) => (seen.has(b.key) ? false : (seen.add(b.key), true)));
	const out: AcceptSection[] = [];
	for (const d of blockDocuments(m)) {
		if (doc && d.path !== doc) continue;
		const g = acceptanceOf(m, d.path);
		const a: Acceptance = { changed: once(g.changed), taken: g.taken.map((t) => ({ label: t.label, rows: once(t.rows) })).filter((t) => t.rows.length), never: once(g.never), accepted: once(g.accepted) };
		if (a.changed.length || a.taken.length || a.never.length || a.accepted.length) out.push({ path: d.path, file: d.path.split('/').pop() ?? d.path, a });
	}
	return out;
}

/** A block as a row of Results to accept: the document it is listed under, which names it, why it waits, and for one taken in, where from. */
export interface AcceptItem {
	key: string;
	doc: string;
	row: UnresolvedReview;
	taken?: string;
}

/** An adoption waiting in Results to accept: the blocks one agent's copy brought in, each under the document that lists it, in the order they are listed. */
export interface AdoptionItem {
	/** The copy, by path; for a block that names none, where it came from as its group is headed. */
	copy: string;
	/** The copy's name. */
	name: string;
	/** The document listing its first block, which its row names. */
	doc: string;
	blocks: AcceptItem[];
}

/** A row of Results to accept: a block of its own, or an adoption, which opens to its blocks. */
export type AcceptRowItem = ({ type: 'block' } & AcceptItem) | ({ type: 'adoption' } & AdoptionItem);

/** What Results to accept draws: the rows waiting (`rows`), by document, each document's changed blocks before those taken in, an adoption one row standing where its first block does; every block those rows hold (`waiting`); beneath, folded and counting nothing, the never accepted and the accepted. */
export interface AcceptList {
	rows: AcceptRowItem[];
	waiting: AcceptItem[];
	never: AcceptItem[];
	accepted: { key: string; doc: string; k: Key }[];
}

/** A copy's name: its file's, without `.tex`. */
const copyName = (path: string): string => (path.split('/').pop() ?? path).replace(/\.tex$/, '');

/** The copy an adopted block came from, which its adoption's row is one for; null for a block not taken in from a copy. */
export const adoptionOf = (row: UnresolvedReview): string | null => (row.cause === 'adopted' ? (row.contribution ?? takenLabel(row)) : null);

/** Results to accept's rows, every draft's or one draft's. */
export function acceptList(m: Manifest, doc?: string | null): AcceptList {
	const out: AcceptList = { rows: [], waiting: [], never: [], accepted: [] };
	const adoptions = new Map<string, Extract<AcceptRowItem, { type: 'adoption' }>>();
	for (const s of acceptSections(m, doc)) {
		const item = (b: BlockRow, taken?: string): AcceptItem => ({ key: b.key, doc: s.path, row: b.row!, ...(taken ? { taken } : {}) });
		const waiting = [...s.a.changed.map((b) => item(b)), ...s.a.taken.flatMap((t) => t.rows.map((b) => item(b, t.label)))];
		out.waiting.push(...waiting);
		for (const b of waiting) {
			const copy = adoptionOf(b.row);
			if (copy === null) {
				out.rows.push({ type: 'block', ...b });
				continue;
			}
			const row = adoptions.get(copy);
			if (row) row.blocks.push(b);
			else {
				const r = { type: 'adoption' as const, copy, name: b.row.contribution ? copyName(b.row.contribution) : copy, doc: b.doc, blocks: [b] };
				adoptions.set(copy, r);
				out.rows.push(r);
			}
		}
		out.never.push(...s.a.never.map((b) => item(b)));
		out.accepted.push(...s.a.accepted.map((k) => ({ key: k.key, doc: s.path, k })));
	}
	return out;
}

/** The rows Results to accept draws as waiting: each block changed since accepted or taken in from Overleaf, each once, and each adoption; in one draft when given. */
export function acceptWaiting(m: Manifest, doc?: string | null): number {
	return acceptList(m, doc).rows.length;
}

/** The changes Proposed edits draws, by the document listing them: every one, or, in a draft, one group of those in its text. Changes just kept or discarded (`gone`) are left out at once. */
export function changeGroups(m: Manifest, gone: Record<string, unknown>, doc?: string | null): ChangeGroup[] {
	const groups = doc ? [{ path: doc, label: doc.split('/').pop() ?? doc, document: true, changes: pending(m).filter((c) => c.documents?.includes(doc)) }] : byDocument(m);
	return groups.map((g) => ({ ...g, changes: g.changes.filter((c) => !(c.id in gone)) })).filter((g) => g.changes.length);
}

/** A change as a row of Proposed edits: the document whose text holds it, null for one in no document's, and what its group is called. */
export interface ChangeItem {
	c: PendingChange;
	doc: string | null;
	label: string;
}

/** Proposed edits' rows of changes, by document, in the order `changeGroups` gives. */
export function changeList(m: Manifest, gone: Record<string, unknown>, doc?: string | null): ChangeItem[] {
	return changeGroups(m, gone, doc).flatMap((g) => g.changes.map((c) => ({ c, doc: g.document ? g.path : null, label: g.label })));
}

/** A row of Proposed edits: a suggested edit alone, or a file with edits made in place, which opens to each of them; a document's own file holds too the edits to the files it loads beside its text (`also`, by path). */
export type EditRow = ({ type: 'suggested' } & ChangeItem) | ({ type: 'file'; path: string; changes: PendingChange[]; also: string[] } & Omit<ChangeItem, 'c'>);

/** Whether a change was made in the file rather than suggested. */
export const inPlace = (c: Pick<PendingChange, 'kind'>): boolean => c.kind !== 'suggested';

/** Proposed edits' rows of changes, by document as `changeList` orders them: each suggested edit, and one row a file for the edits made in place, standing where the file's first change stands; a file a document loads beside its text folded into that document's row (`folded`). */
export function editRows(m: Manifest, gone: Record<string, unknown>, doc?: string | null): EditRow[] {
	return folded(m, fileRows(m, gone, doc));
}

/** Each suggested edit, and one row a file for the edits made in place. */
function fileRows(m: Manifest, gone: Record<string, unknown>, doc?: string | null): EditRow[] {
	const out: EditRow[] = [];
	const files = new Map<string, Extract<EditRow, { type: 'file' }>>();
	for (const i of changeList(m, gone, doc)) {
		if (!inPlace(i.c)) {
			out.push({ type: 'suggested', ...i });
			continue;
		}
		// a file is one row within the document listing it
		const at = `${i.doc ?? ''}\n${i.c.path}`;
		const row = files.get(at);
		if (row) row.changes.push(i.c);
		else {
			const r = { type: 'file' as const, path: i.c.path, changes: [i.c], also: [], doc: i.doc, label: i.label };
			files.set(at, r);
			out.push(r);
		}
	}
	return out;
}

/** The rows with each file a document loads beside its text (its `loads`, of which only a LaTeX file such as a preamble is watched for edits) folded into the row of the document's own file, where it has one, which then holds its edits too; the first such document in the quilt's order takes it, and a file whose document has no row stays a row of its own. */
function folded(m: Manifest, rows: EditRow[]): EditRow[] {
	type FileRow = Extract<EditRow, { type: 'file' }>;
	const files = rows.filter((r): r is FileRow => r.type === 'file');
	const own = new Map<string, FileRow>();
	for (const r of files) if (!own.has(r.path)) own.set(r.path, r);
	const live = m.masters.filter((d) => !d.closed && !d.context_only);
	const ranked = [...live.filter((d) => !isAgentDocument(d)), ...live.filter((d) => isAgentDocument(d))];
	const gone = new Set<FileRow>();
	for (const r of files) {
		if (r.also.length) continue;
		const host = ranked.find((d) => d.path !== r.path && d.loads?.includes(r.path) && own.has(d.path) && !gone.has(own.get(d.path)!));
		if (!host) continue;
		const into = own.get(host.path)!;
		into.changes.push(...r.changes);
		into.also.push(r.path);
		gone.add(r);
	}
	return rows.filter((r) => r.type !== 'file' || !gone.has(r));
}

/** The agents' copies waiting to be taken in; those into one draft when given. */
export function copiesOf(m: Manifest, doc?: string | null) {
	return adoptionsOf(m).filter((c) => !doc || c.source === doc);
}

/** The rows Proposed edits draws: each file with edits made in place, each suggested edit and each agent's copy. */
export function changesWaiting(m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return editRows(m, gone, doc).length + copiesOf(m, doc).length;
}

/** What a kind drawn from the manifest counts, in one draft when given: its rows waiting. */
export function yoursCount(kind: YoursKind, m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return kind === 'accepted-changed' ? acceptWaiting(m, doc) : changesWaiting(m, gone, doc);
}

/** How many of loom's rows of one kind concern a draft, from its whole list; null before the list is read. */
export function theirs(list: ReviewList | null, doc: string): number | null {
	return list ? list.groups.reduce((n, g) => n + g.rows.filter((r) => r.docs.includes(doc)).length, 0) : null;
}
