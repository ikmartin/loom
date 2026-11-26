// Notes as files (`docs/design/model.md`, "Notes"): New note in an item's toolbar, for the whole item, and Settings › Notes, whose folder is the quilt's and whose command is the person's own. The actions at a selection are in annotations.e2e.ts.
import { expect, test, type Page } from '@playwright/test';
import { settings } from '../workspace';
import { serveKept } from '../manifest';

/** A publisher serving `caps`, whose answers are recorded by endpoint; `notes-settings` keeps the command it is sent, as loom does. */
async function publisher(page: Page, caps: string[]): Promise<Record<string, Record<string, unknown>[]>> {
	const sent: Record<string, Record<string, unknown>[]> = {};
	let command = 'emacsclient -n {request}';
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: caps, token: 't' } }));
	await page.route('**/_api/*', (r) => {
		const endpoint = new URL(r.request().url()).pathname.split('/').pop() ?? '';
		const body = r.request().postDataJSON() as Record<string, unknown>;
		(sent[endpoint] ??= []).push(body);
		if (endpoint === 'notes-settings') {
			if (typeof body.command === 'string') command = body.command;
			return r.fulfill({ json: { ok: true, result: 'notes settings', command, kept: '/Users/someone/.config/loom/notes.toml' } });
		}
		if (endpoint === 'new-note') return r.fulfill({ json: { ok: true, result: 'wrote notes/2026-11-26-main-tex.md', how: 'wrote', path: 'notes/2026-11-26-main-tex.md' } });
		return r.fulfill({ json: { ok: true, result: 'done' } });
	});
	return sent;
}

// the config as this loom publishes it, whether or not the committed fixture was built by one: the folder New note uses is a setting Settings may change
test.beforeEach(({ page }) =>
	serveKept(page, (m) => {
		if (!m.config) return;
		m.config.notes ??= { dir: '', default: 'notes' };
		if (!m.config.editable.includes('notes.dir')) m.config.editable.push('notes.dir');
	})
);

test('New note in a document toolbar is given the whole document, and says where a Markdown note was written', async ({ page }) => {
	const sent = await publisher(page, ['annotate', 'new-note']);
	await page.goto('/master/drafting/main');
	const button = page.getByTestId('item-controls').first().getByTestId('toolbar-new-note');
	await expect(button).toHaveText('New note');
	// a reasonable size: as tall as the toolbar's other controls
	expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(22);
	await button.click();
	await expect.poll(() => sent['new-note']?.[0]).toMatchObject({ link: 'quilt:drafting/main.tex', quote: '' });
	expect(String(sent['new-note'][0].title)).toContain('main');
	await expect(page.getByTestId('toast')).toContainText('New note: notes/2026-11-26-main-tex.md');
});

test('New note is not offered where no publisher runs it', async ({ page }) => {
	await publisher(page, ['annotate']);
	await page.goto('/master/drafting/main');
	await expect(page.getByTestId('item-controls').first().getByTestId('toggle-annotation-row')).toBeVisible();
	await expect(page.getByTestId('toolbar-new-note')).toHaveCount(0);
});

test("Settings › Notes: the folder is the quilt's, saved with its settings; the command is the person's, saved at once and never to config.toml", async ({ page }) => {
	const sent = await publisher(page, ['settings-save', 'notes-settings', 'new-note']);
	await page.goto('/master/drafting/main');
	await settings(page, 'notes');
	await expect(page.getByTestId('settings-window')).toContainText('it never travels with the quilt, and an agent cannot set it');
	// the command the person keeps for this quilt is read, and where it is kept said
	const command = page.getByTestId('notes-command');
	await expect(command).toHaveValue('emacsclient -n {request}');
	await expect(page.getByTestId('notes-command-kept')).toContainText('notes.toml');
	await command.fill("emacsclient -n -e '(my-new-note \"{request}\")'");
	await page.getByTestId('notes-command-save').click();
	await expect.poll(() => sent['notes-settings']?.at(-1)).toEqual({ command: "emacsclient -n -e '(my-new-note \"{request}\")'" });
	await expect(page.getByTestId('notes-command-save')).toBeDisabled();
	// the folder is picked from the quilt's own folders, and waits for Save as every quilt setting does
	const folder = page.getByTestId('config-notes.dir');
	await expect(folder.locator('option').first()).toHaveText('notes/ (the default)');
	await folder.selectOption('drafting');
	await page.getByTestId('settings-save').click();
	await expect.poll(() => sent['settings-save']?.[0]).toEqual({ changes: { 'notes.dir': 'drafting' } });
	expect(JSON.stringify(sent['settings-save'])).not.toContain('emacsclient');
});
