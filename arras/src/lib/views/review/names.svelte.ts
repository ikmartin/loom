// The names of what Review's rows name by id (`evidence.md` §6: a row carries ids, never loom's words): a work by its reference, from `library-works`; a library result by its node, from `library-node` (brief), read once each; a draft's result by its label or block, from the manifest. Asked for from an effect (`want`), so no read starts while a row is drawn.

import { SvelteMap } from 'svelte/reactivity';
import * as api from '$lib/library/api';
import { library as gen } from '$lib/library/gen.svelte';
import { Read } from '$lib/library/read.svelte';
import type { ReviewRow, TaskRow, WorksAnswer } from '$lib/library/types';
import { store } from '$lib/manifest/client.svelte';
import { nodeName } from '$lib/workspace/names';
import type { Names } from './rows';

class ReviewNames implements Names {
	#works = new Read<WorksAnswer>();
	#byRef = $derived(new Map((this.#works.value?.works ?? []).map((w) => [w.ref, w])));
	#nodes = new SvelteMap<string, { name: string; short: string }>();
	#asked = new Set<string>();

	work(ref: string): { short: string; title: string } | undefined {
		const w = this.#byRef.get(ref);
		return w ? { short: w.short, title: w.title } : undefined;
	}

	node(id: string): { name: string; short: string } | undefined {
		return this.#nodes.get(id);
	}

	result(label: string): string | undefined {
		const m = store.manifest;
		return m?.nodes[label] ? nodeName(m, label) : undefined;
	}

	/** Reads the works and the nodes `rows` name, each once; the works again as the library changes. */
	want(rows: (ReviewRow | TaskRow)[]): void {
		const refs = rows.some((r) => r.kind === 'fetch' || r.kind === 'agents' || (r.kind === 'questions' && r.on.ref));
		if (refs) {
			void gen.gen;
			void this.#works.load('works', (s) => api.works(undefined, s));
		}
		for (const r of rows) for (const id of nodesOf(r)) this.#ask(id);
	}

	#ask(id: string): void {
		if (this.#asked.has(id)) return;
		this.#asked.add(id);
		void api.node({ node: id, brief: true }).then((a) => {
			if (a.ok) this.#nodes.set(id, { name: a.value.name, short: a.value.work.short });
		});
	}
}

/** The library results a row names by node. */
function nodesOf(r: ReviewRow | TaskRow): string[] {
	if (r.kind === 'agents') return [...(r.nodes ?? []), ...(r.on.node ? [r.on.node] : []), ...(r.target?.node ? [r.target.node] : [])];
	if (r.kind === 'questions' && r.on.node) return [r.on.node];
	return [];
}

export const reviewNames = new ReviewNames();
