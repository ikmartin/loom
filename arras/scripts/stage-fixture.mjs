// Copy a corpus build directory (default the vendored conformance fixture; or a quilt's `.loom/cache/site`) to `INTO/build`, where the app looks for it and loom serve publishes it. INTO defaults to `static`, so `vite dev` serves it; the Playwright configs stage into their own copy of the built app instead (scripts/bundle.mjs). `--clean` removes it from `static` so a production build ships no fixture.
//
// Usage: node scripts/stage-fixture.mjs [FIXTURE [INTO]] | --clean
import { cpSync, existsSync, rmSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';

const arg = process.argv[2] ?? 'tests/fixture';
const into = process.argv[3] ?? 'static';
if (arg === '--clean') {
	rmSync('static/build', { recursive: true, force: true });
	rmSync('static/digests', { recursive: true, force: true });
	console.log('removed static/build');
	process.exit(0);
}
if (!existsSync(`${arg}/manifest.json`)) {
	console.error(`${arg} has no manifest.json`);
	process.exit(2);
}
rmSync(join(into, 'build'), { recursive: true, force: true });
rmSync(join(into, 'digests'), { recursive: true, force: true });
cpSync(arg, join(into, 'build'), { recursive: true });

// A quilt's own site, `.loom/cache/site`, has its store at `.loom/library/storage` and its documents' compile folders beside it at `.loom/cache/tex`; both are staged where `loom serve` answers them, `digests/storage/` beside `build/` (the address `artifacts.dir` names, which `artifactUrl` climbs out of `build/` for) and `build/tex/` (the address a manifest's `pdf` names). A corpus that is not a quilt's site, the conformance fixture among them, stages neither, so its papers have nothing to draw and its PDFs nothing to open.
const site = resolve(arg);
if (basename(site) === 'site' && basename(dirname(site)) === 'cache') {
	const store = resolve(site, '..', '..', 'library', 'storage');
	if (existsSync(store)) {
		cpSync(store, join(into, 'digests', 'storage'), { recursive: true });
		console.log('staged the store beside it, so the papers are servable');
	}
	const tex = resolve(site, '..', 'tex');
	if (existsSync(tex)) {
		cpSync(tex, join(into, 'build', 'tex'), { recursive: true });
		console.log('staged the compile folders under it, so the PDFs are servable');
	}
}
console.log(`staged ${arg} -> ${join(into, 'build')}`);
