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

/** Has the draft's `nth` citation name `node`, as its fragment will once citations resolve to the library's nodes (`dialect.md` §2.8 changing with the digest). */
async function citing(page: Page, nth: number, node: string): Promise<void> {
	await expect(page.locator('.fragment span.cite').nth(nth)).toBeAttached();
	await page.evaluate(([i, n]) => (document.querySelectorAll<HTMLElement>('.fragment span.cite')[Number(i)].dataset.target = String(n)), [nth, node]);
}

test("a citation's card shows the cited result and opens its work beside the draft at its place; a stub's offers to locate it or have it read", async ({ page }) => {
	await open(page);
	const card = page.getByTestId('cite-card');
	await citing(page, 0, 'tq-0203');
	await page.locator('.fragment span.cite').nth(0).locator('a').first().hover();
	await expect(card).toContainText('Proposition 2.1');
	await expect(card).toContainText('Arden 2024 · page 7');
	await expect(card).toContainText('matches the paper');
	await card.getByRole('button', { name: 'open at its place' }).click();
	await expect(page.getByTestId('reading-item')).toBeVisible();
	await expect(page.getByRole('tab', { name: /Arden 2024/ })).toBeVisible();
	await expect(card).toHaveCount(0);
	await citing(page, 1, 'tq-04A1');
	await page.locator('.fragment span.cite').nth(1).locator('a').first().hover();
	await expect(card).toContainText('Theorem 2.3');
	await expect(card).toContainText('Okafor 2022');
	await expect(card).toContainText('Loom knows this result only by its number. Nobody has read it.');
	await expect(card.getByRole('button', { name: 'locate in PDF' })).toBeVisible();
	await card.getByRole('button', { name: 'ask an agent to read it' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to read it.');
	await expect(page).toHaveURL(/\/master\//);
});

test('the notes tab lists every note by work, the orphaned first, and by date; an orphan is deleted, a group shows the rest, and a note on a work opens it beside the draft', async ({ page }) => {
	await open(page);
	await page.getByTestId('docs-notes').click();
	const tab = page.getByTestId('notes-tab');
	await expect(page.getByRole('tab', { name: /All notes/ })).toBeVisible();
	const groups = tab.getByTestId('notes-group');
	await expect(groups.first()).toContainText('Orphaned · their document is gone, or their words are not found');
	await expect(groups.first().getByTestId('note')).toHaveCount(2);
	await expect(groups.first()).toContainText('was on old-intro.tex, deleted 14 Nov');
	await expect(tab).toContainText('show orphaned notes (2)');
	const head = (name: string) => groups.filter({ has: page.locator('h2', { hasText: new RegExp(`^${name}`) }) });
	const main = head('main.tex');
	await expect(main.getByTestId('note')).toHaveCount(3);
	await main.getByRole('button', { name: '6 more' }).click();
	await expect(main.getByTestId('note')).toHaveCount(9);
	await expect(head('Arden 2024')).toContainText('summary');
	await groups.first().getByTestId('note').first().getByRole('button', { name: 'delete' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Note deleted.');
	await expect(groups.first().getByTestId('note')).toHaveCount(1);
	await tab.getByTestId('notes-orphaned').uncheck();
	await expect(groups.first()).not.toContainText('Orphaned');
	await tab.getByRole('button', { name: 'date' }).click();
	await expect(tab.getByTestId('note').first()).toContainText('is saturated by Proposition 2.6');
	await tab.getByTestId('note').filter({ hasText: 'whose coordinates sum to zero' }).getByRole('button').first().click();
	await expect(page.getByTestId('reading-item')).toBeVisible();
	await expect(page).toHaveURL(/\/notes|\/master\//);
});
