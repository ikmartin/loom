import { describe, expect, it } from 'vitest';
import { plainLink, request } from './ask';

const THM = { name: 'main.tex, Theorem 3.1', href: 'quilt:drafting/main.tex#sh-0009' };

describe('the request Ask your agent copies', () => {
	it("names the place in words with its document's link, no id in it, and asks the agent to look", () => {
		expect(request(THM)).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex).');
	});

	it('gives the link with its id where Show ids is on', () => {
		expect(request(THM, '', '', true)).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex#sh-0009).');
	});

	it('names the mode to work in', () => {
		expect(request(THM, 'referee')).toBe('In loom, work in the referee mode on main.tex, Theorem 3.1 (quilt:drafting/main.tex).');
	});

	it('quotes the words selected, on one line', () => {
		expect(request({ ...THM, words: 'is the set of\n integer vectors' })).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex), at the words “is the set of integer vectors”.');
	});

	it('puts the person’s own words after a blank line, and none when they wrote none', () => {
		expect(request(THM, '', '  Is step 2 right?  ')).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex).\n\nIs step 2 right?');
		expect(request(THM, '', '   ')).not.toContain('\n');
	});

	it('cuts a long selection at a word, with an ellipsis', () => {
		const words = Array.from({ length: 300 }, (_, i) => `w${i}`).join(' ');
		const said = request({ ...THM, words });
		const quoted = said.slice(said.indexOf('“') + 1, said.indexOf('”'));
		expect(quoted.length).toBeLessThanOrEqual(601);
		expect(quoted.endsWith('…')).toBe(true);
		expect(quoted.slice(0, -1).split(' ').every((w) => /^w\d+$/.test(w))).toBe(true);
	});
});

describe('a link with no id in it', () => {
	it('keeps a document or a file by its path, a page or a heading, and drops a key after it', () => {
		expect(plainLink('quilt:drafting/main.tex#sh-0009')).toBe('quilt:drafting/main.tex');
		expect(plainLink('quilt:slice4D/slice4D.tex#q-000O')).toBe('quilt:slice4D/slice4D.tex');
		expect(plainLink('quilt:drafting/main.tex#sh-0009/proof')).toBe('quilt:drafting/main.tex');
		expect(plainLink('quilt:drafting/main.tex')).toBe('quilt:drafting/main.tex');
		expect(plainLink('quilt:papers/a.pdf#page=3')).toBe('quilt:papers/a.pdf#page=3');
		expect(plainLink('quilt:notes/day1.md#setup')).toBe('quilt:notes/day1.md#setup');
	});

	it('is none for a thing only a key names: a result alone, a work', () => {
		expect(plainLink('quilt:sy-0003')).toBe('');
		expect(plainLink('quilt:tq-00A1-ref')).toBe('');
	});
});
