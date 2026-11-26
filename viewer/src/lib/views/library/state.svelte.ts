// What the Library remembers while the person moves between views: its tabs (the list of works, and a tab for each work open), the list's search, filter, sort, columns and selection, the result beside each work's page, what is being chosen to digest, and the reads on screen. Kept in this module, not the component, since the column and the view both draw from it and a view is taken down when another is shown. The list or thumbnails choice, the sort, the columns and the digest marks are remembered across visits, per viewer.

import { SvelteMap, SvelteSet } from 'svelte/reactivity';
import { MarkDesk } from '$lib/pdf/desk.svelte';
import { goto } from '$app/navigation';
import { route } from '$lib/paths';
import { Annotating } from '$lib/review/annotating.svelte';
import { PdfView } from '$lib/pdf/view.svelte';
import { Read } from '$lib/library/read.svelte';
import type { WorkAnswer, WorksAnswer } from '$lib/library/types';

export type Filter = 'all' | 'used' | 'nodoc';
export type Column = 'title' | 'authors' | 'year' | 'digested' | 'holds' | 'used';
export const COLUMNS: Column[] = ['title', 'authors', 'year', 'digested', 'holds', 'used'];

const LAYOUT = 'viewer.library.layout';
const OVERLAY = 'viewer.library.overlay';
const SORT = 'viewer.library.sort';
const OPEN = 'viewer.library.open';

/** The works open in this browser tab's visit before a reload. */
function visited(): string[] {
	try {
		const v = typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(OPEN);
		return v ? (JSON.parse(v) as string[]) : [];
	} catch {
		return [];
	}
}
const TAB = 'viewer.library.tab';
const ZOOM = 'viewer.library.zoom';

/** Each open work's paper's zoom, where the reader gave it one, kept for the visit as the open works are. */
function zooms(): Record<string, number> {
	try {
		const v = typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(ZOOM);
		return v ? (JSON.parse(v) as Record<string, number>) : {};
	} catch {
		return {};
	}
}
function keepZoom(ref: string, zoom: number): void {
	try {
		sessionStorage.setItem(ZOOM, JSON.stringify({ ...zooms(), [ref]: zoom }));
	} catch {
		// a browser that keeps nothing opens the paper at the start again after a reload
	}
}

/** The tab shown when the Library was left, where it is one of the open works. */
function shown(open: string[]): string {
	try {
		const v = typeof sessionStorage === 'undefined' ? null : sessionStorage.getItem(TAB);
		return v && open.includes(v) ? v : 'works';
	} catch {
		return 'works';
	}
}
const COLS = 'viewer.library.columns';

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

/** A choice kept as JSON, or `fallback` where none is kept or it cannot be read. */
function kept<T>(key: string, fallback: T): T {
	try {
		const v = remembered(key);
		return v ? { ...fallback, ...JSON.parse(v) } : fallback;
	} catch {
		return fallback;
	}
}

/** What is beside a work's page: a node, or an item of its source not yet digested. */
export type Beside = { node: string } | { item: string };

class LibraryState {
	// the list
	filter = $state<Filter>('all');
	q = $state('');
	#sort = $state<{ key: Column; dir: 1 | -1 }>(kept(SORT, { key: 'title', dir: 1 }));
	#cols = $state<Record<Column, boolean>>(kept(COLS, { title: true, authors: true, year: true, digested: true, holds: false, used: false }));

	get sort(): { key: Column; dir: 1 | -1 } {
		return this.#sort;
	}
	set sort(v: { key: Column; dir: 1 | -1 }) {
		this.#sort = v;
		remember(SORT, JSON.stringify(v));
	}
	get cols(): Record<Column, boolean> {
		return this.#cols;
	}
	set cols(v: Record<Column, boolean>) {
		this.#cols = v;
		remember(COLS, JSON.stringify(v));
	}
	#layout = $state<'list' | 'thumbs'>(remembered(LAYOUT) === 'thumbs' ? 'thumbs' : 'list');
	/** Works selected with ⌘-click, for "everything in the papers I select". */
	multi = new SvelteSet<string>();

	// the tabs: the works open, kept for the browser tab's visit so a reload keeps them, and the one shown, which the address says (`/library?work=…`) and the Library's name goes back to
	#open = $state<string[]>(visited());
	#tab = $state<string>(shown(this.#open));

	get tab(): string {
		return this.#tab;
	}
	set tab(v: string) {
		this.#tab = v;
		try {
			sessionStorage.setItem(TAB, v);
		} catch {
			// a browser that keeps nothing goes back to the list after a reload
		}
	}

	/** Where the Library was left: the list, or the work whose tab was shown. */
	get address(): string {
		return route('/library') + (this.tab !== 'works' && this.open.includes(this.tab) ? `?work=${encodeURIComponent(this.tab)}` : '');
	}

	get open(): string[] {
		return this.#open;
	}
	set open(v: string[]) {
		this.#open = v;
		try {
			sessionStorage.setItem(OPEN, JSON.stringify(v));
		} catch {
			// a browser that keeps nothing forgets the open works on a reload
		}
	}

	// a work's tab
	beside = $state<Record<string, Beside | null>>({});
	/** The work whose outline is being chosen in, and what is ticked there. */
	choosing = $state<string | null>(null);
	/** The work whose entry is open as a field to edit, by reference; one at a time. */
	editingEntry = $state<string | null>(null);
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
		this.show(ref);
	}

	/** Shows a tab by going to its address, so Back and Forward move between the Library's tabs and a reload stays on it. */
	show(tab: string): void {
		this.tab = tab;
		void goto(this.address, { keepFocus: true, noScroll: true });
	}

	/** The tab the address names, opened where it is not: what a reload, Back, Forward or a link lands on. */
	arrive(tab: string): void {
		if (tab !== 'works' && !this.open.includes(tab)) this.open = [...this.open, tab];
		this.tab = tab;
	}

	/** Closes a work's tab; the tab to its left, or the list, comes forward. */
	closeWork(ref: string): void {
		const at = this.open.indexOf(ref);
		this.open = this.open.filter((r) => r !== ref);
		if (this.tab === ref) this.show(this.open[Math.max(0, at - 1)] ?? 'works');
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

	/** A work's reader's view and annotating, kept while the person moves between tabs; its paper's zoom is its own, kept for the visit. */
	reader(ref: string): { view: PdfView; notes: Annotating } {
		let r = this.#readers.get(ref);
		if (!r) this.#readers.set(ref, (r = { view: new PdfView(zooms()[ref], (z) => keepZoom(ref, z)), notes: new Annotating(`work:${ref}`) }));
		return r;
	}

	/** Each work's paper as its reader names it: its address and its file's name. */
	#papers = new SvelteMap<string, { url: string; name: string }>();
	#desks = new Map<string, MarkDesk>();

	/** Says which paper a work's reader shows, for its desk. */
	paper(ref: string, url: string, name: string): void {
		const was = this.#papers.get(ref);
		if (was?.url !== url || was?.name !== name) this.#papers.set(ref, { url, name });
	}

	/** A work's reader's drawing desk, one for the work wherever its reader and its bar are drawn: in a Library tab the reader's own bar, beside a draft the pane's. */
	desk(ref: string): MarkDesk {
		let d = this.#desks.get(ref);
		if (!d) {
			d = new MarkDesk(() => ({ on: ref, owns: (a) => a.target.work === ref, url: this.#papers.get(ref)?.url ?? '', name: this.#papers.get(ref)?.name ?? '', notes: this.reader(ref).notes }));
			this.#desks.set(ref, d);
		}
		return d;
	}
}

export const lib = new LibraryState();
