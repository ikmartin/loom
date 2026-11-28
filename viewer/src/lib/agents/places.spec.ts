import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it } from 'vitest';
import { here } from '$lib/here.svelte';
import type { Manifest } from '$lib/manifest/types';
import { placesFor, withoutQuote } from './places';

const m = JSON.parse(readFileSync('tests/fixture/manifest.json', 'utf8')) as Manifest;

beforeEach(() => {
	here.block = {};
	here.seen = {};
	here.selection = null;
});

describe('what Ask your agent is about from a toolbar', () => {
	it('is a result alone on its own page, named and linked through the document that numbers it', () => {
		expect(placesFor(m, { kind: 'node', id: 'sy-0003' }).map((p) => [p.name, p.href])).toEqual([['main.tex, Theorem 2.1', 'quilt:drafting/main.tex#sy-0003']]);
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

	it('offers the words selected in the pane first, at the result they are in, under the number the document read shows', () => {
		// Lemma 1.2 in main.tex is Lemma 3 in the talk, and Definition 2.4 Definition 1
		here.block = { 'document:drafting/talk.tex': { src: 'x', key: 'sy-0008' } };
		here.selection = { item: 'document:drafting/talk.tex', key: 'sy-0002', text: 'every orbit' };
		const got = placesFor(m, { kind: 'document', id: 'drafting/talk.tex' });
		expect(got.map((p) => [p.href, p.label, p.words])).toEqual([
			['quilt:drafting/talk.tex#sy-0002', 'The words you selected in Lemma 3', 'every orbit'],
			['quilt:drafting/talk.tex#sy-0008', 'Definition 1, where you are reading', undefined],
			['quilt:drafting/talk.tex', 'The document, talk.tex', undefined]
		]);
		expect(got[0].name).toBe('talk.tex, Lemma 3');
	});

	it('leaves out words selected in another pane, and the reading place where it is the one selected in', () => {
		here.block = { 'document:drafting/main.tex': { src: 'x', key: 'sy-0003' } };
		here.selection = { item: 'document:drafting/talk.tex', key: 'sy-0002', text: 'every orbit' };
		expect(placesFor(m, { kind: 'document', id: 'drafting/main.tex' }).map((p) => p.href)).toEqual(['quilt:drafting/main.tex#sy-0003', 'quilt:drafting/main.tex']);
		here.selection = { item: 'document:drafting/main.tex', key: 'sy-0003', text: 'finite widget' };
		expect(placesFor(m, { kind: 'document', id: 'drafting/main.tex' }).map((p) => [p.href, p.words])).toEqual([
			['quilt:drafting/main.tex#sy-0003', 'finite widget'],
			['quilt:drafting/main.tex', undefined]
		]);
	});

	it('offers the results on screen after the one at the top of the pane, each under its number, then the document', () => {
		here.block = { 'document:drafting/main.tex': { src: 'x', key: 'sy-0003' } };
		here.seen = { 'document:drafting/main.tex': ['sy-0003', 'sy-0008'] };
		const got = placesFor(m, { kind: 'document', id: 'drafting/main.tex' });
		expect(got.map((p) => [p.href, p.label])).toEqual([
			['quilt:drafting/main.tex#sy-0003', 'Theorem 2.1, where you are reading'],
			['quilt:drafting/main.tex#sy-0008', 'Definition 2.4, on screen'],
			['quilt:drafting/main.tex', 'The document, main.tex']
		]);
	});

	it('offers the results on screen before a section at the top of the pane, which says only roughly where the reader is', () => {
		here.block = { 'document:drafting/main.tex': { src: 'x', key: 'sy-0100' } };
		here.seen = { 'document:drafting/main.tex': ['sy-0002'] };
		const got = placesFor(m, { kind: 'document', id: 'drafting/main.tex' });
		expect(got.map((p) => p.label)).toEqual(['Lemma 1.2, on screen', 'Section 1, where you are reading', 'The document, main.tex']);
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
