// The side panel: the documents and their contents, the Nodes section, and the foot. Each test is named for the rule it holds.
import { expect, test, type Page } from '@playwright/test';
import { beside, pane, scrollPane, viewMenu } from '../workspace';
import { REFEREE, serveKept } from '../manifest';

// these are about annotations and the page; the fixture's pending changes are left out, and tested apart (changes.e2e.ts)
test.beforeEach(({ page }) => serveKept(page));

/** Advertise a write API with `caps`; the static server serves none, and the controls appear only where one is. */
async function writes(page: Page, caps: string[]): Promise<void> {
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: caps, token: 't' } }));
}

test('nothing says whether a session is chosen, and an annotation needs none', async ({ page }) => {
	await writes(page, ['annotate']);
	await page.goto('/node/sy-0002');
	const words = pane(page, 0).locator('.fragment .env[data-id="sy-0002"] p[data-src]').first();
	await expect(words).toBeVisible();
	await page.getByTestId('tool-comment').click();
	await words.click({ position: { x: 4, y: 4 } });
	await page.getByTestId('popup-comment-field').fill('Say which orbit.');
	await expect(page.getByTestId('popup-save')).toBeEnabled();
	await expect(page.getByTestId('session-footer')).toHaveCount(0);
	await expect(page.getByTestId('session-picker')).toHaveCount(0);
	await expect(page.locator('body')).not.toContainText(/session chosen|writing in/i);
});

