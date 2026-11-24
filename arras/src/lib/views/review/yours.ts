// Review's two kinds that today's Your Changes draws on a served quilt, in place of round six's rows for them: "Accepted results that changed" shows its Waiting to be accepted section, every document's blocks by document, "Proposed edits" its Changes to keep and the agents' copies. The column counts for them what these sections list as waiting, and a draft narrows them as it narrows every kind.

import type { Manifest } from '$lib/manifest/types';
import type { ReviewKind, ReviewList } from '$lib/library/types';
import { isAgentDocument } from '$lib/manifest/documents';
import { byDocument, pending, type ChangeGroup } from '$lib/review/changes';
import { adoptionsOf } from '$lib/review/proposed';
import { documentsWithBlocks } from '$lib/review/queue';
import { acceptanceOf, waitingIn, type Acceptance } from '$lib/review/yourChanges';

/** Which section of Your Changes a kind draws. */
export type Part = 'accept' | 'changes';

/** The kinds Your Changes draws, by the section each shows. */
export const PARTS = { 'accepted-changed': 'accept', edits: 'changes' } as const satisfies Partial<Record<ReviewKind, Part>>;

export type YoursKind = keyof typeof PARTS;

/** The two kinds, as a list. */
export const YOURS = Object.keys(PARTS) as YoursKind[];

/** Whether Your Changes draws this kind. */
export const isYours = (kind: string): kind is YoursKind => kind in PARTS;

/** The person's documents with blocks to accept, as the accept section offers them: open, read in full, and no agent's. */
export function blockDocuments(m: Manifest): Manifest['masters'] {
	return documentsWithBlocks(
		m,
		m.masters.filter((x) => !x.closed && !x.context_only && !isAgentDocument(x))
	);
}

/** One document's part of the accept section. */
export interface AcceptSection {
	path: string;
	/** The document's file name. */
	file: string;
	/** Its blocks, less those an earlier document lists. */
	a: Acceptance;
}

/** What the accept section draws: each document with blocks, its own blocks grouped by why they wait, each block once, under the first document that reads it; one draft's only when given. Never accepted and accepted blocks are folded there and count nothing. */
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

/** The blocks the accept section lists as waiting, changed since accepted or taken in, each once; in one draft when given. */
export function acceptWaiting(m: Manifest, doc?: string | null): number {
	return acceptSections(m, doc).reduce((n, s) => n + waitingIn(s.a), 0);
}

/** The changes the changes section draws, by the document listing them: every one, or, in a draft, one group of those in its text. Changes just kept or discarded (`gone`) are left out at once. */
export function changeGroups(m: Manifest, gone: Record<string, unknown>, doc?: string | null): ChangeGroup[] {
	const groups = doc ? [{ path: doc, label: doc.split('/').pop() ?? doc, document: true, changes: pending(m).filter((c) => c.documents?.includes(doc)) }] : byDocument(m);
	return groups.map((g) => ({ ...g, changes: g.changes.filter((c) => !(c.id in gone)) })).filter((g) => g.changes.length);
}

/** The agents' copies waiting to be taken in; those into one draft when given. */
export function copiesOf(m: Manifest, doc?: string | null) {
	return adoptionsOf(m).filter((c) => !doc || c.source === doc);
}

/** The cards the changes section lists as waiting: each change and each agent's copy. */
export function changesWaiting(m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return changeGroups(m, gone, doc).reduce((n, g) => n + g.changes.length, 0) + copiesOf(m, doc).length;
}

/** What a kind Your Changes draws counts, in one draft when given. */
export function yoursCount(kind: YoursKind, m: Manifest, gone: Record<string, unknown>, doc?: string | null): number {
	return PARTS[kind] === 'accept' ? acceptWaiting(m, doc) : changesWaiting(m, gone, doc);
}

/** How many of loom's rows of one kind concern a draft, from its whole list; null before the list is read. */
export function theirs(list: ReviewList | null, doc: string): number | null {
	return list ? list.groups.reduce((n, g) => n + g.rows.filter((r) => r.docs.includes(doc)).length, 0) : null;
}
