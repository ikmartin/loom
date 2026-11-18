// A document's compiled PDF from the document itself: **PDF** on its toolbar opens the PDF beside the text, and the PDF's own toolbar saves a copy named by the document; the same for an agent's copy; and beside **PDF**, in words, that there is none yet, that it is compiling, that the last compile failed. Every address is the fixture manifest's own, answered here with a PDF of the test's.
import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { manifest, PDF, serve } from '../manifest';
import { pane } from '../workspace';

type Doc = { path: string; default: boolean; pdf?: string; copy_of?: string };
const docs = manifest.masters as Doc[];
const main = docs.find((d) => d.default)!;
const copy = docs.find((d) => d.copy_of === main.path)!;
const file = (d: Doc) => d.path.split('/').pop()!;
const route = (d: Doc) => '/master/' + d.path.replace(/\.tex$/, '');

/** Answer each document's compiled PDF where its manifest entry says it is. */
async function servePdfs(page: Page): Promise<void> {
	const at = new Set(docs.filter((d) => d.pdf).map((d) => `/build/${d.pdf}`));
	await page.route((url) => at.has(url.pathname), (r) => r.fulfill({ body: PDF, contentType: 'application/pdf' }));
}

/** A publisher whose stream says how each compile stands, as `said()` has it at each reconnect. */
async function compiling(page: Page, said: () => Record<string, unknown>): Promise<void> {
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: [], token: 't', stream: true } }));
	await page.route('**/_api/stream', (r) => r.fulfill({ contentType: 'text/event-stream', body: `retry: 100\nevent: compiles\ndata: ${JSON.stringify(said())}\n\n` }));
}

/** Open a document's PDF from its toolbar, and save a copy from the PDF's: the file the browser is handed, by name and bytes. */
async function openAndSave(page: Page, d: Doc): Promise<void> {
	const pdf = pane(page, 0).getByTestId('toolbar-pdf');
	await expect(pdf.getByRole('link')).toHaveText('PDF');
	await expect(pdf.getByTestId('toolbar-pdf-state')).toHaveCount(0);
	await pdf.getByRole('link').click();
	// beside the text, which stays where it was
	const paper = pane(page, 1).getByTestId('pdf-item');
	await expect(paper).toHaveAttribute('data-document', d.path);
	await expect(paper.locator('canvas').first()).toBeVisible();
	await expect(pane(page, 0).getByTestId('toolbar-pdf')).toBeVisible();

	const save = pane(page, 1).getByTestId('pdf-save');
	await expect(save).toHaveText('Save a copy');
	const [download] = await Promise.all([page.waitForEvent('download'), save.click()]);
	expect(download.suggestedFilename()).toBe(file(d).replace(/\.tex$/, '.pdf'));
	expect(readFileSync((await download.path())!, 'latin1')).toBe(PDF);
}

test("a document's PDF opens from its own toolbar, beside it, and saves under the document's name", async ({ page }) => {
	await servePdfs(page);
	await page.goto(route(main));
	await openAndSave(page, main);
});

test("an agent's copy has the same PDF control and saves under its own name", async ({ page }) => {
	await servePdfs(page);
	await page.goto(route(main));
	await page.getByTestId('docs-copies').getByRole('link', { name: file(copy), exact: true }).click();
	await expect(pane(page, 0).getByTestId('toolbar-pdf')).toHaveAttribute('data-document', copy.path);
	await openAndSave(page, copy);
});

test('PDF says in words when nothing is compiled yet, while it compiles, and when the last compile failed', async ({ page }) => {
	let said: Record<string, unknown> = {};
	await compiling(page, () => said);
	await serve(page, (m) => delete m.masters.find((d: Doc) => d.path === main.path).pdf);
	await page.goto(route(main));
	const pdf = pane(page, 0).getByTestId('toolbar-pdf');
	const state = pdf.getByTestId('toolbar-pdf-state');
	// greyed and opening nothing until there is a PDF
	await expect(pdf).toContainText('PDF');
	await expect(pdf.getByRole('link')).toHaveCount(0);
	await expect(state).toHaveText('not compiled yet');

	said = { [main.path]: { state: 'compiling', again: false, last: null } };
	await expect(state).toHaveText('compiling');

	said = { [main.path]: { state: 'idle', again: false, last: { result: 'failed', ended: 'now', error: '! Undefined control sequence.', at: 'l.12 \\hlind' } } };
	await expect(state).toHaveText('did not compile');
	await expect(state).toHaveAttribute('title', '! Undefined control sequence. at l.12 \\hlind');
});
