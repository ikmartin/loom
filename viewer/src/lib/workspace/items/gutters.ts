// The width a document's gutters are worked out from (theme.css, `.gutters`), given to their host by script rather than by a size container: a container makes every layout of the pane resolve the gutters' style and lay out the whole document's grid again, which on a long paper was most of a scroll's frames.

/** Below this width the gutter cannot hold an id at all, so it holds nothing (theme.css, `.node-margin`). */
const NARROW_REM = 34;

/** What a host last measured. A document shown again, a tab come back to, starts from it, so its first layout already has its gutters and is not laid out a second time when the measurement arrives; nothing is read from the page to start it, which would restyle a document just put in. */
let known: { width: number; narrow: boolean } | null = null;

function give(node: HTMLElement, { width, narrow }: { width: number; narrow: boolean }): void {
	node.style.setProperty('--host-width', `${width}px`);
	node.classList.toggle('narrow', narrow);
}

/**
 * Keep `--host-width` and the `narrow` class on a `.gutters-host` as wide as it is, changed only when its width changes; a new host starts at the width the last one measured.
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
	let last = known?.width ?? -1;
	if (known) give(node, known);
	const watch = new ResizeObserver(([e]) => {
		const width = Math.round(e.contentBoxSize?.[0]?.inlineSize ?? e.contentRect.width);
		// a document growing as the blocks near the screen are laid out changes its height on every frame of a scroll, and nothing here
		if (width === last) return;
		last = width;
		const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
		known = { width, narrow: width < NARROW_REM * rem };
		give(node, known);
	});
	watch.observe(node);
	return { destroy: () => watch.disconnect() };
}
