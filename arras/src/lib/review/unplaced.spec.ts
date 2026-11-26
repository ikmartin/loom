import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import type { Annotation, Manifest } from '$lib/manifest/types';
import { masterUrl } from '$lib/nav';
import { itemForQuilt } from '$lib/workspace/links';
import { keyName, linkName } from '$lib/workspace/names';
import { APART, apartIn, apartOf, documentOf, notesApart, notesHere, noteUrl, placeOf, PLAIN, whyApart } from './annotating.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn(async () => {}) }));

const fixture = JSON.parse(readFileSync('tests/fixture/manifest.json', 'utf8')) as Manifest;

function note(id: string, over: Partial<Annotation> = {}): Annotation {
	return {
		id,
		author: { kind: 'person', id: 'Tester' },
		created: '2026-11-20',
		target: { key: '', hash: 'sha256:x' },
		type: 'note',
		look: { ...PLAIN },
		body_html: '<p>cite the classification</p>',
		status: 'open',
		in_reply_to: null,
		anchored: false,
		detached: true,
		...over
	};
}

/** The fixture with a note on no block written on sy-0003 (read in `drafting/main.tex`). */
function withUnplaced(): Manifest {
	const m = structuredClone(fixture);
	m.annotations = { ...m.annotations, u: note('u') };
	m.unplaced = [{ id: 'u', key: 'sy-0003', why: 'its block was deleted', document: 'drafting/main.tex' }];
	return m;
}

describe('a note on no block', () => {
	it('is named by no key', () => {
		const m = withUnplaced();
		expect(keyName(m, '')).toBe('');
		expect(linkName(m, 'quilt:u')).toBe('Note on no block');
	});

	it('belongs to the document it was written in, and a link to it opens that document at the note', () => {
		const m = withUnplaced();
		expect(documentOf(m, m.annotations.u)).toBe('drafting/main.tex');
		expect(itemForQuilt(m, 'u')).toEqual({ kind: 'document', id: 'drafting/main.tex', note: 'u' });
		expect(noteUrl(m, m.annotations.u)).toBe(masterUrl('drafting/main.tex') + '?note=u');
	});

	it('is listed apart in its own document’s Comments and Notes, and counted in its Notes badge', () => {
		const m = withUnplaced();
		expect(apartIn(m, 'drafting/main.tex')).toEqual(['u']);
		expect(apartIn(m, 'drafting/talk.tex')).toEqual([]);
		const here = { order: [], apart: ['u'], hidden: [], todo: false, layer: 'all' as const };
		expect(apartOf(m, here, false).map((a) => a.id)).toEqual(['u']);
		expect(apartOf(m, { ...here, layer: 'changes' }, false)).toEqual([]);
		expect(apartOf(m, { ...here, hidden: ['Tester'] }, false)).toEqual([]);
		expect(notesApart(m, here).map((a) => a.id)).toEqual(['u']);
		expect(notesHere(m, here)).toBe(1);
		expect(placeOf(m, m.annotations.u)).toBe(APART);
	});
});

describe('a note on no block whose written key names nothing now', () => {
	it('is listed in, and opens from, the document the manifest gives it', () => {
		const m = withUnplaced();
		m.annotations.w = note('w');
		m.unplaced = [...(m.unplaced ?? []), { id: 'w', key: 'drafting/sections/gone.tex#lemma:3', why: 'The block it was written on is gone, and nothing says where its words went.', document: 'drafting/talk.tex' }];
		expect(documentOf(m, m.annotations.w)).toBe('drafting/talk.tex');
		expect(apartIn(m, 'drafting/talk.tex')).toEqual(['w']);
		expect(apartIn(m, 'drafting/main.tex')).toEqual(['u']);
		expect(itemForQuilt(m, 'w')).toEqual({ kind: 'document', id: 'drafting/talk.tex', note: 'w' });
	});

	it('falls back to the default document where the manifest gives none', () => {
		const m = withUnplaced();
		m.annotations.w = note('w');
		m.unplaced = [{ id: 'w', key: 'sy-0FFF', why: 'The block it was written on is gone, and nothing says where its words went.', document: '' }];
		const main = m.masters.find((d) => d.default)?.path;
		expect(main).toBeTruthy();
		expect(documentOf(m, m.annotations.w)).toBe(main);
	});
});

describe('why a note is on no block', () => {
	it('is the manifest’s own sentence for a note on no block, and nothing for one on a block', () => {
		const m = withUnplaced();
		m.unplaced = [{ id: 'u', key: 'sy-000A', why: 'Its block is in a file no document reads now; it is back on that block once a document reads the file again.', document: 'drafting/main.tex' }];
		expect(whyApart(m, m.annotations.u)).toMatch(/^Its block is in a file no document reads now/);
		const placed = Object.values(m.annotations).find((a) => a.target.key);
		expect(placed && whyApart(m, placed)).toBe('');
	});
});
