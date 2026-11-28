// The Library view on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/`), as the author settled it (`docs/design/mockups/library-round-6/`): the list of works and its thumbnails, adding a work, the digest menus, a work's tab with its outline, the result beside its page and the digest marks, deleting with undo; and the rules that hold everywhere: no control but the four view names changes view, no id is drawn, and nothing is asked for before it is shown.
import { expect, test, type Page, type Request } from '@playwright/test';
import { paperBytes } from '../../src/lib/library/fixtures/paper';

/** A paper of two pages, as a file the person drops on the intake. */
const PAPER = Buffer.from(paperBytes(2));

async function open(page: Page): Promise<Request[]> {
	const asked: Request[] = [];
	page.on('request', (r) => asked.push(r));
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6');
	await expect(page.getByTestId('works-table')).toBeVisible();
	return asked;
}

const row = (page: Page, title: string) => page.getByTestId('work-row').filter({ hasText: title }).first();

test("the list holds round six's 300 works, sorted by title, and sorts, filters and narrows as asked", async ({ page }) => {
	await open(page);
	await expect(page.getByTestId('work-row')).toHaveCount(300);
	await expect(page.getByTestId('work-row').first()).toContainText('A note on admissible weightings');
	await page.getByTestId('sort-title').click();
	await expect(page.getByTestId('work-row').first()).not.toContainText('A note on admissible weightings');
	await expect(page.getByTestId('library-column').getByRole('button')).toHaveText(['All works', 'Cited in your drafts', 'No PDF or source']);
	// the amber ring's words are Review's: a copy not yet checked against its paper
	await page.getByTestId('legend-open').click();
	await expect(page.getByTestId('legend')).toContainText('not yet checked against its paper');
	await page.keyboard.press('Escape');
	await page.getByTestId('filter-nodoc').click();
	const nodoc = await page.getByTestId('work-row').count();
	expect(nodoc).toBeGreaterThan(3);
	expect(nodoc).toBeLessThan(300);
	await page.getByTestId('filter-all').click();
	await page.getByTestId('works-search').fill('widgets and their');
	await expect(page.getByTestId('work-row')).toHaveCount(1);
	await expect(page.getByText('1 of 300')).toBeVisible();
	await expect(row(page, 'Widgets and their bounds')).toContainText('11 of 62 · 2 checked');
});

test("a work's title is drawn in the list's sans, at the size of the columns beside it", async ({ page }) => {
	await open(page);
	const [title, authors] = await row(page, 'Widgets and their bounds').locator('td').evaluateAll((tds) => tds.slice(0, 2).map((td) => { const s = getComputedStyle(td); return `${s.fontFamily} ${s.fontSize}`; }));
	expect(title).toBe(authors);
});

test('thumbnails draw sixty at first, and the choice is remembered', async ({ page }) => {
	await open(page);
	await page.getByTestId('works-thumbs').click();
	await expect(page.getByTestId('work-thumb')).toHaveCount(60);
	// the pages of a row stand level, whatever the length of each caption
	const rows = await page.getByTestId('work-thumb').evaluateAll((cards) => {
		const tops = new Map<number, number[]>();
		for (const c of cards.slice(0, 24)) {
			const pg = c.querySelector('.pg')!.getBoundingClientRect();
			const row = Math.round(pg.top / 100);
			tops.set(row, [...(tops.get(row) ?? []), pg.top]);
		}
		return [...tops.values()].map((t) => Math.max(...t) - Math.min(...t));
	});
	expect(rows.length).toBeGreaterThan(1);
	for (const spread of rows) expect(spread).toBeLessThan(0.5);
	await page.reload();
	await expect(page.getByTestId('works-thumbnails')).toBeVisible();
	await page.getByTestId('works-list').click();
	await expect(page.getByTestId('works-table')).toBeVisible();
});

test('a pasted arXiv number adds its work, said in the column with undo, and the view does not change', async ({ page }) => {
	await open(page);
	await page.getByTestId('add-work').click();
	await expect(page.getByTestId('choose-files')).toBeVisible();
	await page.getByTestId('paste-identifier').fill('2209.01234v2');
	await page.getByTestId('paste-identifier').press('Enter');
	await expect(page.getByTestId('column-message')).toContainText('Added Gadget towers, Halberd and Ravel 2021, found by its arXiv number, with its TeX source.');
	await expect(page.getByTestId('column-message-undo')).toBeVisible();
	await expect(page).toHaveURL(/\/library/);
});

