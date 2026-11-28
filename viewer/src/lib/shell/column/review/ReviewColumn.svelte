<script lang="ts">
	// Review's column (`docs/specs/library-views.md` §4.1): "Waiting for you", Everything and the kinds alphabetically with their counts, Problems among them by its name, which opens Review's Problems page with the count of what is wrong in the person's own files, the drafts with what concerns each, then the tasks agents are still working on, which need nothing of the person, and at its foot History. Each entry has its hover card. Choosing one shows it in Review's list, from any of Review's pages. Every count is what choosing its entry would list: under a draft each kind counts its rows in that draft, and each draft counts what the kind shown holds there (loom's whole list, its rows' `docs`). The two kinds drawn from the manifest, Results to accept and Proposed edits, are counted as their rows are drawn (`views/review/yours.ts`), and Everything and each draft with them.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { route } from '$lib/paths';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import type { ReviewKind } from '$lib/library/types';
	import { hovercard } from '$lib/shell/hovercards.svelte';
	import { COLUMN_ORDER, READS, rv } from '$lib/views/review/state.svelte';
	import { review as words } from '$lib/words/review';
	import { store } from '$lib/manifest/client.svelte';
	import { acted } from '$lib/review/acted.svelte';
	import { YOURS, isYours, theirs, yoursCount, type YoursKind } from '$lib/views/review/yours';
	import { yoursCount as problemsCount } from '$lib/diagnostics';

	$effect(() => {
		void gen.gen;
		void rv.counts.load('counts', (s) => api.reviewCounts(s));
		void rv.whole.load('whole', (s) => api.reviewList('all', undefined, s));
	});

	const m = $derived(store.manifest);
	/** The rows a kind drawn from the manifest lists as waiting, in one draft when given. */
	const ours = (kind: YoursKind, doc?: string | null) => (m ? yoursCount(kind, m, acted.map, doc) : 0);
	/** A kind's count: as drawn for the two from the manifest, else loom's, summed over the kinds the entry reads. */
	const kindCount = (kind: ReviewKind) => (isYours(kind) && m ? ours(kind) : loomCount(kind));
	const loomCount = (kind: ReviewKind) => (READS[kind] ?? [kind]).reduce<number | undefined>((n, k) => (counts?.kinds[k] === undefined ? n : (n ?? 0) + counts.kinds[k]!), undefined);
	/** A draft's count with its two kinds as drawn: loom's until its rows of them are read. */
	function draftCount(d: { doc: string; n: number }): number {
		let n = d.n;
		for (const k of YOURS) {
			const t = theirs(rv.whole.value, d.doc, [k]);
			if (t === null) return d.n;
			n += ours(k, d.doc) - t;
		}
		return n;
	}
	/** What one kind, or the agents' tasks, holds in one draft: as drawn for the two from the manifest, else loom's rows there; '' before loom's whole list is read. */
	function inDraft(kind: ReviewKind | 'agents', doc: string): number | '' {
		if (isYours(kind)) return m ? ours(kind, doc) : '';
		return theirs(rv.whole.value, doc, kind === 'agents' ? ['agents'] : (READS[kind] ?? [kind])) ?? '';
	}
	/** A draft's entry: what the list would show choosing it, the kind shown in that draft. */
	const draftShown = (d: { doc: string; n: number }) => (rv.kind === 'all' ? draftCount(d) : inDraft(rv.kind, d.doc));

	const counts = $derived(rv.counts.value);
	const everything = $derived(counts ? counts.everything + YOURS.reduce((n, k) => n + ours(k) - (counts.kinds[k] ?? 0), 0) : undefined);
	// a draft's whole count is its entry in `drafts`, made what is drawn for the two kinds from the manifest
	const draft = $derived(rv.doc ? counts?.drafts.find((d) => d.doc === rv.doc) : undefined);
	const kinds = $derived(COLUMN_ORDER.filter((k) => loomCount(k) !== undefined));
	const inList = $derived(page.route.id === '/review');
	/** The problems in the person's own files, as Review's Problems page counts them. */
	const problems = $derived(m ? problemsCount(m) : 0);
	const onProblems = $derived(page.route.id === '/review/problems');
	/** The entries under Everything: the kinds, and Problems placed among them by its name. */
	const entries = $derived.by((): ((typeof kinds)[number] | 'problems')[] => {
		const at = kinds.findIndex((k) => words.kinds[k].name.localeCompare(words.column.problems) > 0);
		return at < 0 ? [...kinds, 'problems'] : [...kinds.slice(0, at), 'problems', ...kinds.slice(at)];
	});

	/** Shows `kind` in the list, coming back to it from History. */
	function pick(kind: ReviewKind | 'all' | 'agents'): void {
		rv.choose(kind);
		if (!inList) void goto(route('/review'));
	}
	function narrow(doc: string): void {
		rv.draft(doc);
		if (!inList) void goto(route('/review'));
	}
	const on = (kind: ReviewKind | 'all' | 'agents') => inList && rv.kind === kind;
