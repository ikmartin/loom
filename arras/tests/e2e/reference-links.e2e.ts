// Every kind of link to a cited result, and where it lands (V7): the paper at the result's page wherever a copy is filed and the page is known, the digest node's own page where not. One test per kind of link; a click is read off the pane it opens, a hover off its card, and the two must name one place.
import { expect, test, type Locator, type Page } from '@playwright/test';
import { beside, pane } from '../workspace';
import { PDF5, REFEREE, saying, serve, servePapers } from '../manifest';

const RESULT = 'Kre99-thm-2.1';
/** Where every link to Theorem 2.1 goes: its locator says `p.~4`. */
const AT = `/library/Kre99?page=4&result=${RESULT}`;

/** Kre99 filed as a five-page paper whose sidecar carries Theorem 2.1's lines; `edit` changes the copy of the manifest further. */
async function filed(page: Page, edit: (m: any) => void = () => {}): Promise<void> {
	await serve(page, (m) => {
		m.references.Kre99.artifacts.pdf = true;
		m.references.Kre99.spans = { path: 'spans/arxiv/math_9810166v2.json', sha256: 'abc' };
		edit(m);
	});
	await servePapers(page, PDF5);
	await page.route('**/spans/**.json', (route) => route.fulfill({ json: { artifact: 'x', pages: {}, quads: { [RESULT]: [[72, 300, 540, 316]] } } }));
}

/** The page of the paper in view in `scope`: the one whose holder spans the middle of its column; 0 before one does. */
function shown(scope: Locator): Promise<number> {
	return scope
		.getByTestId('pdf-doc')
		.locator('.column')
		.first()
		.evaluate((c) => {
			const mid = c.getBoundingClientRect().top + c.clientHeight / 2;
			for (const h of c.querySelectorAll<HTMLElement>('[data-holder]')) {
				const r = h.getBoundingClientRect();
				if (r.top <= mid && r.bottom > mid) return Number(h.dataset.holder);
			}
			return 0;
		});
}

/** A pane shows the work's paper, at page `n`. */
async function onPage(page: Page, index: number, n: number): Promise<void> {
	await expect.poll(() => shown(pane(page, index))).toBe(n);
}

/** Hover a link and wait for its card to show page `n`, which it reaches by scrolling from the first, then let the card go. */
async function hovered(page: Page, link: Locator, n: number): Promise<void> {
	await link.hover();
	const card = page.getByTestId('link-preview');
	await expect(card.getByTestId('pdf-doc')).toBeVisible();
	await expect.poll(() => shown(card)).toBe(n);
	await page.mouse.move(0, 0);
	await expect(card).toHaveCount(0);
}

