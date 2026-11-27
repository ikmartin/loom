// `/`: reading where it was left — this visit's workspace, else the address remembered from an earlier visit, else the quilt's front door (`corpus.home`, its README unless `[quilt] home` says otherwise), else the default draft, else the newest landmark — and, in a quilt with nothing to read, a drop area for a paper. Each test is named for the rule it holds.
import { expect, test, type Page } from '@playwright/test';
import { beside, pane } from '../workspace';
import { manifest, serve } from '../manifest';

test("a first visit opens the front door, the quilt's README", async ({ page }) => {
	await page.goto('/');
	await expect(page).toHaveURL(/\/file\/README\.md$/);
	await expect(pane(page, 0).getByTestId('file-item')).toContainText('The synthetic quilt: invented mathematics');
});

test('a quilt with no front door opens the default draft', async ({ page }) => {
	await serve(page, (m) => {
		m.corpus.home = null;
	});
	await page.goto('/');
	await expect(page).toHaveURL(/\/master\/drafting\/main$/);
	await expect(pane(page, 0).locator('.fragment').first()).toBeVisible();
});

test('a reload, or a visit another day, reopens both panes as they were left', async ({ page }) => {
	await page.goto('/master/drafting/main' + beside('/node/sy-0003'));
	await expect(pane(page, 1).locator('.fragment').first()).toBeVisible();
	await page.goto('/');
	await expect(page).toHaveURL(/\/master\/drafting\/main\?beside=%2Fnode%2Fsy-0003/);
	await expect(pane(page, 1).getByTestId('item-tab')).toContainText('Theorem 2.1');
	// what is remembered is the corpus's own, in this browser
	const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('viewer.workspace') ?? '{}'));
	expect(Object.keys(kept)).toEqual([manifest.corpus.name]);
});

test("where the publisher says which quilt it serves, what is remembered is kept under that, so two quilts of one name on one port keep apart", async ({ page }) => {
	let digest = 'quilt-a';
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: [], token: 't', quilt: digest } }));
	await page.goto('/master/drafting/main' + beside('/node/sy-0003'));
	await expect(pane(page, 1).locator('.fragment').first()).toBeVisible();
	await expect.poll(() => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('viewer.workspace') ?? '{}')))).toEqual(['quilt-a']);
	// a folder turned in the tree is kept under the same
	const notes = page.locator('[data-testid="docs-dir"][data-path="notes"] > .fold');
	const was = await notes.getAttribute('aria-expanded');
	await notes.click();
	await expect(notes).not.toHaveAttribute('aria-expanded', was!);
	await expect.poll(() => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('viewer.tree') ?? '{}')))).toEqual(['quilt-a']);
	// another quilt of the same name on the same port remembers nothing of the first, and opens at its front door
	digest = 'quilt-b';
	await page.goto('/');
	await expect(page).toHaveURL(/\/file\/README\.md$/);
	const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('viewer.workspace') ?? '{}'));
	expect(kept['quilt-a']).toMatch(/beside=/);
	expect(kept['quilt-b']).toMatch(/README/);
	await expect(notes).toHaveAttribute('aria-expanded', was!);
	// and the first, served again, comes back as it was left
	digest = 'quilt-a';
	await page.goto('/');
	await expect(page).toHaveURL(/\/master\/drafting\/main\?beside=%2Fnode%2Fsy-0003/);
});

test('a remembered document no longer in the corpus gives way to the front door', async ({ page }) => {
	await page.addInitScript((name) => localStorage.setItem('viewer.workspace', JSON.stringify({ [name]: '/master/gone' })), manifest.corpus.name);
	await page.goto('/');
	await expect(page).toHaveURL(/\/file\/README\.md$/);
});

/** The fixture with nothing to read: no document, no landmark, no front door. */
async function nothingToRead(page: Page): Promise<void> {
	await serve(page, (m) => {
		m.masters = [];
		m.canon = [];
		m.corpus.home = null;
	});
}

test('a quilt with nothing to read opens on a drop area for a paper or a PDF, and names no command', async ({ page }) => {
	await nothingToRead(page);
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: ['paper-receive', 'paper-import', 'paper-choose'], token: 't' } }));
	await page.goto('/');
	const area = page.getByTestId('paper-drop');
	await expect(area.getByRole('heading', { level: 2 })).toHaveText('Drop your paper here');
	await expect(area).toContainText('Its .tex file, its folder, or its source archive comes into this quilt, open on your paper.');
	await expect(area).toContainText('A PDF comes into its library, for reading it.');
	await expect(area.getByTestId('paper-drop-choose')).toHaveText('or choose a file…');
	await expect(page.getByTestId('how-to-start')).not.toContainText('loom ');
	await expect(page).toHaveURL(/\/$/);
	// and Docs, with nothing to return to, comes back here
	await expect(page.getByTestId('primary-docs')).toHaveAttribute('href', '/');
});

test('a file dropped on the area is its own, and never the library\'s', async ({ page }) => {
	await nothingToRead(page);
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: ['paper-receive', 'paper-import', 'paper-choose', 'library-receive', 'library-take'], token: 't' } }));
	const sent: string[] = [];
	await page.route('**/_api/*', (r) => {
		const path = new URL(r.request().url()).pathname;
		if (path.includes('/paper-')) sent.push(path);
		return r.fulfill(path.endsWith('paper-receive') ? { json: { ok: true, drop: '0123456789abcdef', path: 'notes.txt', size: 4 } } : { status: 409, json: { error: { code: 'no-paper', message: 'what was dropped holds no .tex file that begins a document' } } });
	});
	await page.goto('/');
	const area = page.getByTestId('paper-drop');
	await expect(area).toBeVisible();
	const prevented = await area.evaluate((el) => {
		const data = new DataTransfer();
		data.items.add(new File(['none'], 'notes.txt'));
		el.dispatchEvent(new DragEvent('dragover', { dataTransfer: data, bubbles: true, cancelable: true }));
		return !el.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
	});
	expect(prevented).toBe(true);
	await expect(page.getByTestId('paper-drop-said')).toContainText('That holds no LaTeX file that begins a document.');
	await expect(page.getByTestId('drop-sheet')).toHaveCount(0);
	expect(sent).toEqual(['/_api/paper-receive', '/_api/paper-import']);
});

test('where the publisher takes no paper, a quilt with nothing to read says so', async ({ page }) => {
	await nothingToRead(page);
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: [], token: 't' } }));
	await page.goto('/');
	await expect(page.getByTestId('how-to-start')).toHaveText('Nothing to read yet.');
	await expect(page.getByTestId('paper-drop')).toHaveCount(0);
});
