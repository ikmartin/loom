<script lang="ts">
	// An HTML draft's own text size, on its toolbar, drawn as a PDF's zoom is: a step down, the size in a box that takes one typed, a step up. It sizes this draft alone, and the size given is where the next draft opened starts (`DocumentState.sizeTo`).
	import { TEXT_MAX, TEXT_MIN } from '$lib/prefs.svelte';
	import type { DocumentState } from '$lib/workspace/state.svelte';
	import { docs as words } from '$lib/words/docs';

	let { doc, of }: { doc: DocumentState; of: string } = $props();

	let text = $state('');
	let editing = $state(false);
	$effect(() => {
		if (!editing) text = words.textSize.said(doc.size);
	});
	// Escape survives the blur it causes, so a cancel does not commit what it cancels
	let dropped = false;

	function commit(): void {
		editing = false;
		if (dropped) return;
		const n = Number.parseFloat(text.replace(/[^0-9.]/g, ''));
		if (Number.isFinite(n) && n > 0) doc.sizeTo(n);
		else text = words.textSize.said(doc.size);
	}
	function key(e: KeyboardEvent): void {
		if (e.key !== 'Enter' && e.key !== 'Escape') return;
		e.preventDefault();
		dropped = e.key === 'Escape';
		commit();
		(e.currentTarget as HTMLInputElement).blur();
		dropped = false;
	}
</script>

<div class="size" role="group" aria-label={words.textSize.group(of)} data-testid="text-size">
	<button type="button" class="step" title={words.textSize.smaller} aria-label={words.textSize.smallerOf(of)} data-testid="text-smaller" disabled={doc.size <= TEXT_MIN} onclick={() => doc.sizeTo(doc.size - 1)}>−</button>
	<input
		class="box"
		type="text"
		inputmode="decimal"
		aria-label={words.textSize.box(of)}
		data-testid="text-size-at"
		bind:value={text}
		onfocus={(e) => ((editing = true), e.currentTarget.select())}
		onblur={commit}
		onkeydown={key}
	/>
	<button type="button" class="step" title={words.textSize.larger} aria-label={words.textSize.largerOf(of)} data-testid="text-larger" disabled={doc.size >= TEXT_MAX} onclick={() => doc.sizeTo(doc.size + 1)}>+</button>
</div>

<style>
	/* as `PdfTools` draws the zoom: square steps either side of a filled box */
	.size {
		display: flex;
		align-items: center;
		gap: 3px;
		white-space: nowrap;
	}
	.step {
		width: 28px;
		height: 28px;
		padding: 0;
		font: inherit;
		font-size: 1.1em;
		line-height: 1;
		color: var(--ink-soft);
		background: none;
		border: none;
		border-radius: 4px;
		cursor: pointer;
	}
	.step:hover:not(:disabled) {
		color: var(--ink);
		background: var(--leaf);
	}
	.step:disabled {
		cursor: default;
		opacity: 0.35;
	}
	.box {
		width: 4.4em;
		height: 22px;
		padding: 0 6px;
		font: inherit;
		color: var(--ink);
		text-align: center;
		background: var(--leaf);
		border: 1px solid transparent;
		border-radius: 4px;
	}
	.box:hover {
		border-color: var(--rule);
	}
	.box:focus {
		outline: none;
		border-color: var(--accent);
		background: var(--sheet);
	}
</style>
