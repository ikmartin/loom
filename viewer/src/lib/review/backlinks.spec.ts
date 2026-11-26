// The Notes list beside an item: the files whose links name it, by what loom resolved each link to.
import { describe, expect, it } from 'vitest';
import type { Backlink, Manifest } from '$lib/manifest/types';
import { noteFiles, noteHref } from './backlinks';

const link = (from: string, line: number, kind: string, key: string, place = '', quote = ''): Backlink => ({ from, line, href: `quilt:${key}`, kind, key, place, quote });

const m = {
	nodes: { 'sy-0003': { reached_by: ['drafting/main.tex'] }, 'sy-0004': { reached_by: ['drafting/talk.tex'] } },
	keys: { 'sy-0003': { node: 'sy-0003' }, 'sy-0003/proof': { node: 'sy-0003' }, 'sy-0004': { node: 'sy-0004' } },
	regions: { 'sy-0003#eq:fix': { container: 'sy-0003' } },
	files: [
		{ path: 'notes/reading.org', kind: 'text' },
		{ path: 'notes/lemma.md', kind: 'markdown' },
		{ path: 'notes/book.ipynb', kind: 'notebook' }
	],
	backlinks: [
		link('notes/reading.org', 2, 'work', 'sy-0099-ref', 'page=2', 'the words'),
		link('notes/reading.org', 5, 'work', 'sy-0099-ref'),
		link('notes/lemma.md', 3, 'document', 'drafting/main.tex', 'sy-0003', 'every vertex'),
		link('notes/b.md', 1, 'node', 'sy-0003/proof'),
		link('notes/c.md', 1, 'node', 'sy-0003#eq:fix'),
		link('notes/d.md', 1, 'node', 'sy-0004'),
		link('notes/e.md', 1, 'file', 'papers/median.pdf', 'page=1', 'incidence matrix')
	]
} as unknown as Manifest;

describe('the notes beside an item', () => {
	it('are the files whose links name it, each with its links in line order', () => {
		expect(noteFiles(m, 'work:sy-0099-ref')).toEqual([{ path: 'notes/reading.org', links: [m.backlinks![0], m.backlinks![1]] }]);
		expect(noteFiles(m, 'file:papers/median.pdf').map((f) => f.path)).toEqual(['notes/e.md']);
	});
	it('count a link to a node, its proof or an equation of it, for each document that reaches it', () => {
		expect(noteFiles(m, 'document:drafting/main.tex').map((f) => f.path)).toEqual(['notes/b.md', 'notes/c.md', 'notes/lemma.md']);
		expect(noteFiles(m, 'document:drafting/talk.tex').map((f) => f.path)).toEqual(['notes/d.md']);
		expect(noteFiles(m, 'node:sy-0003').map((f) => f.path)).toEqual(['notes/b.md', 'notes/c.md']);
	});
	it('are none where nothing links, or the publisher says nothing', () => {
		expect(noteFiles(m, 'work:sy-0100-ref')).toEqual([]);
		expect(noteFiles({ ...m, backlinks: undefined }, 'work:sy-0099-ref')).toEqual([]);
	});
	it('open the note at its link, at the line in a plain-text file', () => {
		expect(noteHref(m, m.backlinks![0])).toBe('quilt:notes/reading.org#L2');
		expect(noteHref(m, m.backlinks![2])).toBe('quilt:notes/lemma.md');
		// a Markdown note at the heading above its link
		expect(noteHref(m, { ...m.backlinks![2], at: 'the-lemma' })).toBe('quilt:notes/lemma.md#the-lemma');
		// a notebook at the heading above its link too, rather than its top
		expect(noteHref(m, { ...m.backlinks![2], from: 'notes/book.ipynb', at: 'orbits' })).toBe('quilt:notes/book.ipynb#orbits');
	});
});
