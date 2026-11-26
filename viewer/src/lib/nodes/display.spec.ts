import { describe, expect, it } from 'vitest';
import { placeName, titleSaid, unnumberedName } from './display';

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

describe('a block with no number, title or label, as before a draft compiles', () => {
	const at = (taxon: string, parent: string, extra: Record<string, unknown> = {}) => ({ taxon, numbers: {}, parent: { 'drafting/main.tex': parent }, reached_by: ['drafting/main.tex'], ...extra });
	const nodes = {
		'sy-0300': at('Subsection', 'sy-0200', { title: 'Appendix: an incomplete argument' }),
		'sy-000A': at('Remark', 'sy-0300'),
		'sy-000F': at('Remark', 'sy-0300'),
		'sy-000B': at('Main Theorem', 'sy-0300'),
		'drafting/sections/appendix.tex#remark:1': at('Remark', 'sy-0300'),
		'sy-0007': at('Proposition', 'sy-0300', { title: 'Saturation' }),
		'sy-0009': at('Theorem', 'sy-0300', { title: 'Rank', numbers: { 'drafting/main.tex': { number: '3.1' } } }),
		'sy-0400': at('Lemma', '')
	};
	const m = { nodes, masters: [{ path: 'drafting/main.tex', default: true }] };
	it('is named by its kind and the section it stands in, never its id', () => {
		expect(unnumberedName(m, 'sy-000B')).toBe('Main Theorem in Appendix: an incomplete argument');
		expect(unnumberedName(m, 'sy-0400')).toBe('Lemma in main.tex');
	});
	it('says which of its section\'s blocks of that kind it is where the section holds several, a block named by its file apart', () => {
		expect(unnumberedName(m, 'sy-000A')).toBe('first Remark in Appendix: an incomplete argument');
		expect(unnumberedName(m, 'sy-000F')).toBe('second Remark in Appendix: an incomplete argument');
	});
	it('reads an id a reference left in a title as its number, else its title, else its kind and place', () => {
		expect(titleSaid(m, 'Second proof of Proposition sy-0007')).toBe('Second proof of Proposition Saturation');
		expect(titleSaid(m, 'Second proof of Theorem sy-0009')).toBe('Second proof of Theorem 3.1');
		expect(titleSaid(m, 'As in sy-0009')).toBe('As in Theorem 3.1');
		expect(titleSaid(m, 'Following sy-000B')).toBe('Following Main Theorem in Appendix: an incomplete argument');
		expect(titleSaid(m, 'A title with no id')).toBe('A title with no id');
	});
});
