import { describe, expect, it } from 'vitest';
import { outcomeOf, saidOf, stepAt } from './flow';
import type { Job, QuiltRow } from './api';

const job = (over: Partial<Job>): Job => ({ job: 'j', kind: 'create', state: 'running', step: 'making', ...over });
const row = (over: Partial<QuiltRow>): QuiltRow => ({ quilt: 'q', name: 'Q', folder: '/q', port: 9000, open: true, state: 'starting', ...over });

describe("the home page's window for a new quilt", () => {
	it('finds the step loom names, and takes one it does not list for the first', () => {
		expect(stepAt('making')).toBe(0);
		expect(stepAt('starting')).toBe(1);
		expect(stepAt('importing')).toBe(0);
	});

	it('says a name already taken under the name, as being made while a create of it runs, and a dead end in place of the form', () => {
		expect(saidOf('exists')).toEqual({ under: 'exists' });
		expect(saidOf('exists', true)).toEqual({ under: 'beingMade' });
		expect(saidOf('inside-a-quilt')).toEqual({ under: 'insideQuilt' });
		expect(saidOf('stopping')).toEqual({ refused: 'stopping' });
		expect(saidOf('list-unreadable')).toEqual({ refused: 'unreadable' });
		expect(saidOf('failed')).toEqual({ failed: true });
	});

	it('shows the last step until the quilt made is served, since a create ends before its server answers', () => {
		expect(outcomeOf(undefined)).toBe('running');
		expect(outcomeOf(job({}))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }), row({}))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }), row({ state: 'running', url: 'http://127.0.0.1:9000/' }))).toBe('served');
		expect(outcomeOf(job({ state: 'done' }), row({ state: 'failed', why: 'refused' }))).toBe('unserved');
		expect(outcomeOf(job({ state: 'failed' }))).toBe('failed');
	});
});