test('the digest menu over the list counts what the drafts use, and selecting takes ⌘-click', async ({ page }) => {
	await open(page);
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-used')).toContainText('(14)');
	await expect(page.getByTestId('digest-selected')).toBeDisabled();
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-menu')).toHaveCount(0);
	await row(page, 'Widgets and their bounds').click({ modifiers: ['Meta'] });
	await expect(page.getByTestId('library-tab')).toHaveCount(0);
	await page.getByTestId('digest-all').click();
	await expect(page.getByTestId('digest-selected')).toBeEnabled();
	await expect(page.getByTestId('digest-selected')).toContainText('(1 selected)');
});

test("a work's tab: its outline, a result beside its page, and the person's yes", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('library-tab')).toHaveCount(1);
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	await expect(page.getByTestId('outline-section')).toHaveCount(8);
	const radius = page.getByTestId('outline-item').filter({ hasText: 'Radius' });
	await expect(radius.locator('[data-mark="unchecked"]')).toHaveCount(1);
	await radius.click();
	await expect(page.getByTestId('node-side')).toContainText("Does loom's copy match the paper?");
	await page.getByTestId('it-matches').click();
	await expect(radius.locator('[data-mark="checked"]')).toHaveCount(1);
	// the yes opens the next result not compared, beside its page
	await expect(page.getByTestId('column-message')).toContainText('Definition 3.1 matches the paper; the next not compared is open.');
	await expect(page.getByTestId('node-side')).toContainText('Lemma 3.2');
});

test("a result loom cannot draw asks once for its work's source to be compiled, and then shows TeX's drawing", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	const square = page.getByTestId('outline-item').filter({ hasText: '6.3' }).first();
	await square.click();
	const side = page.getByTestId('node-side');
	// the publisher's drawing is never asked for before the person's word: the text is shown plain, with the one question
	await expect(side.getByTestId('node-plain')).toContainText('tikzcd');
	await expect(side.getByTestId('node-drawn')).toHaveCount(0);
	await expect(side.getByTestId('draw-ask')).toContainText('Compile the source of Smith 2024');
	await side.getByTestId('draw-compile').click();
	await expect(page.getByTestId('column-message')).toContainText('Compiling the source of Smith 2024');
	await expect(side.getByTestId('node-drawn')).toBeVisible();
	await expect(side.getByTestId('draw-ask')).toHaveCount(0);
	// asked once for the work: opened again, the result is TeX's drawing with no question
	await page.getByTestId('outline-item').filter({ hasText: 'Radius' }).click();
	await expect(side).toContainText('Radius');
	await square.click();
	await expect(side.getByTestId('node-drawn')).toBeVisible();
	await expect(side.getByTestId('draw-ask')).toHaveCount(0);
});

test('results chosen in the outline are digested from the TeX source', async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await page.getByTestId('work-digest').click();
	await expect(page.getByTestId('digest-used')).toContainText('(2)');
	await page.getByTestId('digest-choose').click();
	const ticks = page.getByTestId('outline-tick');
	await ticks.nth(0).check();
	await ticks.nth(1).check();
	await page.getByTestId('digest-chosen').click();
	await expect(page.getByTestId('column-message')).toContainText('Digested 2 results from the TeX source');
	await expect(page.getByTestId('outline-tick')).toHaveCount(0);
});

test('the digest marks are asked for only once they are on', async ({ page }) => {
	const asked = await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('work-reader')).toBeVisible();
	await page.waitForTimeout(300);
	expect(asked.some((r) => r.url().includes('library-places'))).toBe(false);
	await page.getByTestId('reader-view').click();
	await page.getByTestId('overlay-toggle').click();
	// Definition 2.1 stands on page 3, where Section 2 begins
	await page.getByTestId('work-reader').getByTestId('page-at').fill('3');
	await page.getByTestId('work-reader').getByTestId('page-at').press('Enter');
	await expect(page.locator('[data-testid="digest-chip"][data-node="tq-00A4"]')).toBeInViewport();
});

