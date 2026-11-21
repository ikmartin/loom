// The frame at each width the layout defines: the column open beside two panes; the column folded to its strip below 1200px; one pane below the workspace's two-pane width. At each, what must stay in reach does, every pane draws its toolbar, and nothing scrolls sideways.
import { expect, test, type Page } from '@playwright/test';
import { beside, pane } from '../workspace';
import { servePapers } from '../manifest';

async function open(page: Page, width: number): Promise<void> {
	await servePapers(page);
	await page.setViewportSize({ width, height: 900 });
	await page.goto('/master/drafting/main' + beside('/library/Kre99'));
	await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
}

const fits = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test('1440: the column open, its four views, its footer, and two panes each with its toolbar', async ({ page }) => {
	await open(page, 1440);
	await expect(page.locator('.panel.away')).toHaveCount(0);
	for (const v of ['docs', 'library', 'web', 'review']) await expect(page.getByTestId(`primary-${v}`)).toBeVisible();
	await expect(page.getByTestId('session-footer')).toBeInViewport();
	for (const i of [0, 1]) await expect(pane(page, i).getByTestId('item-controls')).toBeVisible();
	expect(await fits(page)).toBe(true);
});

test('1100: the column folded to its strip of the four views, two panes each with its toolbar', async ({ page }) => {
	await open(page, 1100);
	await expect(page.locator('.panel.away')).toHaveCount(1);
	for (const id of ['panel-fold', 'session-footer', 'strip-docs', 'strip-library', 'strip-web', 'strip-review']) await expect(page.getByTestId(id)).toBeInViewport();
	await expect(page.getByTestId('strip-docs')).toHaveAttribute('aria-current', 'page');
	await expect(page.getByTestId('primary-docs')).toHaveCount(0);
	// the agent's footer stands wholly inside the strip and the window, not merely overlapping them
	const foot = (await page.getByTestId('session-footer').boundingBox())!;
	const strip = (await page.getByTestId('column').boundingBox())!;
	expect(foot.y).toBeGreaterThanOrEqual(0);
	expect(foot.y + foot.height).toBeLessThanOrEqual(900);
	expect(foot.x).toBeGreaterThanOrEqual(strip.x);
	expect(foot.x + foot.width).toBeLessThanOrEqual(strip.x + strip.width);
	for (const i of [0, 1]) await expect(pane(page, i).getByTestId('item-controls')).toBeVisible();
	expect(await fits(page)).toBe(true);
	// unfolded for this visit, the four views are back
	await page.getByTestId('panel-fold').click();
	await expect(page.getByTestId('primary-review')).toBeVisible();
});

test('700: one pane under one strip of both panes\' tabs, with its toolbar', async ({ page }) => {
	await open(page, 700);
	await expect(page.getByTestId('narrow-strip')).toBeVisible();
	await expect(page.getByTestId('narrow-strip').getByTestId('item-tab')).toHaveCount(2);
	await expect(page.locator('[data-pane]')).toHaveCount(1);
	await expect(page.locator('[data-pane] [data-testid="item-controls"]')).toBeVisible();
	expect(await fits(page)).toBe(true);
});

test('a view name shows its hover card after a moment, is described by it, and each name opens its view', async ({ page }) => {
	await open(page, 1440);
	await page.getByTestId('primary-web').hover();
	await expect(page.getByTestId('hovercard')).toContainText('Every result and what it rests on');
	await page.mouse.move(800, 600);
	await expect(page.getByTestId('hovercard')).toHaveCount(0);
	// a screen reader is told what each view is for, and Escape takes down a card shown by focus
	await expect(page.getByTestId('primary-review')).toHaveAttribute('aria-description', /digested results to check against their papers/);
	await page.getByTestId('primary-library').focus();
	await expect(page.getByTestId('hovercard')).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('hovercard')).toHaveCount(0);
	for (const [v, path] of [['library', '/library'], ['web', '/web'], ['review', '/review']] as const) {
		await page.getByTestId(`primary-${v}`).click();
		await expect(page).toHaveURL(new RegExp(path));
		await expect(page.getByTestId(`primary-${v}`)).toHaveAttribute('aria-current', 'page');
	}
});

test('the legend of the marks opens from the foot in every view and closes on a click elsewhere or on Escape', async ({ page }) => {
	await open(page, 1440);
	for (const v of ['docs', 'library', 'web', 'review']) {
		await page.getByTestId(`primary-${v}`).click();
		await page.getByTestId('legend-open').click();
		await expect(page.getByTestId('legend').locator('[data-mark]')).toHaveCount(8);
		await page.mouse.click(800, 400);
		await expect(page.getByTestId('legend')).toHaveCount(0);
	}
	await page.getByTestId('legend-open').click();
	await expect(page.getByTestId('legend-open')).toHaveAttribute('aria-controls', 'marks-legend');
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('legend')).toHaveCount(0);
});

test("the quilt's name is not a way anywhere, and the head's icons are 28 px targets round a glyph a person can see", async ({ page }) => {
	await open(page, 1440);
	await expect(page.getByTestId('quilt-name')).not.toHaveAttribute('href');
	expect(await page.getByTestId('quilt-name').evaluate((el) => el.tagName)).toBe('SPAN');
	for (const id of ['settings-toggle', 'panel-fold']) {
		const target = (await page.getByTestId(id).boundingBox())!;
		const glyph = (await page.getByTestId(id).locator('svg').boundingBox())!;
		expect(target.width).toBeGreaterThanOrEqual(28);
		expect(target.height).toBeGreaterThanOrEqual(28);
		expect(glyph.width).toBeGreaterThanOrEqual(16);
	}
});
