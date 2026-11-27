// Keep or discard several changes at once, from Proposed edits' head line or a file's row, and say in the column's message what was done and why any was not.

import { said } from '$lib/library/said';
import { discardChanges, keepChanges } from '$lib/review/history.svelte';
import { message } from '$lib/shell/message.svelte';
import { changeSaid } from './answers';

/** Keeps or discards `ids`; the column's message says how many, and why any was not, in the viewer's words (`changeSaid`), or loom's refusal of the whole by its code. */
export async function every(how: 'keep' | 'discard', ids: string[]): Promise<void> {
	const res = how === 'keep' ? await keepChanges({ changes: ids }) : await discardChanges({ changes: ids });
	if (!res.ok) return message.post(said({ code: res.error?.code ?? 'failed', message: res.error?.message ?? '' }));
	const refused = res.refused ?? [];
	message.post(changeSaid(how, res.done?.length ?? ids.length - refused.length, refused));
}
