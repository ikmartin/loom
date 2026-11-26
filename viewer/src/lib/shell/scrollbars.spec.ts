import { afterAll, beforeAll, expect, it } from 'vitest';
import { revealWhileScrolling } from './scrollbars';

const g = globalThis as Record<string, unknown>;
const saved = { document: g.document, Element: g.Element };
let onScroll: (e: { target: unknown }) => void = () => {};

beforeAll(() => {
	g.Element = class {};
	g.document = { addEventListener: (_: string, f: typeof onScroll) => (onScroll = f), removeEventListener: () => {} };
});
afterAll(() => Object.assign(g, saved));

it('marks a scrolling element once, not on every scroll event', () => {
	const stop = revealWhileScrolling();
	const classes = new Set<string>();
	let adds = 0;
	const el = Object.assign(Object.create((g.Element as { prototype: object }).prototype), {
		closest: () => ({}),
		classList: { contains: (c: string) => classes.has(c), add: (c: string) => (adds++, classes.add(c)), remove: (c: string) => classes.delete(c) }
	});
	for (let i = 0; i < 20; i++) onScroll({ target: el });
	expect(classes.has('is-scrolling')).toBe(true);
	expect(adds).toBe(1);
	stop();
});
