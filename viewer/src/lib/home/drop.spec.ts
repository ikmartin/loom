import { describe, expect, it } from 'vitest';
import { readDrop } from './drop';

/** A file entry as a browser gives one for a dropped file. */
const file = (name: string, type = '') => ({ isFile: true, isDirectory: false, name, file: (ok: (f: File) => void) => ok(new File(['x'], name, { type })) });
/** A folder entry, whose reader gives its children in two batches and then none, as a browser's may. */
const folder = (name: string, children: object[]) => ({
	isFile: false,
	isDirectory: true,
	name,
	createReader: () => {
		const batches = [children.slice(0, 1), children.slice(1), []];
		return { readEntries: (ok: (e: object[]) => void) => ok(batches.shift() ?? []) };
	}
});
/** A drop of entries, as a `DataTransfer` gives them. */
const data = (entries: object[]) => ({ items: entries.map((e) => ({ kind: 'file', type: '', webkitGetAsEntry: () => e })), files: [] }) as unknown as DataTransfer;

describe('a drop on the home page', () => {
	it("reads a folder dropped alone as its files, by their paths within it, past a machine's own files", async () => {
		const paper = folder('gadget-towers', [file('gadget-towers.tex'), folder('sections', [file('intro.tex'), file('proof.tex')]), file('.DS_Store'), folder('.git', [file('HEAD')])]);
		const read = await readDrop(data([paper]));
		expect(read?.files.map((f) => f.path).sort()).toEqual(['gadget-towers.tex', 'sections/intro.tex', 'sections/proof.tex']);
		expect(read?.kind).toBe('paper');
		expect(read?.name).toBe('gadget-towers');
		expect(read?.shown).toEqual({ folder: true, name: 'gadget-towers', count: 3 });
	});

	it('keeps the names of several things dropped at once, and a PDF alone is one to read', async () => {
		const many = await readDrop(data([file('paper.tex'), folder('figures', [file('a.pdf', 'application/pdf')])]));
		expect(many?.files.map((f) => f.path).sort()).toEqual(['figures/a.pdf', 'paper.tex']);
		expect(many?.name).toBe('');
		expect(many?.shown.name).toBe('');
		const pdf = await readDrop(data([file('okafor-2022.pdf', 'application/pdf')]));
		expect(pdf?.kind).toBe('pdf');
		expect(pdf?.name).toBe('okafor-2022');
		// a folder of PDFs is a paper's folder, never something to read
		expect((await readDrop(data([folder('figs', [file('a.pdf', 'application/pdf')])])))?.kind).toBe('paper');
	});
});