</script>

<div class="rv-col rail-scroll" data-testid="review-column">
	<p class="rl">{words.column.waiting}</p>
	<nav class="navl" aria-label={words.column.nav}>
		<button type="button" class:on={on('all')} aria-current={on('all') ? 'true' : undefined} data-testid="review-kind-all" use:hovercard={{ text: words.column.everythingHover, place: 'beside' }} onclick={() => pick('all')}
			><span class="t">{words.column.everything}</span><span class="n">{rv.doc ? (draft ? draftCount(draft) : '') : (everything ?? '')}</span></button
		>
		{#each entries as k (k)}
			{#if k === 'problems'}
				<a class="entry" class:on={onProblems} aria-current={onProblems ? 'page' : undefined} href={route('/review/problems')} data-testid="review-problems" use:hovercard={{ text: words.column.problemsHover, place: 'beside' }}
					><span class="t">{words.column.problems}</span><span class="n">{rv.doc ? '' : problems}</span></a
				>
			{:else}
				<button type="button" class:on={on(k)} aria-current={on(k) ? 'true' : undefined} data-testid="review-kind-{k}" use:hovercard={{ text: words.kinds[k].hover, place: 'beside' }} onclick={() => pick(k)}
					><span class="t">{words.kinds[k].name}</span><span class="n">{rv.doc ? inDraft(k, rv.doc) : kindCount(k)}</span></button
				>
			{/if}
		{/each}
	</nav>
	{#if counts?.drafts.length}
		<p class="rl"><span use:hovercard={{ text: words.column.draftsHover, place: 'beside' }}>{words.column.drafts}</span></p>
		<nav class="navl" aria-label={words.column.drafts}>
			{#each counts.drafts as d (d.doc)}
				<button type="button" class:on={inList && rv.doc === d.doc} aria-pressed={rv.doc === d.doc} data-testid="review-draft" onclick={() => narrow(d.doc)}><span class="t">{words.file(d.doc)}</span><span class="n">{draftShown(d)}</span></button>
			{/each}
		</nav>
	{/if}
	<!-- nothing in it needs the person, so it stands apart from what waits for them -->
	<nav class="navl" aria-label={words.kinds.agents.name}>
		<button type="button" class:on={on('agents')} aria-current={on('agents') ? 'true' : undefined} data-testid="review-kind-agents" use:hovercard={{ text: words.kinds.agents.hover, place: 'beside' }} onclick={() => pick('agents')}
			><span class="t">{words.kinds.agents.name}</span><span class="n">{rv.doc ? inDraft('agents', rv.doc) : (counts?.agents ?? '')}</span></button
		>
	</nav>
	<span class="grow"></span>
	<a class="record" class:here={page.route.id?.startsWith('/review/record')} href={route('/review/record')} data-testid="review-record" use:hovercard={{ text: words.column.recordHover, place: 'beside' }}>{words.column.record}</a>
</div>

<style>
	.rv-col {
		flex: 1;
		min-height: 0;
		overflow: auto;
		display: flex;
		flex-direction: column;
		margin: 0 -8px;
		padding: 0 8px 6px;
		font-size: 13px;
	}
	.rl {
		margin: 4px 0 6px;
		padding: 0 2px;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.navl {
		display: flex;
		flex-direction: column;
		gap: 1px;
		margin-bottom: 14px;
	}
	.navl button,
	.navl .entry {
		font: inherit;
		font-size: 12.5px;
		text-align: left;
		display: flex;
		align-items: baseline;
		gap: 6px;
		padding: 4px 6px;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink);
		cursor: pointer;
	}
	.navl .entry {
		text-decoration: none;
	}
	.navl button:hover,
	.navl .entry:hover {
		background: var(--ann-neutral-wash);
	}
	.navl button.on,
	.navl .entry.on {
		background: var(--ann-neutral-wash);
		font-weight: 500;
	}
	/* a label is one line whatever the font and the column's width: its words end in an ellipsis before they wrap, its count stays whole, and its hover says it in full */
	.navl button,
	.navl .entry {
		min-width: 0;
	}
	.t {
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.n {
		flex: none;
		margin-left: auto;
		font-size: 12px;
		color: var(--ink-faint);
		font-variant-numeric: tabular-nums;
		font-weight: 400;
	}
	.grow {
		flex: 1;
	}
	.record {
		align-self: flex-start;
		margin: 10px 2px 0;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.record:hover,
	.record.here {
		color: var(--ink);
		text-decoration: none;
	}
</style>
