// The connection chip at the column's foot, against a publisher `/_api` stands in for: it stands only where a stream says who is connected, at the foot in the open column and as a dot in the folded strip, and opens the panel of what an agent is told, sees and may change. The chip with a real `loom mcp` arriving and leaving is the write suite's (e2e-write/agents.e2e.ts).
import { expect, test, type Page } from '@playwright/test';
import { REFEREE, serve } from '../manifest';
import { settings } from '../workspace';

const RECORD = {
	format: 1,
	pid: 4242,
	ppid: 4200,
	as: 'Claude Code Agent',
	client: { name: 'claude-code', title: 'Claude Code', version: '2.1.321' },
	protocol: '2026-07-28',
	conversation: 'c-1',
	entrypoint: 'claude-desktop',
	session: REFEREE,
	loom: '0.1.0',
	started: '2026-11-20T14:00:00Z',
	last: null
};

/** A publisher whose stream is open and says nothing more: who is connected is what `/_api` said. */
async function publisher(page: Page, connected: unknown[], caps: string[] = []): Promise<void> {
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: caps, token: 't', stream: true, connected, root: '/Users/someone/quilt' } }));
	await page.route('**/_api/stream', () => new Promise(() => {}));
}

test('with no publisher there is no chip', async ({ page }) => {
	await page.goto('/master/drafting/main');
	await expect(page.getByTestId('legend-open')).toBeVisible();
	await expect(page.getByTestId('agent-chip')).toHaveCount(0);
});

test('the chip stands at the foot of the open column, under the legend, and opens the panel with the setup card', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 900 });
	await publisher(page, []);
	await page.goto('/master/drafting/main');
	const chip = page.getByTestId('agent-chip');
	await expect(chip).toBeInViewport();
	await expect(page.getByTestId('agent-chip-lead')).toHaveText('No agent connected');
	const at = (await chip.boundingBox())!;
	const legend = (await page.getByTestId('legend-open').boundingBox())!;
	const column = (await page.getByTestId('column').boundingBox())!;
	expect(at.y).toBeGreaterThan(legend.y);
	expect(at.y + at.height).toBeLessThanOrEqual(900);
	expect(column.y + column.height - (at.y + at.height)).toBeLessThan(2);
	// a reasonable size: one line and its sub-line at most, never a slab
	expect(at.height).toBeLessThanOrEqual(48);
	await chip.click();
	const panel = page.getByTestId('agent-panel');
	await expect(panel.getByTestId('agents-none')).toBeVisible();
	await expect(panel.getByTestId('agent-setup')).toBeVisible();
	await expect(panel).toContainText('What it may change');
	await expect(panel).toContainText('What it never does');
	// the files it may only read are a list, one to a line
	const readOnly = panel.getByTestId('agents-read-only').getByRole('listitem');
	await expect(readOnly).toHaveText([/^\.loom\/ \(but /, 'config.toml', 'research-state.md']);
	const tops = await readOnly.evaluateAll((els) => els.map((el) => el.getBoundingClientRect()));
	for (let i = 1; i < tops.length; i++) expect(tops[i].top).toBeGreaterThanOrEqual(tops[i - 1].bottom - 1);
	// what it sees says when it reads what you write, so a comment is known to reach it
	await expect(panel).toContainText('It reads what is new when its conversation starts');
	// and nothing in the viewer says whether a session is chosen
	await expect(page.locator('body')).not.toContainText(/session chosen|writing in/i);
});

test("What it is told says in words what the line in the app's file asks, and shows no command", async ({ page }) => {
	await serve(page, (m) => {
		m.config.agents.layer = true;
		m.agents.line = "This directory is a quilt managed by loom. Before doing anything, call `loom_ai_orient`, the tool of the loom MCP server, and follow it; if you have no loom tools, run `loom ai orient` in a shell instead, and `loom doctor` to tell the author why. Write anywhere but the paths the orientation names as protected.";
	});
	await publisher(page, []);
	await page.goto('/master/drafting/main');
	await page.getByTestId('agent-chip').click();
	const panel = page.getByTestId('agent-panel');
	await expect(panel.getByTestId('agents-line')).toContainText('ask loom how to work here');
	await expect(panel).not.toContainText(/loom_|loom ai|loom doctor/);
});

