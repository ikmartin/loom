// Loom's home page, end to end: the real viewer on a real `loom app` in a home folder of the test's own (`tests/home.ts`).

import { mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Page } from '@playwright/test';
import { expect, test } from '../home';
import { VIEWER } from '../served';

test('the list shows each quilt with its state, and Stop and Forget act on it', async ({ page, homed }) => {
	await page.goto('/');
	await expect(page.getByTestId('home-empty')).toContainText('Drop your paper here');
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

/** Drop files on the page as a person drags them from the Finder: a drag over the window, then the drop, each file with its name and text. */
async function dropFiles(page: Page, files: { name: string; text?: string; base64?: string; type?: string }[]): Promise<void> {
	// the page takes drops once it has drawn the list
	await expect(page.getByTestId('home-empty').or(page.getByTestId('home-list'))).toBeVisible();
	await page.evaluate((fs) => {
		const data = new DataTransfer();
		for (const f of fs) {
			const bytes = f.base64 ? Uint8Array.from(atob(f.base64), (c) => c.charCodeAt(0)) : (f.text ?? '');
			data.items.add(new File([bytes], f.name, { type: f.type ?? '' }));
		}
		window.dispatchEvent(new DragEvent('dragover', { dataTransfer: data, bubbles: true, cancelable: true }));
		window.dispatchEvent(new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }));
	}, files);
}

/** The demo's invented paper, as a person's own paper dropped on the home page. */
const PAPER = { name: 'calloway-fixed-loci.tex', text: readFileSync(join(VIEWER, '../loom/tests/quilts/sources/demo-works/calloway-fixed-loci.tex'), 'utf8') };

test('a dropped paper becomes an open quilt with nothing typed', async ({ page, context, homed }) => {
	test.setTimeout(180_000);
	await page.goto('/');
	await expect(page.getByTestId('home-empty')).toBeVisible();
	await dropFiles(page, [PAPER]);
	const win = page.getByTestId('quilt-window');
	await expect(win).toHaveAttribute('data-at', 'form');
	await expect(page.getByTestId('quilt-window-dropped')).toHaveText('You dropped calloway-fixed-loci.tex.');
	// the name is filled from the file's, and where it goes is said
	await expect(page.getByTestId('quilt-window-name')).toHaveValue('calloway-fixed-loci');
	await expect(win).toContainText('In ~/Quilts');
	await page.getByTestId('quilt-window-create').click();
	await expect(win).toHaveAttribute('data-at', 'steps');
	// the list behind shows the quilt as being made, or once made, its row
	await expect(page.getByTestId('quilt-row-name')).toHaveText('calloway-fixed-loci');
	await expect(win).toHaveAttribute('data-at', 'done', { timeout: 150_000 });
	const done = page.getByTestId('quilt-window-done');
	// with TeX the paper is typeset; without, it is in and shown as its source
	await expect(done).toHaveText(/calloway-fixed-loci is ready\.|Your paper is in, shown as its source:/);
	const opened = context.waitForEvent('page');
	await page.getByTestId('quilt-window-open').click();
	const quilt = await opened;
	await quilt.waitForLoadState();
	await expect(quilt.getByTestId('pane-0')).toContainText('Fixed loci of involutions', { timeout: 60_000 });
	expect(new URL(quilt.url()).port).not.toBe(new URL(homed.url).port);
	// the window is put away once the quilt is opened, and its row says it runs
	await expect(win).toHaveCount(0);
	await expect(page.getByTestId('quilt-row')).toHaveAttribute('data-state', 'running');
	await quilt.close();
});

test('a drop with two papers in it asks once which file is the paper', async ({ page }) => {
	test.setTimeout(180_000);
	await page.goto('/');
	await dropFiles(page, [PAPER, { name: 'slides.tex', text: '\\documentclass{beamer}\n\\begin{document}\nHi\n\\end{document}\n' }]);
	await expect(page.getByTestId('quilt-window-dropped')).toHaveText('You dropped 2 files.');
	await page.getByTestId('quilt-window-name').fill('Calloway');
	await page.getByTestId('quilt-window-create').click();
	const win = page.getByTestId('quilt-window');
	await expect(win).toHaveAttribute('data-at', 'question');
	await expect(win).toContainText('Which file is the paper?');
	const create = page.getByTestId('quilt-window-create');
	await expect(create).toBeDisabled();
	await page.getByTestId('quilt-window-choice').first().check();
	await create.click();
	await expect(win).toHaveAttribute('data-at', /steps|done/);
	await expect(win).toHaveAttribute('data-at', 'done', { timeout: 150_000 });
});

test('a drop that holds no paper is refused and makes nothing; a name taken is said under it', async ({ page, homed }) => {
	await page.goto('/');
	await dropFiles(page, [{ name: 'notes.txt', text: 'no paper here' }]);
	await page.getByTestId('quilt-window-create').click();
	await expect(page.getByTestId('quilt-window-refused')).toContainText('That holds no LaTeX file that begins a document.');
	await page.getByTestId('quilt-window-close-button').click();
	await expect(page.getByTestId('home-empty')).toBeVisible();
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
	await expect(page.getByTestId('quilt-window-create')).toBeDisabled();
	await page.getByTestId('quilt-window-name').fill('Knot invariants');
	await page.getByTestId('quilt-window-name').press('Enter');
	await expect(win).toHaveAttribute('data-at', 'done', { timeout: 60_000 });
	await expect(page.getByTestId('quilt-window-done')).toHaveText('Knot invariants is ready.');
	// closed without opening it, the quilt stays on the list, served
	await page.getByTestId('quilt-window-close').click();
	await expect(page.getByTestId('quilt-row')).toHaveAttribute('data-state', 'running');
});
