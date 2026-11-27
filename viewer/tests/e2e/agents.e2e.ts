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

test("Ask your agent on a result's own page is about the result", async ({ page }) => {
	await page.goto('/node/sy-0003');
	await page.getByTestId('toolbar-ask').click();
	await expect(page.locator('[data-testid^="ask-about-"]')).toHaveCount(0);
	await expect(page.getByTestId('ask-request')).toHaveText(/^In loom, look at .+ \(quilt:sy-0003\)\.$/);
});
