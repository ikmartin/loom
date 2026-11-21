// The Library view on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/`), as the author settled it (`docs/design/mockups/library-round-6/`): the list of works and its thumbnails, adding a work, the digest menus, a work's tab with its outline, the result beside its page and the digest marks, deleting with undo; and the rules that hold everywhere: no control but the four view names changes view, no id is drawn, and nothing is asked for before it is shown.
import { expect, test, type Page, type Request } from '@playwright/test';
import { readFileSync } from 'node:fs';

/** One of the showcase quilt's stored papers, which the fixture serves as every work's PDF. */
const PAPER = readFileSync('../loom/tests/quilts/showcase/.loom/library/storage/arxiv/2504.01234v1/paper.pdf');

async function open(page: Page): Promise<Request[]> {
	const asked: Request[] = [];
	page.on('request', (r) => asked.push(r));
	await page.route('**/digests/storage/**', (route) => route.fulfill({ body: PAPER, contentType: 'application/pdf' }));
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6');
	await expect(page.getByTestId('works-table')).toBeVisible();
	return asked;
}

const row = (page: Page, title: string) => page.getByTestId('work-row').filter({ hasText: title }).first();

test("the list holds round six's 300 works, sorted by title, and sorts, filters and narrows as asked", async ({ page }) => {
	await open(page);
	await expect(page.getByTestId('work-row')).toHaveCount(300);
	await expect(page.getByTestId('work-row').first()).toContainText('A note on admissible weightings');
	await page.getByTestId('sort-title').click();
	await expect(page.getByTestId('work-row').first()).not.toContainText('A note on admissible weightings');
	await page.getByTestId('filter-nodoc').click();
	const nodoc = await page.getByTestId('work-row').count();
	expect(nodoc).toBeGreaterThan(3);
	expect(nodoc).toBeLessThan(300);
	await page.getByTestId('filter-all').click();
	await page.getByTestId('works-search').fill('widgets and their');
	await expect(page.getByTestId('work-row')).toHaveCount(1);
	await expect(page.getByText('1 of 300')).toBeVisible();
	await expect(row(page, 'Widgets and their bounds')).toContainText('11 of 62 · 2 compared');
});

test('thumbnails draw sixty at first, and the choice is remembered', async ({ page }) => {
	await open(page);
	await page.getByTestId('works-thumbs').click();
	await expect(page.getByTestId('work-thumb')).toHaveCount(60);
	await page.reload();
	await expect(page.getByTestId('works-thumbnails')).toBeVisible();
	await page.getByTestId('works-list').click();
	await expect(page.getByTestId('works-table')).toBeVisible();
});

test('a pasted arXiv number adds its work, said in the column with undo, and the view does not change', async ({ page }) => {
	await open(page);
	await page.getByTestId('add-work').click();
	await expect(page.getByTestId('choose-files')).toBeVisible();
	await page.getByTestId('paste-identifier').fill('2209.01234v2');
	await page.getByTestId('paste-identifier').press('Enter');
	await expect(page.getByTestId('column-message')).toContainText('Added Gadget towers, Halberd and Ravel 2021, found by its arXiv number, with its TeX source.');
	await expect(page.getByTestId('column-message-undo')).toBeVisible();
	await expect(page).toHaveURL(/\/library/);
});

test('the digest menu over the list counts what the drafts use, and selecting takes ⌘-click', async ({ page }) => {
	await open(page);
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-used')).toContainText('(14)');
	await expect(page.getByTestId('digest-selected')).toBeDisabled();
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-menu')).toHaveCount(0);
	await row(page, 'Widgets and their bounds').click({ modifiers: ['Meta'] });
	await expect(page.getByTestId('library-tab')).toHaveCount(0);
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-selected')).toBeEnabled();
	await expect(page.getByTestId('digest-selected')).toContainText('(1 selected)');
});

