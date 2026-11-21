// The Web on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/web6.ts`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 7a and 7b): the scopes, the list by document and by status, its search, the focus card and its neighbourhood, the trail, and the graph; and the rules that hold everywhere: no control but the four view names changes view, no id is drawn, and a folded group is read only when it opens. Where the Web's reads are not served, the Web says so.
import { expect, test, type Page } from '@playwright/test';

async function open(page: Page): Promise<void> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6');
	await expect(page.getByTestId('web-row').first()).toBeVisible();
}

const row = (page: Page, name: string) => page.getByTestId('web-list').getByTestId('web-row').filter({ hasText: name }).first();

test('a draft and what it rests on lists the draft, then the library a work at a time, and a result followed shows its card and neighbourhood', async ({ page }) => {
	await open(page);
	await expect(page.getByTestId('web-list')).toContainText('23 results');
	await expect(page.getByTestId('web-list')).toContainText('library results main.tex uses');
	await expect(page.getByTestId('web-group').filter({ hasText: 'Arden 2024' })).toHaveAttribute('aria-expanded', 'true');
	await row(page, 'Theorem 3.4').click();
	await row(page, 'Theorem 3.1').click();
	const card = page.getByTestId('web-focus');
	await expect(card).toContainText('Theorem 3.1 Rank');
	await expect(card).toContainText('formalized');
	// the marks' words are read with the line, so it is held in two parts
	await expect(page.getByTestId('web-standing')).toContainText('Verified relative to');
	await expect(page.getByTestId('web-standing')).toContainText('Proposition 2.1 of Arden 2024, which is assumed.');
	await expect(page.getByTestId('web-neighbourhood')).toContainText('What its statement uses');
	await expect(page.getByTestId('web-neighbourhood')).toContainText('Definition 1.2 Cycle space');
	await expect(page.locator('.trail')).toHaveText(/Theorem 3.4\s*›\s*Theorem 3.1 · Rank/);
	// a result named in the card is followed from there, and the trail goes back
	await page.getByTestId('web-standing').getByRole('button', { name: 'Proposition 2.1 of Arden 2024' }).click();
	await expect(card).toContainText('Proposition 2.1');
	await expect(card).toContainText('assumed in Lean');
	await page.locator('.trail').getByRole('button', { name: 'Theorem 3.4' }).click();
	await expect(card).toContainText('Theorem 3.4 Bounded balanced weightings');
	await expect(page.getByTestId('web-standing')).toContainText('Not formalized. It rests on');
	await expect(page.getByTestId('web-standing')).toContainText('Lemma 5.7');
	await card.getByRole('button', { name: 'proofs, Lean, and its record' }).click();
	await expect(card).toContainText('in main.tex, Section 3; uses');
	await expect(page).toHaveURL(/\/web/);
});

test('everything folds the drafts and the works, and a group is read only when it opens', async ({ page }) => {
	await open(page);
	await page.getByTestId('web-scope-all').check();
	await expect(page.getByTestId('web-list')).toContainText('your drafts');
	await expect(page.getByTestId('web-list')).toContainText('and 295 works with no results digested');
	const smith = page.getByTestId('web-group').filter({ hasText: 'Smith 2024' });
	await expect(smith).toHaveAttribute('aria-expanded', 'false');
	await expect(row(page, 'Lemma 3.2')).toHaveCount(0);
	await smith.click();
	await expect(row(page, 'Lemma 3.2')).toBeVisible();
	await page.getByTestId('web-scope-draft').check();
	await expect(page.getByTestId('web-list')).toContainText('15 results');
});

test('by status puts what is not read first, and the search finds words in a statement', async ({ page }) => {
	await open(page);
	await page.getByRole('button', { name: 'by status' }).click();
	await expect(page.getByTestId('web-list').getByTestId('web-row').first()).toContainText('Theorem 2.3');
	await page.getByTestId('web-search').fill('polynomial');
	await expect(page.getByTestId('web-hit').first()).toBeVisible();
	await expect(page.getByTestId('web-hit').first().locator('mark')).toHaveText('polynomial');
	await expect(page.getByTestId('web-list')).toContainText('2 results');
	await page.getByTestId('web-search').fill('zzzz');
	await expect(page.getByTestId('web-list')).toContainText('nothing matches');
});

