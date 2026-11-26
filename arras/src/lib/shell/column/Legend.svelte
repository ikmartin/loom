<script lang="ts">
	// The quiet link in the column's foot, "what the marks mean", and the legend it opens: the marks of a result's reading of its paper, of Lean, and the mark a person puts on a page. A click anywhere else, Escape, or the keyboard moving past it closes it.
	import Mark, { type MarkKind } from '$lib/marks/Mark.svelte';
	import { frame } from '$lib/words/frame';

	let open = $state(false);
	let box = $state<HTMLElement | null>(null);
	const PAPER: MarkKind[] = ['checked', 'unchecked', 'stub'];
	const LEAN: MarkKind[] = ['formalized', 'assumed', 'attest', 'not'];

	function away(e: PointerEvent): void {
		if (open && box && !box.contains(e.target as Node)) open = false;
	}
	function left(e: FocusEvent): void {
		if (open && box && !box.contains(e.relatedTarget as Node | null)) open = false;
	}
</script>

<svelte:window onpointerdown={away} onkeydown={(e) => e.key === 'Escape' && (open = false)} />

<div class="legend" bind:this={box} onfocusout={left}>
	{#if open}
		<div class="pop" id="marks-legend" data-testid="legend">
			{frame.legend.head}
			<div class="lg">{#each PAPER as k (k)}<Mark kind={k} size={14} hidden /><span>{frame.marks[k]}</span>{/each}</div>
			{frame.legend.lean}
			<div class="lg">{#each LEAN as k (k)}<Mark kind={k} size={14} hidden /><span>{frame.marks[k]}</span>{/each}</div>
			{frame.legend.page}
			<div class="lg last"><Mark kind="marked" size={14} hidden /><span>{frame.marks.marked}</span></div>
		</div>
	{/if}
	<button type="button" class="open" aria-expanded={open} aria-controls="marks-legend" data-testid="legend-open" onclick={() => (open = !open)}>{frame.legend.open}</button>
</div>

<style>
	.legend {
		position: relative;
		padding: 4px 14px 6px;
	}
	.open {
		font: inherit;
		font-size: 11px;
		color: var(--ink-faint);
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}
	.open:hover {
		color: var(--ink);
	}
	.pop {
		position: absolute;
		left: 12px;
		bottom: calc(100% + 4px);
		width: 250px;
		z-index: 70;
		padding: 10px 12px;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 10px;
		box-shadow: var(--float-shadow);
		font-size: 11px;
		color: var(--ink-faint);
	}
	.lg {
		display: grid;
		grid-template-columns: 16px 1fr;
		gap: 4px 8px;
		align-items: center;
		margin: 4px 0 8px;
		color: var(--ink);
		font-size: 13px;
	}
	.lg.last {
		margin-bottom: 0;
	}
</style>
