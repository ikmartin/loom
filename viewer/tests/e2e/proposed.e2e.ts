// Review › Proposed Changes, read from the fixture: one card for each thing decided in a pass of its own, in order and counted; a copy or a pull opens in the page at its own address, reviewed in one pass (plan 0.25.2). A suggested edit is a pending change, kept or discarded in its document and in Your Changes (changes.e2e.ts, your-changes.e2e.ts); one on a copy is listed on the copy's card. The acts are stubbed: e2e-write drives them against a running publisher.
import { expect, test } from '@playwright/test';
import { manifest, serve } from '../manifest';

const COPY = '.loom/agents/copies/aidoc.tex';
// the fixture's two open suggested edits: one on sy-0002, the newer, and one on sy-0004 answering an annotation
const TEXT = 'e-2026-09-17-zwvx4m';
const ANSWERING = 'e-2026-09-16-r2hw0m';

const card = (page: import('@playwright/test').Page, id: string) => page.locator(`[data-testid="proposed-card"][data-id="${id}"]`);
const edit = (page: import('@playwright/test').Page, id: string) => page.locator(`[data-testid="suggestion"][data-id="${id}"]`);

test('everything to decide in a pass of its own is a card, counted, and a suggested edit is none', async ({ page }) => {
	await page.goto('/review/proposed');
	await expect(page.getByTestId('section-count-proposed')).toHaveText('1');
	await expect(page.getByTestId('proposed-summary')).toContainText('1 to decide');
	await expect(page.getByTestId('proposed-card')).toHaveCount(1);
	await expect(card(page, TEXT)).toHaveCount(0);
	await expect(page.getByTestId('proposed')).toContainText('A suggested edit is kept or discarded where it stands');
	for (const id of ['proposed-take', 'proposed-leave']) await expect(page.getByTestId(id)).toHaveCount(0);
});

test("a suggested edit on a copy is listed on the copy's card with its document, writer, typeset quote, what it says and the annotation it answers, and no act", async ({ page }) => {
	await serve(page, (m) => {
		m.nodes['sy-0002'].reached_by = [COPY];
		m.nodes['sy-0004'].reached_by = [COPY];
	});
	await page.goto('/review/proposed');
	const fold = card(page, COPY).getByTestId('proposed-on-copy');
	await fold.locator('summary').click();
	const text = edit(page, TEXT);
	await expect(text.getByTestId('suggestion-document')).toContainText("the agent's copy");
	await expect(text.getByTestId('suggestion-quote')).not.toContainText('\\ref');
	await expect(text.getByTestId('suggestion-writer')).toContainText('agent');
	await expect(text).toContainText('Say what the comparison shows.');
	await expect(text.getByTestId('suggestion-on-copy')).toBeVisible();
	await expect(text.getByTestId('edit-answers')).toHaveCount(0);
	const answering = edit(page, ANSWERING);
	await expect(answering.getByTestId('edit-answers')).toContainText('It answers Suggestion on');
	await expect(answering.getByTestId('edit-answers').locator('a')).toHaveAttribute('href', /note=a-2026-09-16-hwtkaw/);
	for (const id of ['proposed-take', 'proposed-leave', 'card-keep']) await expect(card(page, COPY).getByTestId(id)).toHaveCount(0);
});

test('a static host can still open a review, which only reads', async ({ page }) => {
	await page.goto('/review/proposed');
	await expect(card(page, COPY).getByTestId('proposed-open')).toBeVisible();
});

test("a copy's card says where it stands and opens its review at its own address, and comes back", async ({ page }) => {
	await page.goto('/review/proposed');
	const c = card(page, COPY);
	await expect(c.getByTestId('proposed-tally')).toContainText("that can't be taken");
	await expect(c.getByTestId('proposed-chips')).toContainText('Orbits');
	await c.getByTestId('proposed-open').click();
	await expect(page).toHaveURL(/\/review\/proposed\?copy=/);
	await expect(page.getByTestId('contribution-bar')).toContainText('From aidoc into main');
	await expect(page.getByTestId('proposed-summary')).toHaveCount(0);
	await page.getByTestId('proposed-back').click();
	await expect(page.getByTestId('proposed-summary')).toBeVisible();
	// a copy no longer waiting leaves the list
	await page.goto('/review/proposed?copy=.loom%2Fcopies%2Fgone.tex');
	await expect(page.getByTestId('proposed-summary')).toBeVisible();
});

test("suggested edits on a copy are folded on its card and not counted, since they come in with it", async ({ page }) => {
	await serve(page, (m) => {
		m.nodes['sy-0002'].reached_by = [COPY];
	});
	await page.goto('/review/proposed');
	await expect(card(page, TEXT)).toHaveCount(0);
	await expect(page.getByTestId('section-count-proposed')).toHaveText('1');
	const fold = card(page, COPY).getByTestId('proposed-on-copy');
	await expect(fold).toContainText('1 suggested edit on it');
	await fold.locator('summary').click();
	await expect(fold.getByTestId('suggestion-on-copy')).toBeVisible();
});

