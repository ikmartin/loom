// A document's compiled PDF from the document itself: `View PDF` in its *view* menu opens the PDF beside the text, and the PDF's own *view* menu opens the file in the browser and saves a copy named by the document; the same for an agent's copy; and beside `View PDF`, in the tree's words, that there is none yet, that it is compiling, that the last compile failed or had errors. Every address is the fixture manifest's own, answered here with a PDF of the test's.
import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import { manifest, PDF, serve } from '../manifest';
import { pane, viewMenu } from '../workspace';

type Doc = { path: string; default: boolean; pdf?: string; copy_of?: string };
const docs = manifest.masters as Doc[];
const main = docs.find((d) => d.default)!;
const talk = docs.find((d) => !d.default && !d.copy_of)!;
const copy = docs.find((d) => d.copy_of === main.path)!;
const file = (d: Doc) => d.path.split('/').pop()!;
const route = (d: Doc) => '/master/' + d.path.replace(/\.tex$/, '');

/** Answer each document's compiled PDF where its manifest entry says it is, to every tab, a new one included. */
async function servePdfs(page: Page): Promise<void> {
	const at = new Set(docs.filter((d) => d.pdf).map((d) => `/build/${d.pdf}`));
	await page.context().route((url) => at.has(url.pathname), (r) => r.fulfill({ body: PDF, contentType: 'application/pdf' }));
}

/** A publisher whose stream says how each compile stands, as `said()` has it at each reconnect. */
async function compiling(page: Page, said: () => Record<string, unknown>): Promise<void> {
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: [], token: 't', stream: true } }));
	await page.route('**/_api/stream', (r) => r.fulfill({ contentType: 'text/event-stream', body: `retry: 100\nevent: compiles\ndata: ${JSON.stringify(said())}\n\n` }));
}

/** Open a document's PDF from its *view* menu, then from the PDF's: open it in the browser, and save it, checking the file the browser is handed by name and bytes. */
async function viewOpenAndSave(page: Page, d: Doc): Promise<void> {
	await viewMenu(page, 0);
	const view = page.getByTestId('toolbar-menu').getByTestId('view-pdf');
	await expect(view).toHaveText('View PDF');
	await expect(view).not.toHaveAttribute('aria-disabled');
	await expect(view.getByTestId('view-pdf-said')).toHaveCount(0);
	await view.click();
	// beside the text, which stays where it was
	const paper = pane(page, 1).getByTestId('pdf-item');
	await expect(paper).toHaveAttribute('data-document', d.path);
	await expect(paper.locator('canvas').first()).toBeVisible();
	await expect(pane(page, 0).getByTestId('item-controls')).toHaveAttribute('aria-label', `controls for ${file(d)}`);

	// the file itself, at its own address, in a tab of its own: the browser's viewer shows it
	await viewMenu(page, 1);
	const menu = page.getByTestId('toolbar-menu');
	await expect(menu.locator('[role^="menuitem"]')).toHaveText(['Open in browser', 'Save as…', 'turn annotations off']);
	const browser = menu.getByTestId('pdf-open-browser');
	await expect(browser).toHaveAttribute('href', `/build/${d.pdf}`);
	await expect(browser).toHaveAttribute('target', '_blank');
	const [tab, asked] = await Promise.all([
		page.context().waitForEvent('page'),
		page.context().waitForEvent('request', (r) => r.isNavigationRequest() && new URL(r.url()).pathname === `/build/${d.pdf}`),
		browser.click()
	]);
	expect(new URL(asked.url()).search).toBe('');
	expect(tab).not.toBe(page);
	await tab.close();
	await expect(menu).toHaveCount(0);

	await viewMenu(page, 1);
	const save = page.getByTestId('toolbar-menu').getByTestId('pdf-save');
	await expect(save).toHaveAttribute('title', `Save a copy of this PDF as ${file(d).replace(/\.tex$/, '.pdf')}`);
	const [download] = await Promise.all([page.waitForEvent('download'), save.click()]);
	expect(download.suggestedFilename()).toBe(file(d).replace(/\.tex$/, '.pdf'));
	expect(readFileSync((await download.path())!, 'latin1')).toBe(PDF);
}

