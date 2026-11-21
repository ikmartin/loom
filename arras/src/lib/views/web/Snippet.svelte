<script lang="ts">
	// A search hit's words around the match, drawn as a statement is: its text-mode LaTeX turned into HTML and its mathematics typeset, the match marked.
	import { store } from '$lib/manifest/client.svelte';
	import { typeset } from '$lib/math/mathjax';
	import { toHtml } from '$lib/node/latexlite';

	let { snippet }: { snippet: { before: string; match: string; after: string } } = $props();
	let box = $state<HTMLElement | null>(null);
	const html = $derived([toHtml(snippet.before, {}).html, `<mark>${toHtml(snippet.match, {}).html}</mark>`, toHtml(snippet.after, {}).html].join(''));
	$effect(() => {
		void html;
		if (box) void typeset(box, store.manifest?.macros?.default ?? []);
	});
</script>

<p class="hit" bind:this={box} data-testid="web-hit">{@html html}</p>