test('an agent copy is reviewed under a pinned bar, each change named, a clash said, and nothing to press without a publisher', async ({ page }) => {
	await page.goto('/review/proposed?copy=' + encodeURIComponent(COPY));
	const bar = page.getByTestId('contribution-bar');
	await expect(bar).toHaveCSS('position', 'sticky');
	await expect(bar).toContainText('From aidoc into main');
	await expect(bar).toContainText("1 can't be taken");
	// no rail: the change takes the page's width, and the counter opens the list
	await expect(page.getByTestId('change-row')).toHaveCount(0);
	const at = page.getByTestId('change-at');
	await expect(at).toHaveText(/^1 of \d+$/);
	await at.click();
	const rows = page.getByTestId('change-row');
	// names, not keys
	await expect(rows.filter({ hasText: 'Orbits' })).toHaveCount(1);
	await expect(rows.filter({ hasText: /^sy-0002/ })).toHaveCount(0);
	const widget = page.locator('[data-testid="change-row"][data-key="sy-0001"]');
	await expect(widget).toHaveAttribute('data-state', 'clash');
	await expect(widget).toContainText("can't be taken");
	// the filter narrows the list
	await page.getByTestId('change-filter').fill('orbit');
	await expect(rows).toHaveCount(2);
	await page.getByTestId('change-filter').fill('');
	// picking one shows it and closes the list; stepping moves through the rest, the bar staying put
	await rows.filter({ hasText: 'Orbits' }).click();
	await expect(rows).toHaveCount(0);
	await expect(at).toHaveText(/^2 of /);
	await page.getByTestId('next-change').click();
	await expect(at).toHaveText(/^3 of /);
	// a static host serves no writes
	for (const id of ['take-it', 'leave-it', 'take-all', 'apply', 'accept-checked']) await expect(page.getByTestId(id)).toHaveCount(0);
});

test('a change both sides edited whose lines fall apart is offered merged, and says so', async ({ page }) => {
	await serve(page, (m) => {
		const c = m.contributions.find((x: { kind: string }) => x.kind === 'adopt');
		const orbits = c.changes.find((x: { key: string }) => x.key === 'sy-0002');
		orbits.class = 'merged';
		orbits.merged = orbits.proposed;
	});
	await page.goto('/review/proposed?copy=' + encodeURIComponent(COPY));
	await page.getByTestId('change-at').click();
	const row = page.locator('[data-testid="change-row"][data-key="sy-0002"]');
	await expect(row).toContainText('merged');
	await row.click();
	await expect(page.getByTestId('merged-note')).toContainText('You both changed it');
});

test("a refusal to prepare the changes is said in the viewer's words, never loom's message, which names a command", async ({ page }) => {
	await serve(page, (m) => {
		const c = m.contributions.find((x: { kind: string }) => x.kind === 'adopt');
		c.choices = { ...c.choices, keys: ['sy-0002'] };
	});
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: ['adopt-decision', 'adopt-preview', 'adopt-finish'], token: 't' } }));
	await page.route('**/_api/adopt-preview', (route) => route.fulfill({ status: 409, json: { error: { code: 'adoption-refused', message: 'sy-0002 is a new result, and placing it changes the document; run `loom adopt aidoc.tex --document-changes`, with the keys you chose' } } }));
	await page.goto('/review/proposed?copy=' + encodeURIComponent(COPY));
	await page.getByTestId('apply').click();
	const bar = page.getByTestId('contribution-bar');
	await expect(bar).toContainText('Loom could not prepare these changes');
	await expect(bar).not.toContainText('loom adopt');
	await expect(bar).not.toContainText('sy-0002');
});

test('what taking a copy in did is said even when the copy leaves the manifest before the answer arrives', async ({ page }) => {
	let gone = false;
	let answer = () => {};
	const held = new Promise<void>((resolve) => (answer = resolve));
	await page.route('**/build/manifest.json', async (route) => {
		const m = structuredClone(manifest);
		const c = m.contributions.find((x: { kind: string }) => x.kind === 'adopt');
		c.choices = { ...c.choices, keys: ['sy-0002'] };
		if (gone) m.contributions = m.contributions.filter((x: { kind: string }) => x.kind !== 'adopt');
		await route.fulfill({ json: m });
	});
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: ['adopt-decision', 'adopt-preview', 'adopt-finish'], token: 't' } }));
	await page.route('**/_api/adopt-preview', (route) => route.fulfill({ json: { ok: true, result: { token: 'p', review: { token: 'r', items: [] } } } }));
	await page.route('**/_api/adopt-finish', async (route) => {
		// the publisher has written the file and republished; its answer is still on its way
		gone = true;
		await held;
		await route.fulfill({ json: { ok: true, result: { accepted: [], pending: ['sy-0002'] } } });
	});
	await page.goto('/review/proposed?copy=' + encodeURIComponent(COPY));
	await page.getByTestId('apply').click();
	// the copy taken in leaves nothing to decide
	await expect(page.getByTestId('proposed-none')).toBeVisible();
	answer();
	await expect(page.getByTestId('proposed-answer')).toContainText('Took 1 change into main: 0 accepted, 1 wait to be accepted.');
});
