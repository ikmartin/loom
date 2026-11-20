import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import type { Annotation, Manifest } from '$lib/manifest/types';
import { masterUrl } from '$lib/nav';
import { itemForQuilt } from '$lib/workspace/links';
import { keyName, linkName } from '$lib/workspace/names';
import { APART, apartIn, apartOf, documentOf, notesApart, notesHere, noteUrl, placeOf, PLAIN } from './annotating.svelte';

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

/** The fixture with a note on no block written on sy-0003 (read in `drafting/main.tex`), and a reference with no identifier, whose `work` is ''. */
function withUnplaced(): Manifest {
	const m = structuredClone(fixture);
	m.annotations = { ...m.annotations, u: note('u') };
	m.unplaced = [{ id: 'u', key: 'sy-0003', why: 'its block was deleted' }];
	m.references = { ...m.references, NoId: { ...Object.values(m.references)[0], citekey: 'NoId', work: '', works: [] } };
	return m;
}

describe('a note on no block', () => {
	it('is named by no key, and never by a reference with no identifier', () => {
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
