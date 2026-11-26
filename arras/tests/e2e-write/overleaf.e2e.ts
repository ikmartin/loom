// The Overleaf mirror under a running `loom serve`, with no command anywhere: a person pastes a project's link in Settings › Overleaf (giving a git token where Overleaf asks for one), chooses the folder and who they are, and pairs; a co-author's edit then arrives by Update from Overleaf, said in its line and listed in Review; and a suggested edit on the mirrored document offers Copy new text and Done in Overleaf in place of Keep, kept only once Overleaf has its words. Overleaf's git is a local bare repository (`overleafStandIn`): nothing reaches Overleaf or the Keychain.
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Page } from '@playwright/test';
import { expect, test, type Served } from '../served';
import { shown } from '../review-rows';

test.use({ overleafStandIn: true });

/** The stand-in project's id, as Overleaf writes one. */
const ID = '5f1e0c2a9b3d4e6f7a8b9c0d';
const PAT: [string, string] = ['Pat Person', 'pat@example.org'];
const CLEO: [string, string] = ['Cleo Colleague', 'cleo@example.org'];
const PAPER = ['\\documentclass{article}', '\\newtheorem{lemma}{Lemma}', '\\begin{document}', '\\begin{lemma}\\label{lem:planar}Such a graph is not planar.\\end{lemma}', '\\begin{lemma}\\label{lem:cover}The cover has two sheets.\\end{lemma}', '\\end{document}', ''].join('\n');

/** Run git in `cwd` as `who`, reading no configuration of the machine's. */
function git(cwd: string, args: string[], who: [string, string] = PAT): string {
	const [name, email] = who;
	const env = { ...process.env, GIT_AUTHOR_NAME: name, GIT_AUTHOR_EMAIL: email, GIT_COMMITTER_NAME: name, GIT_COMMITTER_EMAIL: email, GIT_CONFIG_GLOBAL: '/dev/null', GIT_CONFIG_NOSYSTEM: '1' };
	return execFileSync('git', args, { cwd, env, stdio: 'pipe' }).toString();
}

/** The stand-in project, its first commit Pat's, and a clone of it that commits and pushes as Overleaf records an edit made there; the clone's folder. */
function project(served: Served): string {
	const home = `${served.root}.overleaf`;
	const bare = join(home, 'projects', ID);
	git(home, ['init', '-q', '--bare', '-b', 'main', bare]);
	const clone = join(home, 'edits');
	git(home, ['init', '-q', '-b', 'main', clone]);
	writeFileSync(join(clone, 'paper.tex'), PAPER);
	git(clone, ['add', '.']);
	git(clone, ['commit', '-q', '-m', 'new project']);
	git(clone, ['push', '-q', bare, 'main']);
	return clone;
}

/** An edit made in Overleaf by `who`: `paper.tex` with `from` in place of `to`. */
function edit(clone: string, from: string, to: string, who: [string, string]): void {
	const path = join(clone, 'paper.tex');
	writeFileSync(path, readFileSync(path, 'utf8').replace(from, to));
	git(clone, ['commit', '-q', '-am', 'edit'], who);
	git(clone, ['push', '-q', join(clone, '..', 'projects', ID), 'main'], who);
}

const built = (served: Served) => JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));

async function overleafSettings(page: Page): Promise<void> {
	await page.getByTestId('settings-toggle').click();
	await page.getByTestId('settings-section-overleaf').click();
}

/** Pair the quilt from Settings › Overleaf, Pat ticked as the person, into `paper/`. */
async function pair(page: Page): Promise<void> {
	await overleafSettings(page);
	await page.getByTestId('overleaf-link').fill(`https://www.overleaf.com/project/${ID}`);
	await page.getByTestId('overleaf-connect').click();
	await expect(page.getByTestId('overleaf-folder')).toHaveValue('paper');
	await page.locator(`[data-testid="overleaf-me"][data-email="${PAT[1]}"]`).check();
	await page.getByTestId('overleaf-pair').click();
	await expect(page.getByTestId('overleaf-said')).toHaveText('Connected. Your paper is in the folder paper.');
}

