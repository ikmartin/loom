// What the Web remembers while the person moves between views: its scope and draft, its form, the list's order, search and open groups, the result in focus and the trail of results followed, and the reads on screen. Kept in this module, since the column and the view both draw from it and a view is taken down when another is shown. Whether the source serves the Web's reads is asked once.

import { SvelteMap, SvelteSet } from 'svelte/reactivity';
import * as api from '$lib/library/api';
import { store } from '$lib/manifest/client.svelte';
import { mainDraft } from '$lib/manifest/documents';
import { Read } from '$lib/library/read.svelte';
import type { Row, WebFocus, WebGraph, WebList, WebScope } from '$lib/library/types';

/** How many results the trail keeps. */
const TRAIL = 6;

class WebState {
	scope = $state<WebScope>('deps');
	/** The draft the person chose for a scope of one draft. */
	#chosen = $state<string | null>(null);
	form = $state<'list' | 'graph'>('list');
	sort = $state<'document' | 'status'>('document');
	q = $state('');
	/** Groups whose fold the person turned from how it starts: folded groups opened, open ones folded. */
	turned = new SvelteSet<string>();
	/** An opened folded group's rows (`web-group`), by group. */
	groups = new SvelteMap<string, Row[]>();
	/** The result in focus, and the results followed to it, the last being the focus. */
	trail = $state<{ result: string; name: string; title?: string }[]>([]);
	/** Whether the focus card's fold of proofs, Lean and record is open. */
	more = $state(false);
	served = $state<boolean | null>(null);
	/** The person's results chosen to formalize. */
	chosen = new SvelteSet<string>();

	list = new Read<WebList>();
	focus = new Read<WebFocus>();
	graph = new Read<WebGraph>();

	#asked = false;

	/** The draft a scope of one draft names: the one chosen, else the quilt's main draft; null where the quilt names none. */
	get doc(): string | null {
		return this.#chosen ?? mainDraft(store.manifest);
	}
	set doc(path: string | null) {
		this.#chosen = path;
	}

	/** Whether the reads may be asked: a scope of one draft has a draft to name. */
	get named(): boolean {
		return (this.scope !== 'draft' && this.scope !== 'deps') || !!this.doc;
	}

	/** Whether the scope names a draft and the quilt has none to name: no main draft, and none chosen. */
	get draftless(): boolean {
		return !this.named && !!store.manifest;
	}

	get at(): string | null {
		return this.trail.at(-1)?.result ?? null;
	}

	/** Where every read looks. */
	get where(): api.InScope {
		return { scope: this.scope, ...(this.doc ? { doc: this.doc } : {}) };
	}

	ask(): void {
		if (this.#asked) return;
		this.#asked = true;
		void api.serves('web-list').then((yes) => (this.served = yes));
	}

	/** Puts `row` in focus, at the end of the trail. */
	follow(row: Row): void {
		if (this.at === row.result) return;
		this.trail = [...this.trail.filter((t) => t.result !== row.result), { result: row.result, name: row.name, ...(row.title ? { title: row.title } : {}) }].slice(-TRAIL);
		this.more = false;
	}

	/** Goes back along the trail to its `i`th result. */
	back(i: number): void {
		this.trail = this.trail.slice(0, i + 1);
		this.more = false;
	}

	/** Chooses the scope, forgetting the groups opened under the last. */
	choose(scope: WebScope): void {
		this.scope = scope;
		this.turned.clear();
		this.groups.clear();
	}
}

export const wb = new WebState();

/** Whether a result may be chosen to formalize: one of the person's results that no Lean states yet. */
export const choosable = (r: Row): boolean => !!r.source && 'doc' in r.source && (r.lean?.lean ?? 'none') === 'none';
