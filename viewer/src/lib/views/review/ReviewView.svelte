<script lang="ts">
	// Review's list (`docs/specs/library-views.md` §4.2): under Everything a group for each kind, ordered by who is waiting, each folding, then a rule and the tasks waiting for an agent, folded; a kind alone when the column chooses one; narrowed to a draft when the column chooses one. Read again whenever the library's generation moves. Lean statements to attest holds the attested results that changed, first (`joined`). Results to accept and Proposed edits are drawn from the manifest, whose acts they hold (`Accepting`, `Keeping`, `yours.ts`), and under Everything each is a group while it lists something waiting.
	import { said } from '$lib/library/said';
	import './review.css';
	import { page } from '$app/state';
	import { library as gen } from '$lib/library/gen.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { acted } from '$lib/review/acted.svelte';
	import { review as words } from '$lib/words/review';
	import { RANK, readList, rv } from './state.svelte';
	import Group from './Group.svelte';
	import Row from './Row.svelte';
	import Task from './Task.svelte';
	import { reviewNames } from './names.svelte';
	import ReadAll from './ReadAll.svelte';
	import { joined, stubsOf, type ShownGroup, type ShownKind } from './rows';
	import SeeIt from './SeeIt.svelte';
	import Accepting from './Accepting.svelte';
	import Keeping from './Keeping.svelte';
	import { isYours as yours, yoursCount } from './yours';

	$effect(() => {
		const kind = rv.kind;
		const doc = rv.doc ?? undefined;
		void gen.gen;
		if (!yours(kind)) void rv.list.load(`list:${kind}:${doc ?? ''}`, (s) => readList(kind, doc, s));
	});

	const groups = $derived(joined(rv.list.value?.groups ?? []).filter((g) => g.rows.length && !yours(g.kind)));
	// the works and results the rows name by id, read once each
	$effect(() => reviewNames.want(groups.flatMap((g) => g.rows)));

	// a link to one block's row (`#review-…`) opens Results to accept under Everything, even where nothing in it waits
	const linked = $derived(page.url.hash.startsWith('#review-'));
	$effect(() => {
		if (linked) rv.folded.delete('accepted-changed');
	});
	type Entry = { kind: ShownKind; group?: ShownGroup; n?: number };
	const entries = $derived.by((): Entry[] => {
		const m = store.manifest;
		return RANK.flatMap((kind): Entry[] => {
			if (yours(kind)) {
				const n = m ? yoursCount(kind, m, acted.map, rv.doc) : 0;
				return n || (kind === 'accepted-changed' && linked) ? [{ kind, n }] : [];
			}
			const group = groups.find((g) => g.kind === kind);
			return group ? [{ kind, group }] : [];
		});
	});
</script>

<main class="rvw" data-testid="review-view">
	<div class="scroll">
	<div class="list">
		{#if yours(rv.kind)}
			{#if store.manifest && !yoursCount(rv.kind, store.manifest, acted.map, rv.doc)}<p class="empty" data-testid="review-empty">{words.list.empty}</p>{/if}
			{#if rv.kind === 'accepted-changed'}<Accepting />{:else}<Keeping />{/if}
		{:else if rv.list.error}
			<p class="empty">{rv.list.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(rv.list.error))}</p>
		{:else if !rv.list.value}
			<p class="empty">{words.list.loading}</p>
		{:else if rv.kind === 'all'}
			{#each entries as e (e.kind)}
				{#if e.kind === 'agents'}<div class="rg-rule"></div>{/if}
				{#if e.group}<Group group={e.group} />{:else if yours(e.kind)}<Group kind={e.kind} n={e.n ?? 0}>{#if e.kind === 'accepted-changed'}<Accepting />{:else}<Keeping />{/if}</Group>{/if}
			{:else}
				<p class="empty" data-testid="review-empty">{words.list.empty}</p>
			{/each}
		{:else if !groups.length}
			<p class="empty" data-testid="review-empty">{words.list.empty}</p>
		{:else}
			{#if rv.kind === 'cited' && stubsOf(groups[0].rows).length}
				<div class="rg head">{words.cited.head(stubsOf(groups[0].rows).length)}<ReadAll rows={groups[0].rows} /></div>
			{/if}
			{#each groups[0].rows as r (r.row)}
				{#if r.kind === 'agents'}<Task row={r} />{:else}<Row row={r} />{/if}
			{/each}
		{/if}
	</div>
	</div>
	{#if rv.over}<SeeIt over={rv.over} />{/if}
</main>
