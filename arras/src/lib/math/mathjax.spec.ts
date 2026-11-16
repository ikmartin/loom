import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

/** What MathJax was asked to typeset, one entry per call. */
const calls: unknown[][] = [];

vi.mock('mathjax/es5/tex-svg-full.js', () => {
	const mj = (globalThis as unknown as { window: { MathJax: Record<string, unknown> } }).window.MathJax;
	mj.startup = { promise: Promise.resolve() };
	mj.typesetPromise = (els: unknown[]) => {
		calls.push(els);
		return Promise.resolve();
	};
	return {};
});

/** A stand-in for a body element: its `.math` spans counted, its attributes kept. */
function body(formulas: number, connected = true) {
	const attrs = new Set<string>();
	return {
		isConnected: connected,
		setAttribute: (n: string) => attrs.add(n),
		removeAttribute: (n: string) => attrs.delete(n),
		hasAttribute: (n: string) => attrs.has(n),
		querySelectorAll: () => ({ length: formulas })
	};
}

const frame = () => new Promise((r) => setTimeout(r, 30));

beforeAll(() => {
	(globalThis as unknown as { window: object }).window = globalThis;
	(globalThis as unknown as { requestAnimationFrame: (f: () => void) => number }).requestAnimationFrame = (f) => setTimeout(f, 0) as unknown as number;
});
afterEach(() => {
	calls.length = 0;
});

describe('typesetSoon', () => {
	it('typesets every body that asked before the next paint in one pass, after it, and shows each when done', async () => {
		const { typesetSoon } = await import('./mathjax');
		const [a, b, c] = [body(2), body(0), body(3)];
		const done = [a, b, c].map((el) => typesetSoon(el as unknown as Element, []));
		expect(calls).toHaveLength(0);
		expect(a.hasAttribute('data-typesetting')).toBe(true);
		await Promise.all(done);
		expect(calls).toEqual([[a, b, c]]);
		expect([a, b, c].some((el) => el.hasAttribute('data-typesetting'))).toBe(false);
	});

	it('splits a long list into passes of about 48 formulas and leaves out a body that left the page', async () => {
		const { typesetSoon } = await import('./mathjax');
		const bodies = Array.from({ length: 10 }, () => body(10));
		const gone = body(1, false);
		const done = [...bodies, gone].map((el) => typesetSoon(el as unknown as Element, []));
		await Promise.all(done);
		expect(calls.map((c) => c.length)).toEqual([5, 5]);
		expect(calls.flat()).not.toContain(gone);
		expect(gone.hasAttribute('data-typesetting')).toBe(false);
	});

	it('starts again for a body that asks once the passes have ended', async () => {
		const { typesetSoon } = await import('./mathjax');
		const first = typesetSoon(body(1) as unknown as Element, []);
		await frame();
		await first;
		const late = body(1);
		await typesetSoon(late as unknown as Element, []);
		expect(calls).toHaveLength(2);
		expect(calls[1]).toEqual([late]);
	});
});
