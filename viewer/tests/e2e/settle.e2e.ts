// "Settle as it stands" on the notice of a write loom could neither finish nor undo (`loom:write-left`), against a publisher stood in by routes: offered only where both settling endpoints are served, a preview asked first and drawn in the viewer's words, the act only on the person's confirmation, and what is said after the viewer's own. Each test is named for the rule it holds.
import { expect, test, type Page } from '@playwright/test';
import { serve } from '../manifest';

const ID = 'w-2026-11-25-abc123';
const FILE = 'drafting/nodes/sy-0002.tex';

/** The notice as loom emits it: the person's, its id in its fix's `act` alone. */
const left = {
	severity: 'warning',
	code: 'loom:write-left',
	class: 'latex',
	owner: 'person',
	message: `The journal records a Keep on ${FILE} that loom could neither finish nor undo: it changed since. It goes once each file reads as before the act or as the act left it.`,
	locations: [{ file: FILE, line: 1 }],
	keys: [],
	fixes: [{ label: 'settle it as it stands', command: `loom doctor --settle ${ID}`, act: { endpoint: 'write-settle', body: { act: ID } } }]
};

/** What loom answers, its own sentences among it, which the page must never show. */
const preview = {
	ok: true,
	act: ID,
	kind: 'a Keep',
	said: ['LOOM-SAID: Settling a Keep as it stands writes none of your files.'],
	files: [FILE],
	edits: [
		{ id: 'e-2026-09-17-zwvx4m', words: 'Referee Agent\'s suggestion “the fixed points are those of” for “compare”', outcome: 'kept', why: 'its words stand where it was written' },
		{ id: 'e-2026-09-18-aaaaaa', words: 'Referee Agent\'s suggestion to add “Hence”', outcome: 'closed', why: 'neither its words nor the ones they replace stand where it was written' }
	],
	history: 'removed'
};

/** Stand in for a publisher serving `capabilities`, answering the preview and the settling as given; the bodies settling was sent. */
async function publisher(page: Page, capabilities: string[], answers: { preview?: [number, object]; settle?: [number, object] } = {}): Promise<Record<string, unknown>[]> {
	const sent: Record<string, unknown>[] = [];
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities, token: 't' } }));
	await page.route('**/_api/write-settle-preview', async (route) => {
		const [status, json] = answers.preview ?? [200, preview];
		await route.fulfill({ status, json });
	});
	await page.route('**/_api/write-settle', async (route) => {
		sent.push(route.request().postDataJSON());
		const [status, json] = answers.settle ?? [200, { ...preview, said: preview.said, result: 'LOOM-RESULT: settled a Keep as it stands' }];
		await route.fulfill({ status, json });
	});
	return sent;
}

const notice = (page: Page) => page.locator('[data-testid="problems-yours"] [data-testid="problem-group"][data-codes="loom:write-left"]');

test('where no publisher serves settling, the notice is shown with no control', async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	await page.goto('/review/problems');
	await expect(notice(page).getByTestId('problem')).toHaveCount(1);
	await expect(page.getByTestId('settle-open')).toHaveCount(0);
	await expect(page.getByTestId('fix-act')).toHaveCount(0);
});

test('where the publisher serves the act but not its preview, nothing is offered', async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	await publisher(page, ['write-settle']);
	await page.goto('/review/problems');
	await expect(notice(page).getByTestId('problem')).toHaveCount(1);
	await expect(page.getByTestId('settle-open')).toHaveCount(0);
	await expect(page.getByTestId('fix-act')).toHaveCount(0);
});

