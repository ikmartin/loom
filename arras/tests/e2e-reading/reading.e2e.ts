// Reading under `loom serve` (plan 0.13 §11): the things the fixture-only suite cannot check because they need the publisher — on a work's pages, a selection mapped onto the page text loom derives and recorded, a box recorded as drawn, and a locator lit from a link; in a document, a selection across a citation quoted as written; and a PDF's place kept, as a work's and a project file's.
//
// A test that writes (`test`) is served on its own copy of the showcase, and one that only reads (`readOnly`) on its worker's; a test that needs a note to exist writes it first through the API.
import { ARRAS, compileFolder, expect, readOnly, test, workOf, type Served } from '../served';
import type { Page } from '@playwright/test';
import { openPicker, pickSession } from '../picker';
import { beside, openHere } from '../workspace';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';

/** The showcase quilt every served copy is made from, whose works' references each copy keeps. */
const SHOWCASE = join(ARRAS, '../loom/tests/quilts/showcase');
/** A work's reference, by the key its entry has, as a work's address names it. */
const refOf = (key: string): string => workOf(SHOWCASE, key)!.ref;

const PAGE2 = `/library/${refOf('Bellamy19')}?page=2`;
/** A PDF of the project's own. */
const HANDOUT = '/file/notes/handout.pdf';

/** Bellamy19 in the served copy's library: its reference, and its stored PDF's hash. */
function bellamy(served: Served): { ref: string; hex: string } {
	const work = workOf(served.root, 'Bellamy19')!;
	return { ref: work.ref, hex: basename(work.pdf!, '.pdf') };
}

/** Open page 2 with a session chosen, and wait until the paper has been drawn again for the narrower pane; returns the session. */
async function opened(page: Page, served: Served): Promise<string> {
	await page.goto(PAGE2);
	await page.locator('[data-testid="pdf-page-2"] canvas').waitFor();
	const session = await intoASession(page, served);
	// choosing a session opens its Chat beside, which narrows the paper's pane and draws its pages again at the zoom that fits; a selection made while the text layer is being replaced would be lost with it
	await expect(page.locator('[data-pane="1"]').getByTestId('chat')).toBeVisible();
	await drawn(page, 2);
	return session;
}

/** The text layer page `n` holds now, numbered in the order this page first saw each layer; 0 before it has one. A redraw replaces the layer, so a new number is a new draw. */
async function layerOf(page: Page, n: number): Promise<{ width: number; spans: number; layer: number }> {
	return page.getByTestId(`pdf-page-${n}`).evaluate((el) => {
		const w = window as unknown as { __layers?: WeakMap<Element, number>; __layerCount?: number };
		w.__layers ??= new WeakMap();
		const all = el.querySelectorAll('.text span');
		const first = all[0];
		if (first && !w.__layers.has(first)) w.__layers.set(first, (w.__layerCount = (w.__layerCount ?? 0) + 1));
		return { width: Math.round(el.getBoundingClientRect().width), spans: all.length, layer: first ? w.__layers.get(first)! : 0 };
	});
}

/**
 * Wait until page `n` is drawn and holding still: the same width and the same text layer, with more than 50 spans of text and newer than `after`, on two reads `every` ms apart; returns that layer.
 *
 * Fails showing the last state read.
 */
async function drawn(page: Page, n: number, { every = 300, after = 0 } = {}): Promise<number> {
	let last = '';
	let layer = 0;
	await expect
		.poll(
			async () => {
				const now = await layerOf(page, n);
				const said = `width ${now.width}, ${now.spans} spans, text layer #${now.layer}`;
				const held = said === last && now.width > 0 && now.spans > 50 && now.layer > after;
				last = said;
				layer = now.layer;
				return held ? 'held' : said;
			},
			{ intervals: [every] }
		)
		.toBe('held');
	return layer;
}

/**
 * Choose where the notes will be filed: the showcase's newest open session, read from the copy's session index.
 *
 * A write names its session and nothing is selected at rest (plan 0.13.1), so this is the first thing a reader does before annotating — and therefore the first thing these tests do.
 */
async function intoASession(page: Page, served: Served): Promise<string> {
	const id = served.openSessions().at(-1)!;
	await pickSession(page, id);
	await expect(page.getByTestId('session-footer')).toHaveAttribute('aria-label', /^writing in /);
	return id;
}

/** A person's note on page 2 of Bellamy19 over `phrase`, of type `type` or none, written through the API; returns its id. */
async function noteOnPageAs(served: Served, phrase: string, body: string, type: string | null): Promise<string> {
	const result = await served.api('annotate', { target: bellamy(served).ref, page: 2, quote: phrase, message: body, ...(type ? { type } : {}) });
	return result.split(/\s+/)[0];
}

/** A person's note on page 2 of Bellamy19 over `phrase`, written through the API into `session`; returns its id. */
async function noteOnPage2(served: Served, session: string, phrase: string, body: string): Promise<string> {
	const result = await served.api('annotate', { target: bellamy(served).ref, page: 2, quote: phrase, message: body, type: 'note', session });
	return result.split(/\s+/)[0];
}

/** Select a phrase, as a reader does, and let go. It is scrolled into view first, as one a reader selects is: the chip at its end is hidden while that end is out of its pane's view. */
async function selectOnly(page: Page, phrase: string): Promise<void> {
	const span = page.locator(`[data-testid="pdf-page-2"] .text span:has-text("${phrase}")`).first();
	await span.scrollIntoViewIfNeeded();
	await span.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
}