test.describe('a citation', () => {
	test('of a result opens its paper beside, at the page, as its hover shows it', async ({ page }) => {
		await filed(page);
		await page.goto('/node/sy-000A');
		const cite = pane(page, 0).locator(`span.cite[data-target="${RESULT}"] a`).first();
		await expect(cite).toHaveAttribute('href', AT);
		await hovered(page, cite, 4);
		await cite.click();
		await onPage(page, 1, 4);
	});

	test('lands on the page its anchor was read from, where the result is marked', async ({ page }) => {
		// a result read off the copy filed knows its page there; the locator's is the extraction's, and the two need not agree
		await filed(page, (m) => {
			m.references.Kre99.results = { [RESULT]: { state: 'verified', level: 3, class: 'anchored', page: 3, artifact: 'x', origin: [] } };
		});
		await page.goto('/node/sy-000A');
		const cite = pane(page, 0).locator(`span.cite[data-target="${RESULT}"] a`).first();
		await expect(cite).toHaveAttribute('href', `/library/Kre99?page=3&result=${RESULT}`);
		await cite.click();
		await onPage(page, 1, 3);
		await expect(pane(page, 1).getByTestId(`mark-${RESULT}`)).toBeInViewport();
	});

	test('opened at a page and left before a frame has followed the scroll, it is kept at that page for the next visit', async ({ page }) => {
		await filed(page);
		// the column's scroll never reaches the renderer's follower, which is what a page left within a frame of the scroll is: nothing but the opening itself has said where the paper stands
		await page.addInitScript(() => window.addEventListener('scroll', (e) => { if (e.target instanceof Element && e.target.classList.contains('column')) e.stopPropagation(); }, true));
		await page.goto('/node/' + RESULT);
		await pane(page, 0).locator('span.cite[data-postnote="Theorem 2.1, p.~4"] a').first().click();
		await onPage(page, 1, 4);
		await page.evaluate(() => window.dispatchEvent(new Event('pagehide')));
		const kept = await page.evaluate(() => Object.values(JSON.parse(localStorage.getItem('arras.places') ?? '{}')));
		expect(kept).toEqual([expect.objectContaining({ page: 4 })]);
	});

	test('with no result behind it opens the page its postnote names, or the work as a plain link opens it where it names none', async ({ page }) => {
		await filed(page);
		// `\cite[Lemma 9]{Kre99}` names no page and no result the digest holds, so it is a plain link to the work: at its front, for a work never read
		const lemma = () => pane(page, 0).locator('span.cite[data-postnote="Lemma 9"] a').first();
		await page.goto('/node/sy-0100');
		await expect(lemma()).toHaveAttribute('href', '/library/Kre99');
		await lemma().click();
		await onPage(page, 1, 1);
		// a digest result's own heading cites its work at the page, `[Kre99, Theorem 2.1, p. 4]`, and names no result
		await page.goto('/node/' + RESULT);
		const heading = pane(page, 0).locator('span.cite[data-postnote="Theorem 2.1, p.~4"] a').first();
		await expect(heading).toHaveAttribute('href', '/library/Kre99?page=4');
		await hovered(page, heading, 4);
		await heading.click();
		await onPage(page, 1, 4);
		// and the plain link then opens where that left the reader
		await page.goto('/node/sy-0100');
		await lemma().click();
		await onPage(page, 1, 4);
	});
});

/** The colour the viewer gives a problem, as the page computes it. */
function problemColour(page: Page): Promise<string> {
	return page.evaluate(() => {
		const probe = document.createElement('span');
		probe.style.color = 'var(--state-incomplete)';
		document.body.appendChild(probe);
		const colour = getComputedStyle(probe).color;
		probe.remove();
		return colour;
	});
}

test.describe("a citation of a result loom's reading of the paper lacks", () => {
	test('keeps its words, is underlined as a problem, says so on hover, and opens the paper on a click', async ({ page }) => {
		await filed(page);
		await page.goto('/node/sy-0100');
		// the publisher marks `\cite[Lemma 9]{Kre99}` alone: the citation beside it, of a result the digest holds, is not marked
		const cite = pane(page, 0).locator('span.cite[data-unmatched]');
		await expect(cite).toHaveCount(1);
		await expect(cite).toHaveAttribute('data-postnote', 'Lemma 9');
		await expect(cite).toHaveText('[2, Lemma 9]');
		await expect(pane(page, 0).locator(`span.cite[data-target="${RESULT}"]`).first()).not.toHaveAttribute('data-unmatched');
		const problem = await problemColour(page);
		const line = await cite.evaluate((c) => [getComputedStyle(c).borderBottomStyle, getComputedStyle(c).borderBottomColor]);
		expect(line).toEqual(['dotted', problem]);
		await cite.locator('a').hover();
		const said = page.getByTestId('cite-unmatched');
		await expect(said).toHaveText("loom's reading of this paper has no Lemma 9");
		expect(await said.evaluate((p) => getComputedStyle(p).color)).toBe(problem);
		// its own line, not the work's card: a postnote naming no page names no place to show
		await expect(page.getByTestId('link-preview').getByTestId('pdf-doc')).toHaveCount(0);
		await page.mouse.move(0, 0);
		await expect(said).toHaveCount(0);
		await expect(cite.locator('a')).toHaveAttribute('href', '/library/Kre99');
		await cite.locator('a').click();
		await onPage(page, 1, 1);
	});

	test('says so above the card where one also shows', async ({ page }) => {
		await filed(page);
		// the same citation naming a page as well, whose card shows that page
		await page.route('**/fragments/nodes/sy-0100.html', async (route) => {
			const res = await route.fetch();
			const body = (await res.text()).replace('data-postnote="Lemma 9"', 'data-postnote="Lemma 9, p.~3"').replace('data-unmatched="Lemma 9"', 'data-unmatched="Lemma 9, p. 3"');
			await route.fulfill({ response: res, body });
		});
		await page.goto('/node/sy-0100');
		const cite = pane(page, 0).locator('span.cite[data-unmatched] a');
		await cite.hover();
		const card = page.getByTestId('link-preview');
		await expect(card.getByTestId('cite-unmatched')).toHaveText("loom's reading of this paper has no Lemma 9, p. 3");
		await expect(card.getByTestId('pdf-doc')).toBeVisible();
		const [said, doc] = await Promise.all([card.getByTestId('cite-unmatched').boundingBox(), card.getByTestId('pdf-doc').boundingBox()]);
		expect(said!.y + said!.height).toBeLessThanOrEqual(doc!.y);
	});
});

