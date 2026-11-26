// What the viewer says of the Overleaf mirror, from the manifest's `overleaf` and the answers of the `overleaf-*` endpoints, in the words of `words/overleaf.ts`: whether a file mirrors Overleaf, the line beside Update, and a refusal's words by its code. Pure, so the unit tests hold it.

import type { OverleafState, OverleafUpdate } from '$lib/manifest/types';
import { overleaf as words } from '$lib/words/overleaf';

/** What `overleaf-update` answers. */
export type UpdateAnswer = { state: 'up-to-date' } | ({ state: 'updated'; overwritten: string[] } & Omit<OverleafUpdate, 'when'>);

/** The mirror's state when the quilt mirrors a project, else null. */
export function paired(o: OverleafState | undefined): Extract<OverleafState, { paired: true }> | null {
	return o?.paired ? o : null;
}

/** Whether quilt path `path` lies in the folder that mirrors Overleaf, which only an update writes. */
export function mirrors(o: OverleafState | undefined, path: string): boolean {
	const p = paired(o);
	return !!p?.folder && path.startsWith(`${p.folder}/`);
}

/** A refusal's words by its code; loom's own sentence is never said. */
export function problemSaid(code: string | null | undefined): string {
	return code ? (words.problem[code] ?? words.problem.other) : '';
}

/** When an update was, as the line says it: "on 26 Nov at 15:04", or "just now" within the minute. */
export function whenSaid(iso: string, now: Date = new Date()): string {
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return '';
	if (Math.abs(now.getTime() - d.getTime()) < 60_000) return words.update.now;
	return words.update.at(d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }), d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }));
}

/** An update's sentences: what it changed and by whom, how many changes only the person made it leaves out of Review, each change outside a result, the results changed here it wrote over, and, right after the press, the files it wrote over. */
function updateLines(u: Omit<OverleafUpdate, 'when'> & { overwritten?: string[] }, when: string): string[] {
	const lines = [words.update.updated(when, u.files, u.by)];
	if (u.own > 0) lines.push(words.update.own(u.own));
	if (u.places.length) lines.push(words.update.places(u.places.map((p) => words.update.place(p.file, words.update.where[p.place] ?? '', p.by))));
	if (u.here.length) lines.push(words.update.here(u.here.length));
	if (u.overwritten?.length) lines.push(words.update.overwritten(u.overwritten));
	return lines;
}

/**
 * The line beside Update, as the manifest has the mirror.
 *
 * Parameters
 * ----------
 * o : OverleafState
 *     The manifest's `overleaf`, paired.
 * now : Date, optional
 *     The time now, for saying when the last update was.
 *
 * Returns
 * -------
 * str
 *     What the last update did, or that there has been none; then what the last reach of Overleaf could not do, if anything.
 */
export function standing(o: Extract<OverleafState, { paired: true }>, now: Date = new Date()): string {
	const lines = o.last ? updateLines(o.last, whenSaid(o.last.when, now)) : [words.update.never];
	if (o.problem) lines.push(problemSaid(o.problem));
	return lines.join(' ');
}

/** The line right after pressing Update, from what `overleaf-update` answered. */
export function answered(a: UpdateAnswer): string {
	return a.state === 'up-to-date' ? words.update.upToDate : updateLines(a, words.update.now).join(' ');
}
