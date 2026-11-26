// The Overleaf mirror's acts, shared by Settings › Overleaf, Update on a mirrored document's toolbar and Done in Overleaf on a change: one update at a time, the line its answer leaves (`mirror.said`), and the token Overleaf asked for, given once and the update tried again. Every sentence is `said.ts`'s, from the words file; loom's own are never shown.

import { landed } from '$lib/manifest/updating.svelte';
import { keepChanges } from '$lib/review/history.svelte';
import { overleaf as words } from '$lib/words/overleaf';
import { write, type WriteResult } from '$lib/write';
import { answered, problemSaid, type UpdateAnswer } from './said';

/** The refusals after which Overleaf wants a token pasted. */
export const ASKS_TOKEN = new Set(['no-token', 'token-refused']);

/** Where the mirror's last press stands, for every control that shows it. */
export const mirror = $state({
	/** An update is under way. */
	busy: false,
	/** The line the last press left, '' before one; it outlives the control that pressed. */
	said: '',
	/** Whether that line says something was not done. */
	refused: false,
	/** The refusal's code, when Overleaf asked for a token: the token field shows until one is given. */
	asks: ''
});

/** What Copy new text or Done in Overleaf last said on each change, by its id: kept here, since the change's card is drawn again while Keep is tried (shown kept at once, then back when refused). */
export const told: Record<string, { text: string; refused: boolean }> = $state({});

/** The answer's own fields: `write` passes the endpoint's `result` through untyped. */
const result = <T>(res: WriteResult) => res.result as unknown as T;

/**
 * Update from Overleaf: fetch, and take what Overleaf holds into the mirrored folder as one act.
 *
 * Returns
 * -------
 * bool
 *     Whether loom updated, or found nothing new; `mirror.said` says which, or why not.
 */
export async function updateNow(): Promise<boolean> {
	if (mirror.busy) return false;
	mirror.busy = true;
	const res = await write('overleaf-update', {});
	mirror.busy = false;
	if (res.ok) {
		Object.assign(mirror, { said: answered(result<UpdateAnswer>(res)), refused: false, asks: '' });
		await landed();
		return true;
	}
	const code = res.error?.code ?? '';
	Object.assign(mirror, { said: problemSaid(code), refused: true, asks: ASKS_TOKEN.has(code) ? code : '' });
	return false;
}

/**
 * Give loom the git token Overleaf asked for, then do again what asked for it.
 *
 * Parameters
 * ----------
 * token : str
 *     As pasted.
 * link : str, optional
 *     The project's link, before the quilt is paired.
 *
 * Returns
 * -------
 * str
 *     '' when loom kept it, else the refusal's words.
 */
export async function giveToken(token: string, link?: string): Promise<string> {
	const res = await write('overleaf-token', { token: token.trim(), ...(link ? { link } : {}) });
	if (!res.ok) return problemSaid(res.error?.code);
	mirror.asks = '';
	return '';
}

/**
 * Done in Overleaf: update, then keep change `id`, which loom records kept, writing nothing, once Overleaf's text has it.
 *
 * Parameters
 * ----------
 * id : str
 *     The change, one in the mirrored folder.
 *
 * Returns
 * -------
 * { kept: bool, said: str }
 *     Whether it is kept, and what to say: kept, Overleaf does not have it yet, or why the update could not be made.
 */
export async function doneInOverleaf(id: string): Promise<{ kept: boolean; said: string }> {
	if (!(await updateNow())) return { kept: false, said: mirror.said };
	const res = await keepChanges({ changes: [id] });
	if (res.ok && (res.done ?? []).includes(id)) return { kept: true, said: words.change.kept };
	const code = res.ok ? res.refused?.find((r) => r.id === id)?.code : res.error?.code;
	return { kept: false, said: code === 'mirrored' || code === undefined ? words.change.notYet : problemSaid(code) };
}
