// What Docs draws of the library on round six's fixture (`?fixture=round6`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 8 to 11): the Library button and its picker, a work beside a draft, a citation's card, the notes tab, the Lean marks in the margin and the formalize panel. Where the library's reads are not served, Docs keeps today's Library shelf, which its own specs hold.
import { expect, test, type Page } from '@playwright/test';
import { viewMenu } from '../workspace';

/** Tabs `times` through the page: the keyboard never leaves `dialog`. */
async function tabsWithin(page: Page, dialog: string, times = 12): Promise<void> {
	for (let i = 0; i < times; i++) {
		await page.keyboard.press('Tab');
		const inside = await page.evaluate((id) => {
			const at = document.activeElement;
			return !at || at === document.body || !!at.closest(`[data-testid="${id}"]`);
		}, dialog);
		expect(inside, `Tab ${i + 1} left the dialog`).toBe(true);
	}
}

async function open(page: Page): Promise<void> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/master/drafting/main?fixture=round6');
	await expect(page.getByTestId('docs-library')).toBeVisible();
}

test('the Open a work… button opens the picker over Docs, which finds, sorts and opens a work beside the draft', async ({ page }) => {
	await open(page);
	await expect(page.getByTestId('docs-library')).toHaveText('Open a work…');
	await page.getByTestId('docs-library').click();
	const picker = page.getByTestId('docs-picker');
	// a modal dialog: it takes the keyboard, the draft behind it is inert, and Escape gives the keyboard back to the Library button
	await expect(picker).toHaveAttribute('role', 'dialog');
	await expect(picker).toHaveAttribute('aria-modal', 'true');
	await expect(picker.getByTestId('picker-search')).toBeFocused();
	expect(await page.locator('.fragment').first().evaluate((el) => !!el.closest('[inert]'))).toBe(true);
	await tabsWithin(page, 'docs-picker');
	await page.keyboard.press('Escape');
	await expect(picker).toHaveCount(0);
	await expect(page.getByTestId('docs-library')).toBeFocused();
	expect(await page.locator('.fragment').first().evaluate((el) => !!el.closest('[inert]'))).toBe(false);
	await page.getByTestId('docs-library').click();
	await expect(picker.getByTestId('picker-row')).toHaveCount(300);
	await expect(picker).toContainText('300 works');
	const arden = picker.getByTestId('picker-row').filter({ hasText: 'Cycle spaces of finite quivers' }).filter({ hasText: '2024' });
	await expect(arden.locator('td.d')).toHaveText('[1]');
	await expect(arden.locator('td.d')).toHaveAttribute('title', 'main.tex cites it as [1]');
	await picker.getByTestId('picker-search').fill('median orders on weighting lattices');
	await expect(picker.getByTestId('picker-row')).toHaveCount(1);
	await expect(picker).toContainText('1 work');
	// the search folds accents, as the Library's does
	await picker.getByTestId('picker-search').fill('kovac');
	await expect(picker.getByTestId('picker-row').first()).toContainText('Kovač');
	await picker.getByTestId('picker-search').fill('');
	await picker.getByRole('button', { name: 'thumbnails' }).click();
	await expect(picker.getByTestId('work-thumb')).toHaveCount(60);
	await picker.getByRole('button', { name: 'list' }).click();
	await page.keyboard.press('Escape');
	await expect(picker).toHaveCount(0);
	await page.getByTestId('docs-library').click();
	await picker.getByTestId('picker-row').filter({ hasText: 'Cycle spaces of finite quivers' }).filter({ hasText: '2024' }).click();
	await expect(picker).toHaveCount(0);
	await expect(page.getByTestId('work-item')).toBeVisible();
	await expect(page.getByTestId('work-item').getByTestId('pdf-doc')).toBeVisible();
	await expect(page.getByRole('tab', { name: /Arden 2024/ })).toBeVisible();
	// beside a draft, the reader draws no digest marks and offers none
	await expect(page.getByTestId('work-item').getByTestId('reader-view')).toHaveCount(0);
	// one toolbar over the paper: the pane's row holds the reader's bar
	const bar = page.getByRole('group', { name: 'controls for Arden 2024' });
	await expect(bar.getByTestId('zoom-in')).toBeVisible();
	await expect(bar.getByTestId('page-at')).toBeVisible();
	await expect(page.getByTestId('work-item').locator('.tb')).toHaveCount(0);
	await expect(page.getByTestId('work-item').getByTestId('zoom-in')).toHaveCount(0);
	// words selected offer no note, as in the Library
	const reader = page.getByTestId('work-item');
	await expect(reader.locator('.text span').first()).toBeAttached();
	await reader.evaluate((box) => {
		const span = [...box.querySelectorAll('.text span')].find((s) => (s.textContent ?? '').trim().length > 8)!;
		const range = document.createRange();
		range.selectNodeContents(span);
		getSelection()!.removeAllRanges();
		getSelection()!.addRange(range);
		span.closest('.text')!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	// the one reader's Quote, and no note: beside a draft the Library's own actions are not laid over it
	await expect(page.getByTestId('quote-offer')).toBeVisible();
	await expect(page.getByRole('button', { name: 'note', exact: true })).toHaveCount(0);
	await expect(page.getByTestId('mark-to-digest')).toHaveCount(0);
	await expect(page).toHaveURL(/\/master\//);
});

/** Hovers the draft's `nth` citation, made to name `node`, until the card shows `shows`: a draft drawn again between the two (the manifest is read each second) takes the planted name away, as it would not take a name the publisher wrote. */
async function cardOf(page: Page, nth: number, node: string, shows: string): Promise<void> {
	await expect(async () => {
		await page.mouse.move(0, 0);
		await citing(page, nth, node);
		await page.locator('.fragment span.cite').nth(nth).hover();
		await expect(page.getByTestId('cite-card')).toContainText(shows, { timeout: 2000 });
	}).toPass({ timeout: 20000 });
}

/** Has the draft's `nth` citation name `node`, as its fragment will once citations resolve to the library's nodes (`dialect.md`, a citation carrying no target until then). */
async function citing(page: Page, nth: number, node: string): Promise<void> {
	await expect(page.locator('.fragment span.cite').nth(nth)).toBeAttached();
	await page.evaluate(([i, n]) => (document.querySelectorAll<HTMLElement>('.fragment span.cite')[Number(i)].dataset.target = String(n)), [nth, node]);
}

test("a citation's card shows the cited result and opens its work beside the draft at its place; a stub's offers to locate it or have it read", async ({ page }) => {
	await open(page);
	const card = page.getByTestId('cite-card');
	await cardOf(page, 0, 'tq-0203', 'Proposition 2.1');
	await expect(card).toContainText('Arden 2024 · page 7');
	await expect(card).toContainText('matches the paper');
	await card.getByRole('button', { name: 'open at its place' }).click();
	await expect(page.getByTestId('work-item')).toBeVisible();
	await expect(page.getByRole('tab', { name: /Arden 2024/ })).toBeVisible();
	// at the page the card names
	await expect(page.getByRole('group', { name: 'controls for Arden 2024' }).getByTestId('page-at')).toHaveValue('7');
	await expect(page.getByTestId('work-item').getByTestId('pdf-page-7')).toBeInViewport({ ratio: 0.3 });
	await expect(card).toHaveCount(0);
	await cardOf(page, 1, 'tq-04A1', 'Theorem 2.3');
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
	await expect(page.getByTestId('work-item')).toBeVisible();
	await expect(page).toHaveURL(/\/notes|\/master\//);
});

test('the formalize panel from the Web: chosen results or the card, what stops the request and what keeps it from reading formalized, prove or assume for now, and the request', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6');
	await expect(page.getByTestId('web-row').first()).toBeVisible();
	const pick = (name: string) => page.getByTestId('web-list').locator('.wrow').filter({ hasText: name }).first().getByTestId('web-choose');
	await pick('Lemma 3.10').check();
	await pick('Lemma 3.11').check();
	await expect(page.getByTestId('web-chosen')).toContainText('2 chosen');
	await page.getByTestId('web-chosen').getByRole('button', { name: 'formalize…' }).click();
	const panel = page.getByTestId('formalize-panel');
	await expect(panel).toContainText('Formalize these 2 results');
	await page.keyboard.press('Escape');
	await expect(panel).toHaveCount(0);
	await page.getByTestId('web-chosen').getByRole('button', { name: 'clear' }).click();
	await page.getByTestId('web-list').getByTestId('web-row').filter({ hasText: 'Theorem 3.4' }).first().click();
	await page.getByTestId('focus-formalize').click();
	await expect(panel).toContainText('Formalize Theorem 3.4');
	await expect(page.getByTestId('formalize-lead')).toHaveText('To formalize this, an agent will state 3 definitions in Lean, prove 2 of your lemmas, and assume 4 results from your library.');
	await expect(panel).toContainText('Stops the request');
	await expect(panel).toContainText('Definition 3.2 has no label, so a Lean statement could not name it. Add one in main.tex, then ask again.');
	await expect(panel).toContainText('Before it reads formalized');
	await expect(panel).toContainText('Theorem 2.3 of Okafor 2022 has not been read.');
	await expect(panel).toContainText('Lemmas 5.7 and 5.9 of Arden 2024 and Theorem 5.1 of Arden 2025 have not been checked against their papers.');
	await expect(panel).toContainText('Lemma 3.3 waits for you to attest its Lean statement.');
	// what only the agent's work makes possible, and what nobody settles yet, each said so
	await expect(panel.locator('[data-testid="formalize-before"][data-why="attest"][data-when="after"]')).toHaveText("Theorem 3.4 will wait for you to attest its Lean statement once it is written.After the agent's work.");
	await expect(panel.locator('[data-testid="formalize-before"][data-why="cite"]')).toHaveText('The citation of Oka22 names no result of its work.Nothing you do now settles this; loom does not yet tell which result a citation means.');
	expect(await panel.getByTestId('formalize-before').evaluateAll((bs) => bs.map((b) => b.getAttribute('data-when')))).toEqual(['now', 'now', 'now', 'after', 'waiting']);
	await expect(page.getByTestId('formalize-ask')).toBeDisabled();
	await expect(page.getByTestId('formalize-ask')).toHaveText('add a label to Definition 3.2 first');
	const lemma = panel.getByTestId('formalize-item').filter({ hasText: 'Lemma 3.11' });
	await lemma.getByRole('button', { name: 'assume for now' }).click();
	await expect(page.getByTestId('formalize-lead')).toHaveText('To formalize this, an agent will state 3 definitions in Lean, prove 1 of your lemmas, assume 1 of your lemmas for now, and assume 4 results from your library.');
	await panel.getByTestId('formalize-item').filter({ hasText: 'Definition 3.2' }).getByRole('button', { name: 'Definition 3.2' }).click();
	await expect(panel).toContainText('The height of a weighting w is the largest |w(a)|.');
	await panel.getByRole('button', { name: 'Close the formalize panel' }).click();
	// a result whose plan nothing stops is asked for, one task
	await page.getByTestId('web-scope-all').check();
	await page.getByTestId('web-group').filter({ hasText: 'bounds.tex' }).click();
	await page.getByTestId('web-list').getByTestId('web-row').filter({ hasText: 'Theorem 1' }).first().click();
	await page.getByTestId('focus-formalize').click();
	await expect(page.getByTestId('formalize-ask')).toHaveText('ask an agent to formalize Theorem 1');
	await page.getByTestId('formalize-ask').click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to formalize Theorem 1. It waits in Review, under Agents still working.');
	await expect(panel).toHaveCount(0);
	await expect(page).toHaveURL(/\/web/);
});

test("Lean marks stand in a draft's margin, a click on one not formalized opens the panel there, and the view menu hides them", async ({ page }) => {
	await open(page);
	// the draft's results named by the fixture's keys, as the scan names them in a draft of round six
	await expect(page.locator('.fragment div.env[data-key]').nth(1)).toBeAttached();
	await page.evaluate(() => {
		const envs = document.querySelectorAll<HTMLElement>('.fragment div.env[data-key]');
		envs[0].dataset.key = 'thm:rank';
		envs[1].dataset.key = 'thm:count';
	});
	await viewMenu(page);
	await page.getByTestId('toggle-lean-marks').click();
	await viewMenu(page);
	await page.getByTestId('toggle-lean-marks').click();
	await expect(page.getByTestId('lean-mark')).toHaveCount(2);
	await expect(page.getByTestId('lean-mark').first()).toHaveAttribute('data-mark', 'formalized');
	const not = page.locator('[data-testid="lean-mark"][data-mark="not"]');
	await expect(not).toHaveAttribute('title', 'not formalized · formalize…');
	await not.click();
	const panel = page.getByTestId('formalize-panel');
	await expect(panel).toContainText('Formalize Theorem 3.4');
	// a modal dialog: it takes the keyboard, the draft behind it is inert, and Escape gives the keyboard back to the mark
	await expect(panel).toHaveAttribute('role', 'dialog');
	await expect(panel).toHaveAttribute('aria-modal', 'true');
	await expect(panel).toBeFocused();
	expect(await page.locator('.fragment').first().evaluate((el) => !!el.closest('[inert]'))).toBe(true);
	await tabsWithin(page, 'formalize-panel');
	await page.keyboard.press('Escape');
	await expect(panel).toHaveCount(0);
	await expect(not).toBeFocused();
	await viewMenu(page);
	await page.getByTestId('toggle-lean-marks').click();
	await expect(page.getByTestId('lean-mark')).toHaveCount(0);
	await expect(page).toHaveURL(/\/master\//);
});
