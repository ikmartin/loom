// What the Library remembers while the person moves between views: its tabs (the list of works, and a tab for each work open), the list's search, filter, sort, columns and selection, the result beside each work's page, what is being chosen to digest, and the reads on screen. Kept in this module, not the component, since the column and the view both draw from it and a view is taken down when another is shown. The list or thumbnails choice and the digest marks are remembered across visits, per viewer.

import { SvelteSet } from 'svelte/reactivity';
import { Annotating } from '$lib/review/annotating.svelte';
import { PdfView } from '$lib/pdf/view.svelte';
import { Read } from '$lib/library/read.svelte';
import type { WorkAnswer, WorksAnswer } from '$lib/library/types';

export type Filter = 'all' | 'used' | 'unchecked' | 'nodoc';
export type Column = 'title' | 'authors' | 'year' | 'digested' | 'holds' | 'used';
export const COLUMNS: Column[] = ['title', 'authors', 'year', 'digested', 'holds', 'used'];

const LAYOUT = 'arras.library.layout';
const OVERLAY = 'arras.library.overlay';

function remembered(key: string): string | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage.getItem(key);
	} catch {
		return null;
	}
}
function remember(key: string, value: string): void {
	try {
		localStorage.setItem(key, value);
	} catch {
		// a browser that keeps nothing forgets the choice; the Library still works
	}
}

/** What is beside a work's page: a node, or an item of its source not yet digested. */
export type Beside = { node: string } | { item: string };

class LibraryState {
	// the list
	filter = $state<Filter>('all');
	q = $state('');
	sort = $state<{ key: Column; dir: 1 | -1 }>({ key: 'title', dir: 1 });
	cols = $state<Record<Column, boolean>>({ title: true, authors: true, year: true, digested: true, holds: false, used: false });
	#layout = $state<'list' | 'thumbs'>(remembered(LAYOUT) === 'thumbs' ? 'thumbs' : 'list');
	/** Works selected with ⌘-click, for "everything in the papers I select". */
	multi = new SvelteSet<string>();

	// the tabs
	open = $state<string[]>([]);
	tab = $state<string>('works');

	// a work's tab
	beside = $state<Record<string, Beside | null>>({});
	/** The work whose outline is being chosen in, and what is ticked there. */
	choosing = $state<string | null>(null);
	ticks = new SvelteSet<string>();
	#overlay = $state(remembered(OVERLAY) === 'on');
	plain = $state(false);
	/** The page each work's reader is sent to, and a count that changes each time it is sent, so being sent again lands again. */
	goto = $state<Record<string, { page: number; seq: number }>>({});
	#readers = new Map<string, { view: PdfView; notes: Annotating }>();

	// the reads on screen
	works = new Read<WorksAnswer>();
	work = new Read<WorkAnswer>();

	get layout(): 'list' | 'thumbs' {
		return this.#layout;
	}
	set layout(v: 'list' | 'thumbs') {
		this.#layout = v;
		remember(LAYOUT, v);
	}

	get overlay(): boolean {
		return this.#overlay;
	}
	set overlay(v: boolean) {
		this.#overlay = v;
		remember(OVERLAY, v ? 'on' : 'off');
	}

	/** Opens a work in a tab of its own, or goes to its tab. */
	openWork(ref: string): void {
		if (!this.open.includes(ref)) this.open = [...this.open, ref];
		this.tab = ref;
	}

	/** Closes a work's tab; the tab to its left, or the list, comes forward. */
	closeWork(ref: string): void {
		const at = this.open.indexOf(ref);
		this.open = this.open.filter((r) => r !== ref);
		if (this.tab === ref) this.tab = this.open[Math.max(0, at - 1)] ?? 'works';
		if (this.choosing === ref) this.stopChoosing();
	}

	/** Sends a work's reader to `page`. */
	go(ref: string, page: number): void {
		const seq = (this.goto[ref]?.seq ?? 0) + 1;
		this.goto = { ...this.goto, [ref]: { page, seq } };
	}

	stopChoosing(): void {
		this.choosing = null;
		this.ticks.clear();
	}

	/** A work's reader's view and annotating, kept while the person moves between tabs. */
	reader(ref: string): { view: PdfView; notes: Annotating } {
		let r = this.#readers.get(ref);
		if (!r) this.#readers.set(ref, (r = { view: new PdfView(), notes: new Annotating() }));
		return r;
	}
}

export const lib = new LibraryState();
