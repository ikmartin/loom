// Lean on this computer, against a publisher the routes stand in for: Settings › Lean turns it on with the person's switch and follows the install in the viewer's words, Check again runs loom's check there and beside a result's Lean in the Web, a refusal is said in the viewer's words, and a page with no publisher says it is shown as published.
import { expect, test, type Page } from '@playwright/test';
import { settings } from '../workspace';

interface Job {
	kind: 'install' | 'check';
	state: 'running' | 'done' | 'failed';
	step: string;
	said: string;
	found: Record<string, unknown>;
}

/** A publisher serving the three formal endpoints over `state`, recording each write's body; each read of a running job moves it one step, and the last ends it as `ending` says. */
async function publisher(page: Page, refuse?: { code: string; status: number }) {
	const asked: { endpoint: string; body: Record<string, unknown> }[] = [];
	const state: { on: boolean; project: string | null; fence: string | null; job: Job | null } = { on: false, project: null, fence: null, job: null };
	let steps: string[] = [];
	let ending: Partial<Job> = {};
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: ['formal-state', 'formal-enable', 'formal-check'], token: 't', stream: true } }));
	await page.route('**/_api/stream', () => new Promise(() => {}));
	await page.route('**/_api/formal-*', async (route) => {
		const endpoint = route.request().url().split('/').pop()!;
		const body = route.request().postDataJSON() ?? {};
		if (endpoint === 'formal-state') {
			if (state.job?.state === 'running') {
				if (steps.length) state.job.step = steps.shift()!;
				else Object.assign(state.job, ending);
			}
			return route.fulfill({ json: { ok: true, ...state } });
		}
		asked.push({ endpoint, body });
		if (refuse) return route.fulfill({ status: refuse.status, json: { ok: false, error: { code: refuse.code, message: 'loom’s own words, never drawn' } } });
		if (endpoint === 'formal-enable') {
			state.on = body.on === true;
			if (state.on) {
				state.job = { kind: 'install', state: 'running', step: '', said: '', found: {} };
				steps = ['toolchain', 'mathlib'];
				state.project = 'lean';
				ending = { state: 'done', found: { steps: [{ step: 'toolchain', seconds: 30 }, { step: 'mathlib', seconds: 150 }] } };
			}
		} else {
			state.job = { kind: 'check', state: 'running', step: '', said: '', found: {} };
			steps = ['build', 'probe'];
			ending = { state: 'done', found: { written: ['lem:a'], unchanged: ['thm:b', 'thm:c'], unknown: [], errors: [] } };
		}
		return route.fulfill({ json: { ok: true, result: 'loom’s own words, never drawn' } });
	});
	return { asked, state };
}

test('the switch turns Lean on, the install is followed step by step in the viewer’s words, and Check again runs the check', async ({ page }) => {
	const served = await publisher(page);
	await page.goto('/');
	await settings(page, 'lean');
	await expect(page.getByTestId('settings-title')).toHaveText('Lean');
	await expect(page.getByTestId('settings-window').locator('.where')).toContainText('never in the quilt');
	await expect(page.getByTestId('setting-lean.on')).toContainText('loom runs Lean itself');
	await expect(page.getByTestId('settings-read-only')).toHaveCount(0);
	const toggle = page.getByTestId('lean-switch');
	await expect(toggle).not.toBeChecked();
	await expect(page.getByTestId('lean-check')).toHaveCount(0);

	await toggle.click();
	await expect.poll(() => served.asked).toEqual([{ endpoint: 'formal-enable', body: { on: true } }]);
	const lines = page.getByTestId('lean-install-lines');
	await expect(lines).toContainText('Installing Lean: fetching Mathlib, about 1.3 GB the first time…');
	await expect(lines).toContainText('Lean is installed. That took 3 minutes.');
	await expect(page.getByTestId('lean-standing')).toHaveText('On. The Lean project is in lean/.');
	await expect(toggle).toBeChecked();

	// Check again, a button of a reasonable size, runs loom's check and says what it recorded
	const again = page.getByTestId('lean-check');
	const box = (await again.boundingBox())!;
	expect(box.height).toBeGreaterThanOrEqual(26);
	await again.click();
	await expect.poll(() => served.asked.at(-1)?.endpoint).toBe('formal-check');
	await expect(page.getByTestId('lean-check-lines')).toHaveText('Checked. 1 result recorded anew, 2 results as before.');
	await expect(page.getByTestId('settings-window')).not.toContainText('never drawn');

	await toggle.click();
	await expect.poll(() => served.asked.at(-1)).toEqual({ endpoint: 'formal-enable', body: { on: false } });
	await expect(toggle).not.toBeChecked();
	await expect(page.getByTestId('lean-check')).toHaveCount(0);
});

test('a refusal of the switch is said in the viewer’s words beside it', async ({ page }) => {
	await publisher(page, { code: 'author-only', status: 403 });
	await page.goto('/');
	await settings(page, 'lean');
	await page.getByTestId('lean-switch').click();
	await expect(page.getByTestId('setting-lean.on').getByTestId('setting-refused')).toHaveText('Only a person can do this; loom does not take it from an agent.');
	await expect(page.getByTestId('lean-switch')).not.toBeChecked();
});

test('with no publisher, Settings › Lean says it is shown as published', async ({ page }) => {
	await page.goto('/');
	await settings(page, 'lean');
	await expect(page.getByTestId('lean-not-served')).toHaveText('Shown as published. Turning Lean on needs loom serving this quilt.');
	await expect(page.getByTestId('lean-switch')).toHaveCount(0);
});

test('beside a result’s Lean in the Web, Check again runs loom’s check where Lean is on here', async ({ page }) => {
	const served = await publisher(page);
	served.state.on = true;
	served.state.project = 'lean';
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/web?fixture=round6');
	const row = page.getByTestId('web-list').getByTestId('web-row').filter({ hasText: 'Theorem 3.1' }).first();
	await row.click();
	const card = page.getByTestId('web-focus');
	await card.getByRole('button', { name: 'proofs, Lean, and its record' }).click();
	await expect(card).toContainText('Showcase.rank_cycleSpace');
	await card.getByTestId('focus-check-again').click();
	await expect.poll(() => served.asked.at(-1)?.endpoint).toBe('formal-check');
	await expect(card.getByTestId('focus-check-said')).toHaveText('Checked. 1 result recorded anew, 2 results as before.');
});
