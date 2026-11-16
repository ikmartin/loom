// The width a document's gutters are worked out from (theme.css, `.gutters`), given to their host by script rather than by a size container: a container makes every layout of the pane resolve the gutters' style and lay out the whole document's grid again, which on a long paper was most of a scroll's frames.

/** Below this width the gutter cannot hold an id at all, so it holds nothing (theme.css, `.node-margin`). */
const NARROW_REM = 34;

/**
 * Keep `--host-width` and the `narrow` class on a `.gutters-host` as wide as it is, changed only when its width changes.
 *
 * Parameters
 * ----------
 * node : HTMLElement
 *     The `.gutters-host`.
 *
 * Returns
 * -------
 * { destroy: () => void }
 *     A Svelte action's handle.
 */
export function guttersHost(node: HTMLElement): { destroy: () => void } {
	let last = -1;
	const watch = new ResizeObserver(([e]) => {
		const width = Math.round(e.contentBoxSize?.[0]?.inlineSize ?? e.contentRect.width);
		// a document growing as the blocks near the screen are laid out changes its height on every frame of a scroll, and nothing here
		if (width === last) return;
		last = width;
		const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
		node.style.setProperty('--host-width', `${width}px`);
		node.classList.toggle('narrow', width < NARROW_REM * rem);
	});
	watch.observe(node);
	return { destroy: () => watch.disconnect() };
}
