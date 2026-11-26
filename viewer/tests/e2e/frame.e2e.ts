// The frame at each width the layout defines: the column open beside two panes; the column folded to its strip below 1200px; one pane below the workspace's two-pane width. At each, what must stay in reach does, every pane draws its toolbar, and nothing scrolls sideways; and the column's message, which goes by itself however the last one was ended.
import { expect, test, type Page } from '@playwright/test';
import { beside, pane } from '../workspace';
import { PDF, serve } from '../manifest';
import { wideFont } from '../fonts';

async function open(page: Page, width: number): Promise<void> {
	await page.route('**/_files/drafting/figures/fig.pdf', (route) => route.fulfill({ body: PDF, contentType: 'application/pdf' }));
	await page.setViewportSize({ width, height: 900 });
	await page.goto('/master/drafting/main' + beside('/file/drafting/figures/fig.pdf'));
	await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
}

const fits = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);

test('1440: the column open, its four views, its foot, and two panes each with its toolbar', async ({ page }) => {
	await open(page, 1440);
	await expect(page.locator('.panel.away')).toHaveCount(0);
	for (const v of ['docs', 'library', 'web', 'review']) await expect(page.getByTestId(`primary-${v}`)).toBeVisible();
	await expect(page.getByTestId('legend-open')).toBeInViewport();
	await expect(page.getByTestId('session-footer')).toHaveCount(0);
	for (const i of [0, 1]) await expect(pane(page, i).getByTestId('item-controls')).toBeVisible();
	expect(await fits(page)).toBe(true);
});

test('1100: the column folded to its strip of the four views, two panes each with its toolbar', async ({ page }) => {
	await open(page, 1100);
	await expect(page.locator('.panel.away')).toHaveCount(1);
	for (const id of ['panel-fold', 'strip-docs', 'strip-library', 'strip-web', 'strip-review']) await expect(page.getByTestId(id)).toBeInViewport();
	await expect(page.getByTestId('strip-docs')).toHaveAttribute('aria-current', 'page');
	await expect(page.getByTestId('primary-docs')).toHaveCount(0);
	await expect(page.getByTestId('session-footer')).toHaveCount(0);
	for (const i of [0, 1]) await expect(pane(page, i).getByTestId('item-controls')).toBeVisible();
	expect(await fits(page)).toBe(true);
	// unfolded for this visit, the four views are back
	await page.getByTestId('panel-fold').click();
	await expect(page.getByTestId('primary-review')).toBeVisible();
});

test('700: one pane under one strip of both panes\' tabs, with its toolbar', async ({ page }) => {
	await open(page, 700);
	await expect(page.getByTestId('narrow-strip')).toBeVisible();
	await expect(page.getByTestId('narrow-strip').getByTestId('item-tab')).toHaveCount(2);
	await expect(page.locator('[data-pane]')).toHaveCount(1);
	await expect(page.locator('[data-pane] [data-testid="item-controls"]')).toBeVisible();
	expect(await fits(page)).toBe(true);
});

test('a view name shows its hover card after a moment, is described by it, and each name opens its view', async ({ page }) => {
	await open(page, 1440);
	await page.getByTestId('primary-web').hover();
	await expect(page.getByTestId('hovercard')).toContainText('Every result and what it rests on');
	await page.mouse.move(800, 600);
	await expect(page.getByTestId('hovercard')).toHaveCount(0);
	// a screen reader is told what each view is for, and Escape takes down a card shown by focus
	await expect(page.getByTestId('primary-review')).toHaveAttribute('aria-description', /digested results to check against their papers/);
	await page.getByTestId('primary-library').focus();
	await expect(page.getByTestId('hovercard')).toBeVisible();
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('hovercard')).toHaveCount(0);
	for (const [v, path] of [['library', '/library'], ['web', '/web'], ['review', '/review']] as const) {
		await page.getByTestId(`primary-${v}`).click();
		await expect(page).toHaveURL(new RegExp(path));
		await expect(page.getByTestId(`primary-${v}`)).toHaveAttribute('aria-current', 'page');
	}
});

test('the legend of the marks opens from the foot in every view and closes on a click elsewhere or on Escape', async ({ page }) => {
	await open(page, 1440);
	for (const v of ['docs', 'library', 'web', 'review']) {
		await page.getByTestId(`primary-${v}`).click();
		await page.getByTestId('legend-open').click();
		await expect(page.getByTestId('legend').locator('[data-mark]')).toHaveCount(8);
		await page.mouse.click(800, 400);
		await expect(page.getByTestId('legend')).toHaveCount(0);
	}
	await page.getByTestId('legend-open').click();
	await expect(page.getByTestId('legend-open')).toHaveAttribute('aria-controls', 'marks-legend');
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('legend')).toHaveCount(0);
});

