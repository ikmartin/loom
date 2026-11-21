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

test('a view name shows its hover card after a moment, and each name opens its view', async ({ page }) => {
	await open(page, 1440);
	await page.getByTestId('primary-web').hover();
	await expect(page.getByTestId('hovercard')).toContainText('Every result and what it rests on');
	await page.mouse.move(800, 600);
	await expect(page.getByTestId('hovercard')).toHaveCount(0);
	for (const [v, path] of [['library', '/library'], ['web', '/web'], ['review', '/review']] as const) {
		await page.getByTestId(`primary-${v}`).click();
		await expect(page).toHaveURL(new RegExp(path));
		await expect(page.getByTestId(`primary-${v}`)).toHaveAttribute('aria-current', 'page');
	}
});

test('the legend of the marks opens from the foot in every view and closes on a click elsewhere', async ({ page }) => {
	await open(page, 1440);
	for (const v of ['docs', 'library', 'web', 'review']) {
		await page.getByTestId(`primary-${v}`).click();
		await page.getByTestId('legend-open').click();
		await expect(page.getByTestId('legend').locator('[data-mark]')).toHaveCount(8);
		await page.mouse.click(800, 400);
		await expect(page.getByTestId('legend')).toHaveCount(0);
	}
});
