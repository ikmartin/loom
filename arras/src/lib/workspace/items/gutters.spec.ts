import { afterAll, beforeAll, expect, it } from 'vitest';
import { guttersHost } from './gutters';

let report: (width: number, height: number) => void = () => {};
const g = globalThis as Record<string, unknown>;
const saved = { ResizeObserver: g.ResizeObserver, getComputedStyle: g.getComputedStyle, document: g.document };

beforeAll(() => {
	g.ResizeObserver = class {
		constructor(cb: (e: unknown[]) => void) {
			report = (width, height) => cb([{ contentBoxSize: [{ inlineSize: width, blockSize: height }], contentRect: { width, height } }]);
		}
		observe() {}
		disconnect() {}
	};
	g.getComputedStyle = () => ({ fontSize: '16px' });
	g.document = { documentElement: {} };
});
afterAll(() => Object.assign(g, saved));

it('gives the host its width, and narrow below 34rem, only when the width changes', () => {
	const writes: string[] = [];
	const classes = new Set<string>();
	const node = {
		style: { setProperty: (k: string, v: string) => writes.push(`${k}=${v}`) },
		classList: { toggle: (c: string, on: boolean) => (on ? classes.add(c) : classes.delete(c)) }
	} as unknown as HTMLElement;
	guttersHost(node);
	report(900.4, 30000);
	expect(writes).toEqual(['--host-width=900px']);
	expect(classes.has('narrow')).toBe(false);
	// a document growing as a scroll lays out what nears the screen
	report(900, 31000);
	report(900, 32000);
	expect(writes).toHaveLength(1);
	report(500, 32000);
	expect(writes.at(-1)).toBe('--host-width=500px');
	expect(classes.has('narrow')).toBe(true);
});
