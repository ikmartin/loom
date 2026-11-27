// Pending changes under a running `loom serve` (plan 0.30.3): an edit made in a file since the reviewer's look and a suggested edit, both drawn in the document in Markup and in Final and listed in Review's Proposed edits; Keep and Discard doing the same from either place; an annotation on the words a kept edit replaces carried onto its new words; Keep resolving the annotation a suggestion answers; and Keep all and Discard all, for a document, for every change listed, and for one file's row in Review.
import { expect, test, type Served } from '../served';
import type { Page } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pane } from '../workspace';
import { openRow, shown as drawn } from '../review-rows';

const MAIN = 'drafting/main.tex';
const NODE = 'drafting/nodes/sy-0002.tex';
// the agent's suggestion on sy-0002: "the fixed points are those of" in place of "compare"
const SUGGESTED = 'e-2026-09-17-zwvx4m';
// the reader's own question on "one or two points" in sy-0002
const QUESTION = 'a-2026-09-16-bns3an';

type Row = { id: string; kind: string; path: string; documents: string[]; state: string; old: string; new: string; answers?: string | null };

/** The manifest as the publisher last built it. */
const built = (served: Served) => JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));
const pending = (served: Served): Row[] => built(served).changes ?? [];
const text = (served: Served, path = NODE) => readFileSync(join(served.root, path), 'utf8');

/** Edit sy-0002 in its file, "one or two points" becoming "at most two points", and wait for the change loom cuts from it; its id. */
async function editInPlace(served: Served): Promise<string> {
	writeFileSync(join(served.root, NODE), text(served).replace('one or two points', 'at most two points'));
	let id = '';
	await expect
		.poll(() => (id = pending(served).find((c) => c.kind === 'edit' && c.path === NODE)?.id ?? ''), { timeout: 60_000 })
		.not.toBe('');
	return id;
}

const words = (page: Page, id: string, side: 'old' | 'new') => pane(page, 0).locator(`.fragment span.change[data-change~="${id}"][data-side="${side}"]`);
const card = (page: Page, id: string) => page.locator(`[data-testid="change-card"][data-change="${id}"]`);

/** Keep or discard change `id` from the document, by its popup, or from Review, by its card; done once loom no longer lists it. */
async function act(page: Page, served: Served, where: 'document' | 'review', id: string, how: 'keep' | 'discard'): Promise<void> {
	if (where === 'document') {
		await page.goto('/master/drafting/main');
		await words(page, id, 'new').first().click();
		const p = page.getByTestId('change-popup');
		await expect(p).toHaveAttribute('data-change-id', id);
		await p.getByTestId(how === 'keep' ? 'change-keep' : 'change-discard').click();
		// shown done at once, before the publisher has answered
		await expect(words(page, id, how === 'keep' ? 'old' : 'new').first()).toBeHidden();
	} else {
		await page.goto('/review');
		await drawn(page, card(page, id));
		await card(page, id).getByTestId(how === 'keep' ? 'card-keep' : 'card-discard').click();
		await expect(card(page, id)).toHaveCount(0);
	}
	await expect.poll(() => pending(served).some((c) => c.id === id), { timeout: 60_000 }).toBe(false);
}

test('an edit in the file and a suggested edit are drawn in Markup and in Final, and listed in Review', async ({ page, served }) => {
	const edit = await editInPlace(served);
	await page.goto('/master/drafting/main');
	for (const id of [edit, SUGGESTED]) {
		await expect(words(page, id, 'old').first()).toBeVisible();
		await expect(words(page, id, 'new').first()).toBeVisible();
	}
	// the style is polled, and the words found again each time: a block redrawn by a manifest leaves the element found a moment ago detached, whose computed style reads empty
	await expect(words(page, edit, 'old').first()).toHaveCSS('text-decoration-line', 'line-through');
	await expect(words(page, edit, 'new').first()).toHaveCSS('text-decoration-line', 'underline');
	await expect(words(page, edit, 'new').first()).toContainText('at most');
	await pane(page, 0).getByTestId('changes-toggle').click();
	await page.getByTestId('changes-view-final').click();
	for (const id of [edit, SUGGESTED]) {
		await expect(words(page, id, 'old').first()).toBeHidden();
		await expect(words(page, id, 'new').first()).toBeVisible();
	}
	// nothing of the suggestion's old words is left in Final, the references among them neither
	const shown = await words(page, SUGGESTED, 'new')
		.first()
		.evaluate((s) => {
			const block = s.closest('p, pre') as HTMLElement;
			const seen = (el: Element) => (el as HTMLElement).offsetParent !== null;
			return { text: block.innerText, refs: [...block.querySelectorAll('a.ref')].filter(seen).map((a) => a.getAttribute('data-target')), old: [...block.querySelectorAll('span.change[data-side="old"]')].filter(seen).length };
		});
	expect(shown.text).not.toContain('compare');
	expect(shown.old).toBe(0);
	expect(shown.refs.filter((t) => t === 'sy-0001#eq:fix').length).toBeLessThanOrEqual(1);
	expect(shown.refs.filter((t) => t === 'sy-0001').length).toBeLessThanOrEqual(1);
	await page.goto('/review');
	await drawn(page, card(page, edit));
	await drawn(page, card(page, SUGGESTED));
	await expect(card(page, edit)).toContainText('Edit in the file');
	await expect(card(page, edit).getByTestId('change-words')).toContainText('at most');
	await expect(card(page, SUGGESTED)).toContainText('Suggestion');
	await expect(card(page, SUGGESTED)).toContainText('Say what the comparison shows.');
});

