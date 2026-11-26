<script lang="ts">
	// A quiet note over a section of Review, said once (`once.ts`) and closed by its button.
	import Icon from '$lib/components/Icon.svelte';
	import { review as words } from '$lib/words/review';
	import { closeOnce, once } from './once';

	let { text, testid }: { text: string; testid: string } = $props();
	let open = $state(false);
	$effect(() => {
		open = once(text);
	});
</script>

{#if open}
	<p class="once" data-testid={testid}>
		<span>{text}</span>
		<button type="button" class="x" title={words.once.close} aria-label={words.once.close} onclick={() => { closeOnce(text); open = false; }}><Icon name="close" size={14} /></button>
	</p>
{/if}

<style>
	.once {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0 0 var(--gap, 12px);
		padding: 6px 4px 6px 12px;
		border-left: 3px solid var(--rule);
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.once span {
		flex: 1;
	}
	.x {
		flex: none;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.x:hover {
		background: var(--ann-neutral-wash);
	}
</style>
