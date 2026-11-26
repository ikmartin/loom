// Accepting from Results to accept, one row's block or those chosen together (`rv.picked`): what loom accepts leaves the list once the manifest is read again, and the column's message says what was accepted and, a sentence each, what was refused and why.

import { said } from '$lib/library/said';
import { store } from '$lib/manifest/client.svelte';
import { displayNode } from '$lib/nodes/display';
import { message } from '$lib/shell/message.svelte';
import { review as words } from '$lib/words/review';
import { write, type WriteResult } from '$lib/write';
import { rv } from './state.svelte';

/** What is being accepted: a block's key, `*` for those chosen together, or '' while nothing is. */
export const accepting = $state({ at: '' });

/**
 * Accepts `keys` at once.
 *
 * Parameters
 * ----------
 * keys : string[]
 *     The blocks, by key.
 * at : string
 *     Where it was asked: the row's key, or `*` for those chosen together.
 * docs : Record<string, string>
 *     The document each block is listed under, which names it.
 */
export async function acceptKeys(keys: string[], at: string, docs: Record<string, string>): Promise<void> {
	const m = store.manifest;
	if (!m || accepting.at) return;
	const name = (key: string) => displayNode(m, key, docs[key]).name;
	accepting.at = at;
	const done = (await write('review-accept', { keys })) as WriteResult & { accepted?: string[]; refused?: { key: string; why: string }[] };
	if (!done.ok) {
		accepting.at = '';
		message.post(said({ code: done.error?.code ?? 'failed', message: done.error?.message ?? '' }));
		return;
	}
	const ok = done.accepted ?? [];
	for (const k of ok) rv.picked.delete(k);
	const lines = ok.length ? [ok.length === 1 ? words.accepted.acceptedOne(name(ok[0])) : words.accepted.acceptedMany(ok.length)] : [];
	for (const r of done.refused ?? []) lines.push(`${name(r.key)}: ${r.why.charAt(0).toLowerCase()}${r.why.slice(1)}`);
	await store.refresh();
	accepting.at = '';
	message.post(lines.join(' '));
}
