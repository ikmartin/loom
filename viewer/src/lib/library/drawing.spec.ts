// TeX's drawing of a result is asked for only once the person has compiled its work's source here, and the question that compiles it is asked only of a work holding a source that is not compiled yet.
import { describe, expect, it } from 'vitest';
import { drawing } from './drawing.svelte';
import type { NodeAnswer } from './types';

const node = (compiled: boolean | null | undefined): NodeAnswer => ({
	gen: 1,
	node: 'tq-0163',
	hash: 'sha256:' + 'a'.repeat(64),
	name: 'Lemma 6.3',
	taxon: 'lemma',
	work: { ref: 'tq-00A1-ref', short: 'Smith 2024', pdf: null },
	digested: null,
	paper: 'unchecked',
	macros: { node: 'tq-00A1-macros', hash: 'sha256:' + 'b'.repeat(64), body: '' },
	...(compiled === undefined ? {} : { compiled })
});

describe("TeX's drawing of a result", () => {
	it('is never asked for before the person has compiled the source, and the person is asked instead', () => {
		expect(drawing(node(false), new Set())).toEqual({ drawn: null, ask: true });
	});
	it('is asked for once the source is compiled here, by an earlier visit or in this page', () => {
		const url = `/_api/library/drawn/${'a'.repeat(64)}-${'b'.repeat(64)}.svg`;
		expect(drawing(node(true), new Set())).toEqual({ drawn: url, ask: false });
		expect(drawing(node(false), new Set(['tq-00A1-ref']))).toEqual({ drawn: url, ask: false });
	});
	it('is neither asked for nor offered for a work holding no source, or a publisher that does not say', () => {
		expect(drawing(node(null), new Set(['tq-00A1-ref']))).toEqual({ drawn: null, ask: false });
		expect(drawing(node(undefined), new Set(['tq-00A1-ref']))).toEqual({ drawn: null, ask: false });
	});
});
