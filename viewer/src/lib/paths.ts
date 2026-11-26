// Where the app lives and where the corpus lives (plan 0.9.5 R1). Two different things, and a host may move either.
//
// `base` is SvelteKit's: the prefix the app's own routes are served under, fixed when the bundle is built.
// The data root is the build directory the publisher wrote — `manifest.json` and the fragments beside it. It defaults to `build/` next to the app, which is where a publisher serving both puts it, and a host may point it anywhere before the app boots: a different path, a different origin, a corpus that is not beside the viewer at all.
// Nothing in `src/lib/` builds an origin-absolute URL by hand; every one comes from here.

import { base } from '$app/paths';

let root = '';

function normalise(url: string): string {
	return url.replace(/\/+$/, '') + '/';
}

/** The corpus's build directory, with a trailing slash. */
export function dataRoot(): string {
	return root || normalise(base + '/build');
}

/**
 * Point the viewer at a corpus. A host calls this once, before the app boots; passing an empty string restores the default. Accepts a path (`/papers/build`) or an absolute URL (`https://example.org/corpus/build`).
 */
export function setDataRoot(url: string): void {
	root = url ? normalise(url) : '';
}

/** A file inside the corpus's build directory, by its manifest-relative path. */
export function dataUrl(path: string): string {
	return dataRoot() + path.replace(/^\/+/, '');
}

/** A document's compiled PDF, by the address its manifest entry gives and the compile it is, so each compile is a new file to PDF.js and the browser; '' where there is none. */
export function compiledUrl(d: { pdf?: string; compiled?: string }): string {
	return d.pdf ? `${dataUrl(d.pdf)}?v=${encodeURIComponent(d.compiled ?? '')}` : '';
}

/** A work's stored PDF as the publisher serves it, sandboxed, beside the app, by its hash: `sha256:<hex>` as the library gives it, or the bare hex. */
export function libraryPdfUrl(hash: string): string {
	return base + '/_api/library/pdf/' + hash.replace(/^sha256:/, '');
}

/** A project file as the publisher serves it, sandboxed, beside the app: an image, a PDF, text, an HTML page with no script. */
export function filesUrl(path: string): string {
	return base + '/_files/' + path.split('/').map(encodeURIComponent).join('/');
}

/** A route of this app, prefixed by the base path the bundle was built for. */
export function route(path: string): string {
	return base + path;
}
