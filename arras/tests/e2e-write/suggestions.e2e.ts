// Sessions under a running `loom serve`: a person's writes name no session, whichever transcript is being read. A suggested edit is a pending change, kept or discarded in changes.e2e.ts. None of this compiles anything.
import { expect, test } from '../served';

test("an annotation written while a session's transcript is read names no session", async ({ page, served }) => {
	await served.api('session-new', { title: 'a side sitting' });
	const side = served.openSessions().at(-1)!;
	await page.goto(`/node/sy-0003?beside=${encodeURIComponent('/session/' + side)}`);
	await expect(page.locator('[data-pane="1"]').getByTestId('chat')).toBeVisible();
	const at = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]').first();
	await at.locator('mjx-container').first().waitFor();
	// a comment left on the theorem
	await page.getByTestId('pane-0').getByTestId('tool-comment').click();
	await at.click();
	await page.getByTestId('popup-comment-field').fill('Written while reading the side sitting.');
	await page.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);
	expect(served.written('Written while reading the side sitting.')).not.toHaveProperty('session');
});