test('a work held only as a PDF lists its marks and the stubs no place is known for', async ({ page }) => {
	await open(page);
	await row(page, 'Median orders on weighting lattices').click();
	await expect(page.getByText("Contents, from the PDF's outline")).toBeVisible();
	await expect(page.getByTestId('outline-mark')).toHaveCount(1);
	await expect(page.getByText('Cited, not yet placed')).toBeVisible();
	await expect(page.getByTestId('locate-in-pdf')).toBeVisible();
});

test('deleting a work takes it out, and undo puts it back', async ({ page }) => {
	await open(page);
	const jones = row(page, 'Covering estimates');
	await jones.hover();
	await jones.getByTestId('row-more').click();
	await page.getByTestId('row-delete').click();
	await expect(page.getByTestId('column-message')).toContainText('Deleted Jones 2019, with its results and notes');
	await expect(page.getByTestId('work-row')).toHaveCount(299);
	await page.getByTestId('column-message-undo').click();
	await expect(page.getByTestId('work-row')).toHaveCount(300);
});

test('no control in the Library changes view, and no id is drawn', async ({ page }) => {
	test.setTimeout(600000);
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('work-reader')).toBeVisible();
	// every control the Library draws, in its view and its column, but today's reader's own toolbar and the file chooser, which are not the Library's and open the system's dialogs
	const n = await page.evaluate(() => {
		const roots = [document.querySelector('[data-testid="library-view"]'), document.querySelector('[data-testid="library-column"]')];
		const buttons = roots.flatMap((r) => [...(r?.querySelectorAll('button') ?? [])]).filter((b) => !b.closest('.tb') && !b.closest('[data-testid="pdf-doc"]') && b.getAttribute('data-testid') !== 'choose-files' && b.getAttribute('data-testid') !== 'row-delete');
		buttons.forEach((b, i) => b.setAttribute('data-crawl', String(i)));
		return buttons.length;
	});
	expect(n).toBeGreaterThan(20);
	for (let i = 0; i < n; i++) {
		const b = page.locator(`[data-crawl="${i}"]`);
		if (!(await b.isVisible().catch(() => false))) continue;
		await b.click({ timeout: 5000 }).catch(() => {});
		expect(page.url()).toMatch(/\/library/);
		await page.keyboard.press('Escape');
	}
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\btq-[0-9A-Z]{4}\b/);
});

test("a work's tab has an address: a reload keeps the open works, and Back stays within the Library", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page).toHaveURL(/\/library\?work=/);
	await page.reload();
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	await expect(page.getByTestId('library-tab')).toHaveCount(1);
	await page.goBack();
	await expect(page).toHaveURL(/\/library(\?fixture=round6)?$/);
	await expect(page.getByTestId('works-table')).toBeVisible();
	await expect(page.getByTestId('library-tab')).toHaveCount(1);
});

test("the Library's name goes back to the tab it was left at, after another view and after a reload there", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	await page.getByTestId('primary-docs').click();
	await expect(page).not.toHaveURL(/\/library/);
	await page.getByTestId('primary-library').click();
	await expect(page).toHaveURL(/\/library\?work=/);
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	await page.getByTestId('primary-docs').click();
	await page.reload();
	await page.getByTestId('primary-library').click();
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
	// left at the list, it goes back to the list
	await page.getByTestId('library-tab-works').click();
	await expect(page.getByTestId('works-table')).toBeVisible();
	await page.getByTestId('primary-docs').click();
	await page.getByTestId('primary-library').click();
	await expect(page.getByTestId('works-table')).toBeVisible();
});

test("the list works from the keyboard: a row's title opens its work, and its own controls show while it holds the keyboard", async ({ page }) => {
	await open(page);
	const smith = row(page, 'Widgets and their bounds');
	await smith.getByTestId('work-open').focus();
	await expect(smith.getByTestId('row-digest')).toHaveCSS('opacity', '1');
	await page.keyboard.press('Tab');
	await expect(smith.getByTestId('row-digest')).toBeFocused();
	await smith.getByTestId('work-open').focus();
	await page.keyboard.press('Enter');
	await expect(page.getByTestId('work-title')).toHaveText('Widgets and their bounds');
});

