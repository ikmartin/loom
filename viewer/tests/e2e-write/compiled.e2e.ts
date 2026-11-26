// A document's compiled PDF (plan 0.29.1): `view PDF` in the document's *view* menu opens it to read, the document's row in the tree current meanwhile, and a new compile opens it again where the reader is, with nobody asking; its own *view* menu opens the file the server answers in a tab of its own and saves it. The suite serves with `--no-compile`, so the test stands in for the compile by putting PDFs where one writes.
import { appendFileSync, copyFileSync, mkdirSync, readFileSync, utimesSync } from 'node:fs';
import { join } from 'node:path';
import { ARRAS, compileFolder, expect, test } from '../served';
import { pane, viewMenu } from '../workspace';

const WORKS = join(ARRAS, '../loom/tests/quilts/sources/showcase-works');
const built = (root: string) => join(compileFolder(root, 'drafting/main.tex'), 'main.pdf');

/** Put a PDF where a compile of drafting/main.tex writes, a minute on from now so its time differs from the last. */
function compiled(root: string, pdf: string, minutes: number): void {
	mkdirSync(compileFolder(root, 'drafting/main.tex'), { recursive: true });
	copyFileSync(join(WORKS, pdf), built(root));
	const at = new Date(Date.now() + minutes * 60_000);
	utimesSync(built(root), at, at);
}

test.use({
	prepareQuilt: async ({}, use) => {
		await use(({ root }) => compiled(root, 'arden-cycle-spaces.pdf', 0));
	}
});

test("a document's compiled PDF opens from view PDF, the document's row current in the tree, and a new compile opens it again at the reader's page", async ({ page, served }) => {
	await page.goto('/master/drafting/main');
	await viewMenu(page, 0);
	await page.getByTestId('toolbar-menu').getByTestId('view-pdf').click();
	await expect(page).toHaveURL(/beside=%2Fpdf%2Fdrafting%2Fmain$/);
	const paper = pane(page, 1).getByTestId('pdf-item');
	await expect(paper.locator('canvas').first()).toBeVisible();
	await expect(page.getByTestId('page-count')).toHaveText('/ 2');
	await expect(pane(page, 1).getByTestId('item-tab').filter({ hasText: 'main.tex · PDF' })).toHaveCount(1);
	// the tree has no row for the PDF: with the PDF the one read, its document's own row is the one marked
	await pane(page, 1).getByTestId('item-tab').filter({ hasText: 'main.tex · PDF' }).click();
	await expect(page.getByTestId('docs-tree').getByTestId('docs-pdf')).toHaveCount(0);
	await expect(page.getByTestId('docs-tree').locator('a[title="drafting/main.tex"]')).toHaveAttribute('aria-current', 'page');
	// it is read here, not marked: neither Annotate nor the PDF's drawing tools nor PDF ▾ among its tools
	for (const id of ['tool-annotate', 'tool-comment', 'tool-ink', 'pdf-menu']) await expect(pane(page, 1).getByTestId(id)).toHaveCount(0);

	const at = page.getByTestId('page-at');
	await at.fill('2');
	await at.press('Enter');
	await expect(at).toHaveValue('2');

	// a compile replaces the PDF, and the next publication carries its time
	compiled(served.root, 'arden-cycle-spaces-v2.pdf', 1);
	appendFileSync(join(served.root, 'notes/intro.md'), '\nAnother line.\n');
	await expect(page.getByTestId('page-count')).toHaveText('/ 3');
	await expect(at).toHaveValue('2');
	await expect(pane(page, 1).getByTestId('pdf-item')).toHaveAttribute('data-document', 'drafting/main.tex');
});

test("view PDF opens the compiled PDF beside its document, whose view menu opens the file the server answers in a tab of its own and saves its bytes under the document's name; a document never compiled says so", async ({ page, served }) => {
	await page.goto('/master/drafting/main');
	await viewMenu(page, 0);
	await page.getByTestId('toolbar-menu').getByTestId('view-pdf').click();
	await expect(pane(page, 1).getByTestId('pdf-item')).toHaveAttribute('data-document', 'drafting/main.tex');
	await expect(page.getByTestId('page-count')).toHaveText('/ 2');
	await expect(pane(page, 0).getByTestId('item-controls')).toHaveAttribute('aria-label', 'controls for main.tex');

	await viewMenu(page, 1);
	const browser = page.getByTestId('toolbar-menu').getByTestId('pdf-open-browser');
	const href = (await browser.getAttribute('href'))!;
	expect(href).toMatch(/^\/build\/tex\/.+\/main\.pdf$/);
	const [tab, answer] = await Promise.all([page.context().waitForEvent('page'), page.context().waitForEvent('response', (r) => r.request().isNavigationRequest() && new URL(r.url()).pathname === href), browser.click()]);
	expect(tab).not.toBe(page);
	expect(answer.status()).toBe(200);
	expect(answer.headers()['content-type']).toBe('application/pdf');
	await tab.close();

	await viewMenu(page, 1);
	const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('toolbar-menu').getByTestId('pdf-save').click()]);
	expect(download.suggestedFilename()).toBe('main.pdf');
	expect(readFileSync((await download.path())!).equals(readFileSync(built(served.root)))).toBe(true);

	// nothing compiles under --no-compile, and nothing put a PDF where talk.tex's compile writes
	await page.goto('/master/drafting/talk');
	await viewMenu(page, 0);
	const view = page.getByTestId('toolbar-menu').getByTestId('view-pdf');
	await expect(view.getByTestId('view-pdf-said')).toHaveText('not compiled yet');
	await expect(view).toHaveAttribute('aria-disabled', 'true');
});
