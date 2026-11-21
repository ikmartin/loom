// Review on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/review6.ts`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 4 to 12): the column's kinds, counts and drafts; the list by who is waiting; answering a question, keeping an edit, withdrawing a task; and the rules that hold everywhere: no control but the four view names changes view, and no id is drawn. Where Review's reads are not served, today's Review stands, which its own specs hold.
import { expect, test, type Page } from '@playwright/test';

async function open(page: Page): Promise<void> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/review?fixture=round6');
	await expect(page.getByTestId('review-view')).toBeVisible();
	await expect(page.getByTestId('review-row').first()).toBeVisible();
}

const count = (page: Page, testid: string) => page.getByTestId(testid).locator('.n');

test('Everything lists 29 rows by who is waiting, and the column counts each kind alphabetically, the agents apart', async ({ page }) => {
	await open(page);
	await expect(count(page, 'review-kind-all')).toHaveText('29');
	const kinds = await page.getByTestId('review-column').locator('[data-testid^="review-kind-"]').evaluateAll((bs) => bs.map((b) => b.getAttribute('data-testid')!.slice(12) + ' ' + b.querySelector('.n')?.textContent));
	expect(kinds).toEqual(['all 29', 'accepted-changed 6', 'questions 2', 'attested-changed 2', 'cited 4', 'check 5', 'attest 2', 'fetch 3', 'edits 5', 'agents 6']);
	const groups = await page.getByTestId('review-group').evaluateAll((gs) => gs.map((g) => g.getAttribute('data-kind')));
	expect(groups).toEqual(['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'attested-changed', 'edits', 'agents']);
	await expect(page.getByTestId('review-row')).toHaveCount(29);
	// the agents' group starts folded
	await expect(page.getByTestId('review-task')).toHaveCount(0);
	await page.getByTestId('review-group').filter({ hasText: 'Waiting for an agent' }).getByRole('button').click();
	await expect(page.getByTestId('review-task')).toHaveCount(6);
	await expect(page.getByTestId('review-draft')).toHaveText(['main.tex20', 'bounds.tex9']);
});

test('the column shows a kind alone, and a draft narrows the list and the counts', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	await expect(page.getByTestId('review-row')).toHaveCount(5);
	await expect(page.getByTestId('review-row').first()).toContainText('Smith 2024 · 9 results');
	await expect(page.getByTestId('review-row').first()).toContainText('bounds.tex rests on one');
	await page.getByTestId('review-draft').filter({ hasText: 'bounds.tex' }).click();
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await expect(count(page, 'review-kind-all')).toHaveText('9');
	await page.getByTestId('review-kind-all').click();
	await expect(count(page, 'review-kind-all')).toHaveText('29');
	await expect(page).toHaveURL(/\/review/);
});

test("an agent's question is answered by a choice or in the person's words, and leaves", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-questions').click();
	const first = page.getByTestId('review-row').first();
	await expect(first).toContainText('Claude Code asks, digesting Okafor 2022: your mark on page 7');
	await first.getByRole('button', { expanded: false }).click();
	await first.getByRole('button', { name: 'only the proposition', exact: true }).click();
	await expect(page.getByTestId('column-message')).toContainText('Answered. Claude Code is told.');
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await page.getByTestId('review-row').first().getByRole('button', { expanded: false }).click();
	await page.getByPlaceholder('or answer in your own words').fill('Only for quivers with a cycle.');
	await page.getByRole('button', { name: 'send' }).click();
	await expect(page.getByTestId('review-empty')).toHaveText('Nothing waits here.');
	await expect(count(page, 'review-kind-questions')).toHaveText('0');
});

test('a proposed edit opens to its change and is kept; one made in place that broke the compile says why', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const broke = page.getByTestId('review-row').filter({ hasText: 'bounds.tex · Lemma 2' });
	await expect(broke).toContainText('bounds.tex has not compiled since this edit (line 14)');
	await broke.getByRole('button', { expanded: false }).click();
	await expect(broke.getByTestId('review-statement').locator('span.change[data-side="new"]').first()).toHaveText('Suppose');
	await expect(broke).toContainText('Claude Code made this edit in place. bounds.tex has not compiled since: the command it adds is not defined (line 14).');
	await expect(broke.getByRole('button', { name: 'undo the edit' })).toBeVisible();
	const first = page.getByTestId('review-row').first();
	await first.getByRole('button', { expanded: false }).click();
	await first.getByRole('button', { name: 'keep' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Kept.');
	await expect(page.getByTestId('review-row')).toHaveCount(4);
});

test('the tasks waiting for an agent say what was asked, who works on one, and delete withdraws one', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	await expect(tasks).toHaveCount(6);
	await expect(tasks.first()).toContainText('Digest the 2 places you marked in Okafor 2022');
	await expect(tasks.first()).toContainText('Claude Code is working on it');
	await expect(tasks.nth(4)).toContainText('Read Theorem 2.3 of Okafor 2022');
	await expect(tasks.nth(4)).toContainText('waiting');
	await tasks.nth(4).hover();
	await tasks.nth(4).getByRole('button', { name: 'delete' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Task deleted.');
	await expect(tasks).toHaveCount(5);
	await expect(count(page, 'review-kind-agents')).toHaveText('5');
});

test('no control in Review changes view, and no id is drawn', async ({ page }) => {
	test.setTimeout(300000);
	await open(page);
	// every control Review draws, in its list and its column, each from where the one before left it
	const n = await page.evaluate(() => {
		const roots = [document.querySelector('[data-testid="review-view"]'), document.querySelector('[data-testid="review-column"]')];
		const buttons = roots.flatMap((r) => [...(r?.querySelectorAll('button') ?? [])]);
		buttons.forEach((b, i) => b.setAttribute('data-crawl', String(i)));
		return buttons.length;
	});
	expect(n).toBeGreaterThan(20);
	for (let i = 0; i < n; i++) {
		const b = page.locator(`[data-crawl="${i}"]`);
		if (!(await b.isVisible().catch(() => false))) continue;
		await b.click({ timeout: 5000 }).catch(() => {});
		expect(page.url()).toMatch(/\/review/);
		await page.keyboard.press('Escape');
	}
	await page.getByTestId('review-kind-all').click();
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\b(tq-[0-9A-Z]{4}|t-2026-|ev-2026-|m-2026-|c-[0-9a-f]{8})/);
});
