<script lang="ts">
	// A shelf of the column: a box a shade lighter than the column, whose head folds it and which holds its rows while it is open. Files and Library are the two, drawn alike so that they read as the column's two kinds of thing. A shelf with a count shows it in the head, and one that can be added to has a button beside the head.
	import type { Snippet } from 'svelte';

	let {
		label,
		open = $bindable(),
		testid,
		toggle,
		title,
		count,
		add,
		children
	}: {
		label: string;
		open: boolean;
		/** The box's test id. */
		testid: string;
		/** The head button's test id. */
		toggle: string;
		title?: string;
		count?: number;
		/** The button beside the head: what it is called, its test id, and what a press does. */
		add?: { label: string; testid: string; press: () => void };
		children: Snippet;
	} = $props();
</script>

<div class="shelf-box" data-testid={testid}>
	<p class="shelf-head">
		<button class="shelf" aria-expanded={open} {title} data-testid={toggle} onclick={() => (open = !open)}>
			<span class="caret">{open ? '▾' : '▸'}</span>{label}{#if count !== undefined}{' '}<span class="count">{count}</span>{/if}
		</button>
		{#if add}<button class="shelf-add" aria-label={add.label} title={add.label} onclick={add.press} data-testid={add.testid}>+</button>{/if}
	</p>
	{#if open}<div class="shelf-body">{@render children()}</div>{/if}
</div>

<style>
	/* A shelf is a box with rounded corners, a shade lighter than the column, holding its head and, open, its rows: Files and Library are the column's two kinds of thing, and read as sections rather than as labels. The rows start at the box's own edge, so the column's width goes to the names. */
	.shelf-box {
		margin: var(--gap-tight) 0 var(--gap-hair);
		border-radius: var(--rad-control);
		/* a wash of the ink, so the box shows on the column in either theme */
		background: color-mix(in srgb, var(--ink) 6%, transparent);
	}
	.shelf-box:first-child {
		margin-top: 0;
	}
	.shelf-head {
		display: flex;
		align-items: center;
		margin: 0;
		border-radius: var(--rad-control);
	}
	.shelf-head:has(.shelf:hover) {
		background: color-mix(in srgb, var(--ink) 4%, transparent);
	}
	.shelf {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 3px;
		box-sizing: border-box;
		padding: 3px 6px 3px 4px;
		font: inherit;
		font-size: 12px;
		font-weight: 500;
		line-height: 1.4;
		color: var(--ink);
		background: none;
		border: 0;
		border-radius: var(--rad-control);
		cursor: pointer;
		text-align: left;
	}
	/* a 28px target round its glyph, as every icon control in the column */
	.shelf-add {
		flex: none;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: 0;
		background: none;
		color: var(--ink-faint);
		font-size: 18px;
		line-height: 1;
		padding: 0;
		margin-right: 2px;
		border-radius: var(--rad-control);
		cursor: pointer;
	}
	.shelf-add:hover {
		color: var(--link);
		background: var(--link-wash);
	}
	.shelf .caret {
		width: 10px;
		color: var(--ink-faint);
	}
	.shelf .count {
		margin-left: auto;
		font-weight: 400;
		font-variant-numeric: tabular-nums;
		color: var(--ink-faint);
	}
	/* a top-level row starts where the head's caret does */
	.shelf-body {
		padding: 0 6px 6px 4px;
	}
</style>
