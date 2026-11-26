// The Library on a served quilt: what a write changes is on screen without a reload, since the publisher says the library moved by its stream's `library` event (`docs/specs/library-views.md` §2, "Freshness"). Round six's fixture raises its own generation on every write, so only a real publisher can show that the event comes.
import { expect, test } from '../served';
import type { Page } from '@playwright/test';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { paperBytes } from '../../src/lib/library/fixtures/paper';

/** A paper stating no identifier, its bytes its own, so the intake adds it as a work of its own named by its file. */
const paper = () => Buffer.concat([Buffer.from(paperBytes(2)), Buffer.from(`\n%${Date.now()}-${Math.random()}\n`)]);

/** Chooses files as the person does: from the empty library's box, or from `add work…` above the list. */
async function choose(page: Page, name: string): Promise<void> {
	if (await page.getByTestId('add-work').count()) await page.getByTestId('add-work').click();
	await page.getByTestId('choose-files-input').setInputFiles([{ name, mimeType: 'application/pdf', buffer: paper() }]);
}

test('a drop, a delete and its undo each show in the list with no reload', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library');
	await expect(page.getByTestId('works-table').or(page.getByTestId('works-empty'))).toBeVisible();
	const rows = page.getByTestId('work-row');
	const before = await rows.count();
	await choose(page, 'notes-on-lattice-walks.pdf');
	await expect(page.getByTestId('column-message')).toContainText('Added');
	const added = rows.filter({ hasText: 'notes-on-lattice-walks.pdf' });
	await expect(added).toHaveCount(1);
	await expect(rows).toHaveCount(before + 1);
	await added.hover();
	await added.getByTestId('row-more').click();
	await page.getByTestId('row-delete').click();
	await expect(page.getByTestId('column-message')).toContainText('Deleted');
	await expect(rows).toHaveCount(before);
	await page.getByTestId('column-message-undo').click();
	await expect(added).toHaveCount(1);
	await expect(rows).toHaveCount(before + 1);
});

test("a work added from the command line, outside the viewer, shows in an open list with no reload", async ({ page, served }) => {
	// nothing the viewer did raises the generation here: only the stream's event can tell the list
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/library');
	await expect(page.getByTestId('works-table').or(page.getByTestId('works-empty'))).toBeVisible();
	const rows = page.getByTestId('work-row');
	const before = await rows.count();
	const dir = mkdtempSync(join(tmpdir(), 'loom-library-add-'));
	try {
		const file = join(dir, 'from-the-shell.pdf');
		writeFileSync(file, paper());
		served.loom(['library', 'add', file]);
		await expect(rows.filter({ hasText: 'from-the-shell.pdf' })).toHaveCount(1);
		await expect(rows).toHaveCount(before + 1);
	} finally {
		rmSync(dir, { recursive: true, force: true });
	}
});
