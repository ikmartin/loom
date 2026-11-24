<script lang="ts">
	// A shelf of the column: a box a shade lighter than the column, whose head folds it and which holds its rows while it is open, so that it reads as a section of the column rather than as a label.
	import type { Snippet } from 'svelte';

	let {
		label,
		open = $bindable(),
		testid,
		toggle,
		title,
		children
	}: {
		label: string;
		open: boolean;
		/** The box's test id. */
		testid: string;
		/** The head button's test id. */
		toggle: string;
		title?: string;
		children: Snippet;
	} = $props();
</script>

<div class="shelf-box" data-testid={testid}>
	<p class="shelf-head">
		<button class="shelf" aria-expanded={open} {title} data-testid={toggle} onclick={() => (open = !open)}>
			<span class="caret">{open ? '▾' : '▸'}</span>{label}
		</button>
	</p>
	{#if open}<div class="shelf-body">{@render children()}</div>{/if}
</div>

<style>
	/* A shelf is a box with rounded corners, a shade lighter than the column, holding its head and, open, its rows, read as a section rather than as a label. The rows start at the box's own edge, so the column's width goes to the names. */
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
	.shelf .caret {
		width: 10px;
		color: var(--ink-faint);
	}
	/* a top-level row starts where the head's caret does */
	.shelf-body {
		padding: 0 6px 6px 4px;
	}
</style>
