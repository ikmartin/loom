<script lang="ts">
	// The Web (`docs/specs/library-views.md` §5): as a list, the list beside the trail, the result in focus and what it uses and what uses it; as a graph, the trail, the graph and the focus card under it at full width. The result in focus is the trail's last; until one is chosen, the card says to choose one. Every read is asked again when the library's generation moves.
	import './web.css';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { wb } from './state.svelte';
	import FocusCard from './FocusCard.svelte';
	import Graph from './Graph.svelte';
	import Neighbourhood from './Neighbourhood.svelte';
	import Trail from './Trail.svelte';
	import WebList from './WebList.svelte';
	import { web as words } from '$lib/words/web';

	$effect(() => {
		const r = wb.at;
		const w = wb.where;
		void gen.gen;
		if (r) void wb.focus.load(`${w.scope}:${w.doc}:${r}`, (s) => api.webFocus(w, r, false, s));
	});
	$effect(() => {
		const r = wb.at;
		const w = wb.where;
		void gen.gen;
		if (r && wb.form === 'graph') void wb.graph.load(`${w.scope}:${w.doc}:${r}`, (s) => api.webGraph(w, r, s));
	});
	const focus = $derived(wb.focus.value?.row.result === wb.at ? wb.focus.value : null);
</script>

<main class="wv" data-testid="web-view">
	{#if wb.form === 'list'}
		<div class="webp">
			<WebList />
			<div class="wfocus">
				<Trail />
				{#if focus}<FocusCard {focus} /><Neighbourhood {focus} />{:else if !wb.at}<p class="none" data-testid="web-none">{words.focus.choose}</p>{/if}
			</div>
		</div>
	{:else}
		<div class="drawn">
			<Trail />
			{#if wb.graph.value && wb.graph.value.focus.result === wb.at}<Graph graph={wb.graph.value} />{/if}
			{#if focus}<FocusCard {focus} />{:else if !wb.at}<p class="none" data-testid="web-none">{words.focus.choose}</p>{/if}
		</div>
	{/if}
</main>
