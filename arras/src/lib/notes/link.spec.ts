import { describe, expect, it } from 'vitest';
import { quoteLink } from './link';
import { quiltParts } from '$lib/workspace/links';

describe('a quote link', () => {
	it('is written as loom link writes it', () => {
		// loom link main.tex --quote "the (first) case. It's done!" prints the same body
		expect(quoteLink('paper/main.tex', 'dm-0003', "the (first)  case. It's done!")).toBe('quilt:paper/main.tex#dm-0003&quote=the%20%28first%29%20case%2E%20It%27s%20done%21');
		expect(quoteLink('notes/a b.pdf', 'page=2', 'x')).toBe('quilt:notes/a%20b.pdf#page=2&quote=x');
		expect(quoteLink('dm-0003', '', 'x & y')).toBe('quilt:dm-0003#quote=x%20%26%20y');
		expect(quoteLink('Bellamy19-0A1B-ref', 'page=2')).toBe('quilt:Bellamy19-0A1B-ref#page=2');
		expect(quoteLink('main.tex')).toBe('quilt:main.tex');
	});

	it('reads back as the key, the place and the words', () => {
		const words = 'an & in them, (brackets) and a full stop.';
		expect(quiltParts(quoteLink('notes/a b.pdf', 'page=2', words).slice('quilt:'.length))).toEqual({ key: 'notes/a b.pdf', place: 'page=2', quote: words });
	});
});
