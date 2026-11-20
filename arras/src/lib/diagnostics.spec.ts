import { describe, expect, it } from 'vitest';
import { byWork, classOf, forPerson, groupProblems, ownerOf, partsOf, splitFixes, titleOf, workOf, yoursCount } from './diagnostics';
import type { Diagnostic, Manifest } from './manifest/types';

const d = (code: string, more: Partial<Diagnostic> = {}): Diagnostic => ({ severity: 'error', code, message: `${code} said`, locations: [], keys: [], ...more });

describe('Problems', () => {
	it('says whose each diagnostic is, the person being whose a publisher that does not say leaves it', () => {
		expect(ownerOf(d('dangling-link'))).toBe('person');
		expect(ownerOf(d('dangling-link', { owner: 'copy' }))).toBe('copy');
		expect(ownerOf(d('dangling-link', { owner: 'work' }))).toBe('work');
		expect(ownerOf(d('dangling-link', { owner: 'someone new' }))).toBe('person');
	});

	it("shows a person the problems in their own LaTeX alone, and leaves loom's model and its own difficulties in the manifest", () => {
		expect([classOf(d('a')), classOf(d('a', { class: 'model' })), classOf(d('a', { class: 'internal' })), classOf(d('a', { class: 'someday' }))]).toEqual(['latex', 'model', 'internal', 'latex']);
		const items = [
			d('loom:compile-failed', { class: 'latex' }),
			d('loom:unattached-proof', { class: 'model', severity: 'warning' }),
			d('loom:history-corrupt', { class: 'internal' }),
			d('duplicate-id', { class: 'model', severity: 'warning' }),
			d('duplicate-id', { class: 'latex' }),
			d('other:said-nothing')
		];
		expect(forPerson(items).map((x) => [x.code, x.class ?? '-'])).toEqual([
			['loom:compile-failed', 'latex'],
			['duplicate-id', 'latex'],
			['other:said-nothing', '-']
		]);
		// Review counts the person's errors and warnings in their LaTeX, and the manifest still holds every one
		const m = { diagnostics: [...items, d('loom:compile-errors', { class: 'latex', owner: 'copy' }), d('dangling-link', { class: 'latex', severity: 'info' })] };
		expect(yoursCount(m)).toBe(3);
		expect(m.diagnostics.map((x) => x.code)).toContain('loom:unattached-proof');
		expect([titleOf(d('loom:compile-failed')), titleOf(d('loom:compile-errors'))]).toEqual(['A document did not compile', 'A document compiled with errors']);
	});

	it("puts the person's errors and warnings first and every remark apart, whoever's it is", () => {
		const parts = partsOf([
			d('a'),
			d('b', { severity: 'warning' }),
			d('c', { owner: 'copy' }),
			d('e', { owner: 'work' }),
			d('f', { severity: 'info', owner: 'work' }),
			d('g', { severity: 'info' })
		]);
		expect([parts.yours, parts.copy, parts.works, parts.remarks].map((xs) => xs.map((x) => x.code))).toEqual([['a', 'b'], ['c'], ['e'], ['f', 'g']]);
	});

	it('titles a problem by what is wrong, two codes that say one thing as one group, and an unknown code by its message', () => {
		expect(titleOf(d('dangling-link'))).toBe('A reference points nowhere');
		// a Markdown file's link that goes nowhere is the person's, said by what is missing
		expect(['loom:link-target-missing', 'loom:link-place-missing', 'loom:link-work-unknown'].map((c) => titleOf(d(c, { message: c })))).toEqual(['A link to something that is not there', 'A link to a heading or place that is not there', 'A link to a work the library does not hold']);
		expect(titleOf(d('x:snippet-failed', { severity: 'warning' }))).toBe('TeX could not make a text, shown as its source');
		expect(titleOf(d('zzz:made-up', { message: 'Something new.' }))).toBe('Something new.');
		const groups = groupProblems([d('zzz:made-up', { severity: 'info' }), d('loom:duplicate-label'), d('duplicate-id'), d('duplicate-id'), d('dangling-link', { severity: 'warning' })]);
		expect(groups.map((g) => [g.title, g.items.length, g.codes])).toEqual([
			['Defined twice', 3, ['loom:duplicate-label', 'duplicate-id']],
			['A reference points nowhere', 1, ['dangling-link']],
			['zzz:made-up said', 1, ['zzz:made-up']]
		]);
	});

	it("finds a cited work's diagnostic its work by the fix that digests it again, else by its results", () => {
		const m = { nodes: { 'Kre99-thm-2.1': { digest: 'Kre99', file: '.loom/library/Kre99.tex' } } } as unknown as Pick<Manifest, 'nodes'>;
		const again = d('dangling-link', { owner: 'work', fixes: [{ label: 'digest Man12 again', command: 'x', act: { endpoint: 'library-update', body: { works: ['Man12'], redo: true, steps: ['extract'] } } }] });
		const keyed = d('loom:converter-fallback', { owner: 'work', keys: ['Kre99-thm-2.1'] });
		const located = d('loom:missing-package', { owner: 'work', locations: [{ file: '.loom/library/Kre99.tex', line: 1 }] });
		expect([workOf(m, again), workOf(m, keyed), workOf(m, located), workOf(m, d('x', { owner: 'work' }))]).toEqual(['Man12', 'Kre99', 'Kre99', '']);
		expect(byWork(m, [keyed, again, keyed]).map((w) => [w.work, w.items.length])).toEqual([['Kre99', 2], ['Man12', 1]]);
	});

	it("tells a fix a viewer may do as a button from every other, which is an agent's command", () => {
		const { acts, commands } = splitFixes(d('loom:undigested-citekey', { fixes: [{ label: 'digest it', command: 'a', act: { endpoint: 'library-update', body: { works: ['Har77'] } } }, { label: 'by hand', command: 'b' }] }));
		expect([acts.map((f) => f.command), commands.map((f) => f.command)]).toEqual([['a'], ['b']]);
	});
});
