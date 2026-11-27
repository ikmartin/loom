// A save's blocks drawn from source and swapped for TeX's (a demonstration), against a stubbed manifest store: a draft stands from the `drafted` event until the manifest of the build it names has been fetched, then goes, so the next draw is TeX's block.
import { beforeEach, describe, expect, it, vi } from 'vitest';

/** How many drafts stood each time the manifest was fetched. */
const fetched: number[] = [];
let m: typeof import('./drafts.svelte');
vi.mock('$lib/manifest/client.svelte', () => ({ store: { refresh: async () => void fetched.push(m.drafts.shown.size) } }));

beforeEach(async () => {
	fetched.length = 0;
	vi.resetModules();
	m = await import('./drafts.svelte');
});

const SRC = 'drafting/nodes/sh-0009.tex:0:233';
const event = (build: number, body: string, src = SRC, server = 7) => JSON.stringify({ server, build, blocks: [{ src, kind: 'env', body }] });
const built = (published: number, failed = 0, server = 7) => ({ server, published, failed, why: null });

describe('a block drawn from source', () => {
	it('stands until the manifest of the build that publishes it is fetched, and then gives way to TeX’s', async () => {
		m.drafts.take(event(5, 'Let $c$ be fresh.'));
		expect(m.drafts.shown.get(SRC)?.build).toBe(5);
		await m.drafts.heard(built(4));
		expect(m.drafts.shown.has(SRC)).toBe(true);
		expect(fetched).toEqual([]);
		await m.drafts.heard(built(5));
		// fetched while the draft still stood, so the page never draws the old block between the two
		expect(fetched).toEqual([1]);
		expect(m.drafts.shown.size).toBe(0);
	});

	it('goes at once when its build failed, or another server answers', async () => {
		m.drafts.take(event(5, 'one'));
		await m.drafts.heard(built(4, 5));
		expect(m.drafts.shown.size).toBe(0);
		m.drafts.take(event(6, 'two'));
		await m.drafts.heard(built(1, 0, 8));
		expect(m.drafts.shown.size).toBe(0);
		expect(fetched).toEqual([]);
	});

	it('is replaced whole by a later save of the same file, which is said against the same publication', () => {
		m.drafts.take(event(5, 'first'));
		m.drafts.take(event(6, 'second', 'drafting/nodes/sh-0009.tex:234:632'));
		expect([...m.drafts.shown.keys()]).toEqual(['drafting/nodes/sh-0009.tex:234:632']);
		m.drafts.take(event(6, 'elsewhere', 'drafting/nodes/sh-0007.tex:0:228'));
		expect(m.drafts.shown.size).toBe(2);
	});

	it('is drawn with the page’s numbers, `??` for a label TeX has not numbered, and an unknown command as its source', () => {
		const html = m.drawDraft('\\label{sh-0009}\\uses{sh-0007}\nBy Proposition~\\ref{sh-0007} and \\ref{sh-0999}, $x \\in \\Zcyc$ is \\fancy{new}.', { 'sh-0007': { number: '2.6' } });
		expect(html).toContain('2.6');
		expect(html).toContain('??');
		expect(html).toContain('<span class="tx-unknown">\\fancy</span>');
		expect(html).toContain('<span class="math inline">\\(x \\in \\Zcyc\\)</span>');
		expect(html).not.toContain('sh-0009');
		expect(html).not.toContain('uses');
	});
});
