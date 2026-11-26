// The session verbs of Review › History › Sessions, so a session is renamed, closed, reopened or deleted one way.

import { store } from '$lib/manifest/client.svelte';
import type { SessionRow } from '$lib/manifest/types';
import { write } from '$lib/write';
import { sessionView } from './sessions.svelte';

async function act(id: string, endpoint: string, body: Record<string, unknown> = {}): Promise<boolean> {
	const res = await write(endpoint, { session: id, ...body });
	void store.refresh();
	return res.ok;
}

/** Rename, shown at once: the list drops the pending name when the manifest carries it. */
export async function renameSession(s: SessionRow, want: string): Promise<boolean> {
	sessionView.renamed[s.id] = want;
	const ok = await act(s.id, 'session-rename', { title: want });
	if (!ok) delete sessionView.renamed[s.id];
	return ok;
}

/** Close. */
export async function closeSession(id: string): Promise<boolean> {
	return act(id, 'session-close');
}

/** Reopen. */
export async function reopenSession(id: string): Promise<boolean> {
	return act(id, 'session-reopen');
}

/** Delete: a tombstone in the index; its annotations stay in the log. */
export async function deleteSession(id: string): Promise<boolean> {
	return act(id, 'session-delete');
}
