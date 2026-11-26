<script lang="ts">
	// A quilt's page whose server stopped: the page dimmed under one card that says so and links to loom's home page, where the quilt is opened again, and what to do when that page does not load either (`gone.svelte.ts`). It goes by itself once the server answers again.
	import { stopped } from './gone.svelte';
	import { frame } from '$lib/words/frame';
</script>

{#if stopped.on}
	<div class="stopcover" role="alert" data-testid="stopped">
		<div class="card">
			<p>{frame.stopped.said}</p>
			{#if stopped.home}
				<p><a href={stopped.home} data-testid="stopped-home">{frame.stopped.home}</a></p>
				<p class="small">{frame.stopped.homeDown}</p>
			{:else}
				<p class="small">{frame.stopped.noHome}</p>
			{/if}
		</div>
	</div>
{/if}

<style>
	.stopcover {
		position: fixed;
		inset: 0;
		z-index: 90;
		background: color-mix(in srgb, var(--paper) 78%, transparent);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 150px;
		font-family: var(--sans);
		font-size: 13px;
		line-height: 1.45;
	}
	.card {
		width: 470px;
		max-width: calc(100% - 32px);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 12px;
		box-shadow: var(--float-shadow);
		padding: 16px 20px;
		color: var(--ink);
	}
	.card p {
		margin: 0 0 10px;
	}
	.card p:last-child {
		margin: 0;
	}
	.small {
		font-size: 11px;
		color: var(--ink-faint);
	}
	a {
		color: var(--link);
		text-decoration: none;
	}
	a:hover {
		text-decoration: underline;
	}
</style>
