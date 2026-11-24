<script lang="ts" module>
	import { typesetSoon } from '$lib/math/mathjax';
	import type { Macro } from '$lib/manifest/types';

	// the hits waiting to be typeset, all at once when the typing rests, in MathJax's passes, each a task of its own
	const waiting = new Set<HTMLElement>();
	let rest: ReturnType<typeof setTimeout> | undefined;
	const REST_MS = 250;

	function typesetWhenRested(box: HTMLElement, macros: Macro[]): void {
		box.setAttribute('data-typesetting', '');
		waiting.add(box);
		clearTimeout(rest);
		rest = setTimeout(() => {
			const boxes = [...waiting].filter((b) => b.isConnected);
			waiting.clear();
			for (const b of boxes) void typesetSoon(b, macros);
		}, REST_MS);
	}
</script>

<script lang="ts">
	// A search hit's words around the match, drawn as a statement is, in one paragraph: its text-mode LaTeX turned into HTML, the match an inline mark (a whole formula where it falls inside one), and its mathematics typeset once the typing rests.
	import { store } from '$lib/manifest/client.svelte';
	import { toHtml } from '$lib/node/latexlite';
	import { CLOSE, marked, OPEN } from './marked';

	let { snippet }: { snippet: { before: string; match: string; after: string } } = $props();
	let box = $state<HTMLElement | null>(null);
	const html = $derived(toHtml(marked(snippet.before, snippet.match, snippet.after), {}).html.replaceAll(OPEN, '<mark>').replaceAll(CLOSE, '</mark>'));
	$effect(() => {
		void html;
		if (box) typesetWhenRested(box, store.manifest?.macros?.default ?? []);
	});
</script>

<div class="hit" bind:this={box} data-testid="web-hit">{@html html}</div>

<style>
	/* the converter's paragraphs run on as one line of words */
	.hit :global(.tx-par) {
		display: inline;
	}
	.hit :global(.tx-par + .tx-par)::before {
		content: ' ';
	}
</style>
