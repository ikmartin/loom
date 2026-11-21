// The Web's list draws only the lines in view, however many results it holds.
import { describe, expect, it } from 'vitest';
import type { Row, WebList } from '$lib/library/types';
import { HEIGHT, inView, lay } from './window';

const row = (i: number): Row => ({ result: `r${i}`, name: `Lemma ${i}`, taxon: 'lemma', title: null, source: { ref: 'w', short: 'W' }, paper: 'unchecked', lean: null });

describe("the Web's list in a window", () => {
	it('lays out a draft and what it rests on at five thousand results, and draws a few dozen of them', () => {
		const groups = Array.from({ length: 60 }, (_, g) => ({ group: `w${g}`, short: `W ${g}`, n: 80, ...(g < 3 ? { rows: Array.from({ length: 80 }, (_, i) => row(g * 80 + i)) } : {}) }));
		const list: WebList = { gen: 1, count: 5140, sections: [{ head: 'draft', doc: 'd.tex', rows: Array.from({ length: 340 }, (_, i) => row(10000 + i)) }, { head: 'uses', doc: 'd.tex', groups }] };
		const { lines, height } = lay(list, () => true, (g) => g.rows ?? null);
		expect(lines.length).toBe(2 + 340 + 60 + 60 * 80);
		expect(height).toBe(2 * HEIGHT.head + (340 + 4800) * HEIGHT.row + 60 * HEIGHT.group);
		const shown = inView(lines, 20000, 20800);
		expect(shown.length).toBeLessThan(60);
		expect(shown.some((l) => l.kind === 'pending')).toBe(true);
	});

	it('lays out the list by status, and its last line while more is to be read', () => {
		const { lines } = lay({ gen: 1, count: 500, rows: Array.from({ length: 200 }, (_, i) => row(i)), more: 300 }, () => true, () => null);
		expect(lines.at(-1)?.kind).toBe('note');
		expect(inView(lines, 0, 600).length).toBeLessThan(40);
	});

	it("draws five of a graph's column of more than six, whatever it was sent", async () => {
		const { capped } = await import('./window');
		expect(capped(Array.from({ length: 300 }, (_, i) => i), 0)).toEqual({ rows: [0, 1, 2, 3, 4], more: 295 });
		expect(capped([1, 2, 3, 4, 5, 6], 0)).toEqual({ rows: [1, 2, 3, 4, 5, 6], more: 0 });
		expect(capped([1, 2, 3, 4, 5], 12)).toEqual({ rows: [1, 2, 3, 4, 5], more: 12 });
	});
});
