// Put a private copy of the built app in OUT, with FIXTURE staged into it when one is named, for one Playwright config to serve. Each config serves its own copy, so a build by another config or by hand never changes the files under a running server.
//
// Usage: node scripts/bundle.mjs OUT [FIXTURE]
//
// VIEWER_PREBUILT names a built app (the output of `npm run build`, no fixture staged) to copy; scripts/verify builds once and sets it for every suite. Without it this runs `npm run build` under a lock, so two configs started together do not build into `build/` and `.svelte-kit/` at once.
//
// VIEWER_WIDE_FONT set puts `tests/wide-font.css` in every page of the copy, so a whole suite runs in the faces a runner without this Mac's fonts draws (`scripts/verify --wide-font`).

import { execFileSync, execSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const VIEWER = fileURLToPath(new URL('..', import.meta.url));
const [outArg, fixture] = process.argv.slice(2);
if (!outArg) {
	console.error('usage: node scripts/bundle.mjs OUT [FIXTURE]');
	process.exit(2);
}
const out = resolve(VIEWER, outArg);

function sleep(ms) {
	Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function alive(pid) {
	try {
		process.kill(pid, 0);
		return true;
	} catch (err) {
		return err.code === 'EPERM';
	}
}

/** Run `fn` holding `.tmp-e2e/build.lock`; a lock whose owner has exited is taken over. */
function locked(fn) {
	const lock = join(VIEWER, '.tmp-e2e', 'build.lock');
	mkdirSync(join(VIEWER, '.tmp-e2e'), { recursive: true });
	const deadline = Date.now() + 300000;
	for (;;) {
		try {
			mkdirSync(lock);
			writeFileSync(join(lock, 'pid'), String(process.pid));
			break;
		} catch (err) {
			if (err.code !== 'EEXIST') throw err;
			let owner = 0;
			try {
				owner = Number(readFileSync(join(lock, 'pid'), 'utf8'));
			} catch {
				/* the owner has made the directory and not yet written its pid */
			}
			if (owner && !alive(owner)) rmSync(lock, { recursive: true, force: true });
			else if (Date.now() > deadline) throw new Error(`${lock} held by pid ${owner} for five minutes`);
			else sleep(200);
		}
	}
	try {
		return fn();
	} finally {
		rmSync(lock, { recursive: true, force: true });
	}
}

rmSync(out, { recursive: true, force: true });
const prebuilt = process.env.VIEWER_PREBUILT && resolve(VIEWER, process.env.VIEWER_PREBUILT);
if (prebuilt) {
	if (!existsSync(join(prebuilt, 'index.html'))) {
		console.error(`VIEWER_PREBUILT=${prebuilt} has no index.html`);
		process.exit(2);
	}
	cpSync(prebuilt, out, { recursive: true });
} else {
	locked(() => {
		execSync('npm run build', { cwd: VIEWER, stdio: ['ignore', 'ignore', 'inherit'] });
		cpSync(join(VIEWER, 'build'), out, { recursive: true });
	});
}
if (process.env.VIEWER_WIDE_FONT) {
	const style = `<style data-wide-font>${readFileSync(join(VIEWER, 'tests', 'wide-font.css'), 'utf8')}</style>`;
	for (const name of readdirSync(out, { recursive: true, encoding: 'utf8' }).filter((n) => n.endsWith('.html'))) {
		const page = readFileSync(join(out, name), 'utf8');
		if (page.includes('</head>') && !page.includes('data-wide-font')) writeFileSync(join(out, name), page.replace('</head>', `${style}</head>`));
	}
}
if (fixture) execFileSync(process.execPath, [join(VIEWER, 'scripts', 'stage-fixture.mjs'), resolve(VIEWER, fixture), out], { cwd: VIEWER, stdio: ['ignore', 'ignore', 'inherit'] });
