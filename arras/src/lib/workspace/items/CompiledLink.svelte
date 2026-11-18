<script lang="ts">
	// **PDF** on a document's toolbar: a link to the PDF loom compiled from it, which a link in a pane opens beside the text (W7), as the tree's row under the document does in the pane in focus. Beside it, in words, what the tree's row says: `compiling`, `waiting to compile`, `did not compile` with the error as its title, `compiled with errors`; and `not compiled yet` where there is no PDF, when `PDF` stands greyed and opens nothing.
	import { compileError, compiles, pdfWord } from '$lib/manifest/compiles.svelte';
	import type { Master } from '$lib/manifest/types';
	import { pdfRoute } from '../item';

	let { document, of, divided = false }: { document: Master; of: string; divided?: boolean } = $props();

	const c = $derived(compiles.all[document.path]);
	const word = $derived(pdfWord(!!document.pdf, c));
	const why = $derived(compileError(c));
	const wrong = $derived(!!c?.last && c.last.result !== 'ok' && c.state === 'idle');
</script>

<span class="compiled" class:divided role="group" aria-label="the PDF of {of}" data-testid="toolbar-pdf" data-document={document.path}>
	{#if document.pdf}
		<a class="tool" href={pdfRoute(document.path)} title="Open the PDF loom compiled from {document.path}" aria-label="PDF of {of}{word ? `, ${word}` : ''}">PDF</a>
	{:else}
		<span class="tool off" aria-disabled="true" title="{document.path} has no compiled PDF yet">PDF</span>
	{/if}
	{#if word}<span class="said" class:wrong title={why || undefined} data-testid="toolbar-pdf-state">{word}</span>{/if}
</span>

<style>
	.compiled {
		display: inline-flex;
		align-items: center;
		gap: 3px;
	}
	/* the divider before it, only when something stands to its left */
	.compiled.divided {
		padding-left: 6px;
		margin-left: 4px;
		border-left: 1px solid var(--rule);
	}
	.tool {
		display: inline-flex;
		align-items: center;
		height: 22px;
		padding: 0 6px;
		color: var(--ink-soft);
		text-decoration: none;
		border-radius: 4px;
	}
	a.tool:hover,
	a.tool:focus-visible {
		color: var(--ink);
		background: var(--leaf);
		outline: none;
	}
	.tool.off {
		color: var(--ink-faint);
		cursor: default;
	}
	.said {
		padding-right: 4px;
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.said.wrong {
		color: var(--ink-soft);
	}
</style>