test('several files chosen at once are said together, and one undo takes every work back', async ({ page }) => {
	await open(page);
	await page.getByTestId('add-work').click();
	await page.getByTestId('choose-files-input').setInputFiles([
		{ name: 'alpha.pdf', mimeType: 'application/pdf', buffer: PAPER },
		{ name: 'beta.pdf', mimeType: 'application/pdf', buffer: PAPER },
		{ name: 'gamma.pdf', mimeType: 'application/pdf', buffer: PAPER }
	]);
	await expect(page.getByTestId('column-message')).toContainText('Added 3 works.');
	await expect(page.getByTestId('work-row')).toHaveCount(303);
	await page.getByTestId('column-message-undo').click();
	await expect(page.getByTestId('work-row')).toHaveCount(300);
});

test("edit its entry… opens the work's entry as a field, a refusal says why in the viewer's words, and a saved entry is the work's", async ({ page }) => {
	await open(page);
	const smith = row(page, 'Widgets and their bounds');
	await smith.hover();
	await smith.getByTestId('row-more').click();
	await page.getByTestId('row-edit-entry').click();
	const field = page.getByTestId('entry-field');
	await expect(field).toBeFocused();
	await expect(field).toHaveValue(/^@article\{Smi24,/);
	await field.fill('not an entry');
	await page.getByTestId('entry-save').click();
	await expect(page.getByTestId('entry-refused')).toHaveText('That is not a BibTeX entry loom can keep for this work.');
	await field.fill('@article{Smi24,\n  author = {Smith},\n  title  = {Widgets, bounded},\n  year   = {2024},\n}');
	await page.getByTestId('entry-save').click();
	await expect(page.getByTestId('column-message')).toContainText('Saved the entry of Smith 2024.');
	await expect(page.getByTestId('entry-field')).toHaveCount(0);
	await expect(page.getByTestId('work-title')).toHaveText('Widgets, bounded');
});

test("a file stating an arXiv number a work states is asked about in the column, each answer settles it, and one closed unanswered is not asked again here", async ({ page }) => {
	await open(page);
	const msg = page.getByTestId('column-message');
	const choose = async (name: string) => {
		await page.getByTestId('add-work').click();
		await page.getByTestId('choose-files-input').setInputFiles([{ name, mimeType: 'application/pdf', buffer: PAPER }]);
	};
	// yes: the file is filed under the work, which holds no PDF, and no row is added
	await choose('2008.01056v2.pdf');
	await expect(msg).toContainText('2008.01056v2.pdf states arXiv 2008.01056, as Lindqvist and Ueda 2017 in your library does. Is it that work?');
	const answers = msg.getByTestId('column-message-choice');
	await expect(answers).toHaveText(['yes', 'no, a work of its own']);
	for (const a of await answers.all()) expect((await a.boundingBox())!.height).toBeGreaterThanOrEqual(28);
	await expect(page.getByTestId('work-row')).toHaveCount(300);
	await answers.filter({ hasText: 'yes' }).click();
	await expect(msg).toContainText('Filed 2008.01056v2.pdf under Lindqvist and Ueda 2017.');
	await expect(page.getByTestId('work-row')).toHaveCount(300);
	// no: a work of its own
	await choose('2003.01021v1.pdf');
	await msg.getByTestId('column-message-choice').filter({ hasText: 'no, a work of its own' }).click();
	await expect(page.getByTestId('work-row')).toHaveCount(301);
	// closed unanswered: not asked again on this page, and nothing written; the work of its own just added holds a PDF, so it is named beside the question rather than offered
	await choose('2003.01021v2.pdf');
	await expect(msg).toContainText('as Jones 2019 in your library does. Is it that work? 2003.01021v1.pdf states it too and holds its PDF already.');
	await expect(answers).toHaveText(['yes', 'no, a work of its own']);
	await page.getByTestId('column-message-dismiss').click();
	await expect(msg).toHaveCount(0);
	await page.getByTestId('add-work').click();
	await page.getByTestId('paste-identifier').fill('2209.01234v2');
	await page.getByTestId('paste-identifier').press('Enter');
	await expect(msg).toContainText('Added');
	await page.getByTestId('column-message-dismiss').click();
	await expect(msg).toHaveCount(0);
	await expect(page.getByTestId('work-row')).toHaveCount(302);
});

test("a file dropped on a work's row is asked about before anything is taken in: yes files it under that work, no makes a work of its own", async ({ page }) => {
	await open(page);
	const msg = page.getByTestId('column-message');
	const answers = msg.getByTestId('column-message-choice');
	const rows = page.getByTestId('work-row');
	const drop = (title: string, name: string) =>
		row(page, title).evaluate((el, name) => {
			const data = new DataTransfer();
			data.items.add(new File(['%PDF-1.4'], name, { type: 'application/pdf' }));
			el.dispatchEvent(new DragEvent('dragover', { dataTransfer: data, bubbles: true, cancelable: true }));
			el.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
		}, name);
	// the row under the pointer is no sign of what the person meant: nothing is filed until they say
	await drop('Widgets and their bounds', 'zakharov-kuznetsov.pdf');
	await expect(msg).toContainText(/^Is zakharov-kuznetsov\.pdf .+, the work you dropped it on\?/);
	await expect(answers).toHaveText(['yes', 'no, a work of its own']);
	await expect(rows).toHaveCount(300);
	await answers.filter({ hasText: 'no, a work of its own' }).click();
	await expect(msg).toContainText('Added zakharov-kuznetsov.pdf');
	await expect(rows).toHaveCount(301);
	await expect(row(page, 'zakharov-kuznetsov.pdf')).toBeVisible();
	// yes: filed under the work, and no row is added
	await page.getByTestId('column-message-dismiss').click();
	await drop('Widgets and their bounds', 'widgets.pdf');
	await answers.filter({ hasText: 'yes' }).click();
	await expect(msg).toContainText(/^Filed widgets\.pdf under /);
	await expect(rows).toHaveCount(301);
});

test('on a window narrow enough to fold the column, what a drop on the works list did is said beside the folded column, with its answers', async ({ page }) => {
	await page.setViewportSize({ width: 760, height: 800 });
	await page.goto('/library?fixture=round6');
	await expect(page.getByTestId('works-table')).toBeVisible();
	await expect(page.getByTestId('panel-fold')).toHaveAttribute('aria-expanded', 'false');
	await row(page, 'Widgets and their bounds').evaluate((el) => {
		const data = new DataTransfer();
		data.items.add(new File(['%PDF-1.4'], 'mZK_paper.pdf', { type: 'application/pdf' }));
		el.dispatchEvent(new DragEvent('dragover', { dataTransfer: data, bubbles: true, cancelable: true }));
		el.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
	});
	const msg = page.getByTestId('column-message');
	await expect(msg).toContainText(/^Is mZK_paper\.pdf .+, the work you dropped it on\?/);
	const box = (await msg.boundingBox())!;
	expect(box.x).toBeGreaterThanOrEqual(60);
	expect(box.x + box.width).toBeLessThanOrEqual(760);
	// its answers are under the pointer, not under the works list
	await msg.getByTestId('column-message-choice').filter({ hasText: 'no, a work of its own' }).click();
	await expect(msg).toContainText('Added mZK_paper.pdf');
	await expect(page.getByTestId('work-row')).toHaveCount(301);
});

test('a copy of a PDF every work stating its number holds already is asked about as a copy, naming each work so its row can be told apart, kept as a work of its own or let go', async ({ page }) => {
	await open(page);
	const msg = page.getByTestId('column-message');
	const answers = msg.getByTestId('column-message-choice');
	const choose = async (name: string) => {
		await page.getByTestId('add-work').click();
		await page.getByTestId('choose-files-input').setInputFiles([{ name, mimeType: 'application/pdf', buffer: PAPER }]);
	};
	// Arden 2024 holds its PDF, so it is never offered: the copy is kept as a work of its own, taken without the network
	await choose('2000.01000v3.pdf');
	await expect(msg).toContainText('2000.01000v3.pdf states arXiv 2000.01000, whose PDF Arden 2024 holds already. Keep it as a work of its own?');
	await expect(answers).toHaveText(['yes, a work of its own', 'no, let it go']);
	await answers.filter({ hasText: 'yes, a work of its own' }).click();
	await expect(page.getByTestId('work-row')).toHaveCount(301);
	await choose('2000.01000v3 (1).pdf');
	await expect(msg).toContainText('whose PDF Arden 2024 and 2000.01000v3.pdf hold already.');
	await answers.filter({ hasText: 'yes, a work of its own' }).click();
	await expect(page.getByTestId('work-row')).toHaveCount(302);
	const alike = page.getByTestId('work-row').filter({ hasText: 'arXiv 2000.01000v3' });
	await expect(alike).toHaveCount(2);
	await expect(alike.getByTestId('work-came-as')).toHaveCount(2);
	expect((await alike.getByTestId('work-came-as').allInnerTexts()).sort()).toEqual(['2000.01000v3 (1).pdf', '2000.01000v3.pdf']);
	// a third names all three, each as the row tells it from the others
	await choose('2000.01000v3 (2).pdf');
	await expect(msg).toContainText('2000.01000v3 (2).pdf states arXiv 2000.01000, whose PDF Arden 2024, 2000.01000v3.pdf and 2000.01000v3 (1).pdf hold already. Keep it as a work of its own?');
	// a work deleted while the question waits is no longer named: asked again once the column is quiet, it names what the library still holds
	const remove = async (w: ReturnType<typeof page.getByTestId>) => {
		await w.hover();
		await w.getByTestId('row-more').click();
		await page.getByTestId('row-delete').click();
		await expect(msg).toContainText('Deleted');
		await page.getByTestId('column-message-dismiss').click();
	};
	const came = (name: string) => page.getByTestId('work-row').filter({ has: page.getByTestId('work-came-as').filter({ hasText: new RegExp(`^${name.replace(/[.()]/g, '\\$&')}$`) }) });
	await remove(came('2000.01000v3.pdf'));
	await expect(msg).toContainText('whose PDF Arden 2024 and 2000.01000v3 (1).pdf hold already.');
	// with every work it named gone, it asks only whether the file is a work of its own
	await remove(came('2000.01000v3 (1).pdf'));
	await remove(row(page, 'Cycle spaces of finite quivers').filter({ hasText: '2024' }));
	await expect(msg).toContainText('2000.01000v3 (2).pdf states arXiv 2000.01000, as a work since deleted from your library did. Add it as a work of its own?');
	await expect(answers).toHaveText(['yes, a work of its own']);
	const before = await page.getByTestId('work-row').count();
	await answers.click();
	await expect(page.getByTestId('work-row')).toHaveCount(before + 1);
	// let go: nothing is added, and the column says so
	await page.getByTestId('column-message-dismiss').click();
	await choose('2006.01042v1.pdf');
	await expect(msg).toContainText('2006.01042v1.pdf states arXiv 2006.01042, whose PDF Smith 2024 holds already. Keep it as a work of its own?');
	await answers.filter({ hasText: 'no, let it go' }).click();
	await expect(msg).toContainText('Let 2006.01042v1.pdf go.');
	await expect(page.getByTestId('work-row')).toHaveCount(before + 1);
});

test('a delete a killed act left under way is said once, by the first read of the list, with its undo', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6&delete=killed');
	await expect(page.getByTestId('works-table')).toBeVisible();
	const msg = page.getByTestId('column-message');
	await expect(msg).toContainText('Deleted Ostrander 2020, with its results and notes');
	await expect(page.getByTestId('work-row')).toHaveCount(299);
	await page.getByTestId('column-message-undo').click();
	await expect(page.getByTestId('work-row')).toHaveCount(300);
	await expect(row(page, 'Widget categories and their duals')).toHaveCount(1);
});

