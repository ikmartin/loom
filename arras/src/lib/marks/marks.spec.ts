import { describe, expect, it } from 'vitest';
import { leanMark, paperMark } from './marks';

describe('the marks a status is drawn as', () => {
	it('draws a reading of the paper', () => {
		expect(paperMark('matches')).toBe('checked');
		expect(paperMark('unchecked')).toBe('unchecked');
		expect(paperMark('stub')).toBe('stub');
		expect(paperMark('marked')).toBe('marked');
	});
	it('draws Lean: formalized or assumed, waiting on the person, or not', () => {
		expect(leanMark({ lean: 'formalized', role: 'proved' })).toBe('formalized');
		expect(leanMark({ lean: 'formalized', role: 'assumed' })).toBe('assumed');
		expect(leanMark({ lean: 'unattested' })).toBe('attest');
		expect(leanMark({ lean: 'changed' })).toBe('attest');
		// waiting is the person's only where something under it is theirs to compare or attest; waiting on reading is an outline
		expect(leanMark({ lean: 'waiting', waiting_on: [{ node: 'n', why: 'unchecked' }] })).toBe('attest');
		expect(leanMark({ lean: 'waiting', waiting_on: [{ node: 'n', why: 'stub' }, { node: 'm', why: 'unknown' }] })).toBe('not');
		for (const lean of ['none', 'rerun', 'failed'] as const) expect(leanMark({ lean })).toBe('not');
	});
});
