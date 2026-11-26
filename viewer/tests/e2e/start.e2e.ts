// `/`: reading where it was left — this visit's workspace, else the address remembered from an earlier visit, else the quilt's front door (`corpus.home`, its README unless `[quilt] home` says otherwise), else the default draft, else the newest landmark — and, in a quilt with nothing to read, how to start. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';
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
	const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('arras.workspace') ?? '{}'));
	expect(Object.keys(kept)).toEqual([manifest.corpus.name]);
});

test("where the publisher says which quilt it serves, what is remembered is kept under that, so two quilts of one name on one port keep apart", async ({ page }) => {
	let digest = 'quilt-a';
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: [], token: 't', quilt: digest } }));
	await page.goto('/master/drafting/main' + beside('/node/sy-0003'));
	await expect(pane(page, 1).locator('.fragment').first()).toBeVisible();
	await expect.poll(() => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('arras.workspace') ?? '{}')))).toEqual(['quilt-a']);
	// a folder turned in the tree is kept under the same
	const notes = page.locator('[data-testid="docs-dir"][data-path="notes"] > .fold');
	const was = await notes.getAttribute('aria-expanded');
	await notes.click();
	await expect(notes).not.toHaveAttribute('aria-expanded', was!);
	await expect.poll(() => page.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('arras.tree') ?? '{}')))).toEqual(['quilt-a']);
	// another quilt of the same name on the same port remembers nothing of the first, and opens at its front door
	digest = 'quilt-b';
	await page.goto('/');
	await expect(page).toHaveURL(/\/file\/README\.md$/);
	const kept = await page.evaluate(() => JSON.parse(localStorage.getItem('arras.workspace') ?? '{}'));
	expect(kept['quilt-a']).toMatch(/beside=/);
	expect(kept['quilt-b']).toMatch(/README/);
	await expect(notes).toHaveAttribute('aria-expanded', was!);
	// and the first, served again, comes back as it was left
	digest = 'quilt-a';
	await page.goto('/');
	await expect(page).toHaveURL(/\/master\/drafting\/main\?beside=%2Fnode%2Fsy-0003/);
});

test('a remembered document no longer in the corpus gives way to the front door', async ({ page }) => {
	await page.addInitScript((name) => localStorage.setItem('arras.workspace', JSON.stringify({ [name]: '/master/gone' })), manifest.corpus.name);
	await page.goto('/');
	await expect(page).toHaveURL(/\/file\/README\.md$/);
});

test('a quilt with nothing to read opens on how to start: the publisher\'s advice, one step a fix', async ({ page }) => {
	await serve(page, (m) => {
		m.masters = [];
		m.canon = [];
		m.corpus.home = null;
		m.diagnostics = [
			{
				severity: 'info',
				code: 'loom:no-live-document',
				message: 'nothing is being worked on: drafting/ holds no document; write one there with \\documentclass, or begin from a paper',
				locations: [],
				keys: [],
				fixes: [
					{ label: 'bring in a paper you are writing', command: 'loom import FILE' },
					{ label: 'file a paper you are reading', command: 'loom library add FILE' }
				]
			}
		] as typeof m.diagnostics;
	});
	await page.goto('/');
	const start = page.getByTestId('how-to-start');
	await expect(start.getByRole('heading', { level: 1 })).toHaveText('Nothing to read yet');
	await expect(start).toContainText('write one there with \\documentclass');
	await expect(start.getByTestId('start-step')).toHaveCount(2);
	await expect(start.getByTestId('start-step').locator('code')).toHaveText(['loom import FILE', 'loom library add FILE']);
	await expect(page).toHaveURL(/\/$/);
	// and Docs, with nothing to return to, comes back here
	await expect(page.getByTestId('primary-docs')).toHaveAttribute('href', '/');
});
