<script lang="ts">
	// The question-mark circle beside a page title: what the page means and what each state means. Its words are Review's (`words/review.ts`, `help`).
	import Popover from '$lib/components/Popover.svelte';
	import { review } from '$lib/words/review';

	let { label, topic }: { label: string; topic: 'review' | 'problems' | (string & {}) } = $props();

	const t = $derived(review.help[topic] ?? { title: label, body: '', states: [] });
</script>

<Popover placement="below" width={320} role="note" testid="help-panel-{topic}">
	{#snippet trigger({ open, toggle })}
		<button class="help" aria-label={label} aria-expanded={open} title={label} onclick={toggle} data-testid="help-{topic}">?</button>
	{/snippet}
	<div class="pop">
		<p class="title">{t.title}</p>
		<p>{t.body}</p>
		{#if t.states.length}
			<dl>
				{#each t.states as [name, meaning] (name)}
					<dt>{name}</dt>
					<dd>{meaning}</dd>
				{/each}
			</dl>
		{/if}
	</div>
</Popover>

<style>
	button {
		width: 15px;
		height: 15px;
		border-radius: 999px;
		border: 1px solid var(--rule-strong);
		background: var(--leaf);
		color: var(--ink-faint);
		font-family: var(--sans);
		font-size: 9px;
		line-height: 1;
		cursor: pointer;
		vertical-align: middle;
	}
	button:hover {
		color: var(--link);
		border-color: var(--link);
	}
	.pop {
		padding: var(--gap);
		font-family: var(--sans);
		font-size: 11px;
		line-height: 1.55;
		color: var(--ink-soft);
		text-transform: none;
		letter-spacing: 0;
	}
	.pop p {
		margin: 0 0 var(--gap-tight);
	}
	.pop .title {
		color: var(--ink);
		font-weight: 500;
	}
	dl {
		margin: 0 0 var(--gap-tight);
		display: grid;
		grid-template-columns: 74px 1fr;
		gap: 2px var(--gap-tight);
	}
	dt {
		color: var(--ink);
	}
	dd {
		margin: 0;
	}
</style>
