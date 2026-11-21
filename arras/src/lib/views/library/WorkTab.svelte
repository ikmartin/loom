<script lang="ts">
	// A work's tab (2, 3): the paper in the one reader, and beside it the result chosen in the outline or on the page. A work loom holds no document of says so, with its own page to open. Its outline is the column's (`shell/column/library/`).
	import { said } from '$lib/library/said';
	import { lib } from './state.svelte';
	import { library as words } from '$lib/words/library';
	import WorkReader from './WorkReader.svelte';
	import NodeSide from './NodeSide.svelte';

	let { ref }: { ref: string } = $props();

	const w = $derived(lib.work.value?.ref === ref ? lib.work.value : null);
	const beside = $derived(lib.beside[ref] ?? null);
</script>

{#if lib.work.error && !w}
	<p class="note" role="alert">{said(lib.work.error)}</p>
{:else if !w}
	<p class="note grey">{words.works.loading}</p>
{:else if !w.holds.pdf}
	<div class="nodoc" data-testid="work-no-document">
		<p class="grey">{words.reader.noDocument}</p>
		{#if w.link}<button type="button" class="btn" onclick={() => window.open(w.link!, '_blank', 'noopener')}>{words.works.openSource}</button>{/if}
	</div>
{:else}
	<div class="body">
		<WorkReader work={w} />
		{#if beside}<NodeSide {ref} {beside} />{/if}
	</div>
{/if}

<style>
	.note {
		padding: 20px;
	}
	.nodoc {
		padding: 24px 28px;
		max-width: 560px;
	}
	.nodoc p {
		margin: 0 0 12px;
	}
	.body {
		flex: 1;
		min-height: 0;
		display: flex;
	}
</style>
