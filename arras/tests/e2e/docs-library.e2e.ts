// What Docs draws of the library on round six's fixture (`?fixture=round6`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 8 to 11): the Library button and its picker, a work beside a draft, a citation's card, the notes tab, the Lean marks in the margin and the formalize panel. Where the library's reads are not served, Docs keeps today's Library shelf, which its own specs hold.
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

/** One of the showcase quilt's stored papers, which the fixture serves as every work's PDF. */
const PAPER = readFileSync('../loom/tests/quilts/showcase/.loom/library/storage/arxiv/2504.01234v1/paper.pdf');

async function open(page: Page): Promise<void> {
	await page.route('**/digests/storage/**', (route) => route.fulfill({ body: PAPER, contentType: 'application/pdf' }));
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/master/drafting/main?fixture=round6');
	await expect(page.getByTestId('docs-library')).toBeVisible();
}

test('the Library button opens the picker over Docs, which finds, sorts and opens a work beside the draft', async ({ page }) => {
	await open(page);
	await page.getByTestId('docs-library').click();
	const picker = page.getByTestId('docs-picker');
	await expect(picker.getByTestId('picker-row')).toHaveCount(300);
	await expect(picker).toContainText('300 works');
	const arden = picker.getByTestId('picker-row').filter({ hasText: 'Cycle spaces of finite quivers' }).filter({ hasText: '2024' });
	await expect(arden.locator('td.d')).toHaveText('[1]');
	await expect(arden.locator('td.d')).toHaveAttribute('title', 'main.tex cites it as [1]');
	await picker.getByTestId('picker-search').fill('median orders on weighting lattices');
	await expect(picker.getByTestId('picker-row')).toHaveCount(1);
	await expect(picker).toContainText('1 work');
	await picker.getByTestId('picker-search').fill('');
	await picker.getByRole('button', { name: 'thumbnails' }).click();
	await expect(picker.getByTestId('work-thumb')).toHaveCount(60);
	await picker.getByRole('button', { name: 'list' }).click();
	await page.keyboard.press('Escape');
	await expect(picker).toHaveCount(0);
	await page.getByTestId('docs-library').click();
	await picker.getByTestId('picker-row').filter({ hasText: 'Cycle spaces of finite quivers' }).filter({ hasText: '2024' }).click();
	await expect(picker).toHaveCount(0);
	await expect(page.getByTestId('reading-item')).toBeVisible();
	await expect(page.getByTestId('reading-item').getByTestId('pdf-doc')).toBeVisible();
	await expect(page.getByRole('tab', { name: /Arden 2024/ })).toBeVisible();
	// beside a draft, the reader draws no digest marks and offers none
	await expect(page.getByTestId('reading-item').getByTestId('reader-view')).toHaveCount(0);
	await expect(page).toHaveURL(/\/master\//);
});
