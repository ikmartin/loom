// Review's rows say what round six says: the works' results named or counted, which drafts rest on them, and each task's sentence from what was asked and of what.
import { describe, expect, it } from 'vitest';
import { review as words } from '$lib/words/review';
import { REF, round6 } from '$lib/library/fixtures/round6';
import type { ReviewRow, TaskRow } from '$lib/library/types';
import { joined, line, marks, question, quiet, task, type Names } from './rows';

describe("a work's results in a row", () => {
	it('are named when one or two, the word made plural for two of a kind, and counted past two', () => {
		expect(words.results(['Theorem 5.1'])).toBe('Theorem 5.1');
		expect(words.results(['Theorem 2.3', 'Corollary 4.2'])).toBe('Theorem 2.3 and Corollary 4.2');
		expect(words.results(['Lemma 5.7', 'Lemma 5.9'])).toBe('Lemmas 5.7 and 5.9');
		expect(words.results(['Corollary 1', 'Corollary 2'])).toBe('Corollaries 1 and 2');
		expect(words.results(Array.from({ length: 9 }, (_, i) => `Lemma ${i}`))).toBe('9 results');
	});

	it('say which drafts rest on them, of how many', () => {
		expect(words.rests(['drafting/main.tex'], 1, 1)).toBe('main.tex rests on it');
		expect(words.rests(['drafting/main.tex'], 2, 2)).toBe('main.tex rests on both');
		expect(words.rests(['drafting/bounds.tex'], 1, 9)).toBe('bounds.tex rests on one');
		expect(words.rests(['drafting/main.tex', 'drafting/bounds.tex'], 3, 5)).toBe('main.tex and bounds.tex rest on 3');
		expect(words.rests([], 0, 3)).toBe('');
	});
});

