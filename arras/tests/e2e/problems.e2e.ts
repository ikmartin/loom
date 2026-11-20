// Review › Problems: the problems in the person's own LaTeX, filtered by class from a manifest that keeps every diagnostic; the person's files first, open and counted, an agent's copy's folded beneath and said to be whose it is; problems titled by what is wrong, opened at their place, filtered in the page, and never offered as a command. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';
import { manifest, serve } from '../manifest';

type D = { severity: string; code: string; class?: string; owner?: string; locations: { file: string; line: number }[]; keys: string[] };
const all = manifest.diagnostics as D[];
const latex = (d: D) => (d.class ?? 'latex') === 'latex';
const yours = all.filter((d) => latex(d) && (d.owner ?? 'person') === 'person' && d.severity !== 'info');

/** A cited work's problem: a dangling reference in Kre99's digest, which is loom's reading of the paper and so loom's own. */
const inDigest = {
	severity: 'warning',
	code: 'dangling-link',
	class: 'internal',
	message: '\\ref{nowhere} names no node or region',
	locations: [{ file: '.loom/library/Kre99.tex', line: 12 }],
	keys: [],
	owner: 'work',
	fixes: [{ label: 'digest Kre99 again', command: 'loom library update Kre99 --only extract --redo', act: { endpoint: 'library-update', body: { works: ['Kre99'], redo: true, steps: ['extract'] } } }]
};
/** An agent's copy that did not compile: the LaTeX of a document that is the agent's. */
const copyFailed = {
	severity: 'error',
	code: 'loom:compile-failed',
	class: 'latex',
	message: '.loom/agents/copies/aidoc.tex did not compile: Undefined control sequence \\oops',
	locations: [{ file: '.loom/agents/copies/aidoc.tex', line: 40 }],
	keys: ['.loom/agents/copies/aidoc.tex'],
	owner: 'copy'
};
/** The person's document that did not compile, with a command fix an agent runs. */
const failed = {
	severity: 'error',
	code: 'loom:compile-failed',
	class: 'latex',
	message: 'drafting/main.tex did not compile: Undefined control sequence \\oops',
	locations: [{ file: 'drafting/main.tex', line: 31 }],
	keys: ['drafting/main.tex'],
	owner: 'person',
	fixes: [{ label: 'see the log', command: 'loom compile drafting/main.tex' }]
};

test("a person is shown the problems in their own LaTeX alone, and the manifest keeps every agent's code", async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(inDigest as never, copyFailed as never, failed as never));
	await page.goto('/review/problems');
	const mine = page.getByTestId('problems-yours');
	// every class but the person's LaTeX is in the manifest the page read, and on the page nowhere
	const agents = all.filter((d) => !latex(d));
	expect(agents.map((d) => d.code)).toContain('loom:uses-missing');
	expect(new Set(all.map((d) => d.class))).toEqual(new Set(['latex', 'model', 'internal']));
	await expect(mine.getByTestId('problems-yours-count')).toHaveText(String(yours.length + 1));
	await expect(mine.getByTestId('problem')).toHaveCount(yours.length + 1);
	await expect(mine.locator('[data-testid="problem-group"][data-codes="loom:compile-failed"] .title')).toHaveText('A document did not compile');
	// a code whose every instance is an agent's has no group; one with instances of both kinds shows the person's alone
	for (const code of new Set(agents.map((d) => d.code).filter((c) => !all.some((d) => latex(d) && d.code === c)))) await expect(page.locator(`[data-testid="problem-group"][data-codes~="${code}"]`)).toHaveCount(0);
	const seeNowhere = agents.find((d) => d.code === 'dangling-link') as D & { message: string };
	await expect(page.getByText(seeNowhere.message)).toHaveCount(0);
	await expect(page.getByText('names no node or region')).toHaveCount(0);
	for (const part of ['problems-works', 'problems-remarks']) await expect(page.getByTestId(part)).toHaveCount(0);
	// an agent's copy's LaTeX is the agent's: folded beneath, said whose it is
	await expect(page.getByTestId('problems-copy')).not.toHaveAttribute('open');
	await expect(page.getByTestId('problems-copy')).toContainText('Proposed Changes');
	await expect(page.getByTestId('problems-copy').locator('a[href="/review/proposed"]')).toHaveCount(1);
	// a fix is a command an agent runs, never offered to the person
	await expect(page.getByTestId('fix')).toHaveCount(0);
	await expect(page.locator('main')).not.toContainText('loom compile');
	// Review's column counts what is the person's alone
	await expect(page.getByTestId('section-count-problems')).toHaveText(String(yours.length + 1));
});