for (const where of ['document', 'review'] as const) {
	test(`from ${where === 'document' ? 'the document' : 'Review'}, Keep takes an edit into the look and Discard drops a suggestion, the file as it was`, async ({ page, served }) => {
		const edit = await editInPlace(served);
		await act(page, served, where, edit, 'keep');
		await act(page, served, where, SUGGESTED, 'discard');
		const now = text(served);
		expect(now).toContain('at most two points');
		expect(now).toContain('compare');
		expect(now).not.toContain('the fixed points are those of');
		expect(built(served).suggested_edits[SUGGESTED].status).toBe('discarded');
	});

	test(`from ${where === 'document' ? 'the document' : 'Review'}, Discard writes the old words back over an edit and Keep writes a suggestion in`, async ({ page, served }) => {
		const edit = await editInPlace(served);
		await act(page, served, where, edit, 'discard');
		await act(page, served, where, SUGGESTED, 'keep');
		const now = text(served);
		expect(now).toContain('one or two points');
		expect(now).not.toContain('at most two points');
		expect(now).toContain('the fixed points are those of');
		expect(built(served).suggested_edits[SUGGESTED].status).toBe('kept');
	});
}

test('a suggestion kept is undone from the toolbar: its words come out, the file is as it was byte for byte, and it waits again', async ({ page, served }) => {
	const before = text(served);
	await act(page, served, 'document', SUGGESTED, 'keep');
	expect(text(served)).toContain('the fixed points are those of');
	await expect(pane(page, 0).getByTestId('annotate-undo')).toHaveAttribute('title', 'Undo keep (⌘Z)');
	await pane(page, 0).getByTestId('annotate-undo').click();
	await expect.poll(() => text(served), { timeout: 60_000 }).toBe(before);
	await expect.poll(() => pending(served).some((c) => c.id === SUGGESTED), { timeout: 60_000 }).toBe(true);
	await expect(words(page, SUGGESTED, 'new').first()).toBeVisible({ timeout: 60_000 });
});

test('an annotation on the words a kept edit replaces is drawn again on its new words, and moves to them', async ({ page, served }) => {
	const edit = await editInPlace(served);
	// before Keep it stands on the words kept, and is drawn again on the new ones
	await page.goto('/master/drafting/main');
	await expect(words(page, edit, 'old').first()).toBeVisible();
	await expect(pane(page, 0).locator(`.fragment mark.annotation.moved[data-annotation~="${QUESTION}"]`)).not.toHaveCount(0);
	await act(page, served, 'document', edit, 'keep');
	await expect.poll(() => built(served).annotations[QUESTION]?.earlier?.quote ?? '', { timeout: 60_000 }).toContain('one or');
	await page.goto('/master/drafting/main');
	const mark = pane(page, 0).locator(`.fragment mark.annotation[data-annotation~="${QUESTION}"]`).first();
	await expect(mark).toContainText('at most');
	await mark.click();
	await expect(page.getByTestId('ann-popup').getByTestId('popup-earlier')).toContainText('one or');
});

