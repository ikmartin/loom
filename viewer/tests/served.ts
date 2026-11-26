// The write and reading suites run the real viewer against a real `loom serve`, on a copy of one of loom's committed quilts (the config's `metadata.quilt`). `test` gives each test its own copy and its own server, so what one test writes no other test sees; `readOnly` shares one per worker, for tests that write nothing. `served-setup.ts` builds the bundle and the pristine copy once per run.

import { test as base, expect, type TestInfo } from '@playwright/test';
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cpSync, createWriteStream, existsSync, readdirSync, readFileSync, realpathSync, rmSync, mkdirSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:net';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { patient } from './sites';

/** What a config says about its quilt, in `metadata`. */
export interface Suite {
	/** The quilt under `loom/tests/quilts/`. */
	quilt: string;
	/** Scratch directory, relative to `viewer/`, for the bundle, the pristine copy and every served copy. */
	scratch: string;
}

export const VIEWER = fileURLToPath(new URL('..', import.meta.url));
export const LOOM = join(VIEWER, '../loom/.venv/bin/loom');
/** The variables by which loom tells an agent's shell (`loom.identity.AGENT_MARKERS`). */
const AGENT_MARKERS = ['AI_AGENT', 'CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CODEX_SANDBOX', 'CURSOR_AGENT', 'GEMINI_CLI'];

export type Entry = Record<string, unknown>;

/** One running `loom serve` over one quilt copy. */
export interface Served {
	/** The copy's root, absolute. */
	root: string;
	/** Where it answers, with no trailing slash. */
	url: string;
	/** The annotation log, parsed. */
	log(): Entry[];
	/** The one `created` entry whose body is exactly `body`; fails if there is not exactly one. */
	written(body: string): Entry;
	/** Open sessions, oldest first, from the copy's own session index. */
	openSessions(): string[];
	/** POST to the write API with the served token; returns the publisher's `result`, and fails on a refusal. */
	api(endpoint: string, body: Record<string, unknown>): Promise<string>;
	/** POST to the write API with the served token; returns the publisher's whole answer, and fails on a refusal. */
	answer(endpoint: string, body: Record<string, unknown>): Promise<Record<string, unknown>>;
	/** Run the loom CLI against this copy; returns stdout. */
	loom(args: string[], env?: Record<string, string>): string;
}

export function suiteOf(info: { config: { metadata: Record<string, unknown> } }): Suite {
	const { quilt, scratch } = info.config.metadata as Partial<Suite>;
	if (!quilt || !scratch) throw new Error('the config names no metadata.quilt and metadata.scratch');
	return { quilt, scratch };
}

/** A document's compile folder in a copy of the quilt, as loom names it (`loom.paths.document_build`): its file name without `.tex`, then eight hex digits of the SHA-256 of its path without `.tex`. */
export function compileFolder(root: string, doc: string): string {
	const name = doc.replace(/\.tex$/, '');
	return join(root, '.loom/cache/tex', `${name.split('/').pop()}-${createHash('sha256').update(name).digest('hex').slice(0, 8)}`);
}

/** A work in a copy of the quilt's library, by the key its entry has: its reference's id and the path of the PDF it holds, read off its node (`specs/nodes.md` §7); null for a key no reference has. */
export function workOf(root: string, key: string): { ref: string; pdf: string | null } | null {
	const dir = join(root, '.loom/library/nodes');
	for (const name of readdirSync(dir).filter((n) => n.endsWith('-ref.node'))) {
		const text = readFileSync(join(dir, name), 'utf8');
		if (!new RegExp(`^@\\w+\\{${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')},`, 'm').test(text)) continue;
		const ref = /^id = "([^"]+)"$/m.exec(text)![1];
		const pdf = /^pdf = "sha256:([0-9a-f]{64})"$/m.exec(text)?.[1];
		return { ref, pdf: pdf ? join(root, '.loom/library/documents', `${pdf}.pdf`) : null };
	}
	return null;
}

export function scratchDir(suite: Suite): string {
	return join(VIEWER, suite.scratch);
}

function freePort(): Promise<number> {
	return new Promise((resolve, reject) => {
		const srv = createServer();
		srv.once('error', reject);
		srv.listen(0, '127.0.0.1', () => {
			const port = (srv.address() as { port: number }).port;
			srv.close(() => resolve(port));
		});
	});
}

/** Where the server on `root`, started with `env`, keeps its write token: outside the quilt, in the machine's place under that environment's home, by the quilt's resolved path (`loom.machine.token_file`). */
function tokenFile(root: string, env: NodeJS.ProcessEnv): string {
	const home = env.HOME!;
	const data = process.platform === 'darwin' ? join(home, 'Library', 'Application Support') : env.XDG_DATA_HOME || join(home, '.local', 'share');
	return join(data, 'loom', 'tokens', `${createHash('sha256').update(realpathSync(root)).digest('hex').slice(0, 24)}.json`);
}

/** The write token this attempt's server recorded on taking `port`; '' until it has.
 *
 * The record is written only once the port is held, whereas an answer on the port proves nothing: when two workers are given one port, the server that took it answers the other's probe before the loser has exited, and a test left on it writes to the other test's quilt.
 */
