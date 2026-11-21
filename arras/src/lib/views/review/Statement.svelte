<script lang="ts">
	// A text in a Review body: a fragment of the build by its path, its change marked as a pending change's is (struck old words, new words underlined), and its mathematics typeset with the quilt's macros.
	import { tick } from 'svelte';
	import * as api from '$lib/library/api';
	import { store } from '$lib/manifest/client.svelte';
	import { typeset } from '$lib/math/mathjax';
	import { review as words } from '$lib/words/review';

	let { fragment }: { fragment: string } = $props();
	let html = $state<string | null | undefined>(undefined);
	let box = $state<HTMLElement | null>(null);

	$effect(() => {
		const path = fragment;
		void api.fragment(path).then(async (h) => {
			if (path !== fragment) return;
			html = h;
			await tick();
			if (box) void typeset(box, store.manifest?.macros?.default ?? []);
		});
	});
</script>

{#if html === null}
	<p class="note">{words.statement.missing}</p>
{:else if html}
	<div class="statement fragment changes-markup" bind:this={box} data-testid="review-statement">{@html html}</div>
{/if}

<style>
	.statement {
		margin: 0 0 12px;
		font-family: var(--font-text, serif);
		font-size: 15px;
		line-height: 1.5;
	}
	.statement :global(p) {
		margin: 0;
	}
</style>
