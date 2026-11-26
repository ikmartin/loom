// Copy a corpus build directory (default the vendored conformance fixture; or a quilt's `.loom/cache/site`) to `INTO/build`, where the app looks for it and loom serve publishes it. INTO defaults to `static`, so `vite dev` serves it; the Playwright configs stage into their own copy of the built app instead (scripts/bundle.mjs). `--clean` removes it from `static` so a production build ships no fixture.
//
// Usage: node scripts/stage-fixture.mjs [FIXTURE [INTO]] | --clean
import { cpSync, existsSync, rmSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';

const arg = process.argv[2] ?? 'tests/fixture';
const into = process.argv[3] ?? 'static';
if (arg === '--clean') {
	rmSync('static/build', { recursive: true, force: true });
	console.log('removed static/build');
	process.exit(0);
}
if (!existsSync(`${arg}/manifest.json`)) {
	console.error(`${arg} has no manifest.json`);
	process.exit(2);
}
rmSync(join(into, 'build'), { recursive: true, force: true });
cpSync(arg, join(into, 'build'), { recursive: true });

// A quilt's own site, `.loom/cache/site`, has its documents' compile folders beside it at `.loom/cache/tex`, staged where `loom serve` answers them, `build/tex/` (the address a manifest's `pdf` names). A corpus that is not a quilt's site, the conformance fixture among them, stages none, so its PDFs have nothing to open. A work's stored PDF is the publisher's to answer (`/_api/library/pdf/`), and a static copy has no publisher.
const site = resolve(arg);
if (basename(site) === 'site' && basename(dirname(site)) === 'cache') {
	const tex = resolve(site, '..', 'tex');
	if (existsSync(tex)) {
		cpSync(tex, join(into, 'build', 'tex'), { recursive: true });
		console.log('staged the compile folders under it, so the PDFs are servable');
	}
}
console.log(`staged ${arg} -> ${join(into, 'build')}`);
