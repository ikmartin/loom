<script lang="ts">
	// That loom was updated under this page, or serves a newer viewer than it runs, with Reload; never a command, since the home page restarts each quilt's server after an update (`outOfStep.svelte.ts`). On a document the note stands above it in the left pane (`shell/PageNote.svelte`); elsewhere it is this one line near the foot of the window, clear of the toolbars, and × puts it away for this page.
	import { outOfStep } from '$lib/outOfStep.svelte';
	import { workspace } from '$lib/workspace/store.svelte';
	import { frame } from '$lib/words/frame';

	const step = $derived(outOfStep.said && outOfStep.said !== outOfStep.dismissed ? outOfStep.said : null);
</script>

{#if step && !workspace.onScreen}
	<div class="step" role="status" data-testid="out-of-step" data-step={step}>
		<span class="said">{frame.note.updated}</span>
		<button type="button" class="btn primary small" onclick={() => location.reload()} data-testid="out-of-step-reload">{frame.note.reload}</button>
		<button type="button" class="close" title={frame.note.close} aria-label={frame.note.close} onclick={() => (outOfStep.dismissed = step)} data-testid="out-of-step-close">×</button>
	</div>
{/if}

<style>
	.step {
		position: fixed;
		z-index: 61;
		left: 50%;
		bottom: calc(var(--gap) * 3);
		transform: translateX(-50%);
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--gap-tight);
		max-width: min(640px, calc(100vw - 2 * var(--gap)));
		padding: 6px 10px;
		font-family: var(--sans);
		font-size: 13px;
		background: var(--sheet);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-left: 3px solid var(--state-stale);
		border-radius: var(--rad-control);
		box-shadow: var(--float-shadow);
	}
	.said {
		flex: 1 1 auto;
	}
	.close {
		font: inherit;
		font-size: 16px;
		line-height: 1;
		background: none;
		border: none;
		color: var(--ink-faint);
		cursor: pointer;
		padding: 0 2px;
	}
</style>