/** Click the middle of an annotation's mark on a page: a mark takes no pointer, so the page below is asked what the click landed on. */
async function clickMark(page: Page, id: string): Promise<void> {
	const box = (await page.getByTestId(`page-mark-${id}`).boundingBox())!;
	await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

/** The colour a line of a mark is drawn in: grey, in the light, given as sRGB or as `color()`. */
const GREY = /rgb\(136, 135, 128\)|color\(srgb 0\.533\d* 0\.529\d* 0\.50\d*\)/;

test('a selection stays selected and offers only Quote; a note on its words is drawn on the page in the look loom gave it', async ({ page, served }) => {
	const id = await noteOnPageAs(served, 'incidence matrix', 'So the vertices are integral.', null);
	await opened(page, served);
	// highlighting a phrase to copy it is the ordinary thing to do with a paper, so selecting writes nothing and opens nothing: the selection survives, and Quote is offered at its end
	await selectOnly(page, 'incidence matrix');
	await expect(page.getByTestId('ann-popup')).toHaveCount(0);
	expect(await page.evaluate(() => window.getSelection()?.toString() ?? '')).toContain('incidence matrix');
	await expect(page.getByTestId('quote-offer')).toBeVisible();
	const written = served.written('So the vertices are integral.');
	expect(written.target).toBe(bellamy(served).ref);
	const anchor = written.anchor as Record<string, unknown>;
	expect(anchor.basis).toBe('text');
	expect(anchor.page).toBe(2);
	expect(String(anchor.exact)).toContain('incidence matrix');
	expect(anchor).not.toHaveProperty('quads'); // derived at build time, never recorded for text
	// with no type, the quilt's plain look: a yellow highlight, a band over each line
	await expect(page.getByTestId(`page-mark-${id}`)).toHaveAttribute('data-kind', 'highlight');
	await expect(page.getByTestId(`mark-band-${id}`)).toBeAttached();
});

test('a selection across a citation and a reference is quoted as they were written, and anchors', async ({ page, served }) => {
	// the 0.14 study (F5): the rendered `[2, Theorem 3.2]` shares no text with `\cite[Theorem 3.2]{Bellamy19}`, and the page prints `Ehrhart’s` for `Ehrhart's`, so a selection across either was "quote not found" and only a note on the whole proof was offered
	await page.addInitScript(() => localStorage.setItem('arras.annotate.hand', JSON.stringify({ type: 'question', over: {} })));
	await page.goto('/node/sh-000C');
	await page.getByTestId('tool-annotate').click();
	const para = page.locator('[data-pane="0"] .fragment details p').filter({ hasText: 'Ehrhart' }).first();
	await expect(para.locator('mjx-container').first()).toBeAttached();
	await para.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	// marked with Annotate, holding a type that asks something, so the popup takes the question before anything is written
	const draft = page.getByTestId('ann-popup');
	await expect(draft).toBeVisible();
	await draft.getByTestId('popup-comment-field').fill('Which digraph is this the median polytope of?');
	await draft.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);
	const written = served.written('Which digraph is this the median polytope of?');
	expect(written.target).toBe('sh-000C/proof');
	const quote = String((written.anchor as Record<string, unknown>).exact);
	expect(quote).toContain('\\cite[Theorem 3.2]{Bellamy19}');
	expect(quote).toContain('\\ref{sh-0009}');
	// and the note is anchored where it was written, not merely accepted (WQ-48 is a note that was accepted and not)
	await expect
		.poll(async () => {
			const m = await (await page.request.get('/build/manifest.json')).json();
			const a = m.annotations[written.id as string];
			return a ? `${a.recorded} ${a.anchored}` : 'absent';
		})
		.toBe('true true');
});

