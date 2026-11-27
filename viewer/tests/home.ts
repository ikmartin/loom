// The home page's tests run the real viewer against a real `loom app`, the home server, in a home folder of the test's own: HOME, the XDG folders and the temporary folder are under the suite's scratch directory, so nothing the home keeps for the machine (its list of quilts, its drops, a saved name) reaches the person's, and a quilt the test makes goes in that home's `~/Quilts`. The quilts the home serves are given ports from 9000, past the ports a person's own home gives.

import { test as base, expect } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { createWriteStream, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { LOOM, VIEWER, scratchDir, suiteOf } from './served';
import { patient } from './sites';

/** The variables by which loom tells an agent's shell (`loom.identity.AGENT_MARKERS`): a home started from an agent's shell would take the person for an agent. */
const AGENT_MARKERS = ['AI_AGENT', 'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CODEX_SANDBOX', 'CURSOR_AGENT', 'GEMINI_CLI'];

/** One running home. */
export interface Homed {
	/** Where it answers, with a trailing slash. */
	url: string;
	/** The test's home folder, which the home's `~` is. */
	folder: string;
	/** POST to one of the home's endpoints with its token; the status and the answer. */
	call(endpoint: string, body?: Record<string, unknown>): Promise<{ status: number; said: Record<string, unknown> }>;
}

/** Loom's folder for the machine under `home`, as `loom.machine.data_dir` finds it. */
function machineFolder(home: string, env: NodeJS.ProcessEnv): string {
	return process.platform === 'darwin' ? join(home, 'Library', 'Application Support', 'loom') : join(env.XDG_DATA_HOME!, 'loom');
}

/**
 * Start `loom app` on a free port in a home folder of its own.
 *
 * `name` is the folder under the suite's scratch directory; `author`, when given, is saved as the person's name, else none is known (no git name either, since git's global config is under the same home).
 */
export async function startHome(scratch: string, name: string, author?: string): Promise<{ homed: Homed; stop(): Promise<void>; log: string }> {
	const dir = join(scratch, 'homes', name);
	rmSync(dir, { recursive: true, force: true });
	const folder = join(dir, 'home');
	const env: NodeJS.ProcessEnv = {
		...process.env,
		HOME: folder,
		XDG_CONFIG_HOME: join(dir, 'config'),
		XDG_DATA_HOME: join(folder, '.local', 'share'),
		XDG_CACHE_HOME: join(folder, '.cache'),
		XDG_STATE_HOME: join(folder, '.local', 'state'),
		TMPDIR: join(dir, 'tmp'),
		LOOM_VIEWER_BUNDLE: join(scratch, 'bundle')
	};
	for (const marker of AGENT_MARKERS) delete env[marker];
	for (const d of [folder, env.XDG_CONFIG_HOME!, env.TMPDIR!]) mkdirSync(d, { recursive: true });
	if (author) {
		mkdirSync(join(env.XDG_CONFIG_HOME!, 'loom'), { recursive: true });
		writeFileSync(join(env.XDG_CONFIG_HOME!, 'loom', 'config.toml'), `[author]\nname = ${JSON.stringify(author)}\n`);
	}
	// every port below 9000 counted as given, so the test's quilts keep clear of a person's own
	const app = join(machineFolder(folder, env), 'app');
	mkdirSync(app, { recursive: true });
	writeFileSync(join(app, 'quilts.json'), JSON.stringify({ quilts: [], given: Array.from({ length: 200 }, (_, i) => 8800 + i) }) + '\n');
	const log = join(dir, 'app.log');
	const out = createWriteStream(log, { flags: 'a' });
	const proc: ChildProcess = spawn(LOOM, ['app', '--port', '0'], { cwd: VIEWER, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
	proc.stdout!.pipe(out);
	proc.stderr!.pipe(out);
	let exited = false;
	const gone = new Promise<void>((r) => proc.once('exit', () => ((exited = true), r())));
	const stop = async () => {
		if (!exited) {
			// the home's own stop: it stops every quilt it serves, then exits
			process.kill(proc.pid!, 'SIGTERM');
			const late = setTimeout(() => {
				try {
					process.kill(-proc.pid!, 'SIGKILL');
				} catch {
					/* gone */
				}
			}, 20_000);
			await gone;
			clearTimeout(late);
		}
		out.end();
	};
	const deadline = Date.now() + patient.timeout;
	let url = '';
	while (!exited && Date.now() < deadline && !url) {
		const said = existsSync(log) ? readFileSync(log, 'utf8') : '';
		url = /loom app: (http:\/\/127\.0\.0\.1:\d+\/)/.exec(said)?.[1] ?? '';
		if (!url) await new Promise((r) => setTimeout(r, 50));
	}
	if (!url) {
		await stop();
		throw new Error(`loom app never answered:\n${existsSync(log) ? readFileSync(log, 'utf8') : ''}`);
	}
	const token = ((await (await fetch(url + '_api')).json()) as { token: string }).token;
	const homed: Homed = {
		url,
		folder,
		async call(endpoint, body = {}) {
			const res = await fetch(`${url}_api/${endpoint}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', 'X-Loom-Token': token },
				body: JSON.stringify(body)
			});
			return { status: res.status, said: (await res.json()) as Record<string, unknown> };
		}
	};
	return { homed, stop, log };
}

interface Fixtures {
	/** The person's name the home starts with; none by default. */
	author: string | undefined;
	homed: Homed;
}

/** A test with a home of its own, its page at `baseURL`. */
export const test = base.extend<Fixtures>({
	author: [undefined, { option: true }],
	homed: [
		async ({ author }, use, info) => {
			const scratch = scratchDir(suiteOf(info));
			const name = `${info.testId}-${info.retry}`;
			const running = await startHome(scratch, name, author);
			await use(running.homed);
			await running.stop();
			if (info.status !== info.expectedStatus) await info.attach('loom app', { path: running.log, contentType: 'text/plain' });
			else rmSync(join(scratch, 'homes', name), { recursive: true, force: true });
		},
		{ timeout: patient.timeout }
	],
	baseURL: async ({ homed }, use) => {
		await use(homed.url);
	}
});

export { expect };
