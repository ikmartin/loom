// What the column's message says after an act in Results to accept or Proposed edits: what was done, then what was not, in the viewer's words: a refusal by its code where loom gives one (a keep's or discard's), or by the queue's `refusal_code` on the block (an accept's, whose refusals carry no code), else a plain sentence naming what was not done. Loom's own sentence is written for the command line and is never said. Pure, so the unit tests hold it.

import type { UnresolvedReview } from '$lib/manifest/types';
import { frame } from '$lib/words/frame';
import { review as words } from '$lib/words/review';

const lower = (t: string) => t.charAt(0).toLowerCase() + t.slice(1);

/** A refusal's reason by its code: Review's word for it, else the frame's, else none. */
function why(code: string | undefined, own: Record<string, string>): string | undefined {
	if (!code) return undefined;
	return own[code] ?? (frame.refused[code] ? lower(frame.refused[code]) : undefined);
}

/**
 * The message after accepting.
 *
 * Parameters
 * ----------
 * accepted : string[]
 *     The keys loom accepted.
 * refused : string[]
 *     The keys it refused, its sentences dropped.
 * name : (key) => string
 *     A block's name.
 * row : (key) => UnresolvedReview | undefined
 *     A block's row in the queue, whose `refusal_code` says why it cannot be accepted.
 *
 * Returns
 * -------
 * str
 */
export function acceptSaid(accepted: string[], refused: string[], name: (key: string) => string, row: (key: string) => UnresolvedReview | undefined): string {
	const lines = accepted.length ? [accepted.length === 1 ? words.accepted.acceptedOne(name(accepted[0])) : words.accepted.acceptedMany(accepted.length)] : [];
	for (const k of refused) lines.push(words.accepted.notAccepted(name(k), why(row(k)?.refusal_code, words.accepted.why)));
	return lines.join(' ');
}

/**
 * The message after keeping or discarding changes.
 *
 * Parameters
 * ----------
 * how : 'keep' | 'discard'
 * done : int
 *     How many loom kept or discarded.
 * refused : { code?: string }[]
 *     Those it refused, their sentences dropped.
 *
 * Returns
 * -------
 * str
 *     What was done, then a line for each reason something was not.
 */
export function changeSaid(how: 'keep' | 'discard', done: number, refused: { code?: string }[]): string {
	const lines = done || !refused.length ? [how === 'keep' ? words.edits.keptAll(done) : words.edits.discardedAll(done)] : [];
	const by = new Map<string | undefined, number>();
	for (const r of refused) {
		const w = why(r.code, words.edits.why);
		by.set(w, (by.get(w) ?? 0) + 1);
	}
	for (const [w, n] of by) lines.push(words.edits.notDone(how, n, w));
	return lines.join(' ');
}
