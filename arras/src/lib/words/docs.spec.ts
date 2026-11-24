import { describe, expect, it } from 'vitest';
import { docs } from './docs';

describe("a draft that has not compiled since it changed", () => {
	it("says TeX's messages it knows in the person's words, and any other as TeX said it", () => {
		expect(docs.texError('Undefined control sequence.')).toBe('a command it uses is not defined');
		expect(docs.texError('! Missing $ inserted.')).toBe('a formula is not closed, or mathematics stands outside one');
		expect(docs.texError('LaTeX Error: File `widgets.sty\' not found.')).toBe('a file it reads is missing');
		expect(docs.texError('Paragraph ended before \\@caption was complete.')).toBe('Paragraph ended before \\@caption was complete');
		expect(docs.texError('')).toBe('');
	});
	it('names the file and the line, never a command', () => {
		expect(docs.notCompiled('main.tex', 'a command it uses is not defined', '12')).toBe('main.tex has not compiled since it last changed: a command it uses is not defined (line 12). The PDF is the one from before.');
		expect(docs.notCompiled('main.tex', '', '')).toBe('main.tex has not compiled since it last changed. The PDF is the one from before.');
	});
});