test('a region drawn with Alt is commented on, recorded as drawn, and drawn as an outline in the look in hand', async ({ page, served }) => {
	await page.addInitScript(() => localStorage.setItem('arras.annotate.hand', JSON.stringify({ type: null, over: {}, plain: { color: 'grey', style: 'underline', weight: 1, opacity: 100 } })));
	await opened(page, served);
	const canvas = page.locator('[data-testid="pdf-page-2"] canvas');
	// the column, not the window: the page's top at the top of the reader, so the display a third of the way down is in view
	await canvas.evaluate((c) => c.scrollIntoView({ block: 'start' }));
	// the pages either side report their sizes just after the first draw, which moves page 2 under a box measured too early: wait until its position holds still before drawing on it
	let box = (await canvas.boundingBox())!;
	await expect
		.poll(async () => {
			const again = (await canvas.boundingBox())!;
			const same = Math.abs(again.y - box.y) < 1 && Math.abs(again.height - box.height) < 1;
			box = again;
			return same ? 'held' : `moved to y ${again.y}, height ${again.height}`;
		}, { intervals: [300, 300, 300, 300] })
		.toBe('held');
	// traced, so a drag that draws nothing says what the pointer actually hit
	await page.evaluate(() => {
		const w = window as unknown as { __ev: string[] };
		w.__ev = [];
		for (const t of ['pointerdown', 'pointermove', 'pointerup']) {
			document.addEventListener(t, (e) => w.__ev.push(`${t}:${((e.target as Element).className || (e.target as Element).tagName).toString().slice(0, 30)}`), true);
		}
	});
	// the display on page 2, in the page's own proportions, with Alt held: a region with no tool up
	await page.keyboard.down('Alt');
	await page.mouse.move(box.x + box.width * 0.15, box.y + box.height * 0.36);
	await page.mouse.down();
	await page.mouse.move(box.x + box.width * 0.85, box.y + box.height * 0.4, { steps: 6 });
	await page.mouse.up();
	await page.keyboard.up('Alt');
	const seen = await page.evaluate(() => (window as unknown as { __ev: string[] }).__ev.slice(0, 10));
	const draft = page.getByTestId('draft-host').getByTestId('ann-popup');
	await expect(draft, `the pointer saw: ${seen.join(' ')}`).toBeVisible();
	await draft.getByTestId('popup-comment-field').fill('This is the display I want to cite.');
	await draft.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);
	const written = served.written('This is the display I want to cite.');
	const anchor = written.anchor as Record<string, unknown>;
	expect(anchor.basis).toBe('box');
	expect(anchor.quads).toHaveLength(1);
	// an outline in the look in hand, not an underline: here thin and grey
	await expect(page.getByTestId(`page-mark-${written.id}`)).toHaveAttribute('data-kind', 'box');
	const shape = page.getByTestId(`mark-line-${written.id}`).locator('.shape');
	await expect(shape).toBeAttached();
	expect(await shape.evaluate((el) => getComputedStyle(el).stroke)).toMatch(GREY);
	// its weight, which a mark drawn selected thickens a little
	expect(await page.getByTestId(`mark-line-${written.id}`).evaluate((g) => getComputedStyle(g).getPropertyValue('--weight').trim())).toBe('1');
	await expect(page.getByTestId(`mark-band-${written.id}`)).toHaveCount(0);
	// and its popup is open on it, once written
	await expect(page.getByTestId('ann-popup')).toHaveAttribute('data-annotation-id', String(written.id));
});

test('a mark opens the popup a fragment opens, and Escape closes it', async ({ page, served }) => {
	const id = await noteOnPage2(served, served.openSessions().at(-1)!, 'incidence matrix', 'a note to open from its mark');
	await opened(page, served);
	await expect(page.getByTestId(`page-mark-${id}`)).toBeVisible();
	await clickMark(page, id);
	const open = page.getByTestId('ann-popup');
	await expect(open).toHaveAttribute('data-annotation-id', id);
	await expect(open.getByTestId('popup-comment')).toContainText('a note to open from its mark');
	await page.keyboard.press('Escape');
	await expect(open).toHaveCount(0);
});

test('a locator in the URL is lit while the URL carries it, and a note is focused by its id', async ({ page, served }) => {
	// a note by id: one written here, since the showcase's own are in a closed session and closed sessions' annotations are hidden until shown
	const id = await noteOnPage2(served, served.openSessions().at(-1)!, 'incidence matrix', 'a note to focus by its id');
	await opened(page, served);
	// the page text loom derives from the stored PDF when it is first read, which writing the note above did
	const pageText = readFileSync(join(served.root, '.loom/cache/library/pages', bellamy(served).hex, 'pages/0002.txt'), 'utf8');
	const a = pageText.indexOf('totally unimodular');
	await page.goto(`${PAGE2}&span=${a}-${a + 'totally unimodular'.length}`);
	const lit = page.locator('[data-testid="pdf-page-2"] .mark.transient');
	await expect(lit).toBeVisible();
	await expect(lit).toHaveClass(/on/); // and it is the one in focus
	await page.goto(`${PAGE2}&annot=${id}`);
	await expect(page.getByTestId(`page-mark-${id}`)).toHaveClass(/\bon\b/);
	// and it arrives open: a link to a note is a link to what it says (plan 0.14)
	await expect(page.locator(`[data-testid="ann-popup"][data-annotation-id="${id}"]`)).toBeVisible();
});

test('a session is named on the spot and closed from the page', async ({ page, served }) => {
	await opened(page, served);
	await openPicker(page);
	await page.getByTestId('session-new').click();
	await page.getByTestId('session-new-title').fill('reading Bellamy, closely');
	await page.getByTestId('session-new-title').press('Enter');
	// it is selected on being opened, and the footer says so because that is where a note would land
	await expect(page.getByTestId('session-footer-name')).toContainText('reading Bellamy, closely');
	// closing the selected session clears the selection, so writing is unavailable until another is chosen
	await openPicker(page);
	// the verbs stand over a row only while the pointer is on it
	const row = page.locator('[data-testid="session-list"] li.selected');
	await expect(row.locator('[data-testid^="session-close-"]')).toBeHidden();
	await row.hover();
	await row.locator('[data-testid^="session-close-"]').click();
	await expect(page.getByTestId('session-footer-lead')).toHaveText('not writing in a session');
});

test('two notes on one place are each drawn there, with no count, and a click opens one of them', async ({ page, served }) => {
	const session = served.openSessions().at(-1)!;
	const first = await noteOnPage2(served, session, 'Boundedness holds', 'first on this phrase');
	const second = await noteOnPage2(served, session, 'Boundedness holds', 'second on this phrase');
	await opened(page, served);
	const one = page.getByTestId(`page-mark-${first}`);
	const two = page.getByTestId(`page-mark-${second}`);
	await expect(one).toBeVisible();
	await expect(two).toBeVisible();
	expect(await one.boundingBox()).toEqual(await two.boundingBox());
	expect(await one.evaluate((el) => getComputedStyle(el, '::after').content)).toBe('none');
	await clickMark(page, first);
	await expect(page.getByTestId('ann-popup')).toHaveAttribute('data-annotation-id', new RegExp(`^(${first}|${second})$`));
});

