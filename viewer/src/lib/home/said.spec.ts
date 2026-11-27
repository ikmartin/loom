import { describe, expect, it } from 'vitest';
import { cannotStartOf, importSaidOf, refusalOf, untypesetOf } from './said';

const HOME = '/Users/m';
const QUILT = '/Users/m/Quilts/Thesis';

describe("the home's own words, worded by the page (I-13)", () => {
	it("gives a refused quilt's refusal without loom serve's own lines, unwrapped, its paths written from the quilt", () => {
		// what a quilt's server wrote when its config.toml would not read, as the home gives it
		const said = [
			'loom serve: http://127.0.0.1:8932/  (watching; Ctrl-C to stop)',
			'loom serve: stopping',
			`Error: ${QUILT}/config.toml`,
			"  is not valid TOML, so this is not a readable quilt: Expected ']' at the end of a table",
			'  declaration (at line 1, column 7)'
		].join('\n');
		expect(refusalOf(said, QUILT, HOME)).toEqual({ text: "config.toml is not valid TOML, so this is not a readable quilt: Expected ']' at the end of a table declaration (at line 1, column 7)" });
	});

	it('takes a port lost as the server started for a port another program holds, and never says to pass a port', () => {
		const said = 'Error: cannot listen on port 8932: address already in use; pass --port N for another, or stop what holds it';
		expect(refusalOf(said, QUILT, HOME)).toEqual({ port: true });
	});

	it('knows a quilt a newer loom made, and an older one is said as loom said it, less the command', () => {
		expect(refusalOf("Error: this quilt's .loom/format says 8, and this loom reads format 7", QUILT, HOME)).toEqual({ newer: { found: 8, reads: 7 } });
		const older = refusalOf('Error: this quilt was made by an earlier loom, in format 1, and this loom reads format 2: loom upgrade brings it forward, its library carried into the node store', QUILT, HOME);
		expect(older).toEqual({ text: 'this quilt was made by an earlier loom, in format 1, and this loom reads format 2' });
	});

	it("gives the system's reason a quilt could not start without its error number, under ~", () => {
		expect(cannotStartOf("[Errno 1] Operation not permitted: '/Users/m/Dropbox/lattice-points/.loom'", HOME)).toBe("Operation not permitted: '~/Dropbox/lattice-points/.loom'");
	});

	it("says where TeX stopped in TeX's words, that loom has no TeX for a missing tool, and never names the tool", () => {
		expect(untypesetOf('latexmk is not installed', 'mine')).toBe('Loom has no TeX yet.');
		expect(untypesetOf('! Undefined control sequence.', 'none')).toBe('Loom has no TeX yet.');
		expect(untypesetOf('! Undefined control sequence.', 'mine')).toBe('TeX stopped at “Undefined control sequence”.');
		expect(untypesetOf('latexmk exited 12: Missing input file', 'loom')).toBe('TeX stopped before it finished.');
	});

	it('writes the paths of what was dropped as the person dropped it', () => {
		const said = '/Users/m/Library/Application Support/loom/app/incoming/0a1b2c3d4e5f6a7b/files/gadget-towers.tex: \\input{sections/intro} names a file that is not there';
		expect(importSaidOf(said, HOME)).toBe('gadget-towers.tex: \\input{sections/intro} names a file that is not there');
	});
});
