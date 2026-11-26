<script lang="ts">
	// The page's mark that it is updating, in the column's foot (`$lib/manifest/updating.svelte.ts`): a line from a write's answer until the manifest the page holds carries it, and, where the build that was to show it failed, that said in its place until dismissed, loom's reason on hover. Folded, a dot.
	import Icon from '$lib/components/Icon.svelte';
	import { updating } from '$lib/manifest/updating.svelte';
	import { frame } from '$lib/words/frame';

	let { folded = false }: { folded?: boolean } = $props();
</script>

{#if updating.on}
	<div class="upd" class:folded role="status" title={folded ? frame.updating.on : undefined} aria-label={frame.updating.on} data-testid="updating">
		<span class="dot" aria-hidden="true"></span>
		{#if !folded}<span class="t">{frame.updating.on}</span>{/if}
	</div>
{:else if updating.failure !== null}
	<div class="upd failed" class:folded role="status" title={updating.failure || undefined} aria-label={frame.updating.failed} data-testid="updating-failed">
		<span class="dot" aria-hidden="true"></span>
		{#if !folded}
			<span class="t">{frame.updating.failed}</span>
			<button type="button" class="ib" title={frame.updating.dismiss} aria-label={frame.updating.dismiss} data-testid="updating-dismiss" onclick={() => updating.dismiss()}><Icon name="close" size={16} /></button>
		{/if}
	</div>
{/if}

<style>
	.upd {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 12px 6px;
		padding: 4px 4px 4px 10px;
		font-size: 13px;
		line-height: 1.4;
		color: var(--ink-faint);
	}
	.upd.folded {
		justify-content: center;
		margin: 0;
		padding: 10px 0;
	}
	.t {
		flex: 1;
	}
	.dot {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--ink-faint);
		animation: pulse 1.2s ease-in-out infinite;
	}
	.failed {
		color: var(--ink);
	}
	.failed .dot {
		background: var(--ink);
		animation: none;
	}
	@keyframes pulse {
		50% {
			opacity: 0.3;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.dot {
			animation: none;
		}
	}
	.ib {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		padding: 0;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.ib:hover {
		color: var(--ink);
		background: var(--ann-neutral-wash);
	}
</style>
