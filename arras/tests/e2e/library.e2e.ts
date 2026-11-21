// A work in a pane, by its reference: its stored PDF opened at its pages, which the Library view gives. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';

test.describe('a work', () => {
	test.fixme('a filed paper opens on the paper, whether or not anything is anchored to it yet', async ({ page }) => {
		// needs the Library view to give a work's stored PDF, which opens its pages
		await page.goto('/library/sy-0099-ref');
		await expect(page.getByTestId('pdf-doc')).toBeVisible();
	});
});
