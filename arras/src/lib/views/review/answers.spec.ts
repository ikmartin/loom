// The column's message after accepting, keeping or discarding: what was done, and what was not in the viewer's words, by a code where there is one, else plainly; never loom's own sentence.
import { describe, expect, it } from 'vitest';
import type { UnresolvedReview } from '$lib/manifest/types';
import { acceptSaid, changeSaid } from './answers';

const names: Record<string, string> = { 'sy-0001': 'Widget', 'sy-0002': 'Orbits', 'sy-000B': 'Lemma 2.4' };
const name = (k: string) => names[k] ?? k;
const row = (code: UnresolvedReview['refusal_code']) => ({ key: '', cause: 'earlier-change', pull: '', changed_text: true, refusal: 'Lemma 2.4 has no \\proves or \\cites directive (sy-000B)', refusal_code: code }) as UnresolvedReview;

describe('after accepting', () => {
	it("says what was accepted, and a refused block plainly where its row gives no code, never loom's sentence", () => {
		const text = acceptSaid(['sy-0001'], ['sy-0002'], name, () => undefined);
		expect(text).toBe('Accepted Widget. Orbits was not accepted.');
		expect(text).not.toContain('Accept Widget first');
	});

	it("says why by the row's code", () => {
		const text = acceptSaid([], ['sy-000B'], name, () => row('unclassified'));
		expect(text).toBe('Lemma 2.4 was not accepted: loom cannot tell whether it is proved here, cited, or assumed.');
		expect(text).not.toContain('directive');
	});

	it('counts several accepted', () => {
		expect(acceptSaid(['sy-0001', 'sy-0002'], [], name, () => undefined)).toBe('Accepted 2 results.');
	});
});

describe('after keeping or discarding', () => {
	it('says how many, and each reason something was not done once, by its code', () => {
		const text = changeSaid('keep', 2, [{ code: 'changed-since' }, { code: 'changed-since' }]);
		expect(text).toBe('Kept 2 changes. 2 changes were not kept: its words changed in the file since, so loom left them as they are.');
	});

	it("says a reason Review has no word for by the frame's, and a code nobody knows plainly, never loom's sentence", () => {
		const refused = [{ code: 'author-only', why: 'An agent reads; only the author keeps' }, { code: 'brand-new', why: 'drafting/nodes/sy-0002.tex: the door refused the write (EACCES)' }];
		const text = changeSaid('discard', 0, refused);
		expect(text).toBe('One change was not discarded: only a person can do this; loom does not take it from an agent. One change was not discarded.');
		for (const r of refused) expect(text).not.toContain(r.why);
	});

	it('says nothing was done where nothing was asked of it but refused nothing', () => {
		expect(changeSaid('keep', 0, [])).toBe('Kept 0 changes.');
	});
});
