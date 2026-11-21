// A page the quilt holds is served in the viewer's own origin: what loom derives, which an agent writes, and a document the library stores, which came from outside. Such a page must not run as the viewer: one that did could read the token from `/_api` and post the author's acts naming no author, which the publisher takes for the author's own click (K5).
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { expect, test } from '../served';

/** Synchronous requests, so that by the page's `load` whatever the script did has already reached the publisher. */
const PAYLOAD = `
var x = new XMLHttpRequest();
x.open('GET', '/_api', false);
x.send();
var token = JSON.parse(x.responseText).token;
x.open('POST', '/_api/session-new', false);
x.setRequestHeader('Content-Type', 'application/json');
x.setRequestHeader('X-Loom-Token', token);
x.send(JSON.stringify({ title: 'planted' }));
`;

/** A page that writes as the viewer if it runs. */
const PAGE = `<!doctype html><title>planted</title><script>${PAYLOAD}</script>`;
/** The name a stored document takes, its bytes' hash: the page's, planted where the store keeps a PDF. */
const HEX = createHash('sha256').update(PAGE).digest('hex');

/** Each page by the address it is served at, the file under `.loom/` that holds it, and the type it is served as. */
const PLANTED = [
	{ name: 'an HTML page under build/', path: 'build/agent/x.html', held: '.loom/cache/site/agent/x.html', type: 'text/html; charset=utf-8' },
	{ name: "a page stored as a work's PDF", path: `_api/library/pdf/${HEX}`, held: `.loom/library/documents/${HEX}.pdf`, type: 'application/pdf' }
];

for (const { name, path, held, type } of PLANTED) {
	test(`${name} runs no script as the viewer, so it writes nothing`, async ({ page, served }) => {
		const file = join(served.root, held);
		mkdirSync(dirname(file), { recursive: true });
		writeFileSync(file, PAGE);
		const asked: string[] = [];
		page.on('request', (r) => {
			const at = new URL(r.url()).pathname;
			if (at.startsWith('/_api') && at !== `/${path}`) asked.push(r.url());
		});
		// how it is served, read apart from what a browser does with it
		const res = await page.request.get(`/${path}`);
		expect(res.status()).toBe(200);
		expect(res.headers()['content-security-policy']).toBe('sandbox');
		expect(res.headers()['x-content-type-options']).toBe('nosniff');
		expect(res.headers()['content-type']).toBe(type);
		// a browser opening it: whatever it makes of the bytes, it renders a page, or keeps a file it will not render, and nothing in them runs as the viewer
		await page.goto(`/${path}`).catch((err: Error) => {
			if (!/Download is starting/.test(err.message)) throw err;
		});
		const index = join(served.root, '.loom/agents/sessions/index.jsonl');
		expect(existsSync(index) ? readFileSync(index, 'utf8') : '', 'the session index').not.toContain('planted');
		expect(asked, 'requests the planted page made to the write API').toEqual([]);
	});
}
