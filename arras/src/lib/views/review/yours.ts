// Review's two kinds drawn from the manifest rather than from loom's `review-list`, since their acts are the manifest's: "Results to accept", a row for each block waiting (changed since accepted, or taken in from a copy or a pull), the never accepted and the accepted folded beneath; "Proposed edits", a row for each change waiting in the person's text and for each agent's copy. The column counts for them the rows drawn, and a draft narrows them as it narrows every kind.

import type { Key, Manifest, PendingChange, UnresolvedReview } from '$lib/manifest/types';
import type { ReviewKind, ReviewList } from '$lib/library/types';
import { isAgentDocument } from '$lib/manifest/documents';
import { byDocument, pending, type ChangeGroup } from '$lib/review/changes';
import { adoptionsOf } from '$lib/review/proposed';
import { documentsWithBlocks } from '$lib/review/queue';
import { acceptanceOf, waitingIn, type Acceptance, type BlockRow } from '$lib/review/yourChanges';

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

/** What Results to accept draws: the rows waiting, by document, each document's changed blocks before those taken in; beneath, folded and counting nothing, the never accepted and the accepted. */
export interface AcceptList {
	waiting: AcceptItem[];
	never: AcceptItem[];
	accepted: { key: string; doc: string; k: Key }[];
}

/** Results to accept's rows, every draft's or one draft's. */
export function acceptList(m: Manifest, doc?: string | null): AcceptList {
	const out: AcceptList = { waiting: [], never: [], accepted: [] };
	for (const s of acceptSections(m, doc)) {
		const item = (b: BlockRow, taken?: string): AcceptItem => ({ key: b.key, doc: s.path, row: b.row!, ...(taken ? { taken } : {}) });
		out.waiting.push(...s.a.changed.map((b) => item(b)), ...s.a.taken.flatMap((t) => t.rows.map((b) => item(b, t.label))));
		out.never.push(...s.a.never.map((b) => item(b)));
		out.accepted.push(...s.a.accepted.map((k) => ({ key: k.key, doc: s.path, k })));
	}
	return out;
}

/** The blocks Results to accept lists as waiting, changed since accepted or taken in, each once; in one draft when given. */
export function acceptWaiting(m: Manifest, doc?: string | null): number {
	return acceptSections(m, doc).reduce((n, s) => n + waitingIn(s.a), 0);
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

/** The agents' copies waiting to be taken in; those into one draft when given. */
export function copiesOf(m: Manifest, doc?: string | null) {
	return adoptionsOf(m).filter((c) => !doc || c.source === doc);
}

/** The rows Proposed edits draws: each change and each agent's copy. */
export function changesWaiting(m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return changeList(m, gone, doc).length + copiesOf(m, doc).length;
}

/** What a kind drawn from the manifest counts, in one draft when given: its rows waiting. */
export function yoursCount(kind: YoursKind, m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return kind === 'accepted-changed' ? acceptWaiting(m, doc) : changesWaiting(m, gone, doc);
}

/** How many of loom's rows of one kind concern a draft, from its whole list; null before the list is read. */
export function theirs(list: ReviewList | null, doc: string): number | null {
	return list ? list.groups.reduce((n, g) => n + g.rows.filter((r) => r.docs.includes(doc)).length, 0) : null;
}
