// Loom's home page, end to end: the real viewer on a real `loom app` in a home folder of the test's own (`tests/home.ts`).

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Page } from '@playwright/test';
import { expect, test } from '../home';
import { VIEWER } from '../served';

test('the list shows each quilt with its state, and Stop and Forget act on it', async ({ page, homed }) => {
	await page.goto('/');
	await expect(page.getByTestId('home-empty')).toHaveText('No quilts yet. A quilt is a folder for one piece of research: the papers you write or read, and your notes on them.');
	const made = await homed.call('quilt-create', { name: 'Cycle spaces' });
	expect(made.status).toBe(200);
	const row = page.getByTestId('quilt-row');
	await expect(row).toHaveCount(1);
	await expect(row.getByTestId('quilt-row-name')).toHaveText('Cycle spaces');
	await expect(row).toContainText('~/Quilts/Cycle spaces');
	await expect(row).toHaveAttribute('data-state', 'running', { timeout: 30_000 });
	await expect(row.getByTestId('quilt-row-state')).toHaveText('Running');
	await row.getByTestId('quilt-stop').click();
	await expect(row).toHaveAttribute('data-state', 'stopped');
	await expect(row.getByTestId('quilt-row-state')).toHaveText('Not running');
	await row.getByTestId('quilt-forget').click();
	await expect(page.getByTestId('home-empty')).toBeVisible();
	// nothing on the page names a command
	await expect(page.locator('body')).not.toContainText('loom ');
});

/** Drop files on the page as a person drags them from the Finder: a drag over the window, then the drop, each file with its name and text; whether the page kept the browser from opening them itself. */
async function dropFiles(page: Page, files: { name: string; text?: string; base64?: string; type?: string }[]): Promise<boolean> {
	return page.evaluate((fs) => {
		const data = new DataTransfer();
		for (const f of fs) {
			const bytes = f.base64 ? Uint8Array.from(atob(f.base64), (c) => c.charCodeAt(0)) : (f.text ?? '');
			data.items.add(new File([bytes], f.name, { type: f.type ?? '' }));
		}
		window.dispatchEvent(new DragEvent('dragover', { dataTransfer: data, bubbles: true, cancelable: true }));
		return !window.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
	}, files);
}

/** The demo's invented paper, as a person's own paper. */
const PAPER = { name: 'calloway-fixed-loci.tex', text: readFileSync(join(VIEWER, '../loom/tests/quilts/sources/demo-works/calloway-fixed-loci.tex'), 'utf8') };

test('the home page takes no drop: its list and its two buttons stay, and nothing is made', async ({ page, homed }) => {
	await page.goto('/');
	await expect(page.getByTestId('home-empty')).toBeVisible();
	// nor does the browser open the file in the home page's place
	expect(await dropFiles(page, [PAPER])).toBe(true);
	await expect(page.getByTestId('quilt-window')).toHaveCount(0);
	await expect(page.getByTestId('home-open-quilt')).toBeVisible();
	await expect(page.getByTestId('home-new-quilt')).toBeVisible();
	await expect(page.locator('body')).not.toContainText('Drop');
	expect(((await homed.call('quilt-list')).said.jobs as unknown[]).length).toBe(0);
});

test('a name taken is said under it', async ({ page, homed }) => {
	await page.goto('/');
	mkdirSync(join(homed.folder, 'Quilts', 'Taken', 'x'), { recursive: true });
	await page.getByTestId('home-new-quilt').click();
	await page.getByTestId('quilt-window-name').fill('Taken');
	await page.getByTestId('quilt-window-create').click();
	await expect(page.getByTestId('quilt-window-error')).toHaveText('A folder of that name is there already.');
});

test('New quilt asks only the name and makes an empty quilt on the list', async ({ page }) => {
	await page.goto('/');
	await page.getByTestId('home-new-quilt').click();
	const win = page.getByTestId('quilt-window');
	await expect(win).toContainText('New quilt');
	await expect(win).toContainText('In ~/Quilts');
	// Create with no name made nothing: the name is asked
	await page.getByTestId('quilt-window-create').click();
	await expect(page.getByTestId('quilt-window-name')).toBeFocused();
	await expect(win).toHaveAttribute('data-at', 'form');
	await page.getByTestId('quilt-window-name').fill('Knot invariants');
	await page.getByTestId('quilt-window-name').press('Enter');
	await expect(win).toHaveAttribute('data-at', 'done', { timeout: 60_000 });
	await expect(page.getByTestId('quilt-window-done')).toHaveText('Knot invariants is ready.');
	// closed without opening it, the quilt stays on the list, served
	await page.getByTestId('quilt-window-close').click();
	await expect(page.getByTestId('quilt-row')).toHaveAttribute('data-state', 'running');
});

