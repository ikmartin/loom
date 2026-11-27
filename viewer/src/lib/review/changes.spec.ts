import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Manifest, PendingChange } from '$lib/manifest/types';

const calls: [string, Record<string, unknown>][] = [];
let answer: Record<string, unknown> = { ok: true, result: 'done' };
let quilt: string | undefined = 'q-one';
let probed: Promise<void> = Promise.resolve();
/** What a write waits on before it answers: loom recording it. */
let recording: Promise<void> = Promise.resolve();
const watchers: ((caps: { quilt?: string } | null) => void)[] = [];
vi.mock('$lib/write', () => ({
	can: async () => true,
	capabilities: async () => {
		await probed;
		return { write_api: 1, capabilities: [], quilt };
	},
	onCapabilities: (watch: (caps: { quilt?: string } | null) => void) => watchers.push(watch),
	write: async (endpoint: string, body: Record<string, unknown>) => {
		calls.push([endpoint, body]);
		await recording;
		return answer;
	}
}));
const MAIN = 'drafting/main.tex';
const change = (over: Partial<PendingChange>): PendingChange => ({ id: 'c-0001', kind: 'edit', path: 'drafting/nodes/sy-0001.tex', key: 'sy-0001', documents: [MAIN], old: 'a widget', new: 'a gadget', state: 'ready', ...over });
const live = { annotations: {}, annotation_types: [], reviewer: { name: 'me', source: '' }, masters: [], changes: [] as PendingChange[] };
vi.mock('$lib/manifest/client.svelte', () => ({ store: { manifest: live, refresh: async () => {} } }));

const { actSays, allSays, authorOf, byDocument, changeById, changesIn, IN_THE_FILE, kindName, pending, ready, refusal, summary, whoMade } = await import('./changes');
const { acted, mark, prune } = await import('./acted.svelte');
const { Annotating, entries } = await import('./annotating.svelte');
const { discardChanges, history, keepChanges, undo, redo } = await import('./history.svelte');

const suggestion = change({ id: 'e-1', kind: 'suggested', author: { kind: 'agent', id: 'agent', label: 'Claude' }, created: '2026-11-12T10:00:00Z', comment_html: '<p>plural</p>' });

beforeEach(() => {
	calls.length = 0;
	recording = Promise.resolve();
	answer = { ok: true, result: 'done' };
	acted.map = {};
	history.done = [];
	history.undone = [];
	live.changes = [];
});

