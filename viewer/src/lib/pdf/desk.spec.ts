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

describe('a mark moved', () => {
	it('is put back by Undo to where it was drawn, a move the manifest has not yet published included', async () => {
		const { store } = await import('$lib/manifest/client.svelte');
		const { undo } = await import('$lib/review/history.svelte');
		(store.manifest as { annotations: Record<string, unknown> }).annotations = { 'a-box': { id: 'a-box', target: { work: 'Bellamy19', page: 1, key: '' }, mark: 'box', rects: [[10, 10, 50, 50]], status: 'open', author: { id: 'me' }, created: '2026-11-24T10:00:00Z', body_html: '' } };
		const d = desk();
		d.move({ id: 'a-box', rects: [[20, 20, 60, 60]] });
		await settle();
		// resized before the manifest says it moved
		d.move({ id: 'a-box', rects: [[20, 20, 90, 90]] });
		await settle();
		calls.length = 0;
		await undo();
		expect(calls).toEqual([['edit', { annotation: 'a-box', rects: [[20, 20, 60, 60]] }]]);
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

describe('a mark picked', () => {
	const row = (id: string) => ({ id, target: { work: 'Bellamy19', page: 2, key: '' }, rects: [[10, 20, 60, 30]], status: 'open', author: { id: 'me' }, created: '2026-11-12T10:00:00Z', body_html: '' });

	it('drawn from the write before the manifest holds its annotation opens its popup once the manifest does, not at once, where the popup would close itself', async () => {
		const { store } = await import('$lib/manifest/client.svelte');
		const annotations = (store.manifest as { annotations: Record<string, unknown> }).annotations = {} as Record<string, unknown>;
		hand.set({ type: 'aside', over: {}, plain: {} });
		const d = desk();
		d.markWords({ page: 2, text: 'incidence matrix', rects: [[10, 20, 60, 30]] });
		await settle();
		const id = 'a-2026-11-12-new000';
		expect(d.marks.map((m) => m.id)).toEqual([id]);
		const told: string[] = [];
		d.pick(id, (x) => told.push(x));
		expect(told).toEqual(['']);
		d.settle();
		expect(told).toEqual(['']);
		annotations[id] = row(id);
		d.settle();
		expect(told).toEqual(['', id]);
		// once only
		d.settle();
		expect(told).toEqual(['', id]);
	});

	it('held by the manifest opens at once, and a pick elsewhere lets go of one waiting', async () => {
		const { store } = await import('$lib/manifest/client.svelte');
		const annotations = (store.manifest as { annotations: Record<string, unknown> }).annotations = { 'a-held': row('a-held') } as Record<string, unknown>;
		const d = desk();
		const told: string[] = [];
		d.pick('a-held', (x) => told.push(x));
		expect(told).toEqual(['a-held']);
		d.pick('a-coming', (x) => told.push(x));
		d.pick('', (x) => told.push(x));
		annotations['a-coming'] = row('a-coming');
		d.settle();
		expect(told).toEqual(['a-held', '', '']);
	});
});
