import { describe, expect, it } from 'vitest';
import type { Work } from '$lib/library/types';
import { matches, passes, shown } from './works';

const work = (o: Partial<Work>): Work => ({ ref: 'r', short: '', title: 'T', authors: [], year: '', holds: { pdf: null, tex: false }, digested: null, used_in: [], link: null, version: null, lookup: null, cited_as: null, ...o });

describe('the list of works', () => {
	const smith = work({ ref: 'a', title: 'Widgets and their bounds', authors: ['Smith'], year: '2024', holds: { pdf: 'sha256:1', tex: true }, digested: { statements: 11, of: 62, compared: 2, stubs: 1 }, used_in: ['drafting/bounds.tex'] });
	const jones = work({ ref: 'b', title: 'Covering estimates', authors: ['Jones'], year: '2019' });
	const okafor = work({ ref: 'c', title: 'Median orders on weighting lattices', authors: ['Okafor'], year: '2022', holds: { pdf: 'sha256:2', tex: false }, digested: { statements: 2, of: null, compared: 2, stubs: 0 } });

	it('filters as the column says', () => {
		expect([smith, jones, okafor].filter((w) => passes(w, 'used')).map((w) => w.ref)).toEqual(['a']);
		expect([smith, jones, okafor].filter((w) => passes(w, 'unchecked')).map((w) => w.ref)).toEqual(['a']);
		expect([smith, jones, okafor].filter((w) => passes(w, 'nodoc')).map((w) => w.ref)).toEqual(['b']);
		expect([smith, jones, okafor].filter((w) => passes(w, 'all'))).toHaveLength(3);
	});

	it('finds words in a title or an author, ignoring case', () => {
		expect(matches(smith, 'WIDGETS')).toBe(true);
		expect(matches(smith, 'smi')).toBe(true);
		expect(matches(smith, 'okafor')).toBe(false);
		expect(matches(smith, '  ')).toBe(true);
	});

	it('sorts by a column either way, the title breaking ties', () => {
		const by = (key: 'title' | 'year' | 'digested', dir: 1 | -1) => shown([smith, jones, okafor], { filter: 'all', q: '', sort: { key, dir } }).map((w) => w.ref);
		expect(by('title', 1)).toEqual(['b', 'c', 'a']);
		expect(by('title', -1)).toEqual(['a', 'c', 'b']);
		expect(by('year', 1)).toEqual(['b', 'c', 'a']);
		// digested first, then by title
		expect(by('digested', 1)).toEqual(['c', 'a', 'b']);
	});

	it('finds a name typed without its accents, and puts a work with no year last whichever way the years run', () => {
		const ws = [work({ title: 'A', authors: ['Kovač'], year: '1982' }), work({ title: 'B', authors: ['Smith'] }), work({ title: 'C', authors: ['Arden'], year: '2024' })];
		expect(shown(ws, { filter: 'all', q: 'kovac', sort: { key: 'title', dir: 1 } }).map((w) => w.title)).toEqual(['A']);
		expect(shown(ws, { filter: 'all', q: '', sort: { key: 'year', dir: 1 } }).map((w) => w.title)).toEqual(['A', 'C', 'B']);
		expect(shown(ws, { filter: 'all', q: '', sort: { key: 'year', dir: -1 } }).map((w) => w.title)).toEqual(['C', 'A', 'B']);
	});
});