test('Keep resolves the annotation a suggestion answers', async ({ page, served }) => {
	served.loom(['suggest', 'sy-0002', '--quote', 'Every orbit', '--with', 'Each orbit', '--answers', QUESTION, '--comment', 'One orbit at a time.', '--as', 'Referee Agent']);
	let id = '';
	await expect.poll(() => (id = pending(served).find((c) => c.answers === QUESTION)?.id ?? ''), { timeout: 60_000 }).not.toBe('');
	expect(built(served).annotations[QUESTION].status).toBe('open');
	await page.goto('/master/drafting/main');
	await words(page, id, 'new').first().click();
	await expect(page.getByTestId('change-popup').getByTestId('change-answers')).toContainText('Keep resolves it');
	await act(page, served, 'review', id, 'keep');
	await expect.poll(() => built(served).annotations[QUESTION].status, { timeout: 60_000 }).toBe('resolved');
	expect(text(served)).toContain('Each orbit');
});

test("a keep loom refuses is said in the viewer's words, by its code, and never in loom's", async ({ page, served }) => {
	const edit = await editInPlace(served);
	// loom's answer to a keep it refuses, as `change-keep` gives it; loom's own refusals are its suite's, and this is the viewer's wording of one
	const loomSays = 'drafting/nodes/sy-0002.tex changed at line 3 since the change was listed (sha 1a2b3c)';
	await page.route('**/_api/change-keep', (route) => route.fulfill({ json: { ok: true, result: '1 could not be', done: [], refused: [{ id: edit, why: loomSays, code: 'changed-since' }] } }));
	await page.goto('/review');
	await drawn(page, card(page, edit));
	await card(page, edit).getByTestId('card-keep').click();
	const said = page.getByTestId('column-message');
	await expect(said).toHaveText('One change was not kept: its words changed in the file since, so loom left them as they are.');
	await expect(said).not.toContainText(loomSays);
	expect(text(served)).toContain('at most two points');
});

test("Keep all keeps every ready change of a document from its Changes menu, and Discard all every one Review lists", async ({ page, served }) => {
	await editInPlace(served);
	await page.goto('/master/drafting/main');
	await pane(page, 0).getByTestId('changes-toggle').click();
	await page.getByTestId('changes-keep-all').click();
	await expect.poll(() => pending(served).filter((c) => c.documents.includes(MAIN) && c.state === 'ready').length, { timeout: 60_000 }).toBe(0);
	const now = text(served);
	expect(now).toContain('at most two points');
	expect(now).toContain('the fixed points are those of');
	// what is left, a file in no document's among it: discarded from Review, its words written back
	const intro = 'notes/intro.md';
	expect(pending(served).some((c) => c.path === intro)).toBe(true);
	const before = text(served, intro);
	await page.goto('/review');
	await page.getByTestId('group-discard-all').click();
	await expect.poll(() => pending(served).some((c) => c.path === intro), { timeout: 60_000 }).toBe(false);
	await expect(page.getByTestId('column-message')).toContainText(/^Discarded \d+ changes?\./);
	expect(text(served, intro)).not.toBe(before);
});

test("Keep all on a file's row in Review keeps exactly that file's edits made in place, and no other change", async ({ page, served }) => {
	writeFileSync(join(served.root, NODE), text(served).replace('one or two points', 'at most two points').replace('because', 'since'));
	const inNode = () => pending(served).filter((c) => c.kind === 'edit' && c.path === NODE);
	await expect.poll(() => inNode().length, { timeout: 60_000 }).toBe(2);
	const edits = inNode().map((c) => c.id);
	// the suggested edit in the same file and the edit in notes/intro.md are rows of their own
	const others = pending(served).filter((c) => !edits.includes(c.id));
	expect(others.map((c) => c.id)).toContain(SUGGESTED);
	expect(others.some((c) => c.path === 'notes/intro.md')).toBe(true);
	const sent: unknown[] = [];
	page.on('request', (r) => {
		if (r.url().endsWith('/_api/change-keep')) sent.push(r.postDataJSON());
	});
	await page.goto('/review');
	const row = page.locator(`[data-testid="review-row"][data-file="${NODE}"]`);
	await expect(row).toBeVisible({ timeout: 60_000 });
	await expect(row.locator('.meta')).toHaveText('2 edits since your look');
	await openRow(row);
	await expect(row.getByTestId('change-card')).toHaveCount(2);
	await row.getByTestId('file-keep-all').click();
	await expect.poll(() => inNode().length, { timeout: 60_000 }).toBe(0);
	expect(sent).toEqual([{ changes: expect.arrayContaining(edits) }]);
	expect((sent[0] as { changes: string[] }).changes).toHaveLength(2);
	// kept, the edits stay in the file and every other change still waits
	expect(text(served)).toContain('at most two points');
	const left = pending(served).map((c) => c.id);
	for (const c of others) expect(left).toContain(c.id);
	await expect(row).toHaveCount(0);
});
