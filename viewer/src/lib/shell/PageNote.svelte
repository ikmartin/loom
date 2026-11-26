<script lang="ts">
	// The note above the document in the left pane: what the quilt's first page has to say, here that a quilt just made from a paper has a working copy that does not typeset as the paper did (`made.svelte.ts`). × puts it away.
	import { made } from './made.svelte';
	import { frame } from '$lib/words/frame';
</script>

{#if made.differs}
	<div class="qnote" role="status" data-testid="page-note" data-note="differs">
		<span class="t">{frame.note.differs}</span>
		<button type="button" class="ib" title={frame.note.close} aria-label={frame.note.close} onclick={() => (made.differs = false)}>
			<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
		</button>
	</div>
{/if}

<style>
	.qnote {
		display: flex;
		gap: 10px;
		align-items: center;
		max-width: min(760px, calc(100% - 32px));
		margin: 14px auto 0;
		font-family: var(--sans);
		font-size: 13px;
		line-height: 1.45;
		border: 1px solid var(--rule);
		border-left: 3px solid var(--state-stale);
		border-radius: 8px;
		padding: 6px 6px 6px 12px;
		background: var(--sheet);
		color: var(--ink);
	}
	.t {
		flex: 1;
	}
	.ib {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: 0;
		background: none;
		border-radius: 6px;
		color: var(--ink-faint);
		cursor: pointer;
		flex: none;
		padding: 0;
	}
	.ib:hover {
		background: color-mix(in srgb, var(--ink) 6%, transparent);
		color: var(--ink);
	}
</style>
