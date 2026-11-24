<script lang="ts">
	// `see it in main.tex` (4 see it): the document laid over Review, read only, at the result, until its close button; nothing in it edits, and it never leaves Review.
	import Icon from '$lib/components/Icon.svelte';
	import Fragment from '$lib/fragments/Fragment.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { anchorId } from '$lib/nav';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';

	let { over }: { over: { doc: string; key: string; name: string } } = $props();
	const master = $derived(store.manifest?.masters.find((x) => x.path === over.doc));
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (rv.over = null)} />

<section class="over" data-testid="review-over" aria-label={words.file(over.doc)}>
	<header>
		<b>{words.file(over.doc)}</b>
		<span class="quiet">{words.quiet([over.name ? words.seeIt.at(over.name) : '', words.seeIt.readOnly])}</span>
		<button type="button" class="ib" title={words.seeIt.close} aria-label={words.seeIt.close} onclick={() => (rv.over = null)}><Icon name="close" size={18} /></button>
	</header>
	<div class="doc">
		{#if master}<Fragment path={master.fragment} master={master.path} macroSet={master.macros ?? ''} isolatedMacros={!!master.macros} anchor={anchorId(over.key)} />{/if}
	</div>
</section>

<style>
	.over {
		position: absolute;
		inset: 12px 16px 0;
		z-index: 20;
		display: flex;
		flex-direction: column;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 10px 10px 0 0;
		box-shadow: var(--float-shadow);
	}
	header {
		flex: none;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 8px 6px 16px;
		border-bottom: 1px solid var(--rule);
	}
	header b {
		font-weight: 500;
	}
	header .ib {
		margin-left: auto;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-soft);
		cursor: pointer;
	}
	header .ib:hover {
		background: var(--ann-neutral-wash);
	}
	.doc {
		flex: 1;
		min-height: 0;
		overflow: auto;
		padding: 18px 40px 60px;
	}
</style>
