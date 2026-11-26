// Review's rows as the write suite drives them: a row of Results to accept or Proposed edits draws its acts only once it is open (`views/review/rows/`), so a test opens it first.
import { expect, type Locator, type Page } from '@playwright/test';

/** A block's row in Results to accept. */
export const acceptRow = (page: Page, key: string) => page.locator(`[data-testid="review-row"][data-kind="accepted-changed"][data-key="${key}"]`);

/** Opens a row that is closed, by the button that opens it. */
export async function openRow(row: Locator): Promise<void> {
	const h = row.locator('.rr-h[aria-expanded]');
	if ((await h.getAttribute('aria-expanded')) !== 'true') await h.click();
}

/** Opens every row of Proposed edits' files and suggested edits that is closed, so their cards are drawn. */
export async function openChanges(page: Page): Promise<void> {
	// the first closed one each time, since opening one moves every place after it
	const closed = page.locator('[data-testid="review-row"]:is([data-change], [data-file]) .rr-h[aria-expanded="false"]');
	for (let i = 0; i < 50 && (await closed.count()); i++) await closed.first().click({ timeout: 2000 }).catch(() => {});
}

/** Waits until `card`, a change's card, is drawn once, opening each change's row as it is listed. */
export async function shown(page: Page, card: Locator): Promise<void> {
	await expect(async () => {
		await openChanges(page);
		await expect(card).toHaveCount(1, { timeout: 1000 });
	}).toPass({ timeout: 60_000 });
}
