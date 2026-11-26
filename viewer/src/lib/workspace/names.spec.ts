import { describe, expect, it } from 'vitest';
import { documentLabel } from './names';

describe('documentLabel', () => {
	const masters = [{ path: 'drafting/main.tex' }, { path: 'drafting/outline.tex' }, { path: 'paper/main.tex' }];
	it('is the file name while no other document has it', () => {
		expect(documentLabel(masters, 'drafting/outline.tex')).toBe('outline.tex');
	});
	it('is the path where two documents share a file name', () => {
		expect(documentLabel(masters, 'drafting/main.tex')).toBe('drafting/main.tex');
		expect(documentLabel(masters, 'paper/main.tex')).toBe('paper/main.tex');
	});
});
