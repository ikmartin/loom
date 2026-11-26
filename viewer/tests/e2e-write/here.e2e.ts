// Where the reader is (plan 0.21.8): each tab reports its place to the publisher, and `loom here` reads back the one touched last.
import { expect, readOnly } from '../served';
import type { Page } from '@playwright/test';

/** What `loom here --json` says the person is looking at. */
function looking(served: { loom(args: string[]): string }): Record<string, any> {
	return JSON.parse(served.loom(['here', '--json'])).looking ?? {};
}

/** Select an element's words as a reader would, and let go. */
async function select(page: Page, selector: string): Promise<void> {
	await page.locator(selector).first().evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
}

readOnly('the words selected in a result are what loom here reports, by the key they are in', async ({ page, served }) => {
	await page.goto('/node/sy-0003');
	const statement = '[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]';
	await page.locator(statement).first().locator('mjx-container').first().waitFor();
	await expect.poll(() => looking(served).item?.link).toBe('quilt:sy-0003');
	await select(page, statement);
	await expect.poll(() => looking(served).selection?.text ?? '').toContain('widget');
	expect(looking(served).selection.link).toBe('quilt:sy-0003');
});

readOnly('beside Review\'s panel it is the block under review, and with two tabs open the one touched last', async ({ page, served }) => {
	await page.goto('/node/sy-0003');
	await expect.poll(() => looking(served).item?.link).toBe('quilt:sy-0003');
	const other = await page.context().newPage();
	await other.goto('/master/drafting/main?review=sy-0001&cause=0#sy-0001');
	// the other tab's whole report, its document and the block under review with it, so none of it lands after the first tab is touched
	await expect.poll(() => { const l = looking(served); return `${l.route} ${l.item?.link} ${l.block?.key} ${l.review?.key}`; }).toBe('reading quilt:drafting/main.tex sy-0001 sy-0001');
	expect(looking(served).review.cause).toBeTruthy();
	// the first tab is touched again, and says where it is though nothing there changed; headless Chromium keeps both tabs visible and fires no focus on switching, so the test sends it
	await page.evaluate(() => window.dispatchEvent(new Event('focus')));
	// one reading of both: the other tab's place is a reading route too, so the route alone does not say the first tab's report has landed
	await expect.poll(() => { const l = looking(served); return `${l.route} ${l.item?.link}`; }).toBe('reading quilt:sy-0003');
	await other.close();
});

readOnly('a tab that loads in the background says nothing until it comes into view, and then is the tab touched last', async ({ page, served }) => {
	await page.goto('/node/sy-0003');
	await expect.poll(() => looking(served).item?.link).toBe('quilt:sy-0003');
	const other = await page.context().newPage();
	// hidden as a tab behind another is; headless Chromium keeps every tab visible, so the page is told, and `show` brings it into view
	await other.addInitScript(() => {
		let state: DocumentVisibilityState = 'hidden';
		Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
		Object.defineProperty(document, 'hidden', { configurable: true, get: () => state === 'hidden' });
		(window as unknown as { show: () => void }).show = () => {
			state = 'visible';
			document.dispatchEvent(new Event('visibilitychange'));
		};
	});
	const reports: string[] = [];
	other.on('request', (r) => {
		if (r.url().endsWith('/_api/here')) reports.push(r.postData() ?? '');
	});
	const answered = other.waitForResponse((r) => r.url().endsWith('/_api'));
	await other.goto('/master/drafting/main');
	await answered;
	await other.locator('[data-pane="0"] .fragment').first().waitFor();
	// past the pause after which a visible tab reports a settled place
	await other.waitForTimeout(800);
	expect(reports).toEqual([]);
	expect(looking(served).item?.link).toBe('quilt:sy-0003');
	await other.evaluate(() => (window as unknown as { show: () => void }).show());
	await expect.poll(() => looking(served).item?.link).toBe('quilt:drafting/main.tex');
	await other.close();
});