test("the panel's first heading follows who is connected: never Connected over no agent", async ({ page }) => {
	await publisher(page, []);
	await page.goto('/master/drafting/main');
	await page.getByTestId('agent-chip').click();
	const panel = page.getByTestId('agent-panel');
	await expect(panel.getByTestId('agents-none')).toBeVisible();
	await expect(panel.locator('h4').first()).toHaveText('Not connected');
});

for (const height of [900, 800])
	test(`at 760×${height} the panel opened from the folded dot keeps Use with Claude and Use with Codex in the window`, async ({ page }) => {
		await page.setViewportSize({ width: 760, height });
		// a quilt whose agents are told loom's line and held to its list, as the showcase is: the panel's longest
		await serve(page, (m) => {
			m.config.agents.layer = true;
			m.agents.line = 'This directory is a quilt managed by loom.';
			m.config.agents.holds = 'In the places agents are denied, Claude Code is refused an edit, though whether a command it runs in a shell is held back as well depends on the command and on how you have set it up; Codex, Gemini CLI, Cursor and any other app are only asked not to edit, and a change one of them makes there anyway is not listed in Your Changes.';
		});
		await publisher(page, [], ['agents-setup']);
		await page.goto('/master/drafting/main');
		await page.getByTestId('agent-chip').click();
		for (const id of ['use-claude-code', 'use-codex']) await expect(page.getByTestId(id)).toBeInViewport({ ratio: 1 });
		// read to the panel's end, as a person reads what it sees and may change, and the buttons stay in view and take a click
		await page.getByTestId('agent-popover').evaluate((el) => (el.scrollTop = el.scrollHeight));
		await expect(page.getByTestId('agent-panel')).toContainText('What it never does');
		expect(await page.getByTestId('agent-popover').evaluate((el) => el.scrollTop)).toBeGreaterThan(100);		for (const id of ['use-claude-code', 'use-codex']) {
			await expect(page.getByTestId(id)).toBeInViewport({ ratio: 1 });
			await page.getByTestId(id).click({ trial: true, timeout: 2000 });
		}
	});

test('folded, the chip is its dot inside the strip, its words its hover text', async ({ page }) => {
	await page.setViewportSize({ width: 1100, height: 900 });
	await publisher(page, [RECORD]);
	await page.goto('/master/drafting/main');
	await expect(page.locator('.panel.away')).toHaveCount(1);
	const chip = page.getByTestId('agent-chip');
	await expect(chip).toHaveAttribute('title', 'Claude Code connected, no call yet');
	await expect(page.getByTestId('agent-chip-lead')).toHaveCount(0);
	const dot = (await chip.boundingBox())!;
	const strip = (await page.getByTestId('column').boundingBox())!;
	expect(dot.y + dot.height).toBeLessThanOrEqual(900);
	expect(dot.x).toBeGreaterThanOrEqual(strip.x);
	expect(dot.x + dot.width).toBeLessThanOrEqual(strip.x + strip.width);
});

test('a connected conversation is named with its app, where it was started and its report in Review › History', async ({ page }) => {
	await publisher(page, [RECORD]);
	await page.goto('/master/drafting/main');
	await expect(page.getByTestId('agent-chip-lead')).toHaveText('Claude Code connected');
	await expect(page.getByTestId('agent-chip-sub')).toHaveText('no call yet');
	await page.getByTestId('agent-chip').click();
	const record = page.getByTestId('agent-record');
	await expect(record).toContainText('Claude Code');
	await expect(record).toContainText('in the Claude app');
	await expect(record).toContainText('Writes as Claude Code Agent');
	await expect(record.getByTestId('agent-last')).toHaveText('No call yet.');
	await expect(record.getByTestId('agent-session')).toHaveText('referee');
	await expect(record.getByTestId('agent-session')).toHaveAttribute('href', new RegExp(`/session/${REFEREE}$`));
	await expect(page.getByTestId('agent-setup')).toHaveCount(0);
});