test('a popup shows the write it fired, without being closed and reopened', async ({ page, served }) => {
	// a popup reads its annotation from the manifest by id, so a resolve that comes back on the next poll is shown where the reader acted
	const id = await noteOnPageAs(served, 'exchange inequalities', 'resolve me', 'question');
	await opened(page, served);
	await expect(page.getByTestId(`page-mark-${id}`)).toBeVisible();
	await clickMark(page, id);
	const p = page.getByTestId('ann-popup');
	await expect(p.getByTestId('popup-status')).toHaveText('Open');
	await p.getByTestId('popup-resolve').click();
	// the same popup, still open, now resolved, with Reopen its undo
	await expect(p.getByTestId('popup-status')).toHaveText('Resolved');
	await expect(p.getByTestId('popup-resolve')).toHaveCount(0);
	await p.getByTestId('popup-reopen').click();
	await expect(p.getByTestId('popup-status')).toHaveText('Open');
});

test('a selection records the lines it covers and nothing else', async ({ page, served }) => {
	// **A phantom rectangle is a wrong anchor, not a cosmetic fault.** A range over the text layer yields a rectangle for every element it crosses, degenerate ones included, and those were mapped to points and recorded, at the layer's top-left, hundreds of points above the words they claimed to be. Words marked with Annotate are anchored by their text, and the rectangles drawn for them are the lines they cover.
	await opened(page, served);
	await page.getByTestId('tool-annotate').click();
	await selectOnly(page, 'rational polytope');
	await page.keyboard.press('Escape');
	// where the drawn rectangles stand, as the manifest publishes them; a letter-sized page bounds them
	const manifest = () => JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));
	type Raw = { id: string; quote?: string | null; rects?: number[][] | null };
	const found = () => (Object.values(manifest().annotations) as Raw[]).find((a) => (a.quote ?? '').includes('rational polytope'));
	await expect.poll(() => found()?.rects?.length ?? 0).toBeGreaterThan(0);
	for (const [x0, y0, x1, y1] of found()!.rects!) {
		expect(x1, `a quad with no width: ${JSON.stringify([x0, y0, x1, y1])}`).toBeGreaterThan(x0);
		expect(y1, `a quad with no height: ${JSON.stringify([x0, y0, x1, y1])}`).toBeGreaterThan(y0);
		expect(x0).toBeGreaterThanOrEqual(-1);
		expect(y0).toBeGreaterThanOrEqual(-1);
		expect(x1).toBeLessThanOrEqual(612 + 1);
		expect(y1).toBeLessThanOrEqual(792 + 1);
	}
});

readOnly('the page and the zoom are typed into, and take exactly what was typed', async ({ page, served }) => {
	// The controls live on the pane's toolbar rather than in a toolbar of the renderer's own, and both boxes are editable the way a desktop viewer's are: `+` twelve times is not how a reader reaches page 12. Typing over a box is the case that broke -- the field held `140`, the reader typed `150`, and `140150` clamped to the maximum -- so each assertion below is that the value taken is exactly the value typed.
	await opened(page, served);
	const zoom = page.getByTestId('zoom-at');
	const at = page.getByTestId('page-at');
	await expect(page.getByTestId('page-count')).toContainText('/');

	await zoom.click();
	await page.keyboard.type('150');
	await page.keyboard.press('Enter');
	await expect(zoom).toHaveValue('150%');

	await zoom.click();
	await page.keyboard.type('75');
	await page.keyboard.press('Enter');
	await expect(zoom).toHaveValue('75%');

	// Escape puts back what the view holds rather than committing what was typed
	await zoom.click();
	await page.keyboard.type('300');
	await page.keyboard.press('Escape');
	await expect(zoom).toHaveValue('75%');

	// matching the width is a zoom the reader did not have to name, so the box reports whatever it came to
	await page.getByTestId('zoom-fit').click();
	await expect(page.getByTestId('zoom-fit')).toHaveAttribute('aria-pressed', 'true');
	await expect(zoom).not.toHaveValue('75%');

	// and the page box moves the reader, the count beside it saying how far it can go
	await at.click();
	await page.keyboard.type('1');
	await page.keyboard.press('Enter');
	await expect(at).toHaveValue('1');
});

readOnly('a link that quotes a work without a page is lit on the page the publisher finds it on', async ({ page }) => {
	await page.goto(`/library/${refOf('Bellamy19')}?quote=` + encodeURIComponent('The median orders of a weighted digraph are in bijection with the vertices'));
	await expect(page.locator('[data-mark="_locator"]').first()).toBeInViewport();
	await expect(page.getByTestId('page-at')).toHaveValue('2');
});

readOnly('a mark round a formula leaves the formula typeset', async ({ page }) => {
	// the quote `underlying graph has $c$ connected components` is TeX; its mark takes the formula whole, so MathJax still reads it (phase 4)
	await page.goto('/node/sh-0009');
	const mark = page.locator('[data-pane="0"] .fragment mark.annotation', { hasText: 'underlying graph' }).first();
	await expect(mark.locator('mjx-container')).toHaveCount(1);
	await expect(page.locator('[data-pane="0"] .fragment')).not.toContainText('\\(');
});

