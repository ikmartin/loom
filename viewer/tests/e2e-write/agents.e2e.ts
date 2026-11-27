// Attaching an agent, from the viewer, under a running `loom serve`: the chip says an agent is connected only while a real `loom mcp` lives, whether it ends by a signal or is killed outright; the panel names the conversation's report; the setup card sets the synthetic quilt, which has no agent layer, up for Claude Code alone and says to trust the folder; and Ask your agent copies a request naming the place and the mode.
import { spawn, type ChildProcess } from 'node:child_process';
import { existsSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import type { Page, TestInfo } from '@playwright/test';
import { expect, LOOM, readOnly, reviewerEnv, suiteOf, test, type Served } from '../served';
import { settings } from '../workspace';

/** What Claude Code 2.1 puts in every request's `_meta`, since it sends no `initialize`. */
const META = {
	'io.modelcontextprotocol/protocolVersion': '2026-07-28',
	'io.modelcontextprotocol/clientInfo': { name: 'claude-code', title: 'Claude Code', version: '2.1.321' },
	'io.modelcontextprotocol/clientCapabilities': {}
};

/** One `loom mcp` started in the served copy as an agent's app starts it, spoken to in raw JSON-RPC lines. */
interface Agent {
	proc: ChildProcess;
	request(method: string, params?: Record<string, unknown>): Promise<Record<string, unknown>>;
	/** Send `sig` and wait for the process to end. */
	stop(sig: NodeJS.Signals): Promise<void>;
}

function attach(served: Served, info: TestInfo, name = 'Claude Code Agent'): Agent {
	const env = { ...reviewerEnv(suiteOf(info), `${served.root}.agent`), CLAUDE_CODE_SESSION_ID: `conversation-${info.testId}`, CLAUDE_CODE_ENTRYPOINT: 'claude-desktop' };
	const proc = spawn(LOOM, ['mcp', '--as', name, '--quilt', served.root], { env, stdio: ['pipe', 'pipe', 'ignore'] });
	const waiting = new Map<number, (got: Record<string, unknown>) => void>();
	createInterface({ input: proc.stdout! }).on('line', (line) => {
		try {
			const got = JSON.parse(line) as Record<string, unknown>;
			waiting.get(got.id as number)?.(got);
		} catch {
			// a line that is not an answer
		}
	});
	const ended = new Promise<void>((r) => proc.once('exit', () => r()));
	let next = 0;
	return {
		proc,
		request(method, params = {}) {
			const id = ++next;
			const answered = new Promise<Record<string, unknown>>((r) => waiting.set(id, r));
			proc.stdin!.write(JSON.stringify({ jsonrpc: '2.0', id, method, params: { ...params, _meta: META } }) + '\n');
			return answered;
		},
		async stop(sig) {
			if (proc.exitCode === null && proc.signalCode === null) proc.kill(sig);
			await ended;
		}
	};
}

const chip = (page: Page) => page.getByTestId('agent-chip');
const live = (served: Served) => join(served.root, '.loom/local/live');

test('the chip says an agent is connected only while its server lives, whether it ends on a signal or is killed', async ({ page, served }, info) => {
	await page.goto('/');
	await expect(chip(page)).toContainText('No agent connected');

	const first = attach(served, info);
	try {
		await first.request('server/discover');
		await expect(chip(page)).toContainText('Claude Code connected');
		await expect(page.getByTestId('agent-chip-sub')).toHaveText('no call yet');
		await first.request('tools/call', { name: 'loom_since', arguments: {} });
		await expect(page.getByTestId('agent-chip-sub')).toHaveText('active · last call just now');
		await expect(chip(page)).toHaveAttribute('data-tone', 'active');
		// the panel says what it is and did
		await chip(page).click();
		const record = page.getByTestId('agent-record');
		await expect(record).toHaveCount(1);
		await expect(record).toContainText('Claude Code');
		await expect(record).toContainText('in the Claude app');
		await expect(record).toContainText('Writes as Claude Code Agent');
		await expect(page.getByTestId('agent-last')).toContainText('Last call just now: the since tool.');
		// its session is its report, a link to its transcript, and nothing says whether a session is chosen
		await expect(page.getByTestId('agent-session')).toHaveAttribute('href', /\/session\/s-/);
		await expect(page.locator('body')).not.toContainText(/session chosen|writing in/i);
		await page.keyboard.press('Escape');
	} finally {
		await first.stop('SIGTERM');
	}
	// ended as Claude Code ends a conversation: its record goes, and the chip with it
	await expect(chip(page)).toContainText('No agent connected');

	const killed = attach(served, info);
	await killed.request('server/discover');
	await expect(chip(page)).toContainText('Claude Code connected');
	await killed.stop('SIGKILL');
	// killed outright, its record is left unheld, and the server's next look takes it off the list and off the disk
	await expect(chip(page)).toContainText('No agent connected');
	await expect.poll(() => existsSync(join(live(served), `${killed.proc.pid}.json`))).toBe(false);
});

test('two conversations are counted, and the one left is still connected when the other ends', async ({ page, served }, info) => {
	await page.goto('/');
	const a = attach(served, info);
	const b = attach(served, info);
	try {
		await Promise.all([a.request('server/discover'), b.request('server/discover')]);
		await expect(chip(page)).toContainText('Claude Code · 2 conversations');
		await a.stop('SIGINT');
		await expect(chip(page)).toContainText('Claude Code connected');
	} finally {
		await a.stop('SIGKILL');
		await b.stop('SIGKILL');
	}
	await expect(chip(page)).toContainText('No agent connected');
});

test('the setup card sets a quilt with no agent layer up for Claude Code alone, says to trust the folder, and says when Claude Code connects', async ({ page, served }, info) => {
	await page.goto('/');
	await chip(page).click();
	await expect(page.getByTestId('agents-none')).toBeVisible();
	expect(existsSync(join(served.root, 'CLAUDE.md'))).toBe(false);
	await page.getByTestId('use-claude-code').click();
	const card = page.getByTestId('setup-claude-code');
	await expect(card).toBeVisible();
	for (const file of ['CLAUDE.md', '.claude/settings.json', '.mcp.json']) expect(existsSync(join(served.root, file)), file).toBe(true);
	// Claude Code's alone: no other app's server file
	for (const file of ['.codex/config.toml', '.gemini/settings.json', '.cursor/mcp.json']) expect(existsSync(join(served.root, file)), file).toBe(false);
	expect(readFileSync(join(served.root, '.mcp.json'), 'utf8')).toContain('"loom"');
	await expect(page.getByTestId('setup-wrote')).toContainText('CLAUDE.md');
	await expect(card).toContainText('trust this folder');
	await expect(card).toContainText("applies none of loom's permissions");
	await expect(page.getByTestId('setup-root')).toHaveText(realpathSync(served.root));
	await expect(page.getByTestId('setup-waiting')).toHaveText('Waiting for Claude Code…');
	await page.keyboard.press('Escape');

	// Settings › Agents shows the same card, and says when the app's first conversation starts loom here
	await settings(page, 'agents');
	await expect(page.getByTestId('setting-agents.apps').getByText('Set up').first()).toBeVisible();
	const agent = attach(served, info);
	try {
		await agent.request('server/discover');
		await expect(page.getByTestId('setup-connected')).toContainText('Connected: Claude Code at');
	} finally {
		await agent.stop('SIGTERM');
	}
	await expect(page.getByTestId('setup-waiting')).toBeVisible();
});

readOnly('Ask your agent copies a request naming the result, its link and the mode, and from a selection the words', async ({ page, context }) => {
	await context.grantPermissions(['clipboard-read', 'clipboard-write']);
	await page.goto('/node/sy-0008');
	await expect(page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"]')).toBeVisible();
	await page.getByTestId('toolbar-ask').click();
	const request = page.getByTestId('ask-request');
	await expect(request).toContainText('In loom, look at');
	await expect(request).toContainText('(quilt:sy-0008).');
	await page.getByTestId('ask-mode').selectOption('referee');
	await expect(page.getByTestId('ask-fits')).not.toBeEmpty();
	await page.getByTestId('ask-words').fill('Is the second step right?');
	await expect(request).toContainText('In loom, work in the referee mode on');
	const text = (await request.textContent())!;
	expect(text.endsWith('\n\nIs the second step right?')).toBe(true);
	await page.getByTestId('ask-copy').click();
	await expect(page.getByTestId('ask-agent')).toHaveCount(0);
	expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(text);

	// from a selection: the words, quoted
	const words = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"] > p[data-src]').first();
	await words.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		window.getSelection()?.removeAllRanges();
		window.getSelection()?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	await page.getByTestId('selection-actions').click();
	await page.getByTestId('selection-ask').click();
	await expect(request).toContainText('at the words “');
	await expect(request).toContainText('(quilt:sy-0008)');
});
