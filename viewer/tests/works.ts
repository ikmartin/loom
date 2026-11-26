// A publisher's library for the static suite, which has none: the works list holding one work with a stored PDF, and that PDF at the address the node store serves it from, so a work's item opens on its paper. Nothing else of a publisher is stood in.
import type { Page } from '@playwright/test';
import { paperBytes } from '../src/lib/library/fixtures/paper';

/** Serves `ref` as a work holding a stored PDF of `pages` pages, its short name `short`. */
export async function serveWork(page: Page, ref: string, { pages = 2, short = 'Kremer 1999' } = {}): Promise<void> {
	const hex = 'c'.repeat(64);
	await page.route('**/_api', (route) => route.fulfill({ json: { write_api: 1, capabilities: ['library-works'], token: 't' } }));
	await page.route('**/_api/library-works', (route) =>
		route.fulfill({ json: { ok: true, result: '1 work', gen: 1, works: [{ ref, short, title: short, authors: [], year: '', holds: { pdf: `sha256:${hex}`, tex: false }, digested: null, used_in: [], link: null, version: null, lookup: null, cited_as: null }] } })
	);
	await page.route(`**/_api/library/pdf/${hex}`, (route) => route.fulfill({ body: Buffer.from(paperBytes(pages)), contentType: 'application/pdf' }));
}