test.describe('a document never compiled', () => {
	// the talk's compile taken away, so it has none of its own: the default document's `Theorem 3.1` would be plausible and wrong there (V3)
	test.use({
		prepareQuilt: async ({}, use) => {
			await use(({ root }) => rmSync(compileFolder(root, 'drafting/talk.tex'), { recursive: true, force: true }));
		}
	});

	test('shows its source, and none of another document’s numbers', async ({ page }) => {
		await page.goto('/master/drafting/talk');
		await page.locator('[data-pane="0"] .fragment pre.source').first().waitFor();
		await expect(page.locator('[data-pane="0"] .fragment .env-label').first()).toBeVisible();
		await expect(page.locator('[data-pane="0"] .fragment .env-label .number')).toHaveCount(0);
		await expect(page.getByTestId('item-controls')).not.toContainText('not yet numbered');
	});
});

readOnly("a paper's page in view is what loom here reports, at the address loom link prints", async ({ page, served }) => {
	await page.goto(PAGE2);
	await page.locator('[data-testid="pdf-page-2"] canvas').waitFor();
	const looking = () => JSON.parse(served.loom(['here', '--json'])).looking ?? {};
	await expect.poll(() => looking().item?.work).toBe(refOf('Bellamy19'));
	await expect.poll(() => looking().item?.page).toBe(2);
	expect(looking().item.link).toMatch(/^cited:.+\?page=2$/);
});

// Where a work opens: where the reader last was, unless a link names a place. These write nothing to the quilt, only to this browser, so each runs on its worker's copy in a browser of its own.
const BELLAMY = `/library/${refOf('Bellamy19')}`;
/** Arden's second version, a work of its own. */
const SECOND = `/library/${refOf('ArdenCycleSpaces')}`;
const QUOTE = 'The median orders of a weighted digraph are in bijection with the vertices';

/** A work's stored PDF in a copy of the quilt, by the key its entry has. */
function fileOf(root: string, key: string): Buffer {
	return readFileSync(workOf(root, key)!.pdf!);
}

/** The paper's scrolling column in a pane. */
const paperIn = (page: Page, pane: number) => page.locator(`[data-pane="${pane}"] .column`);

type At = { page: number; share: number };

/** Where a pane's paper stands, read off the column itself: the page at its top, and how far down that page. */
async function placeIn(page: Page, pane = 0): Promise<At> {
	return paperIn(page, pane).evaluate((c) => {
		const tops = [...c.querySelectorAll<HTMLElement>('[data-holder]')].map((h) => h.offsetTop);
		let at = 0;
		while (at + 1 < tops.length && tops[at + 1] <= c.scrollTop) at++;
		return { page: at + 1, share: Math.max(0, (c.scrollTop - tops[at]) / ((tops[at + 1] ?? c.scrollHeight) - tops[at])) };
	});
}

const said = (at: At) => `page ${at.page}, ${at.share.toFixed(3)} down`;

/** Wait until a pane's paper stands at `want`, to within `within` of a page: a hundredth is about eleven pixels at the default zoom. */
async function isAt(page: Page, want: At, { pane = 0, within = 0.01 } = {}): Promise<void> {
	await expect
		.poll(async () => {
			const at = await placeIn(page, pane);
			return at.page === want.page && Math.abs(at.share - want.share) <= within ? said(want) : said(at);
		})
		.toBe(said(want));
}

/** As `isAt`, and still there a moment later: what undoes a place arrives after it has been reached, a drawn page or a landing's scroll. */
async function staysAt(page: Page, want: At, { pane = 0, within = 0.01 } = {}): Promise<void> {
	await isAt(page, want, { pane, within });
	await paperIn(page, pane).locator(`[data-holder="${want.page}"] canvas`).waitFor();
	await page.waitForTimeout(800);
	await isAt(page, want, { pane, within });
}

/** Wait until page `n`'s top is at the top of a pane's paper, where asking for a page sends it, and still there a moment later. Measured exactly, since a page's top can fall between pixels, where `placeIn`, which reads rounded offsets, calls it the foot of the page before. */
async function arrived(page: Page, n: number, pane = 0): Promise<void> {
	const off = () => paperIn(page, pane).evaluate((c, n) => Math.abs(c.querySelector(`[data-holder="${n}"]`)!.getBoundingClientRect().top - c.getBoundingClientRect().top), n);
	await expect.poll(off).toBeLessThanOrEqual(1);
	await page.waitForTimeout(800);
	await expect.poll(off).toBeLessThanOrEqual(1);
}

/** Wait until this browser has kept `want` as where the reader is in a file, which it does once the column has been still a moment: a window opened or a reload before that finds the place before it. */
async function kept(page: Page, want: At): Promise<void> {
	await expect
		.poll(async () => {
			const places = await page.evaluate(() => Object.values<At>(JSON.parse(localStorage.getItem('arras.places') ?? '{}')));
			return places.some((at) => at.page === want.page && Math.abs(at.share - want.share) <= 0.01) ? said(want) : places.map(said).join(', ') || 'nothing kept';
		})
		.toBe(said(want));
}

