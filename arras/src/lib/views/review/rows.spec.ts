// Review's rows say what round six says: the works' results named or counted, which drafts rest on them, and each task's sentence from what was asked and of what.
import { describe, expect, it } from 'vitest';
import { review as words } from '$lib/words/review';
import { round6 } from '$lib/library/fixtures/round6';
import type { ReviewRow, TaskRow } from '$lib/library/types';
import { line, marks, question, quiet, task } from './rows';

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
	const r = round6().review;
	const byRow = (id: string) => r.rows.find((x) => x.row.startsWith(id)) as ReviewRow;

	it('draw their first lines and quiet lines as the prototype does', () => {
		const okafor = r.rows.find((x) => x.kind === 'cited' && x.citation === undefined && x.short === 'Okafor 2022')!;
		expect(line(okafor)).toBe('Okafor 2022 · Theorem 2.3 and Corollary 4.2');
		expect(quiet(okafor)).toBe('PDF only · main.tex rests on both');
		const smith = r.rows.find((x) => x.kind === 'cited' && x.citation === undefined && x.short === 'Smith 2024')!;
		expect(quiet(smith)).toBe('not found in its TeX source · bounds.tex rests on it');
		expect(line(byRow('cited:m-'))).toBe('main.tex · the proof of Theorem 3.4 cites Okafor 2022 without naming a result');
		expect(quiet(byRow('check:ev-'))).toBe('proposed by Claude Code');
		expect(line(byRow('check:ev-'))).toBe('Arden 2024 · a correction to Definition 1.2');
		expect(line(byRow('attested-changed:def'))).toBe('main.tex · Definition 3.7, Connected');
		expect(quiet(byRow('attested-changed:def'))).toBe('changed since you attested it · 2 results rest on it');
		expect(quiet(byRow('attested-changed:cor'))).toBe('its statement changed since you attested it, 20 Nov');
		expect(quiet(byRow('edits:c-4d'))).toBe('bounds.tex has not compiled since this edit (line 14)');
		expect(marks(byRow('attest:tq'))).toEqual(['checked', 'attest']);
	});

	it("say an agent's question with where it was asked", () => {
		const [a, b] = r.rows.filter((x) => x.kind === 'questions') as Extract<ReviewRow, { kind: 'questions' }>[];
		expect(question(a).by + question(a).rest).toBe('Claude Code asks, digesting Okafor 2022: your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?');
		expect(question(b).rest).toBe(' asks, on main.tex, Theorem 3.4: should the count include the zero weighting?');
	});

	it("say each task's sentence from what was asked, and one of a kind loom does not make by its own words", () => {
		expect(r.tasks.map(task)).toEqual([
			'Digest the 2 places you marked in Okafor 2022',
			'Transcribe the second proof of Proposition 3.4 of Smith 2024, from Halberd and Ravel 2021, pages 22–23',
			'Answer, on main.tex, proof of Theorem 3.4: does the count need the median order?',
			'Digest the whole of Vance et al. 2023',
			'Read Theorem 2.3 of Okafor 2022',
			'Check the macros of Smith 2024 against its preamble'
		]);
		const t = (what: string, on: TaskRow['on'], text?: string): TaskRow => ({ row: 'r', kind: 'agents', docs: [], task: 't', what, on, text, working: null, asked_at: '' });
		expect(task(t('restate', { name: 'Corollary 3.5', doc: 'drafting/main.tex' }))).toBe('Restate the Lean of Corollary 3.5 of main.tex');
		expect(task(t('which-result', { short: 'Okafor 2022', where: 'the proof of Theorem 3.4' }))).toBe('Say which result of Okafor 2022 the proof of Theorem 3.4 cites');
		expect(task(t('formalize', { name: 'Theorem 3.4', doc: 'drafting/main.tex' }))).toBe('Formalize Theorem 3.4 of main.tex');
		expect(task(t('digest', { short: 'Okafor 2022', scope: 'marked', count: 1 }))).toBe('Digest the place you marked in Okafor 2022');
	});

	it("names a work's results in the paper's order, whatever order they come in", async () => {
		const { inPaperOrder } = await import('./rows');
		expect(words.results(inPaperOrder(['Lemma 5.9', 'Lemma 5.7']))).toBe('Lemmas 5.7 and 5.9');
		expect(inPaperOrder(['Lemma 5.10', 'Theorem 5.9', 'Corollary A.1', 'Lemma 5.7'])).toEqual(['Lemma 5.7', 'Theorem 5.9', 'Lemma 5.10', 'Corollary A.1']);
	});
});
