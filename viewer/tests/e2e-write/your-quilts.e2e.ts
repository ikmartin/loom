// Your quilts on a quilt `loom serve` serves where no home page runs (the suite's HOME is its own, so none does): the house still shows, and its hover text and a click say how to open the home. With a home running it goes back to the home's tab (`home.e2e.ts`); a published viewer shows none (`e2e/frame.e2e.ts`).
import { expect, test } from '../served';

const NO_HOME = 'Open Loom from your Applications folder or the Dock, and open it again from your quilts.';

test('where no home page runs, Your quilts says how to open one, on hover and on a click, open or folded', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/');
	const back = page.getByTestId('your-quilts');
	await expect(back).toBeVisible();
	await expect(back).toHaveAttribute('aria-label', 'Your quilts');
	await expect(back).toHaveAttribute('title', NO_HOME);
	await expect(back).not.toHaveAttribute('href');
	await back.click();
	await expect(page.getByTestId('column-message')).toContainText(NO_HOME);
	expect(page.url()).not.toContain('127.0.0.1:8790');
	// folded to its strip, the house stands above the fold
	await page.setViewportSize({ width: 1100, height: 900 });
	await expect(page.locator('.panel.away')).toHaveCount(1);
	await expect(page.getByTestId('your-quilts')).toBeInViewport();
	await expect(page.getByTestId('your-quilts')).toHaveAttribute('title', NO_HOME);
});
