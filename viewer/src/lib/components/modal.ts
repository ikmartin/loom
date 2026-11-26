// A surface over a view that the person works in, made modal: on opening it takes the keyboard (its first field, else itself), everything outside it is inert, Escape closes it, and on closing the keyboard goes back to the control that opened it.

/** The action: `use:modal={close}` on the dialog's root, which carries `role="dialog"` and `aria-modal="true"`. */
export function modal(node: HTMLElement, close: () => void): { update(next: () => void): void; destroy(): void } {
	let onclose = close;
	const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
	// everything beside the dialog and beside each of its ancestors, up to the page, made inert while it is open
	const inert: Element[] = [];
	for (let el: Element = node; el.parentElement && el !== document.body; el = el.parentElement) {
		for (const sibling of el.parentElement.children) {
			// a live region stays heard, so what the dialog does is still said
			if (sibling === el || sibling.hasAttribute('inert') || sibling.hasAttribute('aria-live') || sibling.tagName === 'SCRIPT' || sibling.tagName === 'STYLE') continue;
			sibling.setAttribute('inert', '');
			inert.push(sibling);
		}
	}
	queueMicrotask(() => {
		const first = node.querySelector<HTMLElement>('input:not([type="hidden"]), [data-autofocus]');
		(first ?? node).focus();
	});
	// on the window, so Escape closes it when a click on what is inert has left the keyboard on the page
	const key = (e: KeyboardEvent) => {
		if (e.key !== 'Escape' || e.defaultPrevented) return;
		e.preventDefault();
		onclose();
	};
	window.addEventListener('keydown', key);
	return {
		update(next) {
			onclose = next;
		},
		destroy() {
			window.removeEventListener('keydown', key);
			for (const el of inert) el.removeAttribute('inert');
			if (opener?.isConnected) opener.focus();
		}
	};
}
