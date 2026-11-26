// Loom's home page, end to end: the real viewer on a real `loom app` in a home folder of the test's own (`tests/home.ts`).

import { expect, test } from '../home';

test('the list shows each quilt with its state, and Stop and Forget act on it', async ({ page, homed }) => {
	await page.goto('/');
	await expect(page.getByTestId('home-empty')).toContainText('Drop your paper here');
	const made = await homed.call('quilt-create', { name: 'Cycle spaces' });
	expect(made.status).toBe(200);
	const row = page.getByTestId('quilt-row');
	await expect(row).toHaveCount(1);
	await expect(row.getByTestId('quilt-row-name')).toHaveText('Cycle spaces');
	await expect(row).toContainText('~/Quilts/Cycle spaces');
	await expect(row).toHaveAttribute('data-state', 'running', { timeout: 30_000 });
	await expect(row.getByTestId('quilt-row-state')).toHaveText('Running');
	await row.getByTestId('quilt-stop').click();
	await expect(row).toHaveAttribute('data-state', 'stopped');
	await expect(row.getByTestId('quilt-row-state')).toHaveText('Not running');
	await row.getByTestId('quilt-forget').click();
	await expect(page.getByTestId('home-empty')).toBeVisible();
	// nothing on the page names a command
	await expect(page.locator('body')).not.toContainText('loom ');
});
