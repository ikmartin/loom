<script lang="ts">
	// Review in the column: the quilt's management, one section at a time, each saying what waits for the author there.
	import { page } from '$app/state';
	import { sectionOf, type Section } from '$lib/review/sections';

	let { sections }: { sections: Section[] } = $props();

	const here = $derived(sectionOf(page.route.id));
</script>

<ul class="plain review-sections" data-testid="review-sections">
	{#each sections as x (x.id)}
		<li>
			<a href={x.href} class:here={here === x.id} aria-current={here === x.id ? 'page' : undefined} title={x.says} data-testid="section-{x.id}"
				><span class="section-name">{x.label}<span class="blurb">{x.blurb}</span></span>{#if x.waits}<span class="waits" data-testid="section-count-{x.id}">{x.waits}</span>{/if}</a
			>
		</li>
	{/each}
</ul>

<style>
	ul.plain {
		list-style: none;
		margin: 0 0 var(--gap-tight);
		padding: 0;
	}
	ul.plain a {
		display: block;
		font-size: 11px;
		color: var(--ink-soft);
		padding: 1px 6px;
		border-radius: var(--rad-pill);
	}
	ul.plain a:hover {
		color: var(--ink);
		text-decoration: none;
	}
	/* after the plain list's rules, which it has the weight of and must win over */
	ul.review-sections a {
		display: flex;
		flex-wrap: nowrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
		font-size: 12px;
		padding: 3px 6px;
	}
	.review-sections a.here {
		color: var(--ink);
	}
	.review-sections a.here .section-name {
		font-weight: 600;
	}
	.section-name {
		flex: 1;
		min-width: 0;
	}
	.blurb {
		display: block;
		font-size: 11px;
		line-height: 1.35;
		font-weight: 400;
		color: var(--ink-faint);
	}
	.waits {
		flex: none;
		font-size: 10.5px;
		font-variant-numeric: tabular-nums;
		color: var(--ink-soft);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: var(--rad-pill);
		padding: 0 6px;
	}
</style>
