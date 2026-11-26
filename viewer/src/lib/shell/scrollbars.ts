// Scrollbars shown only while something scrolls: whatever is scrolling carries `is-scrolling`, and the stylesheet draws its bar only then.

/** How long a bar stays after the last movement: long enough to find it and take hold of it. */
const LINGER = 900;

/**
 * Mark each scrolling element while it scrolls, on the whole page.
 *
 * Returns
 * -------
 * () => void
 *     Removes the listener.
 */
export function revealWhileScrolling(): () => void {
	const timers = new WeakMap<Element, ReturnType<typeof setTimeout>>();
	const onScroll = (e: Event): void => {
		// arras scrolls its panels and panes, never the page; and a host's own elements are the host's to mark, not arras's
		const el = e.target instanceof Element ? e.target : null;
		if (!el?.closest('.arras')) return;
		// a class set again restyles the element on every scroll event, and a pane's is laid out again with it
		if (!el.classList.contains('is-scrolling')) el.classList.add('is-scrolling');
		clearTimeout(timers.get(el));
		timers.set(
			el,
			setTimeout(() => el.classList.remove('is-scrolling'), LINGER)
		);
	};
	// scroll does not bubble, so it is caught on the way down
	document.addEventListener('scroll', onScroll, { capture: true, passive: true });
	return () => document.removeEventListener('scroll', onScroll, { capture: true });
}

/**
 * Keep the bar of the scrolling root at rest while `node` is on the page: a long list read by moving through it (the problems page) shows where the reader is.
 *
 * Parameters
 * ----------
 * node : HTMLElement
 *     The page's `main`.
 *
 * Returns
 * -------
 * { destroy: () => void }
 *     A Svelte action's handle.
 */
export function barShown(node: HTMLElement): { destroy: () => void } {
	const root = node.closest('.arras');
	root?.classList.add('scrollbar-shown');
	return { destroy: () => root?.classList.remove('scrollbar-shown') };
}