test("a work's tab: its outline, a result beside its page, and the person's yes", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('library-tab')).toHaveCount(1);
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	await expect(page.getByTestId('outline-section')).toHaveCount(8);
	const radius = page.getByTestId('outline-item').filter({ hasText: 'Radius' });
	await expect(radius.locator('[data-mark="unchecked"]')).toHaveCount(1);
	await radius.click();
	await expect(page.getByTestId('node-side')).toContainText("Does loom's copy match the paper?");
	await page.getByTestId('it-matches').click();
	await expect(radius.locator('[data-mark="checked"]')).toHaveCount(1);
	await expect(page.getByTestId('column-message')).toContainText('Definition 3.1 matches the paper');
});

test('results chosen in the outline are digested from the TeX source', async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await page.getByTestId('work-digest').click();
	await expect(page.getByTestId('digest-used')).toContainText('(2)');
	await page.getByTestId('digest-choose').click();
	const ticks = page.getByTestId('outline-tick');
	await ticks.nth(0).check();
	await ticks.nth(1).check();
	await page.getByTestId('digest-chosen').click();
	await expect(page.getByTestId('column-message')).toContainText('Digested 2 results from the TeX source');
	await expect(page.getByTestId('outline-tick')).toHaveCount(0);
});

test('the digest marks are asked for only once they are on', async ({ page }) => {
	const asked = await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('work-reader')).toBeVisible();
	await page.waitForTimeout(300);
	expect(asked.some((r) => r.url().includes('library-places'))).toBe(false);
	await page.getByTestId('reader-view').click();
	await page.getByTestId('overlay-toggle').click();
	await expect(page.getByTestId('digest-chip').first()).toBeVisible();
});

test('a work held only as a PDF lists its marks and the stubs no place is known for', async ({ page }) => {
	await open(page);
	await row(page, 'Median orders on weighting lattices').click();
	await expect(page.getByText("Contents, from the PDF's outline")).toBeVisible();
	await expect(page.getByTestId('outline-mark')).toHaveCount(1);
	await expect(page.getByText('Cited, not yet placed')).toBeVisible();
	await expect(page.getByTestId('locate-in-pdf')).toBeVisible();
});

test('deleting a work takes it out, and undo puts it back', async ({ page }) => {
	await open(page);
	const jones = row(page, 'Covering estimates');
	await jones.hover();
	await jones.getByTestId('row-more').click();
	await page.getByTestId('row-delete').click();
	await expect(page.getByTestId('column-message')).toContainText('Deleted Jones 2019, with its results and notes');
	await expect(page.getByTestId('work-row')).toHaveCount(299);
	await page.getByTestId('column-message-undo').click();
	await expect(page.getByTestId('work-row')).toHaveCount(300);
});

test('no control in the Library changes view, and no id is drawn', async ({ page }) => {
	test.setTimeout(600000);
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('work-reader')).toBeVisible();
	// every control the Library draws, in its view and its column, but today's reader's own toolbar and the file chooser, which are not the Library's and open the system's dialogs
	const n = await page.evaluate(() => {
		const roots = [document.querySelector('[data-testid="library-view"]'), document.querySelector('[data-testid="library-column"]')];
		const buttons = roots.flatMap((r) => [...(r?.querySelectorAll('button') ?? [])]).filter((b) => !b.closest('.tb') && !b.closest('[data-testid="pdf-doc"]') && b.getAttribute('data-testid') !== 'choose-files' && b.getAttribute('data-testid') !== 'row-delete');
		buttons.forEach((b, i) => b.setAttribute('data-crawl', String(i)));
		return buttons.length;
	});
	expect(n).toBeGreaterThan(20);
	for (let i = 0; i < n; i++) {
		const b = page.locator(`[data-crawl="${i}"]`);
		if (!(await b.isVisible().catch(() => false))) continue;
		await b.click({ timeout: 5000 }).catch(() => {});
		expect(page.url()).toMatch(/\/library/);
		await page.keyboard.press('Escape');
	}
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\btq-[0-9A-Z]{4}\b/);
});
