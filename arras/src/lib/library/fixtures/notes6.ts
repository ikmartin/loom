// The notes tab's part of round six's fixture: the prototype's notes, two that lost their place, answered as `notes` will answer them and changed by `delete`. Written from the spec (`docs/specs/library-views.md` §6.3) until that read is served.

import type { Note, NotesAnswer, NotesGroup } from '../types';

const MAIN = 'drafting/main.tex';
const BOUNDS = 'drafting/bounds.tex';

/** Round six's notes, newest first, and the older ones a group holds beyond them. */
export function notes6(refs: Record<string, string>): Note[] {
	const n = (annotation: string, color: string, quote: string, message: string, by: string, at: string, at_place: Note['at_place'], extra: Partial<Note> = {}): Note => ({ annotation, color, quote, message, by, at, tags: [], at_place, ...extra });
	const arden = { ref: refs.arden24, page: 2, short: 'Arden 2024' };
	return [
		n('a-o1', 'rgb(218 172 0)', 'the boundary operator commutes with restriction', 'Check this against the old proof of 2.4.', 'you', '2026-11-14T10:00:00Z', null, { was: 'old-intro.tex, deleted 14 Nov' }),
		n('a-o2', 'rgb(26 111 196)', 'a spanning forest gives a basis', 'Is the forest chosen once for all components?', 'you', '2026-11-12T10:00:00Z', null, { was: 'Arden 2024, its PDF replaced 17 Nov' }),
		n('a-n1', 'rgb(204 28 28)', 'is saturated by Proposition 2.6', 'Saturation needs the quiver connected; say so.', 'you', '2026-11-19T10:00:00Z', { doc: MAIN, key: 'thm:rank' }),
		n('a-n5', 'rgb(255 205 0)', 'as the half-plane of Example 2.2 shows', '', 'you', '2026-11-19T09:00:00Z', { ref: refs.smith, page: 1, short: 'Smith 2024' }),
		n('a-n2', 'rgb(218 172 0)', 'the median-order technique of [2, Theorem 2.3]', 'Read Okafor before relying on this.', 'you', '2026-11-18T12:00:00Z', { doc: MAIN, key: 'sec:intro' }),
		n('a-n3', 'rgb(116 67 204)', 'a loop counting as one arrow', 'Fine.', 'Claude Code', '2026-11-18T11:00:00Z', { doc: MAIN, key: 'conv:finite' }),
		n('a-n4', 'rgb(218 172 0)', 'whose coordinates sum to zero on each component', 'This is the form main.tex uses.', 'you', '2026-11-18T10:00:00Z', arden),
		n('a-s1', '#b4b2a9', '', 'A short paper fixing notation for cycle spaces; Sections 2 and 5 are what main.tex uses.', 'Claude Code', '2026-11-18T09:00:00Z', arden, { tags: ['summary'] }),
		...Array.from({ length: 6 }, (_, i) => n(`a-m${i}`, 'rgb(218 172 0)', `an older passage of main.tex, ${i + 1}`, '', 'you', `2026-11-0${i + 1}T10:00:00Z`, { doc: MAIN, key: 'sec:intro' })),
		n('a-a9', 'rgb(26 111 196)', 'an older passage of Arden 2024', '', 'you', '2026-11-02T10:00:00Z', arden),
		...Array.from({ length: 3 }, (_, i) => n(`a-b${i}`, 'rgb(204 28 28)', `a passage of bounds.tex, ${i + 1}`, '', 'you', `2026-11-1${i}T08:00:00Z`, { doc: BOUNDS, key: 'thm:radius' }))
	];
}

const groupOf = (n: Note): string => (!n.at_place ? 'orphaned' : 'doc' in n.at_place ? n.at_place.doc : n.at_place.ref);
const byDate = (a: Note, b: Note) => b.at.localeCompare(a.at);

/** `notes`. */
export function notesAnswer(all: Note[], a: { sort: string; orphaned?: boolean; group?: string; offset?: number }): Omit<NotesAnswer, 'gen'> {
	const shown = all.filter((n) => a.orphaned !== false || n.at_place).sort(byDate);
	const orphaned = all.filter((n) => !n.at_place).length;
	if (a.group) {
		const rest = shown.filter((n) => groupOf(n) === a.group);
		return { notes: rest.slice(a.offset ?? 0), more: 0 };
	}
	if (a.sort === 'date') {
		const at = a.offset ?? 0;
		return { orphaned, notes: shown.slice(at, at + 20), more: Math.max(0, shown.length - at - 20) };
	}
	const order: string[] = [];
	for (const n of shown) if (!order.includes(groupOf(n))) order.push(groupOf(n));
	// the orphaned first, then the drafts, then the works
	order.sort((x, y) => (x === 'orphaned' ? -1 : y === 'orphaned' ? 1 : Number(!x.endsWith('.tex')) - Number(!y.endsWith('.tex'))));
	const groups: NotesGroup[] = order.map((g) => {
		const ns = shown.filter((n) => groupOf(n) === g);
		const first = ns[0].at_place;
		const group: NotesGroup['group'] = g === 'orphaned' ? 'orphaned' : first && 'doc' in first ? { doc: g } : { ref: g, short: (first as { short?: string }).short ?? '' };
		return { group, n: ns.length, notes: g === 'orphaned' ? ns : ns.slice(0, 3), more: g === 'orphaned' ? 0 : Math.max(0, ns.length - 3) };
	});
	return { orphaned, groups };
}