test.describe('a link to a result', () => {
	test('in a `\\ref` goes where its citation goes', async ({ page }) => {
		await filed(page);
		await page.route('**/fragments/nodes/sy-0003.html', async (route) => {
			const res = await route.fetch();
			await route.fulfill({ response: res, body: (await res.text()) + `<p>As in <a class="ref" data-target="${RESULT}" data-tex="\\ref{${RESULT}}">Theorem 2.1</a>.</p>` });
		});
		await page.goto('/node/sy-0003');
		const ref = pane(page, 0).locator(`a.ref[data-target="${RESULT}"]`);
		await expect(ref).toHaveAttribute('href', AT);
		await ref.click();
		await onPage(page, 1, 4);
	});

	test("in a node's context and its local graph opens the paper at the page", async ({ page }) => {
		await filed(page);
		await page.goto('/context/sy-000A');
		const context = pane(page, 0).getByTestId('context');
		await expect(context.locator(`a[title="${RESULT}"]`).first()).toHaveAttribute('href', AT);
		await expect(context.getByTestId('local-graph').locator(`a[data-preview-key="${RESULT}"]`)).toHaveAttribute('href', AT);
		await context.locator(`a[title="${RESULT}"]`).first().click();
		await onPage(page, 1, 4);
	});

	test('in a message, by `quilt:` or `cited:`, opens the paper at the place it names', async ({ page }) => {
		await filed(page);
		await saying(page, `<p><a href="quilt:${RESULT}">a</a> <a href="cited:arxiv:math/9810166v2?page=2">b</a> <a href="cited:arxiv:math/9810166v2?result=${RESULT}">c</a></p>`);
		await page.goto('/master/drafting/main' + beside('/session/' + REFEREE));
		const links = pane(page, 1).getByTestId('message-1').locator('a');
		await links.nth(0).click();
		await onPage(page, 0, 4);
		// the work already open: a new place moves it there, and a result alone names its page
		await links.nth(1).click();
		await onPage(page, 0, 2);
		await links.nth(2).click();
		await onPage(page, 0, 4);
	});

	test('followed again after the reader scrolled away lands again', async ({ page }) => {
		await filed(page);
		await page.goto('/node/sy-000A');
		const cite = pane(page, 0).locator(`span.cite[data-target="${RESULT}"] a`).first();
		await cite.click();
		await onPage(page, 1, 4);
		await pane(page, 1).getByTestId('pdf-doc').locator('.column').first().evaluate((c) => c.scrollTo(0, 0));
		await expect.poll(() => shown(pane(page, 1))).toBe(1);
		await cite.click();
		await expect.poll(() => shown(pane(page, 1))).toBe(4);
	});

	test("with no paper to open at a page goes to the digest node's page", async ({ page }) => {
		// the digest read off another version than the bibliography cites: its pages are that version's
		await filed(page, (m) => (m.references.Kre99.version_mismatch = true));
		await page.goto('/context/sy-000A');
		await expect(pane(page, 0).getByTestId('context').locator(`a[title="${RESULT}"]`).first()).toHaveAttribute('href', `/node/${RESULT}`);
		await page.goto('/node/sy-000A');
		await expect(pane(page, 0).locator(`span.cite[data-target="${RESULT}"] a`).first()).toHaveAttribute('href', `/node/${RESULT}`);
	});
});
