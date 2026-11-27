import { describe, expect, it } from 'vitest';
import { typesettingFirst, type Compile } from './compiles.svelte';

const at = '2026-11-27T12:00:00Z';
const ok = (ended: string) => ({ result: 'ok' as const, ended, error: null, at: null });

describe('typesettingFirst', () => {
	it("says a document's first compile is typesetting it while its text is its source", () => {
		const first: Compile = { state: 'compiling', again: false, last: null };
		expect(typesettingFirst(first, at, false)).toBe(true);
		expect(typesettingFirst({ ...first, state: 'queued' }, at, false)).toBe(true);
		// TeX's page is there already: nothing to wait for
		expect(typesettingFirst(first, at, true)).toBe(false);
	});

	it('waits past the end of the run for the manifest that carries its page', () => {
		expect(typesettingFirst({ state: 'idle', again: false, last: ok('2026-11-27T12:00:03Z') }, at, false)).toBe(true);
		expect(typesettingFirst({ state: 'idle', again: false, last: ok('2026-11-27T11:59:58Z') }, at, false)).toBe(false);
		expect(typesettingFirst({ state: 'idle', again: false, last: { ...ok('2026-11-27T12:00:03Z'), result: 'failed' } }, at, false)).toBe(false);
	});

	it('leaves a document TeX gives no page as it is, and says nothing where nothing compiles', () => {
		expect(typesettingFirst({ state: 'compiling', again: false, last: ok('2026-11-27T11:00:00Z') }, at, false)).toBe(false);
		expect(typesettingFirst(undefined, at, false)).toBe(false);
	});
});
