<script lang="ts">
	// The list of works (1, 1 thumbs, 1 add, 1 digest, 1c): a search over titles and authors, the list or its thumbnails, `add work…` and `digest…` over every work, then the works as the column's filter, the search and the sort leave them. An empty library is a box to drop papers in.
	import { said } from '$lib/library/said';
	import { library as words } from '$lib/words/library';
	import { lib } from './state.svelte';
	import { menus } from './menus.svelte';
	import { shown } from './works';
	import AddWorkPanel from './AddWorkPanel.svelte';
	import DigestMenu from './DigestMenu.svelte';
	import WorksTable from './WorksTable.svelte';
	import WorksThumbs from './WorksThumbs.svelte';

	const all = $derived(lib.works.value?.works ?? []);
	const list = $derived(shown(all, { filter: lib.filter, q: lib.q, sort: lib.sort }));
</script>

{#if lib.works.error && !lib.works.value}
	<p class="note" role="alert" data-testid="works-failed">{lib.works.error.code === 'not-served' ? words.works.notServed : words.works.failed(said(lib.works.error))}</p>
{:else if !lib.works.value}
	<p class="note grey">{words.works.loading}</p>
{:else if all.length === 0}
	<div class="empty" data-testid="works-empty">
		<div class="box">
			<b>{words.empty.head}</b>
			<p>{words.empty.body}</p>
			<AddWorkPanel inline />
		</div>
	</div>
{:else}
	<div class="bar">
		<input class="search" type="search" placeholder={words.works.search} bind:value={lib.q} data-testid="works-search" />
		{#if lib.q.trim()}<span class="small grey">{words.works.narrowed(list.length, all.length)} · <button type="button" class="linkish" onclick={() => (lib.q = '')}>{words.works.clear}</button></span>{/if}
		<span class="grow"></span>
		<span class="seg">
			<button type="button" class:on={lib.layout === 'list'} onclick={() => (lib.layout = 'list')} data-testid="works-list">{words.works.list}</button>
			<button type="button" class:on={lib.layout === 'thumbs'} onclick={() => (lib.layout = 'thumbs')} data-testid="works-thumbs">{words.works.thumbnails}</button>
		</span>
		<span class="menuwrap">
			<button type="button" class="btn" aria-expanded={menus.open === 'add'} data-testid="add-work" onclick={() => menus.toggle('add')}>{words.works.add}</button>
			{#if menus.open === 'add'}<div class="menu addpanel" data-testid="add-panel"><AddWorkPanel /></div>{/if}
		</span>
		<span class="menuwrap">
			<button type="button" class="btn" aria-expanded={menus.open === 'all'} data-testid="digest-all" onclick={() => menus.toggle('all')}>{words.works.digest}</button>
			{#if menus.open === 'all'}<DigestMenu target="all" />{/if}
		</span>
	</div>
	{#if lib.layout === 'thumbs'}
		<WorksThumbs works={list} />
	{:else}
		<WorksTable works={list} />
	{/if}
{/if}

<style>
	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 20px;
		border-bottom: 1px solid var(--rule);
	}
	.grow {
		flex: 1;
	}
	.note {
		padding: 20px;
	}
	.addpanel {
		right: 0;
		top: calc(100% + 4px);
		width: 330px;
		padding: 12px 14px;
	}
	.empty {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.box {
		width: 560px;
		border: 2px dashed var(--rule);
		border-radius: 16px;
		padding: 46px 40px;
		text-align: center;
		background: var(--sheet);
	}
	.box b {
		display: block;
		font-size: 16px;
		font-weight: 500;
		margin-bottom: 8px;
	}
	.box p {
		color: var(--ink-faint);
		margin: 0 0 18px;
	}
</style>
