// What Review remembers while the person moves between views: the kind and the draft the column chose, the groups folded under Everything, the rows open, and the reads on screen. Kept in this module, since the column and the list both draw from it and a view is taken down when another is shown. Whether the source serves Review's reads is asked once: where it does not, Review is today's, its sections and their pages.

import { SvelteSet } from 'svelte/reactivity';
import * as api from '$lib/library/api';
import { Read } from '$lib/library/read.svelte';
import type { ReviewCounts, ReviewKind, ReviewList } from '$lib/library/types';
import type { ShownKind } from './rows';

/** The kinds as the column lists them: alphabetically by their names. Lean statements to attest holds the attested results that changed too (`joined`). */
export const COLUMN_ORDER: Exclude<ShownKind, 'agents'>[] = ['accepted-changed', 'questions', 'cited', 'check', 'attest', 'fetch', 'edits'];

/** The groups' order under Everything, by who waits, as `review-list` answers them; the two kinds today's Your Changes draws take their places in it. */
export const RANK: ShownKind[] = ['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'edits', 'agents'];

/** The kinds of loom's that one entry of the column reads, in the order its list shows them. */
export const READS: Partial<Record<ReviewKind, ReviewKind[]>> = { attest: ['attested-changed', 'attest'] };

/** `review-list` for what the list shows: one kind, or the kinds one entry of the column reads (`READS`) as one answer, each asked whole. */
export async function readList(kind: ReviewKind | 'all' | 'agents', doc?: string, s?: number): Promise<api.Answer<ReviewList>> {
	const kinds = kind === 'all' || kind === 'agents' ? undefined : READS[kind];
	if (!kinds) return api.reviewList(kind, doc, s);
	const answers = await Promise.all(kinds.map((k) => api.reviewList(k, doc)));
	const values: ReviewList[] = [];
	for (const a of answers) {
		if (!a.ok) return a;
		values.push(a.value);
	}
	return { ok: true, value: { gen: Math.max(...values.map((v) => v.gen)), groups: values.flatMap((v) => v.groups) } };
}

class ReviewState {
	/** What the list shows: everything, one kind, the tasks waiting for an agent, or a collaborator's pull. */
	kind = $state<ReviewKind | 'all' | 'agents' | 'incoming'>('all');
	/** A document laid over the list, read only, at a result; none while the list shows. */
	over = $state<{ doc: string; key: string; name: string } | null>(null);
	/** The draft the list is narrowed to, or none. */
	doc = $state<string | null>(null);
	/** Kinds folded under Everything; the agents' group starts folded. */
	folded = new SvelteSet<string>(['agents']);
	/** Rows open, by their ids, which stay the same while what they are about waits. */
	open = new SvelteSet<string>();
	/** Inside an open row of a work, the result open under it, by the row; a row not in here opens its first. */
	sub = $state<Record<string, string | null>>({});
	/** Whether results are shown as their LaTeX rather than drawn. */
	plain = $state(false);
	/** Whether the source answers Review's reads; null until it has said. */
	served = $state<boolean | null>(null);

	counts = new Read<ReviewCounts>();
	list = new Read<ReviewList>();
	/** Loom's own rows of the two kinds today's Your Changes draws, whole, by which a draft's count is made what is drawn. */
	theirs = { 'accepted-changed': new Read<ReviewList>(), edits: new Read<ReviewList>() };

	#asked = false;

	/** Asks once whether Review's reads are served. */
	ask(): void {
		if (this.#asked) return;
		this.#asked = true;
		void api.serves('review-list').then((yes) => (this.served = yes));
	}

	/** Shows one kind, or everything; choosing Everything shows every draft again. */
	choose(kind: ReviewKind | 'all' | 'agents' | 'incoming'): void {
		this.kind = kind;
		this.over = null;
		if (kind === 'all') this.doc = null;
	}

	/** Narrows the list to one draft, or widens it again when that draft is chosen twice. */
	draft(doc: string): void {
		this.doc = this.doc === doc ? null : doc;
	}

	fold(kind: string): void {
		if (this.folded.has(kind)) this.folded.delete(kind);
		else this.folded.add(kind);
	}

	toggle(row: string): void {
		if (this.open.has(row)) this.open.delete(row);
		else this.open.add(row);
	}
}

export const rv = new ReviewState();