test('on a quilt that has not said whether loom may use the network, a work added by an identifier asks in its row to be looked up this once', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6&network=unasked');
	await expect(page.getByTestId('works-table')).toBeVisible();
	await page.getByTestId('add-work').click();
	await page.getByTestId('paste-identifier').fill('2209.01234v2');
	await page.getByTestId('paste-identifier').press('Enter');
	const added = row(page, 'arXiv 2209.01234v2');
	await expect(added).toContainText('look it up this once?');
	// not now leaves it unconfirmed; a later look up, refused as the quilt has not answered, asks again
	await added.getByTestId('look-not').click();
	await expect(added).toContainText('details unconfirmed');
	await added.getByRole('button', { name: 'look up' }).click();
	await expect(added).toContainText('look it up this once?');
	await expect(page.getByTestId('column-message')).not.toContainText('Loom could not do that.');
	await added.getByTestId('look-yes').click();
	await expect(row(page, 'Gadget towers')).toBeVisible();
	await expect(row(page, 'Gadget towers')).not.toContainText('look it up');
});

test("at 760, an arXiv number added on a quilt that has not said whether loom may go online says plainly that its title waits, and its row's question is in view whole", async ({ page }) => {
	await page.setViewportSize({ width: 760, height: 800 });
	await page.goto('/library?fixture=round6&network=unasked');
	await expect(page.getByTestId('works-table')).toBeVisible();
	await page.getByTestId('add-work').click();
	await page.getByTestId('paste-identifier').fill('1709.09864');
	await page.getByTestId('paste-identifier').press('Enter');
	const msg = page.getByTestId('column-message');
	await expect(msg).toContainText('Added arXiv 1709.09864. Its title and authors are not looked up yet');
	await expect(msg).not.toContainText('found by');
	const added = row(page, 'arXiv 1709.09864');
	await added.scrollIntoViewIfNeeded();
	await expect(added.getByTestId('look-yes')).toBeInViewport({ ratio: 1 });
	expect((await added.getByTestId('look-yes').boundingBox())!.x + 10).toBeLessThan(760);
	await added.getByTestId('look-yes').click();
	await expect(added).toHaveCount(0);
});

