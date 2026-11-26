// Before `npm run dev:loom` starts: say whether ARRAS_LOOM names a `loom serve` that is running, so that a dev server pointed at nothing says so at once instead of showing "Loading manifest…" for ever.
//
// Usage: ARRAS_LOOM=http://127.0.0.1:PORT node scripts/loom-target.mjs
const target = (process.env.ARRAS_LOOM ?? '').replace(/\/+$/, '');
const how = 'start one on a quilt (`loom serve --quilt PATH --port 8791`) and run `ARRAS_LOOM=http://127.0.0.1:8791 npm run dev:loom`';
if (!target) {
	console.error(`dev:loom runs the viewer against a running loom serve, and ARRAS_LOOM names none: ${how}`);
	process.exit(2);
}
// the server answers only as 127.0.0.1 or localhost at its own port, so any other name would be refused on every request
if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(target)) {
	console.error(`ARRAS_LOOM is ${target}; loom serve answers only as http://127.0.0.1:PORT or http://localhost:PORT`);
	process.exit(2);
}
try {
	const said = await (await fetch(`${target}/_api`)).json();
	if (typeof said.write_api !== 'number') throw new Error('what answered is not loom serve');
	console.log(`the viewer's dev server will read and write through ${target}`);
} catch (err) {
	console.error(`no loom serve answers at ${target} (${err.message}): ${how}`);
	process.exit(2);
}
