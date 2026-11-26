// The sessions as the viewer lists them: each conversation's report, reached from Review › History. Nothing in the viewer chooses one: an agent writes in its own conversation's session, and a person's writes name none.

import type { Manifest, SessionRow } from '$lib/manifest/types';

class SessionView {
	/** Names asked for and not yet in the manifest, by session id: a rename shows at once rather than after the publisher rebuilds. */
	renamed = $state<Record<string, string>>({});
}

export const sessionView = new SessionView();

/** A session's name as the reader last set it: the pending rename while the manifest still carries the old one. */
export function titleOf(s: SessionRow): string {
	return sessionView.renamed[s.id] ?? s.title;
}

/** The sessions, open then closed, each most recently touched first. */
export function grouped(m: Manifest | null): { open: SessionRow[]; closed: SessionRow[] } {
	const rows = m?.sessions ?? [];
	// Most recently touched first. The index is append-only and was shown in creation order, so the sitting you were in five minutes ago sat at the bottom of the list under everything you had finished with.
	const recent = (a: SessionRow, b: SessionRow) => (b.opened || b.created).localeCompare(a.opened || a.created);
	return {
		open: rows.filter((s) => s.state === 'open').sort(recent),
		closed: rows.filter((s) => s.state !== 'open').sort(recent)
	};
}