test('in thumbnails, a work added by an identifier and not looked up says so on its page, and its tab says what waits and looks it up on the word', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6&network=unasked');
	await expect(page.getByTestId('works-table')).toBeVisible();
	await page.getByTestId('add-work').click();
	await page.getByTestId('paste-identifier').fill('1709.09864');
	await page.getByTestId('paste-identifier').press('Enter');
	await expect(row(page, 'arXiv 1709.09864')).toBeVisible();
	await page.getByRole('searchbox').fill('1709');
	await page.getByTestId('works-thumbs').click();
	const card = page.getByTestId('work-thumb').filter({ hasText: 'arXiv 1709.09864' });
	await expect(card).toContainText('not looked up yet');
	await expect(card).not.toContainText('no document');
	await card.click();
	const tab = page.getByTestId('work-no-document');
	await expect(tab).toContainText('Loom has not looked this work up yet');
	await tab.getByTestId('work-look-up').click();
	await expect(tab).toHaveCount(0);
});

test('with no backend, the list says so in a sentence, with no name of an endpoint', async ({ page }) => {
	await page.goto('/library');
	await expect(page.getByTestId('works-failed')).toHaveText('This loom does not serve the Library yet.');
});

test('the chosen columns and the sort are kept across a reload', async ({ page }) => {
	await open(page);
	await page.getByTestId('sort-year').click();
	await page.getByTestId('works-columns').click();
	await page.getByTestId('col-holds').click();
	await page.reload();
	await expect(page.getByTestId('sort-year').locator('xpath=..')).toHaveAttribute('aria-sort', 'ascending');
	await expect(page.getByTestId('sort-holds')).toBeVisible();
});