describe("round six's rows", () => {
	const f = round6();
	const r = f.review;
	const byRow = (id: string) => r.rows.find((x) => x.row.startsWith(id)) as ReviewRow;
	// what the rows name by id, as the views read it: the works from the list, a library result from its node, a draft's result from the manifest
	const NODES: Record<string, { name: string; short: string }> = { 'tq-04A1': { name: 'Theorem 2.3', short: 'Okafor 2022' } };
	const RESULTS: Record<string, string> = { 'sy-0003': 'Theorem 2.1', 'sy-0004': 'proof of Theorem 2.1', 'cor:cycle': 'Corollary 3.5', 'thm:count': 'Theorem 3.4', 'thm:count/proof': 'proof of Theorem 3.4' };
	const n: Names = { work: (ref) => f.works.find((w) => w.ref === ref), node: (id) => NODES[id], result: (label) => RESULTS[label] };
	const none: Names = { work: () => undefined, node: () => undefined, result: () => undefined };

	it('draw their first lines and quiet lines as the prototype does', () => {
		const okafor = r.rows.find((x) => x.kind === 'cited' && x.citation === undefined && x.short === 'Okafor 2022')!;
		expect(line(okafor, n)).toBe('Okafor 2022 · Theorem 2.3 and Corollary 4.2');
		expect(quiet(okafor)).toBe('PDF only · main.tex rests on both');
		const smith = r.rows.find((x) => x.kind === 'cited' && x.citation === undefined && x.short === 'Smith 2024')!;
		expect(quiet(smith)).toBe('not found in its TeX source · bounds.tex rests on it');
		expect(line(byRow('cited:m-'), n)).toBe('main.tex · the proof of Theorem 3.4 cites Okafor 2022 without naming a result');
		expect(quiet(byRow('check:ev-'))).toBe('proposed by Claude Code');
		expect(line(byRow('check:ev-'), n)).toBe('Arden 2024 · a correction to Definition 1.2');
		expect(line(byRow('attested-changed:def'), n)).toBe('main.tex · Definition 3.7');
		expect(quiet(byRow('attested-changed:def'))).toBe('changed since you attested it · 2 results rest on it');
		expect(quiet(byRow('attested-changed:cor'))).toBe('its statement changed since you attested it, 20 Nov');
		expect(line(byRow('fetch:t-2026-11-21-pq0d4n'), n)).toBe('Jones 2019 · Covering estimates');
		expect(line(byRow('fetch:t-2026-11-21-pq0d4n'), none)).toBe('a paper');
		expect(quiet(byRow('edits:c-4d'))).toBe('bounds.tex has not compiled since this edit (line 14)');
		expect(marks(byRow('attest:tq'))).toEqual(['checked', 'attest']);
	});

	it("say an agent's question with where it was asked", () => {
		const [a, b] = r.rows.filter((x) => x.kind === 'questions') as Extract<ReviewRow, { kind: 'questions' }>[];
		// where the agent's session was digesting a work when it asked, the row says so
		expect(question(a, n).by + question(a, n).rest).toBe('Claude Code asks, digesting Okafor 2022: your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?');
		expect(question({ ...a, under: null }, n).rest).toBe(' asks, on Okafor 2022, page 7: your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?');
		expect(question(b, n).rest).toBe(' asks, on main.tex, Theorem 2.1: should the count include the zero weighting?');
		// while the names are read, or where nothing names them, a row says what it is without an id
		expect(question(b, none).rest).toBe(' asks, on main.tex, a result: should the count include the zero weighting?');
	});

	it("say each task's sentence from what was asked, and one of a kind loom does not make by its own words", () => {
		expect(r.tasks.map((t) => task(t, n))).toEqual([
			'Digest the 2 places you marked in Okafor 2022',
			'Transcribe the second proof of Proposition 3.4 of Smith 2024, from Halberd and Ravel 2021, pages 22–23',
			'Answer, on main.tex, proof of Theorem 2.1: does the count need the median order?',
			'Digest the whole of Vance et al. 2023',
			'Read Theorem 2.3 of Okafor 2022',
			'Check the macros of Smith 2024 against its preamble'
		]);
		const t = (what: string, on: TaskRow['on'], own: Partial<TaskRow>): TaskRow => ({ row: 'r', kind: 'agents', docs: ['drafting/main.tex'], task: 't', what, on, working: null, asked_at: '', words: '', ...own });
		expect(task(t('restate', { label: 'cor:cycle' }, { target: { label: 'cor:cycle' }, differs: 'the cycle' }), n)).toBe('Restate the Lean of Corollary 3.5 of main.tex');
		expect(task(t('which-result', { block: { key: 'thm:count/proof' } }, { cites: REF.okafor }), n)).toBe('Say which result of Okafor 2022 the proof of Theorem 3.4 cites');
		expect(task(t('formalize', { label: 'thm:count' }, { target: { label: 'thm:count' } }), n)).toBe('Formalize Theorem 3.4 of main.tex');
		expect(task(t('digest', { ref: REF.okafor }, { ref: REF.okafor, scope: 'marked', marks: ['a-1'] }), n)).toBe('Digest the place you marked in Okafor 2022');
		expect(task(t('read', { node: 'tq-04A1' }, { nodes: ['tq-04A1'] }), none)).toBe('Read a result of a paper');
	});

	it("names a work's results in the paper's order, whatever order they come in", async () => {
		const { inPaperOrder } = await import('./rows');
		expect(words.results(inPaperOrder(['Lemma 5.9', 'Lemma 5.7']))).toBe('Lemmas 5.7 and 5.9');
		expect(inPaperOrder(['Lemma 5.10', 'Theorem 5.9', 'Corollary A.1', 'Lemma 5.7'])).toEqual(['Lemma 5.7', 'Theorem 5.9', 'Lemma 5.10', 'Corollary A.1']);
	});
});

describe('the kinds the viewer shows', () => {
	const row = (kind: string, id: string) => ({ row: id, kind }) as unknown as ReviewRow;
	it('join the attested results that changed to the Lean statements to attest, first, in the place of whichever came first', () => {
		const shown = joined([
			{ kind: 'questions', rows: [row('questions', 'q')] },
			{ kind: 'attest', rows: [row('attest', 'a1'), row('attest', 'a2')] },
			{ kind: 'attested-changed', rows: [row('attested-changed', 'c1')] },
			{ kind: 'edits', rows: [row('edits', 'e')] }
		]);
		expect(shown.map((g) => g.kind)).toEqual(['questions', 'attest', 'edits']);
		expect(shown[1].rows.map((r) => r.row)).toEqual(['c1', 'a1', 'a2']);
		expect(joined([{ kind: 'attested-changed', rows: [row('attested-changed', 'c1')] }])).toEqual([{ kind: 'attest', rows: [row('attested-changed', 'c1')] }]);
	});
});
