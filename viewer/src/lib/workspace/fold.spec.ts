import { describe, expect, it } from 'vitest';
import { drawnAt, foldedAt, MOST, ROW, WORDS } from './fold';

/** Which of `n` groups each place draws at a fold. */
const split = (fold: number, n: number) => {
	const folded = foldedAt(fold);
	const ids = [...Array(n).keys()];
	return { row: ids.filter((i) => drawnAt({ menu: false, folded }, i, n)), menu: ids.filter((i) => drawnAt({ menu: true, folded }, i, n)) };
};

describe('folding the tools that write', () => {
	it('moves no group while only words fold', () => {
		for (let f = 0; f <= WORDS; f++) expect(split(f, 3)).toEqual({ row: [0, 1, 2], menu: [] });
	});

	it('moves the last group first, and every group is drawn in exactly one place', () => {
		expect(split(WORDS + 1, 3)).toEqual({ row: [0, 1], menu: [2] });
		expect(split(WORDS + 2, 3)).toEqual({ row: [0], menu: [1, 2] });
		expect(split(MOST, 3)).toEqual({ row: [], menu: [0, 1, 2] });
		// a bar with two groups is all in the menu before the toolbar's last fold
		expect(split(WORDS + 2, 2)).toEqual({ row: [], menu: [0, 1] });
		expect(split(MOST, 2)).toEqual({ row: [], menu: [0, 1] });
	});

	it('draws a bar outside a toolbar whole, in the row', () => {
		expect([0, 1].every((i) => drawnAt(ROW, i, 2))).toBe(true);
	});
});
