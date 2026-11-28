<script lang="ts">
	// The PDF's own tools, after Annotate, Comment and Undo and Redo on a page's toolbar: ink, words on the page, a box, an oval and an arrow, each drawn in the look in hand. A tool stays up until another is chosen, it is pressed again or Escape is pressed, as a pen stays in the hand; choosing one puts Annotate and Comment down.
	import Icon from '$lib/components/Icon.svelte';
	import { frame } from '$lib/words/frame';
	import type { Annotating } from '$lib/review/annotating.svelte';
	import type { PageTool } from './marks';
	import type { PdfView } from './view.svelte';

	let {
		view,
		notes,
		of = '',
		disabled = false
	}: {
		view: PdfView;
		notes: Annotating;
		/** What the tools act on, for their accessible names. */
		of?: string;
		disabled?: boolean;
	} = $props();

	const w = frame.toolbar.annotate;
	const TOOLS: { tool: PageTool; icon: string; title: string }[] = [
		{ tool: 'ink', icon: 'ink', title: w.draw.ink },
		{ tool: 'text', icon: 'type', title: w.draw.text },
		{ tool: 'rect', icon: 'rect', title: w.draw.rect },
		{ tool: 'oval', icon: 'oval', title: w.draw.oval },
		{ tool: 'arrow', icon: 'arrow', title: w.draw.arrow }
	];

	function choose(tool: PageTool): void {
		notes.tool = null;
		view.tool = view.tool === tool ? 'select' : tool;
	}
</script>

<span class="draw-tools" role="group" aria-label={w.drawing(of)}>
	{#each TOOLS as t (t.tool)}
		<button type="button" class="tool" class:on={!disabled && view.tool === t.tool} title={t.title} aria-label={w.drawName(t.title, of)} aria-pressed={view.tool === t.tool} {disabled} data-testid="tool-{t.tool}" onclick={() => choose(t.tool)}><Icon name={t.icon} size={15} /></button>
	{/each}
</span>

<style>
	.draw-tools {
		display: inline-flex;
		align-items: center;
		gap: 1px;
	}
	.tool {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		padding: 0;
		color: var(--ink-soft);
		background: none;
		border: 0;
		border-radius: 4px;
		cursor: pointer;
	}
	.tool:hover:not(:disabled) {
		color: var(--ink);
		background: var(--leaf);
	}
	.tool.on {
		color: var(--ink);
		background: var(--accent-wash);
	}
	.tool:disabled {
		opacity: 0.35;
		cursor: default;
	}
</style>
