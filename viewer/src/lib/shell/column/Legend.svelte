<script lang="ts">
	// The quiet link in the column's foot, How loom works, and the panel it opens: the margin's icons beside a text (as `fragments/gutter.ts` draws them), the marks of how a result stands with its paper and its Lean, the mark a person puts on a page, and when a version is kept and how to compare. A click anywhere else, Escape, or the keyboard moving past it closes it.
	//
	// The panel is a `Popover` above the link, fixed to the window, so it is not cut to the column's width.
	import Popover from '$lib/components/Popover.svelte';
	import Mark, { type MarkKind } from '$lib/marks/Mark.svelte';
	import { frame } from '$lib/words/frame';

	let open = $state(false);
	let box = $state<HTMLElement | null>(null);
	const PAPER: MarkKind[] = ['checked', 'unchecked', 'stub'];
	const LEAN: MarkKind[] = ['formalized', 'assumed', 'attest', 'not'];
	const w = frame.legend;

	function left(e: FocusEvent): void {
		if (open && box && !box.contains(e.relatedTarget as Node | null)) open = false;
	}
</script>

<div class="legend" bind:this={box} onfocusout={left}>
	<Popover bind:open placement="above" width={300} role="note" label={w.open} testid="legend">
		{#snippet trigger({ open, toggle })}
			<button type="button" class="open" aria-expanded={open} aria-controls="how-loom-works" data-testid="legend-open" onclick={toggle}>{w.open}</button>
		{/snippet}
		<div class="pop" id="how-loom-works">
			<p class="title">{w.open}</p>
			{w.margin}
			<div class="lg" data-testid="legend-margin">
				<span class="mi ma" aria-hidden="true"></span><span>{w.icons.annotation}</span>
				<span class="mi ma talk" aria-hidden="true"></span><span>{w.icons.comment}</span>
				<span class="mi mc" aria-hidden="true"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg></span><span>{w.icons.edit}</span>
				<span class="mi mg" aria-hidden="true">2</span><span>{w.icons.count}</span>
			</div>
			{w.head}
			<div class="lg">{#each PAPER as k (k)}<Mark kind={k} size={14} hidden /><span>{frame.marks[k]}</span>{/each}</div>
			{w.lean}
			<div class="lg">{#each LEAN as k (k)}<Mark kind={k} size={14} hidden /><span>{frame.marks[k]}</span>{/each}</div>
			{w.page}
			<div class="lg"><Mark kind="marked" size={14} hidden /><span>{frame.marks.marked}</span></div>
			{w.versions}
			<p class="say" data-testid="legend-versions">{w.made}</p>
			<p class="say last">{w.compare}</p>
		</div>
	</Popover>
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
		padding: 10px 12px;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.title {
		margin: 0 0 8px;
		color: var(--ink);
		font-size: 13px;
		font-weight: 500;
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
	.say {
		margin: 4px 0 8px;
		color: var(--ink);
		font-size: 12px;
		line-height: 1.45;
	}
	.say.last {
		margin-bottom: 0;
	}
	/* the margin's icons, drawn as the margin draws them (theme.css, "The margin beside a text") */
	.mi {
		display: grid;
		place-items: center;
		justify-self: center;
		box-sizing: border-box;
	}
	.mi.ma {
		width: 11px;
		height: 11px;
		background: var(--ann-blue-band);
		border: 1.5px solid var(--ann-blue);
		border-radius: 50%;
	}
	.mi.ma.talk {
		border-radius: 3px 3px 3px 0;
	}
	.mi.mc {
		width: 15px;
		height: 15px;
		color: var(--change);
		background: var(--sheet);
		border: 1px solid color-mix(in srgb, var(--change) 55%, transparent);
		border-radius: 4px;
	}
	.mi.mg {
		min-width: 16px;
		height: 15px;
		padding: 0 3px;
		font-family: var(--sans);
		font-size: 10px;
		font-weight: 600;
		line-height: 1;
		color: var(--ink-soft);
		background: var(--sheet);
		border: 1px solid var(--rule-strong);
		border-radius: 8px;
	}
</style>