test('Settings › Agents offers the setup card and Set up beside an app not set up, where loom can set one up', async ({ page }) => {
	await serve(page, (m) => {
		m.config.agents.layer = true;
		m.config.agents.variant = 'mcp';
	});
	await publisher(page, [], ['agents-setup', 'config-save']);
	await page.goto('/master/drafting/main');
	await settings(page, 'agents');
	await expect(page.getByTestId('use-claude-code')).toHaveText('Use with Claude');
	await expect(page.getByTestId('use-codex')).toHaveText('Use with Codex');
	await expect(page.getByTestId('agents-apps').getByRole('button', { name: 'Set up' }).first()).toBeVisible();
	await expect(page.getByTestId('settings-window')).not.toContainText('loom ai init');
	await expect(page.getByTestId('settings-window')).toContainText('What it sees');
});

test("Ask your agent stands on a document's toolbar, a reasonable size, about the document or the result at the top of the pane, with a mode from the quilt's own", async ({ page }) => {
	await page.goto('/master/drafting/main');
	const ask = page.getByTestId('item-controls').first().getByTestId('toolbar-ask');
	await expect(ask).toBeVisible();
	const box = (await ask.boundingBox())!;
	expect(box.height).toBeGreaterThanOrEqual(20);
	expect(box.height).toBeLessThanOrEqual(32);
	await ask.click();
	const request = page.getByTestId('ask-request');
	await expect(request).toContainText('(quilt:drafting/main.tex');
	// the document is always a choice; the result at the pane's top comes first when there is one
	const about = page.locator('[data-testid^="ask-about-"]');
	if (await about.count()) await page.getByTestId(`ask-about-${(await about.count()) - 1}`).check();
	await expect(request).toHaveText('In loom, look at main.tex (quilt:drafting/main.tex).');
	const mode = page.getByTestId('ask-mode');
	const first = await mode.locator('option').nth(1).getAttribute('value');
	await mode.selectOption(first!);
	await expect(request).toHaveText(`In loom, work in the ${first} mode on main.tex (quilt:drafting/main.tex).`);
	await expect(page.getByTestId('ask-fits')).not.toBeEmpty();
	// with no publisher, nothing opens Claude
	await expect(page.getByTestId('ask-copy-open')).toHaveCount(0);
	await page.keyboard.press('Escape');
	await expect(page.getByTestId('ask-agent')).toHaveCount(0);
});

test("Ask your agent on a document's toolbar offers the words selected first, at their result, under the number that document shows", async ({ page }) => {
	await page.goto('/master/drafting/talk');
	// Lemma 1.2 in main.tex is Lemma 3 in the talk
	const lemma = page.locator('.fragment .env[data-id="sy-0002"] p[data-src]').first();
	await lemma.scrollIntoViewIfNeeded();
	await lemma.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	await page.getByTestId('item-controls').first().getByTestId('toolbar-ask').click();
	await expect(page.getByTestId('ask-about-0')).toBeChecked();
	await expect(page.locator('label', { has: page.getByTestId('ask-about-0') })).toHaveText('The words you selected in Lemma 3');
	await expect(page.getByTestId('ask-request')).toContainText('In loom, look at talk.tex, Lemma 3 (quilt:drafting/talk.tex#sy-0002), at the words “');
});

test('what Ask your agent copies quotes the words as the reader sees them: math as written, a reference as drawn, never its command', async ({ page }) => {
	await page.goto('/master/drafting/main');
	const proof = page.locator('.fragment p[data-src^="drafting/nodes/sy-0003.tex:437:"]').first();
	await proof.scrollIntoViewIfNeeded();
	await proof.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	await page.getByTestId('item-controls').first().getByTestId('toolbar-ask').click();
	await expect(page.getByTestId('ask-about-0')).toBeChecked();
	const request = page.getByTestId('ask-request');
	await expect(request).toContainText('the permutation $\\sigma$ directly, using (3) from the proof of Lemma 1.2 and Definition 1.1.');
	await expect(request).not.toContainText(/\\(ref|eqref|cite)\{/);
});

test("Ask your agent on a result's own page is about the result", async ({ page }) => {
	await page.goto('/node/sy-0003');
	await page.getByTestId('toolbar-ask').click();
	await expect(page.locator('[data-testid^="ask-about-"]')).toHaveCount(0);
	await expect(page.getByTestId('ask-request')).toHaveText(/^In loom, look at .+ \(quilt:sy-0003\)\.$/);
});
