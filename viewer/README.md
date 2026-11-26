# The viewer

loom's viewer, a static app for node-based text corpora. It reads a build directory conforming to the interface specified in `docs/specs/` at the [repository's root](https://github.com/ikmartin/loom): a `manifest.json` carrying the graph and every non-textual fact, and HTML fragments in a fixed semantic dialect. It renders node pages, a document view per master, a review panel, a problems page, a dependency graph, threads, indexes, and search, and it re-renders whenever the manifest changes. It knows nothing about LaTeX or about mathematics; loom is its first publisher.

Status: pre-alpha, under construction milestone by milestone.

## For users

You do not need this repository or Node. The built viewer ships inside loom; `loom serve` serves it. Any static file server can serve a build directory plus the bundle as well.

## For developers

Requires Node 20 or newer.

```
git clone https://github.com/ikmartin/loom
cd loom/viewer
npm ci
npm run check          # svelte-check
npm run test:unit -- --run
npm run build          # SPA build into build/
npx playwright install chromium   # once, for the end-to-end tests
npm run test:e2e
```

loom vendors `build/` with its own `scripts/vendor_viewer.py`.

## License

AGPL-3.0-or-later; see `LICENSE` and `NOTICE`.