/** Scroll a pane's paper to `want` as a reader does, with the wheel: only a hand on the paper moves it off a link's place. */
async function readTo(page: Page, want: At, pane = 0): Promise<void> {
	const paper = paperIn(page, pane);
	await paper.locator(`[data-holder="${want.page}"]`).waitFor({ state: 'attached' });
	const box = (await paper.boundingBox())!;
	await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
	await expect
		.poll(
			async () => {
				const away = await paper.evaluate((c, to) => {
					const holder = c.querySelector<HTMLElement>(`[data-holder="${to.page}"]`)!;
					const next = holder.nextElementSibling as HTMLElement | null;
					return Math.round(holder.offsetTop + to.share * ((next?.offsetTop ?? c.scrollHeight) - holder.offsetTop) - c.scrollTop);
				}, want);
				if (Math.abs(away) <= 4) return 'there';
				await page.mouse.wheel(0, away);
				return `${away}px away`;
			},
			{ intervals: [300] }
		)
		.toBe('there');
}

/** Open the other work in the pane and bring Bellamy19's tab back, which makes its paper again. */
async function awayAndBack(page: Page): Promise<void> {
	await openHere(page, SECOND);
	await page.getByRole('tab', { name: 'Bellamy 2019' }).click();
}

/** A PDF of `n` pages saying their numbers, the first small and the rest A4, as nothing in the showcase is: long enough that most of it is never drawn, and not one size throughout. */
function longPdf(n: number): Buffer {
	const bodies = ['<< /Type /Catalog /Pages 2 0 R >>', `<< /Type /Pages /Count ${n} /Kids [${Array.from({ length: n }, (_, i) => `${4 + 2 * i} 0 R`).join(' ')}] >>`, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
	for (let i = 0; i < n; i++) {
		const text = `BT /F1 24 Tf 72 400 Td (Page ${i + 1}) Tj ET`;
		bodies.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${i ? '595 842' : '400 600'}] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + 2 * i} 0 R >>`);
		bodies.push(`<< /Length ${text.length} >>\nstream\n${text}\nendstream`);
	}
	let out = '%PDF-1.4\n';
	const offsets = bodies.map((b, i) => {
		const at = out.length;
		out += `${i + 1} 0 obj\n${b}\nendobj\n`;
		return at;
	});
	const xref = out.length;
	out += `xref\n0 ${bodies.length + 1}\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}`;
	out += `trailer\n<< /Size ${bodies.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
	return Buffer.from(out, 'latin1');
}

readOnly('a work opens where the reader left it: after a reload, by a plain link, and by a link outside the panes', async ({ page }) => {
	const left = { page: 2, share: 0.4 };
	await page.goto(BELLAMY);
	await readTo(page, left);
	await page.reload();
	await staysAt(page, left);
	// a new visit, by a plain link
	await page.goto('/review');
	await page.goto(BELLAMY);
	await staysAt(page, left);
	// by a link outside the panes, with something else being read
	await page.goto(SECOND);
	await openHere(page, BELLAMY);
	await staysAt(page, left);
});

readOnly('a link that names a place wins over where the reader last was, and is where they are from then on', async ({ page }) => {
	const left = { page: 3, share: 0.2 };
	await page.goto(BELLAMY);
	await readTo(page, left);
	// a page
	await page.goto(`${BELLAMY}?page=2`);
	await staysAt(page, { page: 2, share: 0 });
	// and the visit has moved where the reader last was
	await page.goto(BELLAMY);
	await staysAt(page, { page: 2, share: 0 });
	// a quote with no page, which the paper only learns is on page 2 from loom's answer
	await readTo(page, left);
	await page.goto(`${BELLAMY}?quote=${encodeURIComponent(QUOTE)}`);
	const lit = page.locator('[data-mark="_locator"]').first();
	await expect(lit).toBeInViewport();
	await expect(page.getByTestId('page-at')).toHaveValue('2');
	await page.waitForTimeout(800);
	await expect(lit).toBeInViewport();
	// a result by its address, and by a citation of it, come back with the library's results: digests went with the node store's phase 2, and a citation names no result until it resolves to a node
});

readOnly('a work never read opens at its start, whatever was read before it', async ({ page }) => {
	await page.goto(BELLAMY);
	await staysAt(page, { page: 1, share: 0 });
	await readTo(page, { page: 2, share: 0.4 });
	await page.goto(SECOND);
	await staysAt(page, { page: 1, share: 0 });
});

readOnly('two works keep a place each', async ({ page }) => {
	const first = { page: 3, share: 0.2 };
	const second = { page: 2, share: 0.4 };
	await page.goto(BELLAMY);
	await readTo(page, first);
	await page.goto(SECOND);
	await readTo(page, second);
	await page.reload();
	await staysAt(page, second);
	await openHere(page, BELLAMY);
	await staysAt(page, first);
	await page.getByRole('tab', { name: 'arden-cycle-spaces-v2.pdf' }).click();
	await staysAt(page, second);
});

readOnly('a work is open in one pane of a window, and a second window on it leaves the first where it is', async ({ page, context }) => {
	await page.goto(`${BELLAMY}?beside=${encodeURIComponent(BELLAMY)}`);
	await expect(page.locator('[data-pane]')).toHaveCount(1);
	await page.goto(BELLAMY);
	const mine = { page: 2, share: 0.4 };
	await readTo(page, mine);
	// a second window opens where the first was, and goes its own way
	const other = await context.newPage();
	await other.goto(BELLAMY);
	await staysAt(other, mine);
	const theirs = { page: 3, share: 0.2 };
	await readTo(other, theirs);
	await staysAt(page, mine);
	// not even a paper made again takes the other window's place: what this window was doing is in the tab
	await awayAndBack(page);
	await staysAt(page, mine);
	await staysAt(other, theirs);
	// whichever moved last is what the next visit opens at
	await readTo(page, { page: 1, share: 0.5 });
	await kept(page, { page: 1, share: 0.5 });
	const third = await context.newPage();
	await third.goto(BELLAMY);
	await staysAt(third, { page: 1, share: 0.5 });
});