function tokenFrom(root: string, port: number, env: NodeJS.ProcessEnv): string {
	try {
		const record = JSON.parse(readFileSync(join(root, '.loom/local/serve.json'), 'utf8')) as { port: number };
		if (record.port !== port) return '';
		const kept = JSON.parse(readFileSync(tokenFile(root, env), 'utf8')) as { root: string; token: string };
		return kept.root === realpathSync(root) ? kept.token : '';
	} catch {
		return '';
	}
}

function parseLines(path: string): Entry[] {
	return readFileSync(path, 'utf8')
		.split('\n')
		.filter((l) => l.trim())
		.map((l) => JSON.parse(l));
}

interface Running {
	served: Served;
	logPath: string;
	stop(): Promise<void>;
}

export function reviewerEnv(suite: Suite, directory: string): NodeJS.ProcessEnv {
	const config = join(directory, 'loom');
	mkdirSync(config, { recursive: true });
	const name = suite.quilt === 'synthetic' ? 'The synthetic quilt' : 'The loom showcase';
	writeFileSync(join(config, 'config.toml'), `[author]\nname = ${JSON.stringify(name)}\n`);
	// loom runs as the author here: an agent running the suite must not make loom refuse the author's own commands, as the Python suite's conftest arranges too; and in a home of the suite's own, so that nothing a loom keeps for the machine, a server's write token first, reaches the person's
	const home = join(directory, 'home');
	mkdirSync(home, { recursive: true });
	const env: NodeJS.ProcessEnv = { ...process.env, XDG_CONFIG_HOME: directory, HOME: home, XDG_DATA_HOME: join(home, '.local', 'share') };
	for (const marker of AGENT_MARKERS) delete env[marker];
	return env;
}

type PrepareQuilt = (quilt: Pick<Served, 'root' | 'loom'>) => void | Promise<void>;

/**
 * Copy the pristine quilt to `name` and serve it on a free port until its manifest answers.
 *
 * The server is started in its own process group, so stopping it also stops an agent turn it launched. A port lost to a race with another worker shows as an early exit, and is retried on a new one. The pristine copy carries a build, so its manifest answers as soon as the server listens, and the server's own first build, which only checks its cache, runs beside the test's first steps; the watcher starts after it.
 */
async function start(suite: Suite, name: string, prepare?: PrepareQuilt, overleaf = false): Promise<Running> {
	const dir = scratchDir(suite);
	const root = join(dir, 'quilts', name);
	const logPath = `${root}.serve.log`;
	// the server's temporary folder, beside its copy and thrown away with it: a server is killed outright, so what it had there is never removed by the server
	const tmp = `${root}.tmp`;
	rmSync(root, { recursive: true, force: true });
	rmSync(tmp, { recursive: true, force: true });
	mkdirSync(tmp, { recursive: true });
	cpSync(join(dir, 'template'), root, { recursive: true });
	const env = reviewerEnv(suite, `${root}.config`);
	if (overleaf) {
		// Overleaf's git stood in by a folder beside the copy, which loom's own Python is pointed at as it starts (`overleaf-stand-in/sitecustomize.py`)
		rmSync(`${root}.overleaf`, { recursive: true, force: true });
		mkdirSync(join(`${root}.overleaf`, 'projects'), { recursive: true });
		Object.assign(env, { LOOM_OVERLEAF_STAND_IN: `${root}.overleaf`, PYTHONPATH: join(VIEWER, 'tests', 'overleaf-stand-in') });
	}
	const loom: Served['loom'] = (args, overrides = {}) =>
		execFileSync(LOOM, [...args, '--quilt', root], { cwd: VIEWER, env: { ...env, ...overrides } }).toString();
	// Finish fixture writes before the publisher scans, so its first manifest describes one consistent source revision.
	await prepare?.({ root, loom });
	let lastLog = '';
	for (let attempt = 0; attempt < 3; attempt++) {
		const port = await freePort();
		const url = `http://127.0.0.1:${port}`;
		const out = createWriteStream(logPath, { flags: 'a' });
		const proc: ChildProcess = spawn(LOOM, ['serve', '--quilt', root, '--port', String(port), '--no-compile'], {
			cwd: VIEWER,
			detached: true,
			env: { ...env, LOOM_VIEWER_BUNDLE: join(dir, 'bundle'), TMPDIR: tmp },
			stdio: ['ignore', 'pipe', 'pipe']
		});
		proc.stdout!.pipe(out);
		proc.stderr!.pipe(out);
		let exited = false;
		const gone = new Promise<void>((r) => proc.once('exit', () => ((exited = true), r())));
		// killed outright: a graceful stop waits out the watcher's poll, over a second per test, and the copy is thrown away after; so the token a graceful stop would remove from the suite's home is removed here
		const stop = async () => {
			if (!exited) {
				try {
					process.kill(-proc.pid!, 'SIGKILL');
				} catch {
					/* already gone */
				}
				await gone;
			}
			try {
				rmSync(tokenFile(root, env), { force: true });
			} catch {
				/* the copy is gone already */
			}
			out.end();
		};
		// the build directory serves what is on disk, and the copy carries the template's build, so a manifest says the server listens, not that its first build is done; a server still starting is left to finish, since starting it again starts over
		const deadline = Date.now() + patient.timeout;
		let token = '';
		while (!exited && Date.now() < deadline) {
			try {
				const res = await fetch(`${url}/build/manifest.json`);
				// Drain even a readiness probe: an unread large HTTP/1.0 response can
				// leave Node’s parser paused when the server closes the connection.
				await res.arrayBuffer();
				if (res.ok) {
					token = tokenFrom(root, port, env);
					if (token) break;
				}
			} catch {
				/* not listening yet */
			}
			await new Promise((r) => setTimeout(r, 50));
		}
		if (!token) {
			await stop();
			lastLog = existsSync(logPath) ? readFileSync(logPath, 'utf8') : '';
			continue;
		}
		const served: Served = {
			root,
			url,
			log: () => parseLines(join(root, '.loom/records/annotations/log.jsonl')),
			written(body) {
				const mine = served.log().filter((e) => e.event === 'created' && e.body === body);
				expect(mine, `the log's created entries with the body ${JSON.stringify(body)}`).toHaveLength(1);
				return mine[0];
			},
			openSessions() {
				const open = new Map<string, boolean>();
				for (const e of parseLines(join(root, '.loom/agents/sessions/index.jsonl'))) {
					const id = String(e.id);
					if (e.event === 'created') open.set(id, true);
					else if (e.event === 'closed' || e.event === 'deleted') open.set(id, false);
					else if (e.event === 'resumed') open.set(id, true);
				}
				return [...open].filter(([, o]) => o).map(([id]) => id);
			},
			async answer(endpoint, body) {
				const res = await fetch(`${url}/_api/${endpoint}`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json', 'X-Loom-Token': token },
					body: JSON.stringify(body)
				});
				const text = await res.text();
				expect(res.status, `POST /_api/${endpoint} answered ${text}`).toBe(200);
				return JSON.parse(text) as Record<string, unknown>;
			},
			async api(endpoint, body) {
				return String((await this.answer(endpoint, body)).result ?? '');
			},
			loom
		};
		return { served, logPath, stop };
	}
	throw new Error(`loom serve never published ${root}:\n${lastLog}`);
}