test.describe('the contents', () => {
	test('the outline is the focused pane\'s document\'s, beneath the documents, and absent for anything else', async ({ page }) => {
		await page.goto('/master/drafting/main' + beside('/node/sy-0003'));
		const contents = page.getByRole('navigation', { name: 'Contents' });
		await expect(contents).toBeVisible();
		await expect(page.getByTestId('outline-divider')).toBeVisible();
		// the tree follows the focused pane: a node has none, and the document's comes back with the focus
		await pane(page, 1).locator('.fragment').first().click();
		await expect(contents).toHaveCount(0);
		await pane(page, 0).locator('.fragment').first().click();
		await expect(contents).toBeVisible();
		// and a node alone shows neither the tree nor its divider, and the documents take the column
		await page.goto('/node/sy-0002');
		await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
		await expect(contents).toHaveCount(0);
		await expect(page.getByTestId('outline-divider')).toHaveCount(0);
	});

	test('the contents tree is in document order and stops above paragraph units', async ({ page }) => {
		await page.goto('/master/drafting/main');
		const entries = page.getByRole('navigation', { name: 'Contents' }).locator('a');
		await expect(entries.first()).toContainText('Introduction');
		const texts = await entries.allInnerTexts();
		expect(texts.join(' | ')).toContain('Results');
		expect(texts.join(' | ')).not.toContain('paragraph');
	});

	test('a contents entry scrolls the document instead of navigating away', async ({ page }) => {
		await page.goto('/master/drafting/main');
		await page.getByRole('navigation', { name: 'Contents' }).getByRole('link', { name: /Results/ }).click();
		await expect(page).toHaveURL(/\/master\/drafting\/main#sy-0200$/);
		await expect(page.locator('#sy-0200')).toBeInViewport();
	});

	test('the contents always mark where the reader is, and the mark follows the scroll both ways', async ({ page }) => {
		// the mark moves with the reader's scroll, not with the URL's hash, and exactly one entry carries it, from before any scrolling (DR-112)
		await page.setViewportSize({ width: 1280, height: 500 });
		await page.goto('/master/drafting/main');
		const contents = page.getByRole('navigation', { name: 'Contents' });
		const current = contents.locator('a[aria-current]');
		await expect(current).toHaveCount(1);
		const first = await current.innerText();
		const target = (await contents.locator('a').last().getAttribute('href'))!.split('#')[1];
		await page.evaluate((id) => document.getElementById(id)?.scrollIntoView({ block: 'start' }), target);
		await expect.poll(() => current.innerText()).not.toBe(first);
		await expect(current).toHaveCount(1);
		// scrolling back returns it; the document scrolls in its pane, not the window
		await scrollPane(page, 0, 'top');
		await expect.poll(() => current.innerText()).toBe(first);
	});

	test('the outline scrolls under the wheel', async ({ page }) => {
		// a box inside it that took the wheel and had nothing of its own to scroll left it stuck, though a scroll from script moved it
		await page.setViewportSize({ width: 1440, height: 330 });
		await page.goto('/master/drafting/main');
		const outline = page.getByTestId('outline');
		await expect(outline.getByRole('navigation', { name: 'Contents' })).toBeVisible();
		expect(await outline.evaluate((e) => e.scrollHeight - e.clientHeight), 'the outline overflows its part, px').toBeGreaterThan(20);
		const box = (await outline.boundingBox())!;
		await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
		await page.mouse.wheel(0, 200);
		await expect.poll(() => outline.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
	});

	test('the line above the outline moves, is remembered, and the documents and the outline scroll apart', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 520 });
		await page.goto('/master/drafting/main');
		const line = page.getByTestId('outline-divider');
		const docs = page.getByTestId('docs-part');
		const outline = page.getByTestId('outline');
		await expect(line).toBeVisible();
		await expect(outline.getByRole('navigation', { name: 'Contents' })).toBeVisible();
		// measured once the column has settled, so the press lands on the line
		await line.hover();
		const before = (await docs.boundingBox())!.height;
		const at = (await line.boundingBox())!;
		await page.mouse.move(at.x + at.width / 2, at.y + at.height / 2);
		await expect(line).toHaveCSS('cursor', 'row-resize');
		await page.mouse.down();
		const start = await line.getAttribute('aria-valuenow');
		await page.mouse.move(at.x + at.width / 2, at.y - 80, { steps: 5 });
		// the moves are drawn a frame at a time, so the drop waits for the line to have followed them, as a hand does
		await expect.poll(() => line.getAttribute('aria-valuenow')).not.toBe(start);
		await expect.poll(async () => Number(await line.getAttribute('aria-valuenow'))).toBeLessThan(40);
		await page.mouse.up();
		await expect.poll(async () => (await docs.boundingBox())!.height).toBeLessThan(before - 40);
		const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('viewer.prefs') ?? '{}').outline);
		expect(stored).toBeLessThan(0.55);
		await page.reload();
		await expect.poll(async () => (await page.getByTestId('docs-part').boundingBox())!.height).toBeLessThan(before - 40);
		// each scrolls in its own box: the outline's last entry is reached by scrolling the outline
		for (const part of [docs, outline]) expect(await part.evaluate((e) => getComputedStyle(e).overflowY)).toBe('auto');
		const last = outline.getByRole('navigation', { name: 'Contents' }).locator('a').last();
		await last.scrollIntoViewIfNeeded();
		await expect(last).toBeInViewport();
		// the keys move it too
		await line.focus();
		const now = Number(await line.getAttribute('aria-valuenow'));
		await page.keyboard.press('ArrowDown');
		await expect(line).toHaveAttribute('aria-valuenow', String(now + 3));
	});

	test("the column's edge turns blue under the pointer, moves sideways, and is remembered", async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 700 });
		await page.goto('/master/drafting/main');
		const edge = page.getByTestId('column-divider');
		const column = page.getByTestId('column');
		await expect(edge).toBeVisible();
		const before = (await column.boundingBox())!.width;
		const at = (await edge.boundingBox())!;
		// the line is the column's own edge, with room inside it to take hold of
		expect(Math.abs(at.x + at.width - before)).toBeLessThanOrEqual(1);
		const line = () => edge.evaluate((e) => getComputedStyle(e, '::before').borderRightColor);
		const resting = await line();
		await page.mouse.move(at.x + at.width / 2, at.y + 200);
		await expect(edge).toHaveCSS('cursor', 'col-resize');
		// under the pointer the line takes the link's blue, as the outline's does
		await expect.poll(line).not.toBe(resting);
		expect(await line()).toBe(await page.getByTestId('outline-divider').evaluate((e) => {
			e.classList.add('moving');
			const c = getComputedStyle(e, '::before').borderTopColor;
			e.classList.remove('moving');
			return c;
		}));
		await page.mouse.down();
		await page.mouse.move(at.x + at.width / 2 + 120, at.y + 200, { steps: 5 });
		await expect.poll(async () => Number(await edge.getAttribute('aria-valuenow'))).toBeGreaterThan(before + 80);
		await page.mouse.up();
		await expect.poll(async () => (await column.boundingBox())!.width).toBeGreaterThan(before + 80);
		const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('viewer.prefs') ?? '{}').column);
		expect(stored).toBeGreaterThan(before + 80);
		await page.reload();
		await expect.poll(async () => (await page.getByTestId('column').boundingBox())!.width).toBeGreaterThan(before + 80);
		// the keys move it too
		await edge.focus();
		const now = Number(await edge.getAttribute('aria-valuenow'));
		await page.keyboard.press('ArrowLeft');
		await expect(edge).toHaveAttribute('aria-valuenow', String(now - 16));
		// folded, the column has no edge to drag
		await page.getByTestId('panel-fold').click();
		await expect(edge).toHaveCount(0);
	});
});

