// The Web on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/web6.ts`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 7a and 7b): the scopes, the list by document and by status, its search, the focus card and its neighbourhood, the trail, and the graph; and the rules that hold everywhere: no control but the four view names changes view, no id is drawn, and a folded group is read only when it opens. Where the Web's reads are not served, the Web says so.
import { expect, test, type Page } from '@playwright/test';
import { serve } from '../manifest';

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
	// a library result's statement is drawn with its work's macros, which come as the macros node
	await expect(card).toContainText('summing to zero on each component');
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
	// a hit is one paragraph: the match an inline mark among its words, the spaces either side kept and no word cut
	const lemma = page.getByTestId('web-hit').filter({ hasText: 'polynomially' });
	await expect(lemma).toContainText('number polynomially many in h');
	for (const hit of await page.getByTestId('web-hit').all()) expect(await hit.evaluate((e) => (e as HTMLElement).innerText.includes('\n'))).toBe(false);
	const [mark, line] = [await lemma.locator('mark').boundingBox(), await lemma.boundingBox()];
	expect(Math.abs(mark!.y - line!.y)).toBeLessThan(4);
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

test("in graph form the column lists the scope's results to choose from, the graph draws the one chosen at the view's full width, and a box followed moves the column's mark", async ({ page }) => {
	await open(page);
	// the list's own controls are not in the column in list form
	await expect(page.getByTestId('web-picks')).toHaveCount(0);
	await expect(page.getByTestId('web-column')).toContainText('Show as');
	await page.getByTestId('web-form-graph').click();
	await expect(page.getByTestId('web-none')).toHaveText('Choose a result in the column to see what it uses and what uses it.');
	await expect(page.getByTestId('web-graph')).toHaveCount(0);
	// folded, the graph's place says to open the column; open again, to choose in it
	await page.getByTestId('panel-fold').click();
	await expect(page.getByTestId('web-none')).toHaveText('Open the column and choose a result to see what it uses and what uses it.');
	await page.getByTestId('panel-fold').click();
	const picks = page.getByTestId('web-picks');
	// the draft's results in paper order, then the library's a work at a time, each work folded
	await expect(picks).toContainText('main.tex');
	await expect(picks).toContainText('library results main.tex uses');
	const arden = picks.getByTestId('web-pick-group').filter({ hasText: 'Arden 2024' });
	await expect(arden).toHaveAttribute('aria-expanded', 'false');
	const names = await picks.getByTestId('web-pick').evaluateAll((els) => els.map((e) => e.querySelector('.nm')?.firstChild?.textContent ?? ''));
	expect(names.indexOf('Theorem 3.1')).toBeLessThan(names.indexOf('Theorem 3.4'));
	await picks.getByTestId('web-pick').filter({ hasText: 'Theorem 3.4' }).click();
	const graph = page.getByTestId('web-graph');
	await expect(graph).toContainText('what uses it');
	await expect(page.getByTestId('web-focus')).toContainText('Theorem 3.4');
	await expect(picks.locator('[aria-current="true"]')).toContainText('Theorem 3.4');
	// the graph keeps the view's width, the column beside it
	const [g, v] = await Promise.all([graph.boundingBox(), page.getByTestId('web-view').boundingBox()]);
	expect(g!.width).toBeGreaterThan(v!.width - 60);
	// a box followed in the graph moves the column's mark, opening its work's group, and the trail grows
	await graph.getByTestId('web-node').filter({ hasText: 'Proposition 2.1' }).first().click();
	await expect(page.getByTestId('web-focus')).toContainText('Proposition 2.1');
	await expect(arden).toHaveAttribute('aria-expanded', 'true');
	const marked = picks.locator('[aria-current="true"]');
	await expect(marked).toContainText('Proposition 2.1');
	await expect(marked).toBeInViewport();
	await expect(page.locator('.trail')).toHaveText(/Theorem 3.4\s*›\s*Proposition 2.1/);
	// the column's search finds a result, which a click puts in focus
	await page.getByTestId('web-pick-search').fill('Rank');
	await picks.getByTestId('web-pick').filter({ hasText: 'Theorem 3.1' }).click();
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

test('the Web opens on the quilt\'s main draft as the manifest gives it, and a draft that holds no result says so', async ({ page }) => {
	// bounds.tex is the main draft here, so the Web opens on it and not on main.tex
	await serve(page, (m) => {
		for (const d of m.masters) d.default = false;
		m.masters.push({ ...m.masters[0], path: 'drafting/bounds.tex', title: 'Bounds', default: true });
	});
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6');
	await expect(page.getByTestId('web-draft')).toHaveValue('drafting/bounds.tex');
	await expect(page.getByTestId('web-list')).toContainText('library results bounds.tex uses');
	await expect(row(page, 'Theorem 1')).toBeVisible();
	await page.getByTestId('web-scope-draft').check();
	await page.getByTestId('web-draft').selectOption('drafting/talk.tex');
	await expect(page.getByTestId('web-empty')).toHaveText('talk.tex holds no result.');
});

test('where the quilt names no main draft, the Web says so and reads nothing until a draft is chosen', async ({ page }) => {
	await serve(page, (m) => {
		for (const d of m.masters) d.default = false;
	});
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6');
	await expect(page.getByTestId('web-draftless')).toHaveText('The quilt names no main draft. Choose a draft under Scope.');
	await expect(page.getByTestId('web-draft').locator('option:checked')).toHaveText('choose a draft');
	await expect(page.getByTestId('web-row')).toHaveCount(0);
	// everything names no draft, so it lists at once
	await page.getByTestId('web-scope-all').check();
	await expect(page.getByTestId('web-list')).toContainText('your drafts');
	await page.getByTestId('web-scope-deps').check();
	await expect(page.getByTestId('web-draftless')).toBeVisible();
	await page.getByTestId('web-draft').selectOption('drafting/main.tex');
	await expect(page.getByTestId('web-list')).toContainText('library results main.tex uses');
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