readOnly('a tab brought back is where it was left', async ({ page }) => {
	const left = { page: 2, share: 0.4 };
	await page.goto(BELLAMY);
	await readTo(page, left);
	await openHere(page, SECOND);
	await staysAt(page, { page: 1, share: 0 });
	await page.getByRole('tab', { name: 'Bellamy 2019' }).click();
	await staysAt(page, left);
	// a page asked for in the box is answered once, not again by a paper made later
	const at = page.getByTestId('page-at');
	await at.click();
	await page.keyboard.type('3');
	await page.keyboard.press('Enter');
	await expect(at).toHaveValue('3');
	// read back from page 3, once the paper is there
	await arrived(page, 3);
	await readTo(page, left);
	await awayAndBack(page);
	await staysAt(page, left);
});

readOnly('a link’s place holds until the reader has left its page: then it comes off the address, and a reload stays with them', async ({ page }) => {
	await page.goto(`${BELLAMY}?quote=${encodeURIComponent(QUOTE)}`);
	const lit = page.locator('[data-mark="_locator"]').first();
	await expect(lit).toBeInViewport();
	await expect(page).toHaveURL(/quote=/);
	// moved within its page, the link is still in force and still lit, and a paper made again does not send the reader back to its place
	const within = { page: 2, share: 0.4 };
	await readTo(page, within);
	await expect(page).toHaveURL(/quote=/);
	await expect(lit).toBeAttached();
	await awayAndBack(page);
	await staysAt(page, within);
	await expect(lit).toBeAttached();
	// off its page, it lets go
	const on = { page: 3, share: 0.2 };
	await readTo(page, on);
	await expect(page).toHaveURL(new RegExp(`${BELLAMY}$`));
	await expect(page.locator('[data-mark="_locator"]')).toHaveCount(0);
	await staysAt(page, on);
	await page.reload();
	await staysAt(page, on);
});

readOnly('a plain link to a work already open leaves the reader where they are', async ({ page }) => {
	const left = { page: 2, share: 0.4 };
	await page.goto(BELLAMY);
	await readTo(page, left);
	await openHere(page, BELLAMY);
	await staysAt(page, left);
	// and with a link's place in force, it is the plain link that goes
	await page.goto(`${BELLAMY}?page=3`);
	await staysAt(page, { page: 3, share: 0 });
	await readTo(page, { page: 3, share: 0.2 });
	await openHere(page, BELLAMY);
	await expect(page).toHaveURL(new RegExp(`${BELLAMY}$`));
	await staysAt(page, { page: 3, share: 0.2 });
});

readOnly('a place holds at another zoom and another width, with most of a long paper never drawn', async ({ page }) => {
	const body = longPdf(40);
	await page.route('**/paper.pdf', (r) => r.fulfill({ body, contentType: 'application/pdf' }));
	await page.goto(BELLAMY);
	await expect(page.getByTestId('page-count')).toContainText('40');
	const at = page.getByTestId('page-at');
	await at.click();
	await page.keyboard.type('30');
	await page.keyboard.press('Enter');
	await page.locator('[data-testid="pdf-page-30"] canvas').waitFor();
	const left = { page: 30, share: 0.4 };
	await readTo(page, left);
	await page.reload();
	await staysAt(page, left);
	// the pages it passed over hold a size and nothing else, and the size is the first page's even though the first page was never drawn
	await expect(page.locator('[data-testid="pdf-page-1"] canvas')).toHaveCount(0);
	await expect(page.locator('[data-testid="pdf-page-20"] canvas')).toHaveCount(0);
	const tall = (n: number) => page.locator(`[data-holder="${n}"]`).evaluate((h) => h.getBoundingClientRect().height);
	expect((await tall(20)) / (await tall(30))).toBeCloseTo(600 / 842, 2);
	const zoom = page.getByTestId('zoom-at');
	await zoom.click();
	await page.keyboard.type('75');
	await page.keyboard.press('Enter');
	await expect(zoom).toHaveValue('75%');
	await staysAt(page, left, { within: 0.02 });
	await page.reload();
	await staysAt(page, left, { within: 0.02 });
	await page.setViewportSize({ width: 900, height: 700 });
	await page.reload();
	await staysAt(page, left, { within: 0.02 });
});

readOnly('a page asked for as a long paper opens is where it stays, as the pages around it draw at their own size', async ({ page }) => {
	const body = longPdf(300);
	await page.route('**/paper.pdf', (r) => r.fulfill({ body, contentType: 'application/pdf' }));
	await page.goto(BELLAMY);
	await expect(page.getByTestId('page-count')).toContainText('300');
	const at = page.getByTestId('page-at');
	await at.click();
	await page.keyboard.type('250');
	await page.keyboard.press('Enter');
	await arrived(page, 250);
	await expect(at).toHaveValue('250');
	// and it is where a paper made again opens
	await awayAndBack(page);
	await arrived(page, 250);
});

