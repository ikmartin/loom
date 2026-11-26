// A work in a pane, by its reference: its stored PDF opened at its pages, which the Library view gives. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';
import { serveWork } from '../works';

test.describe('a work', () => {
	test('a filed paper opens on the paper, whether or not anything is anchored to it yet', async ({ page }) => {
		await serveWork(page, 'sy-0099-ref');
		await page.goto('/library/sy-0099-ref');
		await expect(page.getByTestId('pdf-doc')).toBeVisible();
	});
});
