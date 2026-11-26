<script lang="ts">
	// A text in a view: a fragment of the build by its path (a Review body, a draft's result in the Web), its change marked as a pending change's is (struck old words, new words underlined), a citation marked where asked, and its mathematics typeset with the quilt's macros.
	import { tick } from 'svelte';
	import * as api from '$lib/library/api';
	import { store } from '$lib/manifest/client.svelte';
	import { typeset } from '$lib/math/mathjax';
	import { review as words } from '$lib/words/review';

	let { fragment, hot = null }: { fragment: string; /** Which of its citations (`span.cite`) to mark, counted from 0. */ hot?: number | null } = $props();
	let html = $state<string | null | undefined>(undefined);
	let box = $state<HTMLElement | null>(null);

	$effect(() => {
		const path = fragment;
		void api.fragment(path).then(async (h) => {
			if (path !== fragment) return;
			html = h;
			await tick();
			if (!box) return;
			if (hot !== null) box.querySelectorAll('span.cite')[hot]?.classList.add('hot');
			void typeset(box, store.manifest?.macros?.default ?? []);
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
		text-indent: 0;
	}
	.statement :global(span.cite.hot) {
		background: var(--link-wash);
		border-radius: 3px;
	}
</style>