test("the person's name is asked once, then shown in the footer and changed there", async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('home-name')).toHaveCount(0);
	const asked = page.getByTestId('home-name-asked');
	await expect(asked).toContainText('Your name, as it appears beside your comments and decisions');
	await page.getByTestId('home-name-save').click();
	await expect(page.getByTestId('home-name-field')).toBeFocused();
	await expect(asked).toBeVisible();
	await page.getByTestId('home-name-field').fill('Maren Holt');
	await page.getByTestId('home-name-save').click();
	await expect(asked).toHaveCount(0);
	// saved in loom's own settings, so no source is said: only git's would be
	await expect(page.getByTestId('home-name')).toHaveText(/^Your name: Maren Holt\s*·\s*Change$/);
	await page.getByTestId('home-name-change').click();
	await page.getByTestId('home-name-field').fill('M. Holt');
	await page.getByTestId('home-name-field').press('Enter');
	await expect(page.getByTestId('home-name-shown')).toHaveText('M. Holt');
	// asked no more, after a reload too
	await page.reload();
	await expect(page.getByTestId('home-name-shown')).toHaveText('M. Holt');
	await expect(asked).toHaveCount(0);
});

test("a quilt's page whose server stopped says so and links to the home page, and goes once it is served again", async ({ page, context, homed }) => {
	test.setTimeout(120_000);
	const made = await homed.call('quilt-create', { name: 'Thesis' });
	expect(made.status).toBe(200);
	await page.goto('/');
	const row = page.getByTestId('quilt-row');
	await expect(row).toHaveAttribute('data-state', 'running', { timeout: 30_000 });
	const opened = context.waitForEvent('page');
	await row.getByTestId('quilt-open').click();
	const quilt = await opened;
	await quilt.waitForLoadState();
	await expect(quilt.getByTestId('column')).toBeVisible();
	await expect(quilt.getByTestId('stopped')).toHaveCount(0);
	await row.getByTestId('quilt-stop').click();
	const card = quilt.getByTestId('stopped');
	await expect(card).toContainText('Loom has stopped serving this quilt.', { timeout: 30_000 });
	await expect(card.getByTestId('stopped-home')).toHaveAttribute('href', homed.url);
	await expect(card).not.toContainText('loom serve');
	// opened again from the home page, the card goes by itself
	await row.getByTestId('quilt-open').click();
	await expect(card).toHaveCount(0, { timeout: 30_000 });
	await quilt.close();
});

test("a quilt that refused to start shows loom's refusal worded, with no command and no long path, and Copy details", async ({ page, homed }) => {
	test.setTimeout(120_000);
	const made = await homed.call('quilt-create', { name: 'Covering estimates' });
	const key = (made.said as { job: string }).job;
	await expect.poll(async () => ((await homed.call('quilt-list')).said.jobs as { job: string; state: string }[]).find((j) => j.job === key)?.state, { timeout: 60_000 }).toBe('done');
	const quilt = (((await homed.call('quilt-list')).said.quilts as { quilt: string }[])[0]).quilt;
	await homed.call('quilt-stop', { quilt });
	writeFileSync(join(homed.folder, 'Quilts', 'Covering estimates', 'config.toml'), '[quilt\nname = "Covering estimates"\n');
	await homed.call('quilt-open', { quilt });
	await page.goto('/');
	const row = page.getByTestId('quilt-row');
	await expect(row).toHaveAttribute('data-why', 'refused', { timeout: 60_000 });
	await expect(row.getByTestId('quilt-row-state')).toContainText('Loom could not open it:');
	const said = row.getByTestId('quilt-row-said');
	await expect(said).toHaveText(/^config\.toml is not valid TOML/);
	for (const raw of ['loom serve', 'Ctrl-C', 'Error:', homed.folder]) await expect(said).not.toContainText(raw);
	await row.getByTestId('copy-details').click();
	await expect(row.getByTestId('copy-details-done')).toHaveText('Copied');
	await expect(row.getByTestId('quilt-again')).toBeVisible();
	await expect(row.getByTestId('quilt-forget')).toBeVisible();
});
