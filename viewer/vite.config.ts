import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import type { ProxyOptions } from 'vite';

// arras is a single-page application served as files, by a publisher that serves index.html for unknown paths. The interface it renders is docs/specs in the loom-arras workspace.
//
// ARRAS_BASE is the path the app is served under, empty for the root. It is a build-time choice because SvelteKit
// resolves routes and assets against it; where the *corpus* lives is a separate, runtime choice (src/lib/paths.ts),
// so a bundle built for one path can still be pointed at a corpus served from another.
const raw = (process.env.ARRAS_BASE ?? '').replace(/\/+$/, '');
const base = (raw && !raw.startsWith('/') ? '/' + raw : raw) as '' | `/${string}`;

// ARRAS_LOOM names a running `loom serve` (`ARRAS_LOOM=http://127.0.0.1:8791 npm run dev:loom`). The dev server then sends the quilt's own paths to it, so the viewer under development reads a real quilt and writes to it, with hot reload: the write API and its stream, a work's stored PDF among its answers, the build directory and the project's files. Everything else, the app itself, is the dev server's.
//
// `loom serve` answers only a request that names it and comes from one of its own pages. A proxied request is therefore sent as the server's own: its `Host`, and, where the browser says the request came from a page of this dev server, the server's `Origin` and `Referer` in place of the dev server's. A request from any other page goes on as it came and is refused there as it would be.
const loom = (process.env.ARRAS_LOOM ?? '').replace(/\/+$/, '');
const LOOM_PATHS = ['/_api', '/build', '/_files'];

function toLoom(): ProxyOptions {
	return {
		target: loom,
		changeOrigin: true,
		configure(proxy) {
			proxy.on('proxyReq', (sent, asked) => {
				const own = `http://${asked.headers.host}`;
				if (asked.headers.origin === own) sent.setHeader('origin', loom);
				const referer = asked.headers.referer;
				if (referer && (referer === own || referer.startsWith(own + '/'))) sent.setHeader('referer', loom + referer.slice(own.length));
			});
		}
	};
}

export default defineConfig({
	server: loom ? { proxy: Object.fromEntries(LOOM_PATHS.map((path) => [path, toLoom()])) } : undefined,
	// the graph's force layout runs in a module worker (src/lib/graph/force.worker.ts)
	worker: { format: 'es' },
	plugins: [
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
			},
			adapter: adapter({ fallback: 'index.html', strict: false }),
			paths: { base }
		})
	],
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'unit',
					environment: 'node',
					// a limit on a hang, since no unit test here is about time: the graph's layout outran vitest's 5 s default on a loaded machine
					testTimeout: 120000,
					hookTimeout: 120000,
					include: ['src/**/*.{test,spec}.{js,ts}', 'tests/unit/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