test('the graph draws four columns, a dashed line for a proof, five of a long column and the rest said, and a box followed', async ({ page }) => {
	await open(page);
	await row(page, 'Theorem 3.4').click();
	await page.getByTestId('web-form-graph').click();
	const graph = page.getByTestId('web-graph');
	await expect(graph).toContainText('two steps back');
	await expect(graph).toContainText('what it uses');
	await expect(graph).toContainText('what uses it');
	await expect(graph).toContainText(/and \d+ more · in the list/);
	await expect(graph.locator('path.edge.proof').first()).toBeAttached();
	await graph.getByTestId('web-node').filter({ hasText: 'Theorem 3.1' }).click();
	await expect(page.getByTestId('web-focus')).toContainText('Theorem 3.1 Rank');
	await expect(page).toHaveURL(/\/web/);
});

test('no control in the Web changes view, and no id is drawn', async ({ page }) => {
	test.setTimeout(300000);
	await open(page);
	const n = await page.evaluate(() => {
		const roots = [document.querySelector('[data-testid="web-view"]'), document.querySelector('[data-testid="web-column"]')];
		const controls = roots.flatMap((r) => [...(r?.querySelectorAll('button, input, [role="button"]') ?? [])]);
		controls.forEach((b, i) => b.setAttribute('data-crawl', String(i)));
		return controls.length;
	});
	expect(n).toBeGreaterThan(20);
	for (let i = 0; i < n; i++) {
		const b = page.locator(`[data-crawl="${i}"]`);
		if (!(await b.isVisible().catch(() => false))) continue;
		await b.click({ timeout: 5000 }).catch(() => {});
		expect(page.url()).toMatch(/\/web/);
	}
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\b(tq-[0-9A-Z]{4}|def:|thm:|lem:|prop:|cor:)/);
});

test('where the Web is not served, it says so', async ({ page }) => {
	await page.goto('/web');
	await expect(page.getByTestId('web-view')).toHaveText('The Web shows every result and what it rests on once loom serves it.');
});

test('at the size a reviewer measured, the list draws only the rows in view, reads a group and the next rows as they come into view, and draws a hit with its mathematics', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6&web=large');
	await expect(page.getByTestId('web-list')).toContainText(/5,?1\d\d results/);
	// nothing is in focus until the person chooses
	await expect(page.getByTestId('web-none')).toHaveText('Choose a result to see what it uses and what uses it.');
	expect(await page.getByTestId('web-row').count()).toBeLessThan(120);
	// a group far down, open and not sent, is read when scrolled to
	const scroller = page.getByTestId('web-list').locator('.wscroll');
	await scroller.evaluate((e) => (e.scrollTop = e.scrollHeight / 2));
	await expect(page.getByTestId('web-row').filter({ hasText: /Lemma \d+\.\d+/ }).first()).toBeVisible();
	await expect(page.locator('.pending')).toHaveCount(0, { timeout: 10000 });
	expect(await page.getByTestId('web-row').count()).toBeLessThan(120);
	// by status, the rest comes in as the end comes into view
	await page.getByRole('button', { name: 'by status' }).click();
	await expect.poll(async () => scroller.evaluate((e) => e.scrollHeight)).toBeGreaterThan(200 * 28);
	for (let i = 0; i < 4; i++) {
		await scroller.evaluate((e) => (e.scrollTop = e.scrollHeight));
		await page.waitForTimeout(150);
	}
	await expect.poll(async () => scroller.evaluate((e) => e.scrollHeight)).toBeGreaterThan(200 * 28 * 2);
	// a hit's words drawn as the statement is: no dollar signs, its mathematics typeset
	await page.getByTestId('web-search').fill('polynomial in');
	const hit = page.getByTestId('web-hit').first();
	await expect(hit).toBeVisible();
	await expect(hit).not.toContainText('$');
	await expect(hit.locator('.math, mjx-container').first()).toBeAttached();
});
