<script lang="ts">
	// Review's list (`docs/specs/library-views.md` §4.2): under Everything a group for each kind, ordered by who is waiting, each folding, then a rule and the tasks waiting for an agent, folded; a kind alone when the column chooses one; narrowed to a draft when the column chooses one. Read again whenever the library's generation moves.
	import { said } from '$lib/library/said';
	import './review.css';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';
	import Group from './Group.svelte';
	import Row from './Row.svelte';
	import Task from './Task.svelte';
	import ReadAll from './ReadAll.svelte';
	import { stubsOf } from './rows';
	import SeeIt from './SeeIt.svelte';
	import Pull from './Pull.svelte';

	$effect(() => {
		const kind = rv.kind;
		const doc = rv.doc ?? undefined;
		void gen.gen;
		if (kind !== 'incoming') void rv.list.load(`list:${kind}:${doc ?? ''}`, (s) => api.reviewList(kind, doc, s));
	});

	const groups = $derived((rv.list.value?.groups ?? []).filter((g) => g.rows.length));
</script>

<main class="rvw" data-testid="review-view">
	<div class="scroll">
	<div class="list">
		{#if rv.kind === 'incoming'}
			<Pull />
		{:else if rv.list.error}
			<p class="empty">{rv.list.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(rv.list.error))}</p>
		{:else if !rv.list.value}
			<p class="empty">{words.list.loading}</p>
		{:else if !groups.length}
			<p class="empty" data-testid="review-empty">{words.list.empty}</p>
		{:else if rv.kind === 'all'}
			{#each groups as g (g.kind)}
				{#if g.kind === 'agents'}<div class="rg-rule"></div>{/if}
				<Group group={g} />
			{/each}
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
