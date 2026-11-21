<script lang="ts">
	// The one hover card on screen (`hovercards.svelte.ts`), floating over everything at the place its owner set.
	import { hovercards } from './hovercards.svelte';
</script>

{#if hovercards.shown}
	<div class="hovercard" role="tooltip" data-testid="hovercard" style:left="{hovercards.shown.left}px" style:top="{hovercards.shown.top}px">{hovercards.shown.text}</div>
{/if}

<style>
	.hovercard {
		position: fixed;
		z-index: 90;
		width: 300px;
		padding: 10px 12px;
		background: var(--sheet);
		color: var(--ink);
		border: 1px solid var(--rule);
		border-radius: 10px;
		box-shadow: var(--float-shadow);
		font-size: 13px;
		line-height: 1.45;
		pointer-events: none;
	}
</style>
