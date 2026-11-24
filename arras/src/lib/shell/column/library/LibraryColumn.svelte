<script lang="ts">
	// The Library's column: with the list of works shown, its four filters; with a work's tab shown, the work's head (its title, byline, what loom holds, its entry, `digest…`) and its outline (`WorkOutline`). What it draws comes from the Library's state, which outlives the column when it folds.
	import '$lib/views/library/library.css';
	import { lib, type Filter } from '$lib/views/library/state.svelte';
	import { library as words } from '$lib/words/library';
	import WorkHead from './WorkHead.svelte';
	import WorkOutline from './WorkOutline.svelte';

	const FILTERS: Filter[] = ['all', 'used', 'unchecked', 'nodoc'];
	const work = $derived(lib.tab !== 'works' && lib.work.value?.ref === lib.tab ? lib.work.value : null);
</script>

<div class="lv-col rail-scroll" data-testid="library-column">
	{#if lib.tab === 'works'}
		<nav class="navl" aria-label={words.column.filtersLabel}>
			{#each FILTERS as f (f)}
				<button type="button" class:on={lib.filter === f} aria-current={lib.filter === f ? 'true' : undefined} onclick={() => (lib.filter = f)} data-testid="filter-{f}">{words.column.filters[f]}</button>
			{/each}
		</nav>
	{:else if work}
		<WorkHead {work} />
		<WorkOutline {work} />
	{/if}
</div>

<style>
	.lv-col {
		flex: 1;
		min-height: 0;
		overflow: auto;
		margin: 0 -8px;
		padding: 0 8px 10px;
		font-size: 13px;
	}
	.navl {
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.navl button {
		font: inherit;
		text-align: left;
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 4px 8px;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink);
		cursor: pointer;
	}
	.navl button:hover {
		background: var(--ann-neutral-wash);
	}
	.navl button.on {
		background: var(--ann-neutral-wash);
		font-weight: 500;
	}
</style>
