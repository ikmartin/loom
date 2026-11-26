import { describe, expect, it } from 'vitest';
import { shown } from '$lib/views/library/works';
import { library } from '$lib/words/library';
import type { Answer } from '../api';
import type { Gen, ReviewCounts, ReviewList, WorkAnswer, WorksAnswer } from '../types';
import { fixtureSource } from './source';

const ok = <T>(r: Answer<Gen>): T => {
	expect(r.ok).toBe(true);
	return (r as { ok: true; value: unknown }).value as T;
};

describe("round six's fixture", () => {
	it('lists the 300 works the author marked, in the order round six draws them', async () => {
		const src = fixtureSource();
		const { works } = ok<WorksAnswer>(await src.call('library-works', {}));
		expect(works).toHaveLength(300);
		const byTitle = shown(works, { filter: 'all', q: '', sort: { key: 'title', dir: 1 } });
		// the first rows of round six's screen 1, sorted by title
		expect(byTitle.slice(0, 4).map((w) => [w.title, library.byline(w.authors), w.year])).toEqual([
			['A note on admissible weightings', 'Aldane', '2022'],
			['A note on balanced gadget sheaves', 'Kovač and Jansen', '1982'],
			['A note on balanced orientation signs', 'Rossi et al.', '2002'],
			['A note on balanced quivers', 'Zeller et al.', '2006']
		]);
		const smith = works.find((w) => w.title === 'Widgets and their bounds')!;
		expect(smith.digested).toEqual({ statements: 11, of: 62, compared: 2, stubs: 0 });
		expect(smith.short).toBe('Smith 2024');
	});

	it('answers unchanged to the generation it gave, and moves it on a write', async () => {
		const src = fixtureSource();
		const first = ok<WorksAnswer>(await src.call('library-works', {}));
		const again = ok<Gen>(await src.call('library-works', { since: first.gen }));
		expect(again.unchanged).toBe(true);
		const smith = first.works.find((w) => w.title === 'Widgets and their bounds')!;
		const work = ok<WorkAnswer>(await src.call('library-work', { ref: smith.ref }));
		expect(work.outline?.from).toBe('tex');
		expect(work.outline?.sections).toHaveLength(8);
		const radius = work.outline!.items.find((i) => i.title === 'Radius')!;
		expect(radius.paper).toBe('unchecked');
		ok(await src.call('library-check', { node: radius.node, hash: 'x' }));
		const after = ok<WorkAnswer>(await src.call('library-work', { ref: smith.ref, since: first.gen }));
		expect(after.unchanged).toBeUndefined();
		expect(after.outline!.items.find((i) => i.title === 'Radius')!.paper).toBe('matches');
	});

	it('digests what is chosen from a TeX source, and asks an agent for a work held only as a PDF', async () => {
		const src = fixtureSource();
		const { works } = ok<WorksAnswer>(await src.call('library-works', {}));
		const smith = works.find((w) => w.title === 'Widgets and their bounds')!;
		const okafor = works.find((w) => w.title === 'Median orders on weighting lattices')!;
		const work = ok<WorkAnswer>(await src.call('library-work', { ref: smith.ref }));
		const chosen = work.outline!.items.filter((i) => !i.paper).slice(0, 3).map((i) => i.item!);
		expect(ok<{ made: number }>(await src.call('library-digest', { refs: [smith.ref], scope: 'chosen', chosen })).made).toBe(3);
		expect(ok<{ tasks: string[] }>(await src.call('library-digest', { refs: [okafor.ref], scope: 'marked' })).tasks).toHaveLength(1);
	});

	it("counts Review as round six does: 29 for the person, 6 for an agent, 20 on main.tex and 9 on bounds.tex, listed by who is waiting", async () => {
		const src = fixtureSource();
		const c = ok<ReviewCounts>(await src.call('review-counts', {}));
		expect([c.everything, c.agents]).toEqual([29, 6]);
		expect(c.kinds).toEqual({ questions: 2, fetch: 3, cited: 4, check: 5, attest: 2, 'accepted-changed': 6, 'attested-changed': 2, edits: 5 });
		expect(c.drafts).toEqual([{ doc: 'drafting/main.tex', n: 20 }, { doc: 'drafting/bounds.tex', n: 9 }]);
		const l = ok<ReviewList>(await src.call('review-list', { kind: 'all' }));
		expect(l.groups.map((g) => g.kind)).toEqual(['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'attested-changed', 'edits', 'agents']);
		// a draft's count is its entry in drafts; the list narrows to it
		expect(ok<ReviewList>(await src.call('review-list', { doc: 'drafting/bounds.tex' })).groups.reduce((n, g) => n + (g.kind === 'agents' ? 0 : g.rows.length), 0)).toBe(9);
		// a yes in the Library leaves Review's row of that work
		await src.call('library-check', { node: 'tq-00K3', hash: 'sha256:x' });
		const after = ok<ReviewList>(await src.call('review-list', { kind: 'check' }));
		expect(after.groups[0].rows.map((r) => r.row).join(' ')).toContain('check:');
		expect(ok<ReviewCounts>(await src.call('review-counts', {})).kinds.check).toBe(5);
	});
});