test("the quilt's name is not a way anywhere, and the head's icons are 28 px targets round a glyph a person can see", async ({ page }) => {
	await open(page, 1440);
	await expect(page.getByTestId('quilt-name')).not.toHaveAttribute('href');
	expect(await page.getByTestId('quilt-name').evaluate((el) => el.tagName)).toBe('SPAN');
	for (const id of ['settings-toggle', 'panel-fold']) {
		const target = (await page.getByTestId(id).boundingBox())!;
		const glyph = (await page.getByTestId(id).locator('svg').boundingBox())!;
		expect(target.width).toBeGreaterThanOrEqual(28);
		expect(target.height).toBeGreaterThanOrEqual(28);
		expect(glyph.width).toBeGreaterThanOrEqual(16);
	}
});

test("a message dismissed by mouse lets the next go by itself, and one dismissed by keyboard hands the keyboard to the foot's next control", async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/review?fixture=round6');
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	await tasks.first().hover();
	await tasks.first().getByRole('button', { name: 'delete' }).click();
	const said = page.getByTestId('column-message');
	await expect(said).toContainText('Task deleted.');
	// dismissed with the pointer: the box goes from under it
	await said.getByTestId('column-message-dismiss').click();
	await expect(said).toHaveCount(0);
	await tasks.first().hover();
	await tasks.first().getByRole('button', { name: 'delete' }).click();
	await expect(said).toContainText('Task deleted.');
	await page.mouse.move(900, 600);
	await expect(said).toHaveCount(0, { timeout: 9000 });
	// dismissed from the keyboard
	await tasks.first().hover();
	await tasks.first().getByRole('button', { name: 'delete' }).click();
	await said.getByTestId('column-message-dismiss').focus();
	await page.keyboard.press('Enter');
	await expect(said).toHaveCount(0);
	await expect(page.getByTestId('legend-open')).toBeFocused();
});

test("an undo by keyboard hands the keyboard to the foot's next control, and a message under the pointer when the column folds lets the next go by itself", async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library?fixture=round6');
	await expect(page.getByTestId('works-table')).toBeVisible();
	const row = page.getByTestId('work-row').filter({ hasText: 'Widgets and their bounds' }).first();
	await row.hover();
	await row.getByRole('button', { name: 'more' }).click();
	await page.getByTestId('row-delete').click();
	const said = page.getByTestId('column-message');
	await said.getByTestId('column-message-undo').focus();
	await page.keyboard.press('Enter');
	await expect(said).toHaveCount(0);
	await expect(page.getByTestId('legend-open')).toBeFocused();
	// a message under the pointer, then the column folds beneath it
	await page.goto('/review?fixture=round6');
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	await tasks.first().hover();
	await tasks.first().getByRole('button', { name: 'delete' }).click();
	await said.hover();
	await page.setViewportSize({ width: 1100, height: 900 });
	await expect(page.getByTestId('column-message-dot')).toBeVisible();
	await tasks.first().hover();
	await tasks.first().getByRole('button', { name: 'delete' }).click();
	await page.mouse.move(700, 600);
	await expect(page.getByTestId('column-message-dot')).toHaveCount(0, { timeout: 9000 });
});

