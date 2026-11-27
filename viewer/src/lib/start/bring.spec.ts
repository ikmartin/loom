import { describe, expect, it } from 'vitest';
import { droppedPaths, saidOf } from './bring';

describe("a paper brought into an empty quilt, as its page says loom's answers", () => {
	it("says loom's known refusals in its own words, and keeps loom's line only for an import that failed", () => {
		expect(saidOf('no-paper')).toEqual({ refused: 'noPaper' });
		expect(saidOf('bad-archive')).toEqual({ refused: 'badArchive' });
		expect(saidOf('too-large')).toEqual({ refused: 'tooLarge' });
		expect(saidOf('no-dialog')).toEqual({ refused: 'noDialog' });
		expect(saidOf('cannot-import', 'paper.tex: a file is missing')).toEqual({ failed: 'paper.tex: a file is missing' });
		expect(saidOf('failed', 'Traceback …')).toEqual({ failed: '' });
	});

	it('writes the paths of what was dropped as the person dropped it', () => {
		const said = '/Users/someone/Library/Application Support/loom/app/incoming/0a1b2c3d4e5f6a7b/files/gadget-towers.tex: \\input{sections/intro} names a file that is not there';
		expect(droppedPaths(said)).toBe('gadget-towers.tex: \\input{sections/intro} names a file that is not there');
		expect(droppedPaths('/Users/someone/papers/towers.tex: a file is missing')).toBe('/Users/someone/papers/towers.tex: a file is missing');
	});
});
