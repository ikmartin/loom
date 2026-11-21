<script lang="ts">
	// The column's message in its foot (`../message.svelte.ts`): what was just done, `undo` where it can be taken back, and a close button.
	import Icon from '$lib/components/Icon.svelte';
	import { frame } from '$lib/words/frame';
	import { message } from '../message.svelte';
</script>

{#if message.said}
	<div class="msg" role="status" data-testid="column-message">
		<span class="t">{message.said.text}</span>
		<span class="u">
			{#if message.said.undo}<button type="button" class="undo" data-testid="column-message-undo" onclick={() => void message.undo()}>{frame.message.undo}</button>{/if}
			<button type="button" class="ib" title={frame.message.dismiss} aria-label={frame.message.dismiss} data-testid="column-message-dismiss" onclick={() => message.clear()}><Icon name="close" size={16} /></button>
		</span>
	</div>
{/if}

<style>
	.msg {
		margin: 0 12px 6px;
		padding: 7px 8px 7px 10px;
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		align-items: flex-start;
		background: var(--sheet);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 8px;
		font-size: 13px;
		line-height: 1.4;
	}
	.t {
		flex: 1 1 100%;
	}
	.u {
		display: flex;
		gap: 10px;
		align-items: center;
		justify-content: flex-end;
		width: 100%;
	}
	.undo {
		font: inherit;
		color: var(--link);
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}
	.undo:hover {
		text-decoration: underline;
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