test("a document's view menu opens its PDF beside it, whose own view menu opens it in the browser and saves it under the document's name", async ({ page }) => {
	await servePdfs(page);
	await page.goto(route(main));
	await viewOpenAndSave(page, main);
	// chosen again, it reveals the PDF where it stands rather than opening a second
	await viewMenu(page, 0);
	await page.getByTestId('toolbar-menu').getByTestId('view-pdf').click();
	await expect(page.getByTestId('pdf-item')).toHaveCount(1);
	await expect(pane(page, 1).getByTestId('pdf-item')).toHaveAttribute('data-document', main.path);
	await expect(pane(page, 1).getByTestId('item-tab')).toHaveCount(1);
});

test("an agent's copy has View PDF too, and its PDF saves under the copy's own name", async ({ page }) => {
	await servePdfs(page);
	await page.goto(route(main));
	await page.getByTestId('docs-copies').getByRole('link', { name: file(copy), exact: true }).click();
	await expect(pane(page, 0).getByTestId('item-controls')).toHaveAttribute('aria-label', `controls for ${file(copy)}`);
	await viewOpenAndSave(page, copy);
});

test('View PDF says in words when nothing is compiled yet, while it compiles and when the last compile failed, greyed while there is no PDF; one compiled with errors, or kept from before a failure, still opens', async ({ page }) => {
	let said: Record<string, unknown> = {};
	await compiling(page, () => said);
	await servePdfs(page);
	await serve(page, (m) => delete m.masters.find((d: Doc) => d.path === main.path).pdf);
	await page.goto(route(main));
	await viewMenu(page, 0);
	const view = page.getByTestId('toolbar-menu').getByTestId('view-pdf');
	const word = view.getByTestId('view-pdf-said');
	// greyed, and opening nothing, until there is a PDF
	await expect(word).toHaveText('not compiled yet');
	await expect(view).toHaveAttribute('aria-disabled', 'true');
	await expect(view).toHaveAttribute('title', 'There is no compiled PDF to open yet');
	await expect(view).toHaveAccessibleName(`view the PDF of ${file(main)}, not compiled yet`);
	await view.click({ force: true });
	await expect(page.getByTestId('toolbar-menu')).toBeVisible();
	await expect(pane(page, 1)).toHaveCount(0);

	said = { [main.path]: { state: 'compiling', again: false, last: null } };
	await expect(word).toHaveText('compiling');
	await expect(view).toHaveAttribute('aria-disabled', 'true');
	said = { [main.path]: { state: 'queued', again: false, last: null } };
	await expect(word).toHaveText('waiting to compile');
	const failed = { result: 'failed', ended: 'now', error: '! Undefined control sequence.', at: 'l.12 \\hlind' };
	said = { [main.path]: { state: 'idle', again: false, last: failed } };
	await expect(word).toHaveText('did not compile');
	await expect(view).toHaveAttribute('title', '! Undefined control sequence. at l.12 \\hlind');
	await expect(view).toHaveAttribute('aria-disabled', 'true');
	await page.keyboard.press('Escape');

	// a document with a PDF: a failure keeps the last, and errors made one, so either opens, the error as its title
	said = { [talk.path]: { state: 'idle', again: false, last: failed } };
	await page.goto(route(talk));
	await viewMenu(page, 0);
	await expect(word).toHaveText('did not compile');
	await expect(view).not.toHaveAttribute('aria-disabled');
	said = { [talk.path]: { state: 'idle', again: false, last: { ...failed, result: 'errors' } } };
	await expect(word).toHaveText('compiled with errors');
	await expect(view).toHaveAttribute('title', '! Undefined control sequence. at l.12 \\hlind');
	await view.click();
	await expect(pane(page, 1).getByTestId('pdf-item')).toHaveAttribute('data-document', talk.path);
	await expect(pane(page, 1).getByTestId('pdf-compile')).toContainText('LaTeX reported errors');
});

test("a project's own PDF opens in the browser from its view menu too, as the file it is", async ({ page }) => {
	const fig = (manifest.files as { path: string; kind: string }[]).find((f) => f.kind === 'pdf')!;
	await page.route(`**/_files/${fig.path}`, (r) => r.fulfill({ body: PDF, contentType: 'application/pdf' }));
	await page.goto('/file/' + fig.path);
	await viewMenu(page, 0);
	const browser = page.getByTestId('toolbar-menu').getByTestId('pdf-open-browser');
	await expect(browser).toHaveText('Open in browser');
	await expect(browser).toHaveAttribute('href', `/_files/${fig.path}`);
	await expect(browser).toHaveAttribute('target', '_blank');
});
