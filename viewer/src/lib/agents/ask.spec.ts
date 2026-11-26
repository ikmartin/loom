import { describe, expect, it } from 'vitest';
import { request } from './ask';

const THM = { name: 'main.tex, Theorem 3.1', href: 'quilt:drafting/main.tex#sh-0009' };

describe('the request Ask your agent copies', () => {
	it('names the place and its link, and asks the agent to look', () => {
		expect(request(THM)).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex#sh-0009).');
	});

	it('names the mode to work in', () => {
		expect(request(THM, 'referee')).toBe('In loom, work in the referee mode on main.tex, Theorem 3.1 (quilt:drafting/main.tex#sh-0009).');
	});

	it('quotes the words selected, on one line', () => {
		expect(request({ ...THM, words: 'is the set of\n integer vectors' })).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex#sh-0009), at the words “is the set of integer vectors”.');
	});

	it('puts the person’s own words after a blank line, and none when they wrote none', () => {
		expect(request(THM, '', '  Is step 2 right?  ')).toBe('In loom, look at main.tex, Theorem 3.1 (quilt:drafting/main.tex#sh-0009).\n\nIs step 2 right?');
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
