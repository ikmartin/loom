import { describe, expect, it } from 'vitest';
import type { Work } from '$lib/library/types';
import { cameAs, matches, passes, shown } from './works';
import { candidate } from '$lib/library/intake';

const work = (o: Partial<Work>): Work => ({ ref: 'r', short: '', title: 'T', authors: [], year: '', holds: { pdf: null, tex: false }, digested: null, used_in: [], link: null, version: null, lookup: null, cited_as: null, ...o });

describe('the list of works', () => {
	const smith = work({ ref: 'a', title: 'Widgets and their bounds', authors: ['Smith'], year: '2024', holds: { pdf: 'sha256:1', tex: true }, digested: { statements: 11, of: 62, compared: 2, stubs: 1 }, used_in: ['drafting/bounds.tex'] });
	const jones = work({ ref: 'b', title: 'Covering estimates', authors: ['Jones'], year: '2019' });
	const okafor = work({ ref: 'c', title: 'Median orders on weighting lattices', authors: ['Okafor'], year: '2022', holds: { pdf: 'sha256:2', tex: false }, digested: { statements: 2, of: null, compared: 2, stubs: 0 } });

	it('filters as the column says', () => {
		expect([smith, jones, okafor].filter((w) => passes(w, 'used')).map((w) => w.ref)).toEqual(['a']);
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

describe('two works stating one identifier', () => {
	const unconfirmed = { state: 'unconfirmed' as const, identifier: 'arxiv:2401.01234v1' };
	it('an unconfirmed row says the name it came in as, unless that is the identifier itself', () => {
		expect(cameAs({ title: 'b.pdf', lookup: unconfirmed })).toBe('b.pdf');
		expect(cameAs({ title: 'arXiv 2401.01234v1', lookup: unconfirmed })).toBe('');
		expect(cameAs({ title: 'Widgets', lookup: null })).toBe('');
	});
	it('the question names each by its short name, and by its title as well where two short names are alike', () => {
		const c = (short: string, title: string) => ({ ref: short + title, short, title, authors: [], year: '', how: 'arxiv:2401.01234v1' });
		const files = [c('b.pdf', 'b.pdf'), c('b3.pdf', 'b3.pdf')];
		expect(files.map((x) => candidate(x, files))).toEqual(['b.pdf', 'b3.pdf']);
		const twins = [c('Arden 2024', 'Cycle spaces of finite quivers'), c('Arden 2024', 'Rank of a cycle space')];
		expect(twins.map((x) => candidate(x, twins))).toEqual(['Arden 2024 · Cycle spaces of finite quivers', 'Arden 2024 · Rank of a cycle space']);
		expect(candidate(c('', ''), [])).toBe('arXiv 2401.01234v1');
	});
});
