// Links: one form for what the quilt owns, `quilt:`, beside `cited:` for a work by its identifier, and one rule for where every link in the viewer opens: revealed where it is already open, otherwise a new tab in the pane the reader is not in. An empty link is named by the viewer, and resting on a link previews what it names. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';
import { beside, pane } from '../workspace';
import { REFEREE, saying, serve } from '../manifest';

/** The block at the top of a pane's body, by its `data-src`, and how far below the top it stands. */
function topBlock(el: Element): { src: string; below: number } {
	const r = el.getBoundingClientRect();
	const block = [...el.querySelectorAll<HTMLElement>('[data-src]')].filter((b) => !b.querySelector('[data-src]')).find((b) => b.getBoundingClientRect().bottom > r.top + 48);
	return { src: block?.dataset.src ?? '', below: block ? block.getBoundingClientRect().top - r.top : 0 };
}

test.describe('naming', () => {
	test('an empty link reads as the viewer names the thing; a titled one as written', async ({ page }) => {
		await saying(page, '<p><a href="quilt:sy-0003"></a>, <a href="quilt:sy-0003">the parity theorem</a>, <a href="quilt:a-2026-09-16-ecnav2"></a> and <a href="quilt:drafting/main.tex"></a>.</p>');
		await page.goto('/session/' + REFEREE);
		const links = page.getByTestId('message-1').locator('a');
		await expect(links.nth(0)).toHaveText('Theorem 2.1');
		await expect(links.nth(1)).toHaveText('the parity theorem');
		await expect(links.nth(2)).toHaveText('Revision on Theorem 2.1');
		await expect(links.nth(3)).toHaveText('main.tex');
	});
});

