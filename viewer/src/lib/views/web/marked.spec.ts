import { describe, expect, it } from 'vitest';
import { CLOSE, marked, OPEN } from './marked';

describe("a search hit's words marked for the converter", () => {
	it('marks the match in place, the words either side kept as they are', () => {
		expect(marked('height at most h number ', 'polynomial', 'ly many in h.')).toBe(`height at most h number ${OPEN}polynomial${CLOSE}ly many in h.`);
	});
	it('marks the whole formula a match falls inside, in either delimiter', () => {
		expect(marked('of height \\(h + ', '1', '\\) is')).toBe(`of height ${OPEN}\\(h + 1\\)${CLOSE} is`);
		expect(marked('of height $h + ', '1', '$ is')).toBe(`of height ${OPEN}$h + 1$${CLOSE} is`);
	});
	it('leaves a formula closed before the match alone', () => {
		expect(marked('of \\(Q\\) of ', 'height', ' at most')).toBe(`of \\(Q\\) of ${OPEN}height${CLOSE} at most`);
		expect(marked('of $Q$ and \\$5 ', 'more', '')).toBe(`of $Q$ and \\$5 ${OPEN}more${CLOSE}`);
	});
});
