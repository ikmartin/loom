// The list of works as the person narrows it: by a filter of the column, by words in a title or an author's name, and in the order of the column they sorted by, the title breaking ties. The viewer holds all of the library's rows (300 at the sizes in use), so this is done here and asks the publisher nothing.

import type { Work } from '$lib/library/types';
import type { Column, Filter } from './state.svelte';

/** Whether a work passes a filter of the column. */
export function passes(w: Work, filter: Filter): boolean {
	if (filter === 'used') return w.used_in.length > 0;
	if (filter === 'unchecked') return !!w.digested && w.digested.compared < w.digested.statements;
	if (filter === 'nodoc') return !w.holds.pdf && !w.holds.tex;
	return true;
}

/** Whether a work's title or an author's name holds the words typed, ignoring case. */
export function matches(w: Work, q: string): boolean {
	const words = q.trim().toLowerCase();
	return !words || `${w.title} ${w.authors.join(' ')}`.toLowerCase().includes(words);
}

/** What a column sorts a work by. */
function key(w: Work, col: Column): string | number {
	if (col === 'title') return w.title.toLowerCase();
	if (col === 'authors') return (w.authors[0] ?? '~').toLowerCase();
	if (col === 'year') return Number(w.year) || 0;
	if (col === 'digested') return w.digested ? 0 : 1;
	if (col === 'holds') return (w.holds.pdf ? 2 : 0) + (w.holds.tex ? 1 : 0);
	return w.used_in[0] ?? '~';
}

/** The works shown: those passing the filter and holding the words, sorted by `sort.key` in `sort.dir`, the title breaking ties. */
export function shown(works: readonly Work[], o: { filter: Filter; q: string; sort: { key: Column; dir: 1 | -1 } }): Work[] {
	const out = works.filter((w) => passes(w, o.filter) && matches(w, o.q));
	return out.sort((a, b) => {
		const x = key(a, o.sort.key);
		const y = key(b, o.sort.key);
		return (x < y ? -1 : x > y ? 1 : 0) * o.sort.dir || a.title.localeCompare(b.title);
	});
}
