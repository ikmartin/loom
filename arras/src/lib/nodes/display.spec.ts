import { describe, expect, it } from 'vitest';
import { placeName } from './display';

describe('a block known by its place alone', () => {
	const nodes = { 'drafting/sections/appendix.tex#remark:1': { taxon: 'Remark' }, 'drafting/sections/gone.tex#lemma:2': { taxon: 'Lemma' }, 'drafting/sections/gone.tex#lemma:3': { taxon: 'Lemma' } };
	it('is named by its taxon and its file, never its key', () => {
		expect(placeName({ nodes }, 'drafting/sections/appendix.tex#remark:1')).toBe('Remark in appendix.tex');
	});
	it('says which of its file\'s blocks of that kind it is where the file holds several', () => {
		expect(placeName({ nodes }, 'drafting/sections/gone.tex#lemma:3')).toBe('third Lemma in gone.tex');
		expect(placeName({ nodes: {} }, 'drafting/x.tex#theorem:12')).toBe('12th Theorem in x.tex');
	});
	it('is null for a key that names a block otherwise', () => {
		expect(placeName({ nodes }, 'sy-0003')).toBeNull();
		expect(placeName({ nodes }, 'drafting/talk.tex')).toBeNull();
	});
});