test('a session rename shows at once', async ({ page }) => {
	await writes(page, ['session-rename', 'session-close']);
	// the publisher does not answer until the name has shown, so a name that waited for it never would
	let shown = () => {};
	const nameShown = new Promise<void>((r) => (shown = r));
	await page.route('**/_api/session-rename', async (route) => {
		await nameShown;
		await route.fulfill({ json: { ok: true, result: '' } });
	});
	await page.goto('/review/record/sessions');
	await page.getByTestId(`sessions-rename-${REFEREE}`).click();
	const field = page.getByRole('textbox', { name: 'Rename referee' });
	await field.fill('the second reading');
	await field.press('Enter');
	await expect(page.getByTestId(`session-row-${REFEREE}`)).toContainText('the second reading');
	const answered = page.waitForResponse('**/_api/session-rename');
	shown();
	await answered;
});

test('accepting needs no session', async ({ page }) => {
	// accepting and incorporating a pull name no session
	await writes(page, ['review-accept']);
	let accepted: string[] = [];
	await page.route('**/_api/review-accept', async (route) => {
		accepted = route.request().postDataJSON().keys;
		await route.fulfill({ json: { ok: true, result: 'accepted 1 of 1', accepted, refused: [] } });
	});
	await page.goto('/review');
	const accept = page.locator('[data-testid="review-row"][data-key="sy-0001"]').getByTestId('review-accept');
	await expect(accept).toBeEnabled();
	await accept.click();
	await expect.poll(() => accepted).toEqual(['sy-0001']);
});

test("the pane alone hides a page's annotations", async ({ page }) => {
	await page.goto('/node/sy-0002');
	const counted = pane(page, 0).locator('.fragment mark.annotation-label');
	await expect(counted).toHaveCount(1);
	await viewMenu(page, 0);
	await page.getByTestId('toggle-hide-notes').click();
	await expect(pane(page, 0).locator('.fragment mark.annotation:not(.hidden)')).toHaveCount(0);
	await viewMenu(page, 0);
	await page.getByTestId('toggle-hide-notes').click();
	await expect(counted).toHaveCount(1);
});

test.describe('sections', () => {
	test('the column lists no results: a result is read where it lives, and found by ⌘K', async ({ page }) => {
		await page.goto('/node/sy-0003');
		await expect(page.getByTestId('docs-tree')).toBeVisible();
		await expect(page.getByTestId('nodes-toggle')).toHaveCount(0);
		await expect(page.getByTestId('nodes-list')).toHaveCount(0);
		// found by ⌘K, which is search's one way in
		await expect(page.getByTestId('column-search')).toHaveCount(0);
	});

	test('the panel never repeats the strip', async ({ page }) => {
		for (const path of ['/threads', '/tags', '/loose']) {
			await page.goto(path);
			await expect(page.locator('.panel .rail-label', { hasText: /^Views$/ })).toHaveCount(0);
			// the documents stand there instead, with the contents folded under the open one
			await expect(page.getByTestId('docs-tree')).toBeVisible();
		}
	});
});
