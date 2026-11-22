<script lang="ts">
	// Review's list (`docs/specs/library-views.md` §4.2): under Everything a group for each kind, ordered by who is waiting, each folding, then a rule and the tasks waiting for an agent, folded; a kind alone when the column chooses one; narrowed to a draft when the column chooses one. Read again whenever the library's generation moves. Accepted results that changed and Proposed edits are today's Your Changes, a section each (`yours.ts`), and under Everything each is a group while its section lists something waiting.
	import { said } from '$lib/library/said';
	import './review.css';
	import { page } from '$app/state';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import type { ReviewGroup, ReviewKind } from '$lib/library/types';
	import { store } from '$lib/manifest/client.svelte';
	import { acted } from '$lib/review/acted.svelte';
	import YourChanges from '$lib/review/YourChanges.svelte';
	import { review as words } from '$lib/words/review';
	import { RANK, rv } from './state.svelte';
	import Group from './Group.svelte';
	import Row from './Row.svelte';
	import Task from './Task.svelte';
	import { reviewNames } from './names.svelte';
	import ReadAll from './ReadAll.svelte';
	import { stubsOf } from './rows';
	import SeeIt from './SeeIt.svelte';
	import Pull from './Pull.svelte';
	import YoursGroup from './YoursGroup.svelte';
	import { isYours as yours, PARTS, yoursCount } from './yours';

	const part = $derived(yours(rv.kind) ? PARTS[rv.kind] : undefined);

	$effect(() => {
		const kind = rv.kind;
		const doc = rv.doc ?? undefined;
		void gen.gen;
		if (kind !== 'incoming' && !yours(kind)) void rv.list.load(`list:${kind}:${doc ?? ''}`, (s) => api.reviewList(kind, doc, s));
	});

	const groups = $derived((rv.list.value?.groups ?? []).filter((g) => g.rows.length && !yours(g.kind)));
	// the works and results the rows name by id, read once each
	$effect(() => reviewNames.want(groups.flatMap((g) => g.rows)));

	// a link to one block's row (`#review-…`) opens the accept section under Everything, even where nothing in it waits
	const linked = $derived(page.url.hash.startsWith('#review-'));
	$effect(() => {
		if (linked) rv.folded.delete('accepted-changed');
	});
	type Entry = { kind: ReviewKind | 'agents'; group?: ReviewGroup; n?: number };
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
		{#if rv.kind === 'incoming'}
			<Pull />
		{:else if part}
			<YourChanges {part} />
		{:else if rv.list.error}
			<p class="empty">{rv.list.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(rv.list.error))}</p>
		{:else if !rv.list.value}
			<p class="empty">{words.list.loading}</p>
		{:else if rv.kind === 'all'}
			{#each entries as e (e.kind)}
				{#if e.kind === 'agents'}<div class="rg-rule"></div>{/if}
				{#if e.group}<Group group={e.group} />{:else if yours(e.kind)}<YoursGroup kind={e.kind} n={e.n ?? 0} />{/if}
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