test("words selected on a page offer their actions, and the Library's mark to digest and ask an agent beside them; an agent's question takes the keyboard and is said", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	const reader = page.getByTestId('work-reader');
	await expect(reader.locator('.text span').first()).toBeAttached();
	await reader.evaluate((box) => {
		const span = [...box.querySelectorAll('.text span')].find((s) => (s.textContent ?? '').trim().length > 8)!;
		const range = document.createRange();
		range.selectNodeContents(span);
		getSelection()!.removeAllRanges();
		getSelection()!.addRange(range);
		span.closest('.text')!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	// the one reader's actions, with the Library's own laid beside them
	await expect(page.getByTestId('selection-actions')).toBeVisible();
	await expect(page.getByTestId('mark-to-digest')).toBeVisible();
	await expect(page.getByRole('button', { name: 'note', exact: true })).toHaveCount(0);
	await page.getByTestId('ask-agent').click();
	await expect(page.getByTestId('ask-field')).toBeFocused();
	await page.keyboard.type('Is this the bound used in Section 4?');
	await page.keyboard.press('Enter');
	await expect(page.getByTestId('column-message')).toContainText('Added to agent tasks: a question on these words.');
});

test("the reader's zoom controls are 28 pixel targets", async ({ page }) => {
	await open(page);
	await row(page, 'Widgets and their bounds').click();
	for (const id of ['zoom-fit', 'zoom-out', 'zoom-in']) {
		const box = (await page.getByTestId('work-reader').getByTestId(id).boundingBox())!;
		expect(Math.round(box.width)).toBeGreaterThanOrEqual(28);
		expect(Math.round(box.height)).toBeGreaterThanOrEqual(28);
	}
});
