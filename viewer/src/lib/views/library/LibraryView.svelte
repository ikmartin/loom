<script lang="ts">
	// The Library view (`docs/specs/library-views.md` §3): its tabs, the list of works always first and a tab for each work open, and under them the list or the work. The list of works is read once and asked again whenever the library's generation moves; the work in the current tab is read for its tab and for the column's outline. A menu open anywhere in the view closes on a click outside it.
	import './library.css';
	import Icon from '$lib/components/Icon.svelte';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { library as words } from '$lib/words/library';
	import { lib } from './state.svelte';
	import { page } from '$app/state';
	import { menus } from './menus.svelte';
	import WorksTab from './WorksTab.svelte';
	import WorkTab from './WorkTab.svelte';

	// the tab the address names
	$effect(() => {
		lib.arrive(page.url.searchParams.get('work') ?? 'works');
	});
	$effect(() => {
		void gen.gen;
		void lib.works.load('works', (s) => api.works(undefined, s));
	});
	$effect(() => {
		const ref = lib.tab;
		void gen.gen;
		if (ref === 'works') lib.work.clear();
		else void lib.work.load(ref, (s) => api.work(ref, s));
	});

	const byRef = $derived(new Map((lib.works.value?.works ?? []).map((w) => [w.ref, w])));

	function away(e: PointerEvent): void {
		if (menus.open && !(e.target as Element).closest?.('.menuwrap')) menus.open = null;
	}
</script>

<svelte:window onpointerdown={away} />

<main class="lv" data-testid="library-view" data-open-work={lib.tab === 'works' ? undefined : lib.tab}>
	<div class="tabs" role="tablist">
		<button type="button" class="tab doc-tab pin" class:on={lib.tab === 'works'} role="tab" aria-selected={lib.tab === 'works'} title={words.tabs.works} data-testid="library-tab-works" onclick={() => lib.show('works')}><span class="name">{words.tabs.works}</span></button>
		{#each lib.open as ref (ref)}
			{@const w = byRef.get(ref)}
			<div class="tab doc-tab" class:on={lib.tab === ref} role="tab" tabindex="-1" aria-selected={lib.tab === ref} title={w?.title} data-testid="library-tab">
				<button type="button" class="linkish name" onclick={() => lib.show(ref)}>{w?.short ?? ''}</button>
				<button type="button" class="ib x" title={words.tabs.close} aria-label={words.tabs.close} onclick={() => lib.closeWork(ref)}><Icon name="close" size={16} /></button>
			</div>
		{/each}
	</div>
	{#if lib.tab === 'works'}
		<WorksTab />
	{:else}
		<WorkTab ref={lib.tab} />
	{/if}
</main>

<style>
	/* the title is cut with an ellipsis where the tab is narrower than it; the tab's hover text gives it whole */
	.name {
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		text-align: left;
		color: inherit;
	}
	.name:hover {
		text-decoration: none;
	}
</style>
