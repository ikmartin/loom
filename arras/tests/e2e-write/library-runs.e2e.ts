// Library runs from the viewer under a running `loom serve` (plan 0.24.1): a run on one work from its Info, and on every work from the library's page, each asking first for the network the synthetic quilt has off, each followed step by step to its verdict.
import { expect, test } from '../served';

test("a work's run starts from its Info, asks for the network the quilt has off, and runs offline to its verdict", async ({ page }) => {
	await page.goto('/library/Kre99');
	await page.getByTestId('run-get').click();
	await expect(page.getByTestId('network-ask')).toBeVisible();
	await page.getByTestId('network-offline').click();
	const run = page.getByTestId('job-progress');
	await expect(run).toHaveAttribute('data-state', 'done');
	// offline, looking up and fetching act on nothing, and say so; the run still reaches its verdict
	await expect(run.locator('[data-step="resolve"]')).toHaveAttribute('data-state', 'skipped');
	await expect(run.locator('[data-step="fetch"]')).toHaveAttribute('data-state', 'skipped');
	await expect(run.locator('.head strong')).not.toHaveText('Done');
	await run.getByRole('button', { name: 'Dismiss' }).click();
	await expect(run).toHaveCount(0);
});

test("a run over every work starts from the library's page and gathers the bibliography first", async ({ page }) => {
	await page.goto('/review/library');
	await page.getByTestId('run-everything').click();
	await page.getByTestId('network-offline').click();
	const run = page.getByTestId('job-progress');
	await expect(run.locator('[data-step="gather"]')).toBeVisible();
	await expect(run).toHaveAttribute('data-state', 'done');
	await expect(run.locator('[data-step="gather"]')).toHaveAttribute('data-state', 'done');
});

test("a cited work's problem is loom's own: Problems shows the person none of it, and the manifest keeps it with the fix that digests the work again", async ({ page, served }) => {
	const fs = await import('node:fs');
	const { join } = await import('node:path');
	const digest = join(served.root, '.loom/library/Kre99.tex');
	// a reference to nothing inside one of Kre99's results, as a fault in the digest writer leaves one
	fs.writeFileSync(digest, fs.readFileSync(digest, 'utf8').replace('\\end{theorem}', 'See \\ref{nowhere-at-all}.\n\\end{theorem}'));
	type D = { code: string; class: string; owner: string; message: string; fixes?: { act?: { endpoint: string; body: { works?: string[] } } }[] };
	const published = async () => ((await (await page.request.get(`${served.url}/build/manifest.json`)).json()).diagnostics as D[]).find((d) => d.message.includes('nowhere-at-all'));
	await expect.poll(published).toBeTruthy();
	const d = (await published())!;
	expect([d.code, d.class, d.owner]).toEqual(['dangling-link', 'internal', 'work']);
	expect(d.fixes?.map((f) => f.act?.endpoint)).toContain('library-update');
	await page.goto('/review/problems');
	await expect(page.getByTestId('problems-yours')).toBeVisible();
	await expect(page.locator('main')).not.toContainText('nowhere-at-all');
	await expect(page.getByTestId('problems-works')).toHaveCount(0);
});
