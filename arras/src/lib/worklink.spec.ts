import { describe, expect, it } from 'vitest';
import { externalUrl, locateBody, normalId, parseWorkLink } from './worklink';

describe('a work link', () => {
	it('names an identifier and a page or a quote', () => {
		expect(parseWorkLink('cited:arxiv:0805.2065v2#page=9')).toEqual({ id: 'arxiv:0805.2065v2', page: 9 });
		expect(parseWorkLink('cited:arXiv:math/9810166v2#quote=fixed%20locus')).toEqual({ id: 'arxiv:math/9810166v2', quote: 'fixed locus' });
		expect(parseWorkLink('cited:DOI:10.1090/S1056-3911-2011-00606-1')).toEqual({ id: 'doi:10.1090/s1056-3911-2011-00606-1' });
		expect(parseWorkLink('https://arxiv.org/abs/0805.2065')).toBeNull();
		expect(parseWorkLink('cited:arxiv:')).toBeNull();
		expect(parseWorkLink('cited:arxiv:1#page=0')).toEqual({ id: 'arxiv:1' });
	});

	it('reads an annotation by the id loom draws for it, or one written under a counter', () => {
		expect(parseWorkLink('cited:arxiv:1?annot=a-2026-11-05-k2m9xq')?.annot).toBe('a-2026-11-05-k2m9xq');
		expect(parseWorkLink('cited:arxiv:1?annot=a-2026-09-16-0001')?.annot).toBe('a-2026-09-16-0001');
		expect(parseWorkLink('cited:arxiv:1?annot=a-2026-11-05-K2M9XQ')?.annot).toBeUndefined();
	});

	it('spells an identifier one way', () => {
		expect(normalId('arXiv:2207.01652')).toBe('arxiv:2207.01652');
		expect(normalId('doi:10.1353/AJM.1998.0020')).toBe('doi:10.1353/ajm.1998.0020');
	});

	it('opens at its own service, by scheme, at the page where the service takes one', () => {
		expect(externalUrl(parseWorkLink('cited:arxiv:0805.2065v2?page=9')!)).toBe('https://arxiv.org/pdf/0805.2065v2#page=9');
		expect(externalUrl(parseWorkLink('cited:DOI:10.1090/S1056-3911-2011-00606-1')!)).toBe('https://doi.org/10.1090/s1056-3911-2011-00606-1');
		expect(externalUrl(parseWorkLink('cited:mr:MR1234567')!)).toBe('https://mathscinet.ams.org/mathscinet-getitem?mr=1234567');
		expect(externalUrl(parseWorkLink('cited:zbl:0909.14006')!)).toBe('https://zbmath.org/?q=an:0909.14006');
		expect(externalUrl({ id: 'work:abcd' })).toBeUndefined();
		expect(externalUrl({ id: 'isbn:9780000000000' })).toBeUndefined();
	});
});

describe('a place on a work\'s pages, asked of `locate`', () => {
	it('names the work by its reference, as the publisher requires', () => {
		expect(locateBody('sh-0403-ref', { span: [93, 171] }, 2)).toEqual({ ref: 'sh-0403-ref', page: 2, span: [93, 171] });
		expect(locateBody('sh-0403-ref', { page: 2, quote: 'totally unimodular' }, 2)).toEqual({ ref: 'sh-0403-ref', page: 2, text: 'totally unimodular' });
	});

	it('looks for a quote with no page across the work, and asks nothing of a place with neither a span nor a quote', () => {
		expect(locateBody('sh-0403-ref', { quote: 'median orders' }, 1)).toEqual({ ref: 'sh-0403-ref', text: 'median orders' });
		expect(locateBody('sh-0403-ref', { page: 3, box: [1, 2, 3, 4] }, 3)).toBeNull();
	});
});