test.describe('the one rule', () => {
	test('what is open is revealed where it is, its place marked, and no tab is added', async ({ page }) => {
		await saying(page, '<p>See <a href="quilt:drafting/main.tex#sy-0003"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		await expect(pane(page, 0)).toHaveClass(/focused/);
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(1);
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toHaveClass(/travelled/);
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toBeInViewport();
	});

	test('what is not open opens as a new tab in the other pane, and the Chat stays', async ({ page }) => {
		// sy-999D is in the talk only, so the open main.tex does not hold it
		await saying(page, '<p>See <a href="quilt:sy-999D"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(2);
		await expect(pane(page, 0).getByRole('tab', { selected: true })).toContainText('sy-999D');
		await expect(pane(page, 1).getByTestId('chat')).toBeVisible();
	});

	test('a node an open document holds is revealed in the document, not opened beside it (DR-280-ikmartin)', async ({ page }) => {
		await saying(page, '<p>See <a href="quilt:sy-0003"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(1);
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toHaveClass(/travelled/);
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toBeInViewport();
		await expect(pane(page, 1).getByTestId('chat')).toBeVisible();
	});

	test('behind another tab, the document is brought forward to the node', async ({ page }) => {
		await saying(page, '<p>See <a href="quilt:sy-0003"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
		// put main.tex behind the talk, opened from the side panel into the reader's pane
		await pane(page, 0).getByRole('tab').first().click();
		await page.getByTestId('docs-tree').getByRole('link', { name: 'talk.tex' }).click();
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(2);
		await expect(pane(page, 0).getByRole('tab', { selected: true })).toContainText('talk.tex');
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		await expect(pane(page, 0).getByRole('tab', { selected: true })).toContainText('main.tex');
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toBeInViewport();
	});

	test("a document's link to its own content takes the same path: it scrolls there and marks it", async ({ page }) => {
		await page.goto('/master/drafting/main');
		const ref = pane(page, 0).locator('.fragment a.ref[href^="#"]').first();
		await expect(ref).toBeVisible();
		const id = decodeURIComponent((await ref.getAttribute('href'))!.slice(1));
		await ref.click();
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(1);
		await expect(pane(page, 0).locator(`[id="${id}"]`)).toHaveClass(/travelled/);
		await expect(pane(page, 0).locator(`[id="${id}"]`)).toBeInViewport();
	});

	test('loom open lands on what its link names, with the words it quotes lit there', async ({ page }) => {
		await page.goto('/open?link=' + encodeURIComponent('quilt:drafting/main.tex#sy-0003&quote=finite%20widget'));
		await expect.poll(() => new URL(page.url()).pathname).toMatch(/\/master\/drafting\/main$/);
		expect(new URL(page.url()).searchParams.get('quote')).toBe('finite widget');
		await expect.poll(() => page.evaluate(() => (CSS as unknown as { highlights?: Map<string, { size: number }> }).highlights?.get('loom-quote')?.size ?? 0)).toBe(1);
		await expect.poll(() => page.evaluate(() => String((CSS as unknown as { highlights: Map<string, Set<Range>> }).highlights.get('loom-quote')!.values().next().value))).toBe('finite widget');
	});

	test('loom open on a link naming nothing here says so', async ({ page }) => {
		await page.goto('/open?link=' + encodeURIComponent('https://example.org/x'));
		await expect(page.getByTestId('open-nothing')).toContainText('names nothing in this quilt');
		await page.goto('/open');
		await expect(page.getByTestId('open-nothing')).toContainText('No link was given');
	});

	test('a link to an annotation opens what it is on, with its popup open', async ({ page }) => {
		await saying(page, '<p>My <a href="quilt:a-2026-09-16-ecnav2"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		const box = pane(page, 0).getByTestId('ann-popup');
		await expect(box).toBeVisible();
		await expect(box).toHaveAttribute('data-annotation-id', 'a-2026-09-16-ecnav2');
		await expect.poll(() => new URL(page.url()).searchParams.get('note')).toBe('a-2026-09-16-ecnav2');
	});

	test("a bare id in an annotation reads as the result it names, and follows like any link", async ({ page }) => {
		// an agent writes `sy-0002(a)` in prose as often as it writes a link; an id the quilt does not know is left as written
		await serve(page, (m) => {
			m.annotations['a-2026-09-16-ecnav2'].body_html = '<p>This invokes sy-0002(a), not sy-9999.</p>';
		});
		await saying(page, '<p>My <a href="quilt:a-2026-09-16-ecnav2"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		const body = pane(page, 0).getByTestId('ann-popup').locator('.body').first();
		await expect(body).toContainText('This invokes Lemma 1.2(a), not sy-9999.');
		await expect(body.locator('a[href="quilt:sy-0002"]')).toHaveAttribute('title', 'sy-0002');
	});

	test('reading is where it was left after a visit to Review: the same tabs, the same place, a closed popup still closed', async ({ page }) => {
		await saying(page, '<p>My <a href="quilt:a-2026-09-16-ecnav2"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		// a link opens the document at an annotation; the reader closes it and reads on
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		const box = pane(page, 0).getByTestId('ann-popup');
		await expect(box).toBeVisible();
		await pane(page, 0).locator('.fragment').first().press('Escape');
		await expect(box).toHaveCount(0);
		const body = pane(page, 0).locator('> .body');
		await body.evaluate((el) => el.scrollTo(0, el.scrollHeight / 2));
		await page.waitForTimeout(300);
		const at = await body.evaluate((el) => el.scrollTop);
		expect(at).toBeGreaterThan(100);
		// the text at the pane's top, and where: blocks skipped while off screen are laid out at their real size as they come back, so the scroll offset itself may move while the text stays
		const place = await body.evaluate(topBlock);
		const tabs = async () => [0, 1].map(async (i) => (await pane(page, i).getByTestId('item-tab').allInnerTexts()).join('|'));
		const before = await Promise.all(await tabs());

		await page.getByTestId('primary-review').click();
		await expect(page).toHaveURL(/\/review/);
		await page.getByTestId('primary-docs').click();

		await expect(pane(page, 0).locator('.fragment mjx-container').first()).toBeAttached();
		expect(await Promise.all(await tabs())).toEqual(before);
		// the place is kept as the block at the pane's top, so it comes back to within a few pixels rather than to the pixel
		await expect.poll(async () => { const now = await body.evaluate(topBlock); return now.src === place.src && Math.abs(now.below - place.below) < 12; }).toBe(true);
		await page.waitForTimeout(500);
		await expect(box).toHaveCount(0);
	});

	test('the place a link went is gone to once: a new manifest leaves the reader where they are', async ({ page }) => {
		// `loom serve` publishes a new manifest whenever anything changes, an agent's annotation or a compile, and each one mounted the document again and went back to the link's annotation, box open
		let revision = 0;
		let served = 0;
		await serve(page, (m) => {
			served += 1;
			m.sessions[0].title = `A sitting, revision ${revision}`;
		});
		await saying(page, '<p>My <a href="quilt:a-2026-09-16-ecnav2"></a>.</p>');
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		await pane(page, 1).getByTestId('message-1').locator('a').click();
		const box = pane(page, 0).getByTestId('ann-popup');
		await expect(box).toBeVisible();
		// the reader closes it and reads on, well away from it
		await pane(page, 0).locator('.fragment').first().press('Escape');
		await expect(box).toHaveCount(0);
		const body = pane(page, 0).locator('> .body');
		await body.evaluate((el) => el.scrollTo(0, el.scrollHeight));
		const at = await body.evaluate((el) => el.scrollTop);
		// and the quilt changes under them
		revision = 1;
		const before = served;
		await expect.poll(() => served).toBeGreaterThan(before + 1);
		await expect(pane(page, 0).locator('.fragment').first()).toBeAttached();
		await page.waitForTimeout(500);
		await expect(box).toHaveCount(0);
		expect(Math.abs((await body.evaluate((el) => el.scrollTop)) - at)).toBeLessThan(4);
	});

	test("a context's link follows the one rule: a new tab in the other pane, the node it came from kept behind it", async ({ page }) => {
		// sy-0005's context links sy-0002, which the pane holding sy-0005 does not show
		await page.goto('/node/sy-0005' + beside('/context/sy-0005'));
		const link = pane(page, 1).getByTestId('context').locator('a[href*="/node/sy-0002"]').first();
		await link.click();
		// the context stays where it was; the other pane gains a tab, and the node the context is about is still there
		await expect(pane(page, 1).getByTestId('context')).toBeVisible();
		await expect(pane(page, 0).getByTestId('item-tab')).toHaveCount(2);
		await expect(pane(page, 0)).toHaveClass(/focused/);
		await expect.poll(() => new URL(page.url()).pathname).toBe('/node/sy-0002');
	});
});

test.describe('works', () => {
	test('a citation is the text the document prints, linking nowhere and previewing nothing', async ({ page }) => {
		await page.clock.install();
		await page.goto('/master/drafting/main');
		await page.waitForSelector('.fragment mjx-container'); // typesetting reflows the text, which would move the citation out from under the pointer
		const cite = page.locator('.fragment span.cite[data-citekey="Har77"]').first();
		await expect(cite).toBeVisible();
		await expect(cite.locator('a')).toHaveCount(0);
		await cite.hover();
		await page.clock.runFor(500);
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
	});

	test('a cited: link opens its identifier at its own service, in a tab of its own, and the viewer stays where it was', async ({ page, context }) => {
		await context.route('https://arxiv.org/**', (route) => route.fulfill({ body: 'the paper', contentType: 'text/plain' }));
		await saying(page, '<p>See <a href="cited:arxiv:math/9810166v2?page=4">Kresch, Theorem 2.1</a>.</p>');
		await page.goto('/session/' + REFEREE);
		const [tab] = await Promise.all([context.waitForEvent('page'), page.getByTestId('message-1').getByRole('link', { name: 'Kresch, Theorem 2.1' }).click()]);
		await expect.poll(() => tab.url()).toBe('https://arxiv.org/pdf/math/9810166v2#page=4');
		expect(new URL(page.url()).pathname).toBe('/session/' + REFEREE);
	});
});

test.describe('previews', () => {
	test('a quilt: link previews what it names, and a link to an annotation previews what it is on', async ({ page }) => {
		await saying(page, '<p><a href="quilt:sy-0003"></a> and <a href="quilt:a-2026-09-16-ecnav2"></a>.</p>');
		await page.goto('/session/' + REFEREE);
		const links = page.getByTestId('message-1').locator('a');
		await links.nth(0).hover();
		await expect(page.getByTestId('link-preview')).toBeVisible();
		await expect(page.getByTestId('link-preview')).toContainText('widget');
		await page.mouse.move(0, 0);
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
		await links.nth(1).hover();
		await expect(page.getByTestId('link-preview')).toBeVisible();
		await expect(page.getByTestId('link-preview').locator('.env[data-id="sy-0003"]').first()).toBeVisible();
	});

	test('resting on a link to a node shows its statement, and Escape dismisses it', async ({ page }) => {
		await page.goto('/node/sy-0003' + beside('/context/sy-0003'));
		const link = page.getByTestId('context').getByRole('link', { name: /^Definition/ }).first();
		await link.hover();
		const card = page.getByTestId('link-preview');
		await expect(card).toBeVisible();
		await expect(card.locator('.fragment mjx-container').first()).toBeVisible();
		// the card names the result as a reader does, with no internal id while Show ids is off
		await expect(card).not.toContainText('sy-000');
		await page.keyboard.press('Escape');
		await expect(card).toHaveCount(0);
	});

	test('a quick pass over a link shows nothing', async ({ page }) => {
		// the card's delay runs on the page's clock, so the test moves that clock past it rather than sleeping
		await page.clock.install();
		await page.goto('/node/sy-0003' + beside('/context/sy-0003'));
		const link = page.getByTestId('context').locator('a[href^="/node/sy-"]').first();
		await link.hover();
		await page.mouse.move(900, 600);
		await page.clock.runFor(500);
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
		// and the same link rested on does show one, so the absence above is the pass being quick
		await link.hover();
		await page.clock.runFor(500);
		await expect(page.getByTestId('link-preview')).toBeVisible();
	});

	test('a link to a kind with no preview opens no card', async ({ page }) => {
		// a document, a context or a session has no small render: nothing is made up in its place (V3)
		// the card's delay runs on the page's clock, which the test moves past it rather than sleeping
		await page.clock.install();
		await page.goto('/node/sy-0003' + beside('/context/sy-0003'));
		// a node link in the same context does preview, so the absence below is the kind's and not the card's
		await page.getByTestId('context').getByRole('link', { name: /^Definition/ }).first().hover();
		await page.clock.runFor(600);
		await expect(page.getByTestId('link-preview')).toBeVisible();
		await page.keyboard.press('Escape');
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
		const doc = page.getByTestId('context').getByRole('link', { name: 'main.tex' }).first();
		await doc.hover();
		await page.clock.runFor(600);
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
	});

	test("a link to a document at a result previews the result, in a transcript and in a Markdown file, and `open here` opens the document there", async ({ page }) => {
		// the second is an agent's copy at one of its own results, as an agent writes it
		await saying(page, '<p><a href="quilt:drafting/main.tex#sy-0003">the parity theorem</a> and <a href="quilt:.loom/agents/copies/aidoc.tex#sy-0001-ai">the copy’s widget</a>.</p>');
		await page.goto('/session/' + REFEREE);
		const links = page.getByTestId('message-1').locator('a');
		const card = page.getByTestId('link-preview');
		await links.nth(1).hover();
		await expect(card.locator('.env[data-id="sy-0001-ai"]').first()).toBeVisible();
		await expect(card.locator('.fragment mjx-container').first()).toBeVisible();
		await page.keyboard.press('Escape');
		await expect(card).toHaveCount(0);
		// the card a `quilt:sy-0003` link shows
		await links.nth(0).hover();
		await expect(card.locator('.env[data-id="sy-0003"]').first()).toBeVisible();
		await expect(card).toContainText('sy-0003');
		// a click opens the document at the place, beside; `open here` opens the same in the link's own pane
		await card.getByTestId('preview-open-here').click();
		await expect(pane(page, 0).getByTestId('item-tab').filter({ hasText: 'main.tex' })).toHaveCount(1);
		await expect(pane(page, 0).locator('[id="sy-0003"]')).toBeInViewport();

		await page.route(/\/files\/notes\/intro\.md\.html/, async (route) => {
			const res = await route.fetch();
			await route.fulfill({ response: res, body: (await res.text()) + '<p>Its theorem is <a href="quilt:drafting/main.tex#sy-0003">the parity theorem</a>.</p>' });
		});
		await page.goto('/file/notes/intro.md');
		const link = pane(page, 0).getByTestId('file-item').getByRole('link', { name: 'the parity theorem' });
		await link.hover();
		await expect(card.locator('.env[data-id="sy-0003"]').first()).toBeVisible();
	});

	test('a link to a document alone previews nothing', async ({ page }) => {
		// the card's delay runs on the page's clock, so the absence is asserted after moving that clock past it
		await page.clock.install();
		await page.goto('/file/notes/intro.md');
		const body = pane(page, 0).getByTestId('file-item');
		await body.getByRole('link', { name: 'the paper' }).hover();
		await page.clock.runFor(600);
		await expect(page.getByTestId('link-preview')).toHaveCount(0);
		// a link to a result in the same file does preview, so the absence above is the document's
		await body.locator('a[href="quilt:sy-0002"]').hover();
		await page.clock.runFor(600);
		await expect(page.getByTestId('link-preview')).toBeVisible();
	});

	test('a reference to an equation previews the display, numbered as the page numbers it, and says what it stands in', async ({ page }) => {
		await page.goto('/master/drafting/main');
		await page.waitForSelector('.fragment mjx-container'); // typesetting reflows the text, which would move the link out from under the pointer
		const card = page.getByTestId('link-preview');
		const display = card.getByTestId('preview-display');
		// an equation in a section's prose: the section's card would be its heading and a count
		await pane(page, 0).locator('a.ref[data-target="sy-0100#eq:prose"]').first().hover();
		await expect(display.locator('.math.display')).toHaveCount(1);
		await expect(display.locator('.math.display')).toHaveAttribute('id', 'sy-0100-eq-prose');
		// typeset with its tag, the number the page shows
		await expect(display.locator('mjx-container [data-mml-node="mlabeledtr"]')).toHaveCount(1);
		await expect(card).toContainText('(1)');
		await expect(card).toContainText('in Section 1');
		await expect(card).toContainText('sy-0100#eq:prose');
		await expect(card).not.toContainText('in this section');
		await page.keyboard.press('Escape');
		await expect(card).toHaveCount(0);
		// an equation in a proof is in the proof of its result
		await pane(page, 0).locator('a.ref[data-target="sy-0002/proof#eq:step"]').first().hover();
		await expect(display.locator('.math.display')).toHaveAttribute('id', 'sy-0002-proof-eq-step');
		await expect(card).toContainText('(3)');
		await expect(card).toContainText('in proof of Lemma 1.2');
	});

	test("a reference to an equation its node's fragment does not hold previews the node, as before", async ({ page }) => {
		await page.route('**/fragments/nodes/sy-0100.html', async (route) => {
			const res = await route.fetch();
			await route.fulfill({ response: res, body: (await res.text()).replace(/<div class="math display"[^>]*id="sy-0100-eq-prose"[^>]*>.*?<\/div>/s, '') });
		});
		await page.goto('/master/drafting/main');
		await page.waitForSelector('.fragment mjx-container');
		await pane(page, 0).locator('a.ref[data-target="sy-0100#eq:prose"]').first().hover();
		const card = page.getByTestId('link-preview');
		await expect(card).toContainText('1 entry in this section');
		await expect(card.getByTestId('preview-display')).toHaveCount(0);
	});
});