describe('the pending changes the manifest lists', () => {
	it('reads only entries that are pending changes, in order, and finds one by id or by document', () => {
		const m = { changes: [change({}), { path: 'notes/intro.md', kind: 'changed', hunks: 1 } as unknown as PendingChange, change({ id: 'c-0002', documents: ['drafting/talk.tex'] })] };
		expect(pending(m).map((c) => c.id)).toEqual(['c-0001', 'c-0002']);
		expect(changeById(m, 'c-0002')?.documents).toEqual(['drafting/talk.tex']);
		expect(changeById(m, 'nope')).toBeUndefined();
		expect(changesIn(m, MAIN).map((c) => c.id)).toEqual(['c-0001']);
		expect(pending(null)).toEqual([]);
	});

	it('names an edit in the file and a suggestion, and who made each', () => {
		expect(kindName(change({}))).toBe('Edit in the file');
		expect(kindName(suggestion)).toBe('Suggestion');
		expect(authorOf(change({}))).toEqual({ id: IN_THE_FILE, name: IN_THE_FILE });
		expect(authorOf(suggestion)).toEqual({ id: 'agent', name: 'Claude' });
		expect(whoMade({ reviewer: { name: 'agent', source: '' } }, suggestion)).toBe('you');
		expect(whoMade(null, suggestion)).toBe('Claude');
		expect(whoMade(null, change({}))).toBe('');
		// the manifest names a change's author by name
		expect(authorOf(change({ author: 'agent' }))).toEqual({ id: 'agent', name: 'agent' });
		expect(whoMade({ reviewer: { name: 'agent', source: '' } }, change({ author: 'agent' }))).toBe('you');
	});

	it('says what one does in a line', () => {
		expect(summary(change({}))).toBe('“a widget” → “a gadget”');
		expect(summary(change({ old: '' }))).toBe('add “a gadget”');
		expect(summary(change({ new: '' }))).toBe('remove “a widget”');
		expect(summary(change({ old: 'x'.repeat(80) })).length).toBeLessThan(80);
	});

	it('says why one that is not ready cannot be kept, in loom\'s words where it gives them', () => {
		expect(refusal(change({}))).toBe('');
		expect(refusal(change({ state: 'unplaced', why: 'an earlier suggestion overlaps it' }))).toBe('an earlier suggestion overlaps it');
		expect(refusal(change({ state: 'on-a-copy' }))).toMatch(/agent's copy/);
		expect(refusal(change({ state: 'taken' }))).toMatch(/already reads/);
		// a suggestion the text already reads as is kept to record it, or discarded
		expect(ready(change({ state: 'taken' }))).toBe(true);
		expect(ready(change({ state: 'unplaced' }))).toBe(false);
	});

	it('says what Keep and Discard do, one and all', () => {
		expect(actSays(change({})).line).toBe('Already in the file. Discard writes your words back.');
		expect(actSays(suggestion).line).toBe('Not in the file yet. Keep writes it in.');
		expect(allSays([suggestion, change({}), change({ id: 'c-2' })])).toEqual({
			keep: 'Writes the 1 suggestion into the file and keeps the 2 edits already in it.',
			discard: 'Deletes the 1 suggestion and writes your old words back over the 2 edits.'
		});
		expect(allSays([])).toEqual({ keep: '', discard: '' });
	});

	it('groups them by the document that lists them, the person\'s own first, a change in no document under its file', () => {
		const masters = [
			{ path: '.loom/agents/copies/aidoc.tex', agent: { name: 'Claude' }, copy_of: MAIN },
			{ path: MAIN, default: true },
			{ path: 'drafting/old.tex', closed: true }
		] as unknown as Manifest['masters'];
		const changes = [change({ id: 'c-1', documents: ['.loom/agents/copies/aidoc.tex', MAIN] }), change({ id: 'c-2', documents: ['drafting/old.tex'], path: 'drafting/old.tex' }), change({ id: 'c-3', documents: ['.loom/agents/copies/aidoc.tex'] }), change({ id: 'c-4', documents: [], path: 'notes/a.md', key: null })];
		const groups = byDocument({ masters, changes });
		expect(groups.map((g) => [g.path, g.document, g.changes.map((c) => c.id)])).toEqual([
			[MAIN, true, ['c-1']],
			['.loom/agents/copies/aidoc.tex', true, ['c-3']],
			['drafting/old.tex', false, ['c-2']],
			['notes/a.md', false, ['c-4']]
		]);
	});
});

describe('changes in the stepper and the list', () => {
	const m = { annotations: { a1: { id: 'a1', status: 'open', type: null, author: { id: 'agent' }, in_reply_to: null } }, annotation_types: [], reviewer: { name: 'me', source: '' }, changes: [change({}), suggestion] } as unknown as Manifest;
	const state = (over: Partial<InstanceType<typeof Annotating>> = {}) => Object.assign(new Annotating(), { order: ['c-0001', 'a1', 'e-1', 'gone'] }, over);

	it('goes through annotations and changes in reading order, as the layer chosen lists them', () => {
		expect(entries(m, state(), false).map((e) => e.id)).toEqual(['c-0001', 'a1', 'e-1']);
		expect(entries(m, state({ layer: 'annotations' }), false).map((e) => e.id)).toEqual(['a1']);
		expect(entries(m, state({ layer: 'changes' }), false).map((e) => e.id)).toEqual(['c-0001', 'e-1']);
	});

	it('keeps every change in To do, leaves out an author the filter leaves out, and one just kept or discarded', () => {
		expect(entries(m, state({ todo: true }), false).map((e) => e.id)).toEqual(['c-0001', 'e-1']);
		expect(entries(m, state({ hidden: [IN_THE_FILE] }), false).map((e) => e.id)).toEqual(['a1', 'e-1']);
		mark(['e-1'], 'kept');
		expect(entries(m, state(), false).map((e) => e.id)).toEqual(['c-0001', 'a1']);
		prune({ changes: [change({})] });
		expect(acted.map).toEqual({});
	});
});

describe('Keep and Discard', () => {
	it('keeps changes by id, shown kept from the answer and not before, and puts nothing on the undo history', async () => {
		live.changes = [change({}), suggestion];
		let recorded = () => {};
		recording = new Promise((r) => (recorded = r));
		const going = keepChanges({ changes: ['c-0001'] });
		await new Promise((r) => setTimeout(r));
		expect(calls).toEqual([['change-keep', { changes: ['c-0001'] }]]);
		expect(acted.map).toEqual({});
		answer = { ok: true, result: 'kept 1', done: ['c-0001'], refused: [] };
		recorded();
		await going;
		expect(acted.map).toEqual({ 'c-0001': 'kept' });
		expect(history.done).toHaveLength(0);
	});

	it('never shows a change loom refused as done', async () => {
		live.changes = [change({}), change({ id: 'c-0002' })];
		answer = { ok: true, result: 'kept 1', done: ['c-0001'], refused: [{ id: 'c-0002', why: 'changed' }] };
		await keepChanges({ changes: ['c-0001', 'c-0002'] });
		expect(acted.map).toEqual({ 'c-0001': 'kept' });
		answer = { ok: false, error: { code: 'changed', message: 'a file changed' } };
		await discardChanges({ changes: ['c-0002'] });
		expect(acted.map).toEqual({ 'c-0001': 'kept' });
	});

	it('discards every ready change of a document; the suggestion among them is undone by change-discard with undo and done again, the edit in the file is not', async () => {
		live.changes = [change({}), suggestion, change({ id: 'c-x', state: 'unplaced' }), change({ id: 'c-t', documents: ['drafting/talk.tex'] })];
		answer = { ok: true, result: 'discarded 2', done: ['c-0001', 'e-1'], refused: [] };
		await discardChanges({ all: true, document: MAIN }, 'not wanted');
		expect(calls).toEqual([['change-discard', { all: true, document: MAIN, why: 'not wanted' }]]);
		expect(acted.map).toEqual({ 'c-0001': 'discarded', 'e-1': 'discarded' });
		expect(history.done).toHaveLength(1);
		expect(await undo()).toBe('');
		expect(calls.at(-1)).toEqual(['change-discard', { changes: ['e-1'], undo: true }]);
		expect(acted.map).toEqual({ 'c-0001': 'discarded' });
		expect(await redo()).toBe('');
		expect(calls.at(-1)).toEqual(['change-discard', { changes: ['e-1'] }]);
	});

	it('puts a discarded edit in the file on no history, its words being back in the file', async () => {
		live.changes = [change({})];
		answer = { ok: true, result: 'discarded 1', done: ['c-0001'], refused: [] };
		await discardChanges({ changes: ['c-0001'] });
		expect(history.done).toHaveLength(0);
	});

	it('puts a suggestion loom writes on the undo history, undone by change-undo and kept again by redo; one taken already is not', async () => {
		live.changes = [change({}), suggestion, change({ id: 'e-2', kind: 'suggested', state: 'taken' })];
		answer = { ok: true, result: 'kept 3', done: ['c-0001', 'e-1', 'e-2'], refused: [] };
		await keepChanges({ all: true, document: MAIN });
		expect(history.done).toHaveLength(1);
		expect(history.done[0].label).toBe('keep');
		answer = { ok: true, result: 'undid 1', done: ['e-1'], refused: [] };
		expect(await undo()).toBe('');
		expect(calls.at(-1)).toEqual(['change-undo', { changes: ['e-1'], quilt: 'q-one' }]);
		expect(acted.map['e-1']).toBeUndefined();
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		expect(await redo()).toBe('');
		expect(calls.at(-1)).toEqual(['change-keep', { changes: ['e-1'] }]);
	});

	it('says why an undo of a keep was refused; one that can never be undone leaves the history, uncovering what is beneath it', async () => {
		live.changes = [suggestion];
		history.done = [{ label: 'resolve', undo: async () => ({ ok: true }), redo: async () => ({ ok: true }) }];
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		await keepChanges({ changes: ['e-1'] });
		expect(history.done.map((s) => s.label)).toEqual(['resolve', 'keep']);
		// a file that moved while loom worked: pressed again it may be undone, so the step stays
		answer = { ok: true, result: 'undid 0', done: [], refused: [{ id: 'e-1', why: 'a file changed while loom was undoing a Keep', code: 'changed' }] };
		// said by its code in Review's words, never by loom's why
		expect(await undo()).toBe('It changed after it was listed, so loom left it as it is.');
		expect(history.done.map((s) => s.label)).toEqual(['resolve', 'keep']);
		// its words changed where they were written: never, so it goes, and Undo reaches the resolve beneath
		answer = { ok: true, result: 'undid 0', done: [], refused: [{ id: 'e-1', why: 'the suggestion “plural” has changed where it was written', code: 'changed-since' }] };
		expect(await undo()).toBe('Its words changed in the file since, so loom left them as they are.');
		expect(history.done.map((s) => s.label)).toEqual(['resolve']);
	});

	it('keeps a Keep step in the tab across a reload, offered only in the quilt it was made in', async () => {
		const kept: Record<string, string> = {};
		vi.stubGlobal('sessionStorage', { getItem: (k: string) => kept[k] ?? null, setItem: (k: string, v: string) => (kept[k] = v) });
		vi.resetModules();
		let h = await import('./history.svelte');
		await vi.waitFor(() => expect(h.history.done).toEqual([]));
		await new Promise((r) => setTimeout(r));
		live.changes = [suggestion];
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		await h.keepChanges({ changes: ['e-1'] });
		expect(JSON.parse(kept['viewer.keeps'])).toEqual({ 'q-one': [['e-1']] });
		// the same tab, another quilt served on the port: nothing of q-one is offered
		quilt = 'q-two';
		vi.resetModules();
		h = await import('./history.svelte');
		await new Promise((r) => setTimeout(r));
		expect(h.history.done).toEqual([]);
		// back in the quilt it was made in, the step is there, and undoes
		quilt = 'q-one';
		vi.resetModules();
		h = await import('./history.svelte');
		await vi.waitFor(() => expect(h.history.done.map((s) => s.label)).toEqual(['keep']));
		answer = { ok: true, result: 'undid 1', done: ['e-1'], refused: [] };
		expect(await h.undo()).toBe('');
		expect(calls.at(-1)).toEqual(['change-undo', { changes: ['e-1'], quilt: 'q-one' }]);
		expect(JSON.parse(kept['viewer.keeps'])).toEqual({ 'q-one': [] });
		vi.unstubAllGlobals();
	});

	it('lets the Keep steps go when the stream comes back from another quilt, and the server refuses one sent anyway', async () => {
		live.changes = [suggestion];
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		await keepChanges({ changes: ['e-1'] });
		expect(history.done.map((s) => s.label)).toEqual(['keep']);
		// a renamed copy served on the port, no reload: the probe after the reconnect names it
		watchers[0]({ quilt: 'q-copy' });
		expect(history.done).toEqual([]);
		// back to the quilt it was made in: the step is offered again, from where the tab kept it
		watchers[0]({ quilt: 'q-one' });
		// and a step that does reach another quilt's server is refused there, for good
		history.done = [];
		await keepChanges({ changes: ['e-1'] });
		answer = { ok: false, error: { code: 'other-quilt', message: 'that Keep was made in another quilt, so nothing was undone' } };
		expect(await undo()).toBe('It was kept in another quilt.');
		expect(history.done).toHaveLength(0);
	});

	it('makes a Keep step only once the server has said which quilt it serves, and none where it names none', async () => {
		let answered = () => {};
		probed = new Promise((r) => (answered = r));
		vi.resetModules();
		let h = await import('./history.svelte');
		live.changes = [suggestion];
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		// kept before the server has answered which quilt it serves: the step waits for it, and names it
		const keeping = h.keepChanges({ changes: ['e-1'] });
		await new Promise((r) => setTimeout(r));
		expect(h.history.done).toEqual([]);
		answered();
		await keeping;
		expect(h.history.done.map((s) => [s.label, s.quilt])).toEqual([['keep', 'q-one']]);
		// a server that names no quilt: no step, so no undo is ever sent without one
		quilt = undefined;
		vi.resetModules();
		h = await import('./history.svelte');
		await h.keepChanges({ changes: ['e-1'] });
		expect(h.history.done).toEqual([]);
		quilt = 'q-one';
	});

	it('lets a step go whose suggestion the quilt does not have, saying so without an id', async () => {
		live.changes = [suggestion];
		answer = { ok: true, result: 'kept 1', done: ['e-1'], refused: [] };
		await keepChanges({ changes: ['e-1'] });
		answer = { ok: false, error: { code: 'no-such-change', message: 'a suggestion it names is not in this quilt' } };
		expect(await undo()).toBe('It no longer waits.');
		expect(history.done).toHaveLength(0);
	});

	it('shows a change refused, or an act refused whole, pending again', async () => {
		live.changes = [change({}), suggestion];
		answer = { ok: true, result: 'kept 1', done: ['c-0001'], refused: [{ id: 'e-1', why: 'author-only' }] };
		await keepChanges({ changes: ['c-0001', 'e-1'] });
		expect(acted.map).toEqual({ 'c-0001': 'kept' });
		answer = { ok: false, error: { code: 'no-such-change', message: 'gone' } };
		const res = await discardChanges({ changes: ['e-1'] });
		expect(res.ok).toBe(false);
		expect(acted.map).toEqual({ 'c-0001': 'kept' });
		expect(history.done).toHaveLength(0);
	});
});