test("a quilt an earlier loom made: the frame's head, one sentence and one button, said while it runs and when it fails, and the quilt itself once upgraded", async ({ page }) => {
	// a publisher waiting on a quilt in an earlier layout, as `write-api.md` §1 has it: only the upgrade served
	let found = 1;
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: found < 2 ? ['library-upgrade'] : [], format: { found, reads: 2 }, token: 't' } }));
	const answers: (() => Promise<void>)[] = [];
	await page.route('**/_api/library-upgrade', (route) => new Promise<void>((done) => answers.push(() => route.fulfill(next()).then(done))));
	let next: () => { status: number; json: unknown } = () => ({ status: 409, json: { error: { code: 'format-unknown', message: "this quilt's .loom/format says 7, and this loom reads format 2" } } });
	await page.setViewportSize({ width: 1440, height: 900 });
	// nothing the frame drew before it knew throws once it is taken away
	const thrown: string[] = [];
	page.on('pageerror', (e) => thrown.push(e.message));
	await page.goto('/library');
	await expect(page.getByTestId('format-old')).toBeVisible();
	await page.goto('/');
	const old = page.getByTestId('format-old');
	await expect(old).toBeVisible();
	await page.waitForTimeout(300);
	expect(thrown).toEqual([]);
	await expect(page.getByTestId('format-old-said')).toHaveText('This quilt was made by an earlier version of loom; upgrading it carries its papers over to this one.');
	// only the head: no view names, no files, no foot
	await expect(page.getByTestId('quilt-name')).toHaveText('loom');
	for (const v of ['docs', 'library', 'web', 'review']) await expect(page.getByTestId(`primary-${v}`)).toHaveCount(0);
	await expect(page.getByTestId('session-footer')).toHaveCount(0);
	await expect(page.locator('main code')).toHaveCount(0);
	// while it runs, then refused: a sentence of loom's, never the publisher's message or a command
	const button = page.getByTestId('format-old-upgrade');
	await button.click();
	await expect(page.getByTestId('format-old-said')).toHaveText('Upgrading the quilt and carrying its papers over…');
	await expect(button).toBeDisabled();
	await expect.poll(() => answers.length).toBe(1);
	await answers.shift()!();
	await expect(page.getByTestId('format-old-said')).toHaveText('This quilt was made by a version of loom this one cannot upgrade from.');
	await expect(old).not.toContainText('.loom');
	await expect(old).not.toContainText('loom upgrade');
	// a research state the door will not write: why, and to mend it, never to try again as it is
	next = () => ({ status: 409, json: { error: { code: 'state-refused', message: 'the carry stopped at research-state.md, whose links to works it rewrites, because loom could not write it: it holds bytes that are not text' } } });
	await button.click();
	await expect.poll(() => answers.length).toBe(1);
	await answers.shift()!();
	await expect(page.getByTestId('format-old-said')).toHaveText('The quilt was not upgraded: its research state holds a link that names nothing or a character that is not text, which loom will not write. Mend the research state, then upgrade the quilt again.');
	await expect(old).not.toContainText('try it again');
	// carried, but not all of it: said, and the button opens the quilt
	next = () => ({ status: 200, json: { ok: true, result: 'brought the quilt forward', carried: { references: 3, documents: 1, notes_rekeyed: 0, overviews: 0, links_rewritten: 0, removed: [], problems: ['one entry could not be read'] } } });
	await button.click();
	await expect.poll(() => answers.length).toBe(1);
	found = 2;
	await answers.shift()!();
	await expect(page.getByTestId('format-old-said')).toHaveText('The quilt is upgraded, but one thing could not be carried over.');
	await expect(button).toHaveText('open the quilt');
	await button.click();
	await expect(old).toHaveCount(0);
	await expect(page.getByTestId('primary-docs')).toBeVisible();
});

test("in a wider font than this Mac's, every label in the four views' columns and the frame's head is one line, each count in view", async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	for (const [at, column] of [['/master/drafting/main', 'docs-part'], ['/library?fixture=round6', 'library-column'], ['/web?fixture=round6', 'web-column'], ['/review?fixture=round6', 'review-column']]) {
		await page.goto(at);
		await expect(page.getByTestId('quilt-name')).toBeVisible();
		await expect(page.getByTestId(column).locator('button, a, label').first()).toBeVisible();
		await wideFont(page);
		// each run of words in a label is one line: an outline's headings are the document's own and may wrap
		const wrapped = await page.evaluate(() => {
			const out: string[] = [];
			const roots = [...document.querySelectorAll('[data-testid$="-column"], [data-testid="docs-part"], [data-testid="column"] .head, [data-testid="column"] nav.primary')];
			for (const r of roots)
				for (const el of r.querySelectorAll('button, a, label, .name')) {
					if (el.closest('[data-testid="outline"]')) continue;
					for (const t of el.childNodes) {
						if (t.nodeType !== 3 || !t.textContent?.trim()) continue;
						const range = document.createRange();
						range.selectNodeContents(t);
						const tops = new Set([...range.getClientRects()].filter((c) => c.width > 0).map((c) => Math.round(c.top)));
						if (tops.size > 1) out.push(el.textContent!.trim());
					}
					const n = el.querySelector(':scope > .n');
					if (n && n.getBoundingClientRect().right > el.getBoundingClientRect().right + 0.5) out.push(`${el.textContent!.trim()}: its count out of view`);
				}
			return out;
		});
		expect(wrapped, at).toEqual([]);
	}
});

test('a run in the wide faces draws the viewer in them, its chrome and its text alike', async ({ page }) => {
	test.skip(!process.env.VIEWER_WIDE_FONT, 'only in a run in the wide faces (scripts/verify --wide-font)');
	await page.goto('/master/drafting/main');
	await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
	const faces = await page.evaluate(() => [document.querySelector('[data-testid="quilt-name"]')!, document.querySelector('.fragment p')!].map((el) => getComputedStyle(el).fontFamily));
	expect(faces[0]).toMatch(/^Verdana/);
	expect(faces[1]).toMatch(/^"?DejaVu Serif/);
});
