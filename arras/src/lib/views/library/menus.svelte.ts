// Which of the Library's menus is open, one at a time: the add panel, the digest menu over the list or on a work, the columns menu, a row's menu. A click outside every menu closes it (`LibraryView.svelte`).

class Menus {
	open = $state<string | null>(null);

	/** Opens `name`, or closes it if it is the one open. */
	toggle(name: string): void {
		this.open = this.open === name ? null : name;
	}
}

export const menus = new Menus();