test("a person pairs from the project's link, gives the token Overleaf asks for, updates, and sees a co-author's change", async ({ page, served }) => {
	const clone = project(served);
	await page.goto('/');
	// Overleaf asks for a token the first time: the field shows, the token goes to loom, and the same request is made again
	let asked = 0;
	await page.route('**/_api/overleaf-pair', async (route) => {
		if (asked++) return route.continue();
		await route.fulfill({ status: 409, json: { ok: false, error: { code: 'no-token', message: 'loom words, never shown' } } });
	});
	await overleafSettings(page);
	await page.getByTestId('overleaf-link').fill(`https://www.overleaf.com/project/${ID}`);
	await page.getByTestId('overleaf-connect').click();
	const token = page.getByTestId('overleaf-token');
	await expect(token).toContainText("Overleaf asks for a git token once. Make one in Overleaf under Account Settings, Git integration, and paste it here; loom keeps it in your Mac's Keychain.");
	await expect(page.getByText('loom words, never shown')).toHaveCount(0);
	await page.getByTestId('overleaf-token-field').fill('olp_standintoken');
	await page.getByTestId('overleaf-token-use').click();
	await expect(token).toHaveCount(0);
	// the token is kept by the stand-in for the Keychain, and nowhere in the quilt
	expect(readFileSync(join(`${served.root}.overleaf`, 'keychain-stand-in'), 'utf8')).toContain('olp_standintoken');
	await expect(page.getByTestId('overleaf-folder')).toHaveValue('paper');
	await page.locator(`[data-testid="overleaf-me"][data-email="${PAT[1]}"]`).check();
	await page.getByTestId('overleaf-pair').click();
	await expect(page.getByTestId('overleaf-said')).toHaveText('Connected. Your paper is in the folder paper.');
	expect(readFileSync(join(served.root, 'paper/paper.tex'), 'utf8')).toBe(PAPER);
	await expect(page.getByTestId('overleaf-mirror')).toContainText('This quilt mirrors an Overleaf project in the folder paper.');
	await expect(page.getByTestId('overleaf-open')).toHaveAttribute('href', `https://www.overleaf.com/project/${ID}`);

	// nothing new yet
	await page.getByTestId('overleaf-update').click();
	await expect(page.getByTestId('overleaf-said')).toHaveText('Up to date with Overleaf · checked just now.');

	// Cleo edits the second lemma in Overleaf; Update brings it, by name
	edit(clone, 'two sheets', 'three sheets', CLEO);
	await page.getByTestId('overleaf-update').click();
	await expect(page.getByTestId('overleaf-said')).toHaveText('Updated from Overleaf just now: 1 file changed, by Cleo Colleague.');
	expect(readFileSync(join(served.root, 'paper/paper.tex'), 'utf8')).toContain('three sheets');
	await page.keyboard.press('Escape');

	// Review lists the block Cleo changed, taken in from Overleaf
	await page.goto('/review');
	await page.getByTestId('review-kind-accepted-changed').click();
	await expect(page.locator('[data-testid="review-row"][data-kind="accepted-changed"]').filter({ hasText: 'paper.tex' }).filter({ hasText: /Overleaf/ })).not.toHaveCount(0);

	// the mirrored document's toolbar updates too, its answer under the toolbar
	await page.goto('/master/paper/paper');
	await page.getByTestId('toolbar-overleaf-update').click();
	await expect(page.getByTestId('overleaf-strip').locator('.said')).toHaveText('Up to date with Overleaf · checked just now.');
});

test('a suggestion on a mirrored document is copied, made in Overleaf, and kept by Done in Overleaf once Overleaf has it', async ({ page, served }) => {
	const clone = project(served);
	await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.goto('/');
	await pair(page);
	await page.keyboard.press('Escape');
	const said = JSON.parse(served.loom(['suggest', 'paper/paper.tex#lemma:1', '--quote', 'not planar', '--with', 'never planar', '--as', 'Claude Agent', '--json']));
	const id = String(said.edit);
	await expect.poll(() => (built(served).changes ?? []).some((c: { id: string }) => c.id === id), { timeout: 60_000 }).toBe(true);

	await page.goto('/review');
	const card = page.locator(`[data-testid="change-card"][data-change="${id}"]`);
	await shown(page, card);
	await expect(card.getByTestId('card-keep')).toHaveCount(0);
	await expect(card.getByTestId('change-card-why')).toHaveText('Its document mirrors Overleaf: make the change there, then choose Done in Overleaf.');
	await expect(card.getByTestId('card-discard')).toBeVisible();

	await card.getByTestId('change-copy-new').click();
	await expect(card.getByTestId('change-overleaf-said')).toHaveText('Copied. Paste it in Overleaf, then choose Done in Overleaf.');
	expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('never planar');

	// before Overleaf has it, nothing is kept and the file is as Overleaf holds it
	await card.getByTestId('change-done-in-overleaf').click();
	await expect(card.getByTestId('change-overleaf-said')).toHaveText('Overleaf does not have this change yet.');
	expect(readFileSync(join(served.root, 'paper/paper.tex'), 'utf8')).toContain('not planar');

	// made in Overleaf by the person, then Done in Overleaf keeps it: the update brings the words, the keep writes nothing more
	edit(clone, 'not planar', 'never planar', PAT);
	await card.getByTestId('change-done-in-overleaf').click();
	await expect(card).toHaveCount(0);
	await expect.poll(() => (built(served).changes ?? []).some((c: { id: string }) => c.id === id), { timeout: 60_000 }).toBe(false);
	expect(readFileSync(join(served.root, 'paper/paper.tex'), 'utf8')).toContain('never planar');
});