readOnly('a place in another file behind the work is not carried over, and a page it no longer has is not looked for', async ({ page, served }) => {
	const left = { page: 2, share: 0.4 };
	await page.goto(BELLAMY);
	await readTo(page, left);
	await kept(page, left);
	// another file of the same length: its page 2 is not the page they were on
	const another = fileOf(served.root, 'Arden24-v2');
	await page.route('**/paper.pdf', (r) => r.fulfill({ body: another, contentType: 'application/pdf' }));
	await page.reload();
	await staysAt(page, { page: 1, share: 0 });
	// a file that came back is the one they were in
	await page.unroute('**/paper.pdf');
	await page.reload();
	await staysAt(page, left);
	// a shorter file has no such page, and opens at its start rather than at its end
	await readTo(page, { page: 3, share: 0.2 });
	await kept(page, { page: 3, share: 0.2 });
	const shorter = longPdf(2);
	await page.route('**/paper.pdf', (r) => r.fulfill({ body: shorter, contentType: 'application/pdf' }));
	await page.reload();
	await expect(page.getByTestId('page-count')).toContainText('2');
	await staysAt(page, { page: 1, share: 0 });
});

test.describe('a PDF among the project’s files', () => {
	const OWN = 'notes/bellamy.pdf';
	const AT = `/file/${OWN}`;
	// the same bytes as Bellamy19's paper, as a reference kept in a folder and also added to the library is
	test.use({
		prepareQuilt: async ({}, use: (p: (q: { root: string }) => void) => Promise<void>) => {
			await use(({ root }) => {
				mkdirSync(join(root, 'notes'), { recursive: true });
				writeFileSync(join(root, OWN), fileOf(root, 'Bellamy19'));
			});
		}
	});

	test('opens where it was left, after a reload, by a plain link and as a tab brought back', async ({ page }) => {
		await page.goto(AT);
		await staysAt(page, { page: 1, share: 0 });
		const left = { page: 2, share: 0.4 };
		await readTo(page, left);
		await page.reload();
		await staysAt(page, left);
		await page.goto('/review');
		await page.goto(AT);
		await staysAt(page, left);
		await openHere(page, HANDOUT);
		await staysAt(page, { page: 1, share: 0 });
		await page.getByRole('tab', { name: 'bellamy.pdf' }).click();
		await staysAt(page, left);
	});

	test('a link to its page wins, until the reader has left that page: then the address lets go, and a reload stays with them', async ({ page }) => {
		await page.goto(AT);
		await readTo(page, { page: 2, share: 0.4 });
		await page.goto(`${AT}#page=3`);
		await staysAt(page, { page: 3, share: 0 });
		// moved within its page, the link is still in force, and a tab brought back does not send the reader back to its place
		const within = { page: 3, share: 0.2 };
		await readTo(page, within);
		await expect(page).toHaveURL(/#page=3$/);
		await openHere(page, HANDOUT);
		await page.getByRole('tab', { name: 'bellamy.pdf' }).click();
		await staysAt(page, within);
		// off its page, it lets go
		const on = { page: 1, share: 0.5 };
		await readTo(page, on);
		await expect(page).toHaveURL(new RegExp(`${AT}$`));
		await staysAt(page, on);
		await page.reload();
		await staysAt(page, on);
	});

	test('a paper drawn again at a new zoom never shows a render refused', async ({ page, context }) => {
		// a page redrawn while its first draw was running told the reader "Cannot use the same canvas during multiple render() operations" (phase 5). The race needs a slow machine to show, so the CPU is slowed and the zoom changed while pages are drawing.
		const cdp = await context.newCDPSession(page);
		await cdp.send('Emulation.setCPUThrottlingRate', { rate: 8 });
		for (const at of [AT, '/master/drafting/main-atomic' + beside(AT)]) {
			await page.goto(at);
			await page.getByTestId('zoom-in').first().waitFor();
			const before = (await layerOf(page, 1)).layer;
			await page.evaluate(async () => {
				const b = document.querySelector<HTMLButtonElement>('[data-testid="pdf-page-1"]')?.closest('[data-pane]')?.querySelector<HTMLButtonElement>('[data-testid="zoom-in"]');
				for (let k = 0; k < 3; k++) {
					b?.click();
					await new Promise((r) => setTimeout(r, 40));
				}
			});
			// the draws the clicks set off have run out: page 1 holds a layer drawn after them, unchanged for a second of the slowed clock
			await drawn(page, 1, { every: 1000, after: before });
			await expect(page.getByText('Cannot use the same canvas')).toHaveCount(0);
			await expect(page.locator('[data-testid="pdf-page-1"] canvas').first()).toBeVisible();
		}
		await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
	});

	test('the same file as a work keeps one place, whichever way it is opened, and neither moves the other when both are open', async ({ page }) => {
		const first = { page: 2, share: 0.4 };
		await page.goto(BELLAMY);
		await readTo(page, first);
		await page.goto(AT);
		await staysAt(page, first);
		// a place the column can stand at in half a pane too, where the pages are drawn smaller and its end comes sooner
		const then = { page: 2, share: 0.1 };
		await readTo(page, then);
		await page.goto(BELLAMY);
		await staysAt(page, then);
		await page.goto(`${BELLAMY}?beside=${encodeURIComponent(AT)}`);
		await staysAt(page, then, { pane: 0 });
		await staysAt(page, then, { pane: 1 });
		const beside = { page: 1, share: 0.5 };
		await readTo(page, beside, 1);
		await staysAt(page, then, { pane: 0 });
		await page.waitForTimeout(400);
		await page.goto(BELLAMY);
		await staysAt(page, beside);
	});
});