/** Keep a failed test's copy and attach its server log; remove a passing one's, with the home its server kept the viewer in and its temporary folder. */
async function finish(running: Running, info: TestInfo): Promise<void> {
	await running.stop();
	if (info.status !== info.expectedStatus) {
		await info.attach('loom serve', { path: running.logPath, contentType: 'text/plain' });
		await info.attach('quilt copy', { body: running.served.root, contentType: 'text/plain' });
		return;
	}
	const root = running.served.root;
	for (const path of [root, `${root}.config`, `${root}.tmp`, `${root}.overleaf`]) rmSync(path, { recursive: true, force: true });
	rmSync(running.logPath, { force: true });
}

interface TestFixtures {
	/** Prepare a test's private quilt before starting its publisher. */
	prepareQuilt: PrepareQuilt | undefined;
	/** Whether this test gets a copy of its own; `readOnly` sets it false. */
	ownQuilt: boolean;
	/** Whether loom reaches a stand-in for Overleaf's git, a folder of bare repositories at `<root>.overleaf/projects/`, one a project id, never Overleaf or the Keychain; a private quilt's only. */
	overleafStandIn: boolean;
	served: Served;
}

interface WorkerFixtures {
	/** The worker's shared server, started the first time a read-only test asks for it. */
	sharedServed: () => Promise<Served>;
}

export const test = base.extend<TestFixtures, WorkerFixtures>({
	ownQuilt: [true, { option: true }],
	overleafStandIn: [false, { option: true }],
	prepareQuilt: undefined,
	sharedServed: [
		async ({}, use, info) => {
			let running: Promise<Running> | undefined;
			await use(async () => (await (running ??= start(suiteOf(info), `worker-${info.workerIndex}`))).served);
			if (running) await (await running).stop();
		},
		{ scope: 'worker' }
	],
	served: [
		async ({ ownQuilt, sharedServed, prepareQuilt, overleafStandIn }, use, info) => {
			if (!ownQuilt) {
				if (prepareQuilt) throw new Error('prepareQuilt requires a private quilt');
				await use(await sharedServed());
				return;
			}
			const running = await start(suiteOf(info), `${info.testId}-${info.repeatEachIndex}-${info.retry}`, prepareQuilt, overleafStandIn);
			await use(running.served);
			await finish(running, info);
		},
		// a budget of its own, so that a server slow to start leaves the test all of the test's
		{ timeout: patient.timeout }
	],
	baseURL: async ({ served }, use) => {
		await use(served.url);
	}
});

/** A test that writes nothing to the quilt, and so shares its worker's server. */
export const readOnly = test.extend({ ownQuilt: false });

export { expect };
