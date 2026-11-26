import { beforeEach, describe, expect, it, vi } from 'vitest';

const calls: [string, Record<string, unknown>][] = [];
vi.mock('$lib/write', () => ({
	can: async () => true,
	write: async (endpoint: string, body: Record<string, unknown>) => {
		calls.push([endpoint, body]);
		return { ok: true, result: 'a-2026-11-12-new000  Bellamy19  p. 2' };
	}
}));
const types = [
	{ id: 'question', name: 'Question', look: { color: 'blue', style: 'highlight', weight: 2, opacity: 60 }, open: true, instructions: '' },
	{ id: 'aside', name: 'Aside', look: { color: 'grey', style: 'highlight', weight: 2, opacity: 60 }, open: false, instructions: '' }
];
vi.mock('$lib/manifest/client.svelte', () => ({ store: { manifest: { annotations: {}, annotation_types: types, reviewer: { name: 'me', source: '' } }, refresh: async () => {} } }));

const { MarkDesk } = await import('./desk.svelte');
const { hand } = await import('$lib/review/annotating.svelte');

const settle = () => new Promise((r) => setTimeout(r, 0));
const desk = () => new MarkDesk(() => ({ on: 'Bellamy19', owns: () => true, url: '', name: 'Bellamy19.pdf' }));

beforeEach(() => {
	calls.length = 0;
});

describe('what the desk writes', () => {
	it('marks words with the type in hand, which draws them, and its style', async () => {
		hand.set({ type: 'aside', over: {}, plain: {} });
		desk().markWords({ page: 2, text: 'incidence matrix', rects: [[10, 20, 60, 30]] });
		await settle();
		expect(calls).toEqual([['annotate', { target: 'Bellamy19', page: 2, rects: [[10, 20, 60, 30]], quote: 'incidence matrix', type: 'aside' }]]);
	});

	it('writes a drawing with the type in hand and the look set over it, its tool drawing it', async () => {
		hand.set({ type: 'aside', over: { color: 'green', style: 'underline', weight: 4 }, plain: {} });
		desk().draw({ kind: 'box', page: 1, rects: [[1, 2, 30, 40]] });
		await settle();
		expect(calls[0][1]).toEqual({ target: 'Bellamy19', page: 1, mark: 'box', rects: [[1, 2, 30, 40]], type: 'aside', look: { color: 'green', weight: 4 } });
	});

	it('with Plain in hand writes only what is set over the plain look, words in its style', async () => {
		hand.set({ type: null, over: {}, plain: { style: 'strike' } });
		desk().markRegion({ page: 3, rects: [[5, 5, 50, 20]] });
		await settle();
		expect(calls[0][1]).toEqual({ target: 'Bellamy19', page: 3, rects: [[5, 5, 50, 20]], look: { style: 'strike' } });
	});
});

describe('the notes on words drawn on no page', () => {
	const note = (id: string, extra: Record<string, unknown> = {}) => ({ id, target: { work: 'Bellamy19', page: 2, key: '' }, quote: 'incidence matrix', status: 'open', author: { id: 'me' }, created: '2026-11-24T10:00:00Z', type: 'aside', body_html: '', ...extra });
	const on = (s: Record<string, unknown>) => new MarkDesk(() => ({ on: 'Bellamy19', owns: () => true, url: '', name: 'Bellamy19.pdf', ...s }));

	it('are said unread while where they stand cannot be learned, and unfound where loom finds their words on no page; a detached one and one with its own place are neither', async () => {
		const { store } = await import('$lib/manifest/client.svelte');
		(store.manifest as { annotations: Record<string, unknown> }).annotations = { 'a-words': note('a-words'), 'a-gone': note('a-gone', { detached: true }), 'a-boxed': note('a-boxed', { rects: [[1, 2, 30, 40]] }) };
		expect(on({ stands: () => null, unread: true }).nowhere).toEqual({ unread: ['a-words'], unfound: [] });
		expect(on({ unread: true }).nowhere).toEqual({ unread: ['a-words'], unfound: [] });
		expect(on({ stands: () => null }).nowhere).toEqual({ unread: [], unfound: ['a-words'] });
		expect(on({ stands: (id: string) => (id === 'a-words' ? { page: 2, rects: [[1, 1, 20, 10]] } : null) }).nowhere).toEqual({ unread: [], unfound: [] });
		// one whose place is not yet known is neither drawn nor listed, and so not said
		expect(on({ stands: () => undefined }).nowhere).toEqual({ unread: [], unfound: [] });
	});
});
