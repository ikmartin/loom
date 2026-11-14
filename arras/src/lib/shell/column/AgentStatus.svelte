<script lang="ts">
	// The foot of the column, in both of its views and folded: which session writing lands in, so that a reader never goes looking for where their work will go. Folded, it is the session's dot alone.
	import SessionFooter from '$lib/sessions/SessionFooter.svelte';

	let { folded = false }: { folded?: boolean } = $props();
</script>

{#if folded}
	<div class="rail-foot">
		<SessionFooter compact />
	</div>
{:else}
	<div class="write-target">
		<SessionFooter />
	</div>
{/if}

<style>
	.rail-foot {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		width: 100%;
	}
	.rail-foot :global(.footer) {
		margin: 0 -4px calc(-1 * var(--gap));
		align-self: stretch;
	}
	.write-target {
		flex: none;
	}
</style>
