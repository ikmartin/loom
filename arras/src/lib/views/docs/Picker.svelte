<script lang="ts">
	// The library's picker over Docs (8a): a search, how many works, list or thumbnails (the Library's choice, one for both), sorted by title, authors or year, the list saying the label the draft cites each work by. A click opens the work beside the draft and closes the picker.
	import '$lib/views/library/library.css';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { Work, WorksAnswer } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { shown } from '$lib/views/library/works';
	import WorksThumbs from '$lib/views/library/WorksThumbs.svelte';
	import { library as libraryWords } from '$lib/words/library';
	import { docs as words } from '$lib/words/docs';
	import { workspace } from '$lib/workspace/store.svelte';
	import { shortNames } from './names.svelte';
	import { docsState as ds } from './docs.svelte';

	let { doc, left }: { doc: string | null; left: number } = $props();
	const read = new Read<WorksAnswer>();

	$effect(() => {
		const d = doc ?? undefined;
		void gen.gen;
		void read.load(`picker:${d ?? ''}`, (s) => api.works(d, s));
	});

	const works = $derived(shown(read.value?.works ?? [], { filter: 'all', q: ds.q, sort: { key: ds.sort, dir: ds.sort === 'year' ? -1 : 1 } }));

	function open(w: Work): void {
		shortNames.set(w.ref, w.short);
		workspace.beside({ kind: 'reading', id: w.ref }, workspace.focus);
		ds.picker = false;
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (ds.picker = false)} />

<section class="lv picker" style:left="{left}px" data-testid="docs-picker" aria-label={words.picker.open}>
	<div class="pk-h">
		<input class="search" placeholder={words.picker.search} aria-label={words.picker.search} bind:value={ds.q} data-testid="picker-search" />
		<span class="small grey">{words.picker.count(works.length)}</span>
		<span class="grow"></span>
		<span class="seg">
			<button type="button" class:on={lib.layout === 'list'} onclick={() => (lib.layout = 'list')}>{words.picker.list}</button>
			<button type="button" class:on={lib.layout === 'thumbs'} onclick={() => (lib.layout = 'thumbs')}>{words.picker.thumbnails}</button>
		</span>
		<button type="button" class="ib" title={words.picker.close} aria-label={words.picker.close} onclick={() => (ds.picker = false)} data-testid="picker-close"><Icon name="close" size={18} /></button>
	</div>
	{#if lib.layout === 'thumbs'}
		<WorksThumbs {works} onopen={open} />
	{:else}
		<div class="pk-b">
			<table class="works">
				<thead>
					<tr>
						{#each ['title', 'authors', 'year'] as const as k (k)}
							<th class:sorted={ds.sort === k} aria-sort={ds.sort === k ? (k === 'year' ? 'descending' : 'ascending') : undefined}><button type="button" class="linkish" onclick={() => (ds.sort = k)}>{words.picker[k]}</button></th>
						{/each}
						<th class="d"></th>
					</tr>
				</thead>
				<tbody>
					{#each works as w (w.ref)}
						<tr data-testid="picker-row" onclick={() => open(w)}>
							<td class="t"><button type="button" class="linkish name" onclick={(e) => (e.stopPropagation(), open(w))}>{w.title}</button></td>
							<td>{libraryWords.byline(w.authors)}</td>
							<td>{w.year}</td>
							<td class="d" title={w.cited_as && doc ? words.picker.citedAs(doc, w.cited_as) : undefined}>{w.cited_as ?? ''}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>

<style>
	.picker {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		height: auto;
		z-index: 60;
		box-shadow: var(--float-shadow);
	}
	.pk-h {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 16px;
		border-bottom: 1px solid var(--rule);
	}
	.pk-h .search {
		width: 300px;
	}
	.grow {
		flex: 1;
	}
	.pk-b {
		flex: 1;
		overflow: auto;
		padding: 0 16px 20px;
	}
	.works {
		width: 100%;
		border-collapse: collapse;
	}
	.works th {
		position: sticky;
		top: 0;
		background: var(--paper);
		text-align: left;
		font-weight: 400;
		font-size: 12px;
		padding: 8px 8px 6px;
		border-bottom: 1px solid var(--rule);
	}
	.works th .linkish {
		color: var(--ink-faint);
	}
	.works th.sorted .linkish {
		color: var(--ink);
		font-weight: 500;
	}
	.works td {
		padding: 6px 8px;
		border-bottom: 1px solid var(--rule);
		cursor: pointer;
	}
	.works tr:hover td {
		background: var(--ann-neutral-wash);
	}
	.works td.t {
		width: 56%;
	}
	.works .name {
		color: var(--ink);
		text-align: left;
	}
	.works td.d {
		width: 44px;
		color: var(--ink-faint);
	}
</style>