test("the control asks for the preview first and draws every file and every decision in the viewer's words, with no id, digest or command", async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	const sent = await publisher(page, ['write-settle-preview', 'write-settle']);
	await page.goto('/review/problems');
	const open = notice(page).getByTestId('settle-open');
	await expect(open).toHaveText('Settle as it stands');
	// a control a person can hit: the page's ordinary button, not a small one
	const box = (await open.boundingBox())!;
	expect(box.height).toBeGreaterThanOrEqual(28);
	expect(await open.evaluate((b) => parseFloat(getComputedStyle(b).fontSize))).toBeGreaterThanOrEqual(13);
	await open.click();
	const p = notice(page).getByTestId('settle-preview');
	await expect(p.getByTestId('settle-lead')).toHaveText('Settling a Keep as it stands writes none of your files.');
	await expect(p).toContainText('This file stays exactly as it is now:');
	await expect(p.getByTestId('settle-files').locator('li')).toHaveText([FILE]);
	await expect(p).toContainText('These suggested edits are recorded as your files show them:');
	await expect(p.getByTestId('settle-edits').locator('li')).toHaveText([
		'Referee Agent\'s suggestion “the fixed points are those of” for “compare”: kept, since its words stand where it was written.',
		'Referee Agent\'s suggestion to add “Hence”: closed, as no longer applying, since neither its words nor the ones they replace stand where it was written.'
	]);
	await expect(p.getByTestId('settle-history')).toHaveText('The version loom began of your files just before this write was never recorded, so it is not kept in your history.');
	// nothing of loom's own: no id, no command, not its sentences
	const main = page.locator('main');
	for (const never of [ID, 'e-2026-09-17', 'loom doctor', '--settle', 'sha256', 'LOOM-SAID']) await expect(main).not.toContainText(never);
	// nothing is settled by looking
	expect(sent).toEqual([]);
	await expect(p.getByTestId('settle-confirm')).toBeFocused();
	// Cancel closes it with nothing done
	await p.getByTestId('settle-cancel').click();
	await expect(notice(page).getByTestId('settle-preview')).toHaveCount(0);
	expect(sent).toEqual([]);
});

test("the person's confirmation settles it, sending the id from the fix, and the outcome is said in the viewer's words, never loom's", async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	const sent = await publisher(page, ['write-settle-preview', 'write-settle']);
	await page.goto('/review/problems');
	await notice(page).getByTestId('settle-open').click();
	await notice(page).getByTestId('settle-confirm').click();
	await expect(page.getByTestId('settle-said')).toHaveText('Settled as it stands: none of your files was written. Suggested edits: 1 kept, 1 closed. The version it began is not kept.');
	expect(sent).toEqual([{ act: ID }]);
	await expect(page.locator('main')).not.toContainText('LOOM-RESULT');
	await expect(page.getByTestId('settle-preview')).toHaveCount(0);
});

test("a refusal is said in the viewer's words by its code, and the control stays to try again", async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	await publisher(page, ['write-settle-preview', 'write-settle'], { settle: [409, { ok: false, error: { code: 'changed', message: `LOOM-REFUSAL: ${FILE} changed while act ${ID} was settled` } }] });
	await page.goto('/review/problems');
	await notice(page).getByTestId('settle-open').click();
	await notice(page).getByTestId('settle-confirm').click();
	await expect(notice(page).getByTestId('settle-refused')).toHaveText('A file changed while it was being settled, so nothing was done. Look at what settling does now, and settle it again.');
	await expect(page.locator('main')).not.toContainText('LOOM-REFUSAL');
	await expect(notice(page).getByTestId('settle-open')).toBeEnabled();
	await expect(page.getByTestId('settle-said')).toHaveCount(0);
});

test('a preview loom refuses is said in the viewer\'s words, and nothing is offered to confirm', async ({ page }) => {
	await serve(page, (m) => void m.diagnostics.push(left as never));
	await publisher(page, ['write-settle-preview', 'write-settle'], { preview: [409, { ok: false, error: { code: 'not-left', message: 'LOOM-REFUSAL' } }] });
	await page.goto('/review/problems');
	await notice(page).getByTestId('settle-open').click();
	await expect(notice(page).getByTestId('settle-refused')).toHaveText('Loom settles that write itself the next time it writes, so there is nothing to decide.');
	await expect(notice(page).getByTestId('settle-confirm')).toHaveCount(0);
});
