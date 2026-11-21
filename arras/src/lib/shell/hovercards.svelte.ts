// The column's hover cards: the view names', and later Review's kinds'. One card at a time, shown after the pointer has rested on its owner for a moment and gone as soon as it leaves; `HoverCard.svelte` draws it, once, in the column.

/** How long the pointer rests on a name before its card shows. */
export const HOVER_DELAY = 600;

/** Where a card stands: under its owner (the view names in the open column), or beside the column at its owner's height (the folded strip, and the column's lists). */
export type Placement = 'below' | 'beside';

export interface Shown {
	text: string;
	left: number;
	top: number;
}

class HoverCards {
	shown = $state<Shown | null>(null);
	#timer: ReturnType<typeof setTimeout> | null = null;
	#owner: HTMLElement | null = null;

	/** Shows `text` for `owner` after the delay, unless the pointer leaves first. */
	arm(owner: HTMLElement, text: string, place: Placement): void {
		if (this.#owner === owner && (this.shown || this.#timer)) return;
		this.disarm();
		this.#owner = owner;
		this.#timer = setTimeout(() => {
			this.#timer = null;
			this.shown = { text, ...where(owner, place) };
		}, HOVER_DELAY);
	}

	/** Takes the card down, and the one waiting to show. */
	disarm(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		this.#owner = null;
		this.shown = null;
	}
}

/** The card's top left: under the owner, a little to its left; or right of the column, level with the owner. */
function where(owner: HTMLElement, place: Placement): { left: number; top: number } {
	const r = owner.getBoundingClientRect();
	if (place === 'below') return { left: Math.max(8, r.left - 8), top: r.bottom + 6 };
	const column = owner.closest('[data-testid="column"]')?.getBoundingClientRect();
	return { left: (column?.right ?? r.right) + 8, top: Math.max(8, r.top - 8) };
}

export const hovercards = new HoverCards();

/** The action that gives an element a hover card: `use:hovercard={{ text, place }}`. Focus shows it as a hover does. */
export function hovercard(node: HTMLElement, params: { text: string; place?: Placement }) {
	let current = params;
	const arm = () => hovercards.arm(node, current.text, current.place ?? 'below');
	const disarm = () => hovercards.disarm();
	node.addEventListener('pointerenter', arm);
	node.addEventListener('pointerleave', disarm);
	node.addEventListener('focus', arm);
	node.addEventListener('blur', disarm);
	node.addEventListener('click', disarm);
	return {
		update(next: { text: string; place?: Placement }) {
			current = next;
		},
		destroy() {
			node.removeEventListener('pointerenter', arm);
			node.removeEventListener('pointerleave', disarm);
			node.removeEventListener('focus', arm);
			node.removeEventListener('blur', disarm);
			node.removeEventListener('click', disarm);
			disarm();
		}
	};
}