/** A document gone with annotations on it, as the publisher says it: the person's to be shown, a warning, with the command an agent runs. */
const goneWithNotes = {
	severity: 'warning',
	code: 'loom:document-gone',
	class: 'latex',
	message: '3 annotations are on drafting/old.tex, which is gone; the history does not say where it went',
	locations: [],
	keys: [],
	owner: 'person',
	subject: 'record',
	fixes: [{ label: 'record where it went, NEW being its path now', command: 'loom mv drafting/old.tex NEW' }]
};
/** A document gone that only acceptance rows name: loom's model, an agent's. */
const goneRowsOnly = { ...goneWithNotes, class: 'model', message: 'drafting/older.tex is gone and the history does not say where it went; 2 acceptance rows name it', keys: ['sy-0002', 'sy-0003'], fixes: [{ label: 'record where it went, NEW being its path now', command: 'loom mv drafting/older.tex NEW' }] };

test('a document gone with annotations on it is one row saying how many, and one with none is not shown', async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(goneWithNotes as never, goneRowsOnly as never));
	await page.goto('/review/problems');
	const group = page.locator('[data-testid="problems-yours"] [data-testid="problem-group"][data-codes="loom:document-gone"]');
	await expect(group.locator('.title')).toHaveText('A document is gone');
	await expect(group.getByTestId('problem')).toHaveCount(1);
	await expect(group.getByTestId('problem')).toContainText('3 annotations are on drafting/old.tex, which is gone');
	await expect(page.locator('main')).not.toContainText('drafting/older.tex');
	await expect(page.locator('main')).not.toContainText('loom mv');
	await expect(page.getByTestId('problems-yours-count')).toHaveText(String(yours.length + 1));
});

test('a problem is titled by what is wrong, with its code beside it', async ({ page }) => {
	await page.goto('/review/problems');
	const mine = page.getByTestId('problems-yours');
	await expect(mine.locator('[data-testid="problem-group"][data-codes="dangling-link"] .title')).toHaveText('A reference points nowhere');
	await expect(mine.locator('[data-testid="problem-group"][data-codes="double-inclusion"] .title')).toHaveText('A file is included twice');
	await expect(mine.locator('[data-testid="problem-group"][data-codes="double-inclusion"] .code')).toHaveText('double-inclusion');
	// errors first
	await expect(mine.getByTestId('problem-group').first()).toHaveClass(/sev-error/);
});

test('a location is a link to its file at its line, and a key opens at its place', async ({ page }) => {
	await page.goto('/review/problems');
	const group = page.locator('[data-testid="problems-yours"] [data-testid="problem-group"][data-codes="missing-include"]');
	const at = group.getByTestId('problem-location').first();
	await expect(at).toHaveText('drafting/main.tex:72');
	await at.click();
	const lines = page.getByTestId('file-lines');
	await expect(lines).toBeVisible();
	await expect(lines.locator('#L72')).toHaveClass(/at/);
	await expect(lines.locator('#L72')).toBeInViewport();
	await page.goto('/review/problems');
	const open = page.locator('[data-testid="problems-yours"] [data-testid="problem-group"][data-codes="dangling-link"]').getByTestId('problem-open').first();
	await expect(open).toHaveAttribute('href', /^\/(node|master|file)\//);
});

test('the filters stand in the page: severity from the URL, and a search over titles and messages', async ({ page }) => {
	await page.goto('/review/problems?severity=error');
	await expect(page.getByTestId('filter-error')).toHaveAttribute('aria-pressed', 'true');
	const errors = yours.filter((d) => d.severity === 'error');
	await expect(page.getByTestId('problems-yours').getByTestId('problem')).toHaveCount(errors.length);
	await page.getByTestId('filter-error').click();
	await expect(page).toHaveURL(/\/review\/problems$/);
	await page.getByTestId('problem-search').fill('points nowhere');
	await expect(page.getByTestId('problems-yours').getByTestId('problem-group')).toHaveCount(1);
	await page.getByTestId('problem-search').fill('no problem says this');
	await expect(page.getByTestId('problems-none')).toHaveText('None of yours matches these filters.');
	// the column is the column's: the page puts no panel in it
	await expect(page.locator('.page-panel')).toHaveCount(0);
});

test('a code the URL names opens where it is, and the help names no command', async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(copyFailed as never));
	await page.goto('/review/problems?code=loom%3Acompile-failed');
	await expect(page.getByTestId('problems-copy')).toHaveAttribute('open');
	await expect(page.getByTestId('filter-code')).toBeVisible();
	await expect(page.getByTestId('problems-copy').getByTestId('problem-group').first()).toHaveAttribute('open');
	await page.getByTestId('help-problems').click();
	await expect(page.getByTestId('help-panel-problems')).toContainText('Your files come first');
	await expect(page.getByTestId('help-panel-problems')).not.toContainText('command line');
});

test('the page is read at rest with its bar drawn', async ({ page }) => {
	await page.goto('/review/problems');
	await expect(page.getByTestId('problems-yours').getByTestId('problem').first()).toBeVisible();
	expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollbarColor)).not.toBe('rgba(0, 0, 0, 0) rgba(0, 0, 0, 0)');
});
