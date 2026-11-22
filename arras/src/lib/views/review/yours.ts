// Review's two kinds that today's Your Changes draws on a served quilt, in place of round six's rows for them: "Accepted results that changed" shows its Waiting to be accepted section whole, "Proposed edits" its Changes to keep and the agents' copies. The column counts for them what these sections list as waiting, and a draft narrows them as it narrows every kind.

import type { Manifest } from '$lib/manifest/types';
import type { ReviewKind, ReviewList } from '$lib/library/types';
import { isAgentDocument } from '$lib/manifest/documents';
import { byDocument, pending, type ChangeGroup } from '$lib/review/changes';
import { adoptionsOf } from '$lib/review/proposed';
import { documentsWithBlocks } from '$lib/review/queue';
import { acceptanceOf } from '$lib/review/yourChanges';

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

/** The blocks the accept section lists as waiting, changed since accepted or taken in, each once; in one draft when given. Never accepted and accepted blocks are folded there and count nothing. */
export function acceptWaiting(m: Manifest, doc?: string | null): number {
	const keys = new Set<string>();
	for (const d of blockDocuments(m)) {
		if (doc && d.path !== doc) continue;
		const a = acceptanceOf(m, d.path);
		for (const b of [...a.changed, ...a.taken.flatMap((t) => t.rows)]) keys.add(b.key);
	}
	return keys.size;
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
