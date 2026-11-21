<script lang="ts">
	// A work's head in the Library's column (2, 3): its title, its byline and year with what loom holds of it, a fold showing its BibTeX entry as text, and its `digest…` menu.
	import type { WorkAnswer } from '$lib/library/types';
	import { menus } from '$lib/views/library/menus.svelte';
	import DigestMenu from '$lib/views/library/DigestMenu.svelte';
	import { served } from '$lib/library/served.svelte';
	import { library as words } from '$lib/words/library';

	let { work }: { work: WorkAnswer } = $props();
	let entry = $state(false);

	const holds = $derived(work.holds.pdf && work.holds.tex ? words.column.holds.both : work.holds.pdf ? words.column.holds.pdf : work.holds.tex ? words.column.holds.tex : words.column.holds.none);
	const meta = $derived([words.byline(work.authors), work.year, holds].filter(Boolean).join(' · '));
</script>

<div class="wk-title" data-testid="work-title">{work.title}</div>
<!-- the entry's fold where the work's read gives the entry -->
<div class="wk-meta">{meta}{#if work.entry} · <button type="button" class="linkish" aria-expanded={entry} onclick={() => (entry = !entry)} data-testid="work-entry">{words.column.entry} {entry ? '▾' : '▸'}</button>{/if}</div>
{#if entry}<pre class="entry">{work.entry}</pre>{/if}
{#if (work.holds.pdf || work.holds.tex) && served.has('library-digest')}
	<span class="menuwrap">
		<button type="button" class="btn" aria-expanded={menus.open === `work:${work.ref}`} onclick={() => menus.toggle(`work:${work.ref}`)} data-testid="work-digest">{words.works.digest}</button>
		{#if menus.open === `work:${work.ref}`}<DigestMenu target={work} left />{/if}
	</span>
{/if}

<style>
	.wk-title {
		font-family: var(--serif);
		font-size: 17px;
		line-height: 1.25;
		margin: 2px 0 4px;
	}
	.wk-meta {
		color: var(--ink-faint);
		font-size: 11px;
		margin-bottom: 8px;
	}
	.wk-meta .linkish {
		font-size: 11px;
	}
	.entry {
		font: 11px/1.5 var(--mono);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 6px;
		padding: 8px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		margin: 0 0 8px;
	}
</style>
