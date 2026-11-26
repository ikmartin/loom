import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it } from 'vitest';
import { here } from '$lib/here.svelte';
import type { Manifest } from '$lib/manifest/types';
import { placesFor, withoutQuote } from './places';

const m = JSON.parse(readFileSync('tests/fixture/manifest.json', 'utf8')) as Manifest;

beforeEach(() => {
	here.block = {};
});

describe('what Ask your agent is about from a toolbar', () => {
	it('is a result alone on its own page', () => {
		expect(placesFor(m, { kind: 'node', id: 'sy-0003' }).map((p) => p.href)).toEqual(['quilt:sy-0003']);
	});

	it('is the document alone until a result stands at the top of its pane', () => {
		expect(placesFor(m, { kind: 'document', id: 'drafting/main.tex' }).map((p) => p.href)).toEqual(['quilt:drafting/main.tex']);
	});

	it('offers the result at the top of the pane first, then the document', () => {
		here.block = { 'document:drafting/main.tex': { src: 'x', key: 'sy-0003' } };
		const got = placesFor(m, { kind: 'document', id: 'drafting/main.tex' });
		expect(got.map((p) => p.href)).toEqual(['quilt:drafting/main.tex#sy-0003', 'quilt:drafting/main.tex']);
		expect(got[0].label).toMatch(/where you are reading$/);
	});

	it('asks nothing without a manifest', () => {
		expect(placesFor(null, { kind: 'node', id: 'sy-0003' })).toEqual([]);
	});
});

describe("a selection's link", () => {
	it('loses its quoted words, which the request quotes itself', () => {
		expect(withoutQuote('quilt:drafting/main.tex#sh-0009&quote=every%20vertex')).toBe('quilt:drafting/main.tex#sh-0009');
		expect(withoutQuote('quilt:papers/a.pdf#quote=the%20median')).toBe('quilt:papers/a.pdf');
		expect(withoutQuote('quilt:sy-0003')).toBe('quilt:sy-0003');
	});
});
