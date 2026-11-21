// A cited work's problem under a running `loom serve`: a fault in its digest is loom's own, which Problems never shows the person, and the manifest keeps it with the fix that digests the work again.
import { expect, test } from '../served';

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
