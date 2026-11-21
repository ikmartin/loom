<script lang="ts">
	// The Web's list (7a, 7a draft, 7a search): a search, how many results, and by document or by status. By document, the draft's results, then the library's it rests on a work at a time; under everything, the drafts and the works folded. A folded group is read when it opens (`web-group`). A search shows its hits, each with the words around the match.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import type { Row, WebGroup, WebSearch, WebSection } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import { web as words } from '$lib/words/web';
	import { wb } from './state.svelte';
	import WebRow from './WebRow.svelte';
	import { formalize } from '$lib/formalize/state.svelte';

	let found = $state<WebSearch | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let offset = $state(0);

	$effect(() => {
		const w = wb.where;
		const sort = wb.sort;
		void gen.gen;
		offset = 0;
		void wb.list.load(`${w.scope}:${w.doc}:${sort}`, (s) => api.webList(w, sort, [], 0, s));
	});
	$effect(() => {
		const q = wb.q.trim();
		const w = wb.where;
		void gen.gen;
		clearTimeout(timer);
		if (!q) return void (found = null);
		timer = setTimeout(async () => {
			const a = await api.webSearch(w, q);
			if (a.ok && wb.q.trim() === q) found = a.value;
		}, 200);
	});

	const list = $derived(wb.list.value);
	/** A group starts open under what a draft rests on, folded elsewhere; the person's turn flips it. */
	const isOpen = (sec: WebSection, g: WebGroup) => (sec.head === 'uses') !== wb.turned.has(g.group);

	async function turn(sec: WebSection, g: WebGroup): Promise<void> {
		if (wb.turned.has(g.group)) wb.turned.delete(g.group);
		else wb.turned.add(g.group);
		if (isOpen(sec, g) && !g.rows && !wb.groups.has(g.group)) {
			const a = await api.webGroup(wb.where, g.group);
			if (a.ok) wb.groups.set(g.group, a.value.rows);
		}
	}
	const rowsOf = (g: WebGroup): Row[] => g.rows ?? wb.groups.get(g.group) ?? [];

	async function more(): Promise<void> {
		offset += 200;
		const a = await api.webList(wb.where, 'status', [], offset);
		if (a.ok && list?.rows) wb.list.value = { ...list, rows: [...list.rows, ...(a.value.rows ?? [])], more: a.value.more };
	}
</script>

<div class="wlist" data-testid="web-list">
	<div class="wbar">
		<input class="search" type="search" placeholder={words.list.search} aria-label={words.list.search} bind:value={wb.q} data-testid="web-search" />
		<span class="quiet">{words.list.count(found ? found.count : (list?.count ?? 0))}</span>
		<span class="seg">
			<button type="button" class:on={wb.sort === 'document'} aria-pressed={wb.sort === 'document'} onclick={() => (wb.sort = 'document')}>{words.list.byDocument}</button>
			<button type="button" class:on={wb.sort === 'status'} aria-pressed={wb.sort === 'status'} onclick={() => (wb.sort = 'status')}>{words.list.byStatus}</button>
		</span>
	</div>
	<div class="wscroll">
		{#if found}
			{#each found.hits as h (h.row.result)}
				<WebRow row={h.row} choosing />
				{#if h.snippet}<p class="hit" data-testid="web-hit">{h.snippet.before}<mark>{h.snippet.match}</mark>{h.snippet.after}</p>{/if}
			{:else}<p class="outscope">{words.list.nothing}</p>{/each}
		{:else if wb.list.error}
			<p class="outscope">{wb.list.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(wb.list.error))}</p>
		{:else if !list}
			<p class="outscope">{words.list.loading}</p>
		{:else if list.rows}
			{#each list.rows as r (r.result)}<WebRow row={r} choosing />{/each}
			{#if list.more}<button type="button" class="linkish more" onclick={more}>{words.list.more(list.more)}</button>{/if}
		{:else}
			{#each list.sections ?? [] as sec, i (i)}
				<p class="whead">{sec.head === 'draft' ? words.file(sec.doc ?? '') : sec.head === 'uses' ? words.list.uses(sec.doc ?? '') : sec.head === 'drafts' ? words.list.drafts : words.list.library}</p>
				{#each sec.rows ?? [] as r (r.result)}<WebRow row={r} source={false} choosing />{/each}
				{#each sec.groups ?? [] as g (g.group)}
					{@const open = isOpen(sec, g)}
					<button type="button" class="wdoc" aria-expanded={open} data-testid="web-group" onclick={() => turn(sec, g)}>
						<Icon name={open ? 'caret' : 'right'} size={15} /><span>{g.doc ? words.file(g.doc) : g.short}</span>{#if g.title}<span class="wt">{g.title}</span>{/if}<span class="n">{g.n}</span>
					</button>
					{#if open}{#each rowsOf(g) as r (r.result)}<WebRow row={r} source={false} indent choosing />{/each}{/if}
				{/each}
			{/each}
			{#if list.undigested}<p class="outscope">{words.list.undigested(list.undigested)}</p>{/if}
		{/if}
	</div>
	{#if wb.chosen.size}
		<div class="pickbar" data-testid="web-chosen">
			<span>{words.choose.chosen(wb.chosen.size)}</span>
			<button type="button" class="linkish" onclick={() => formalize.open([...wb.chosen])}>{words.choose.formalize}</button>
			<span class="grow"></span>
			<button type="button" class="linkish quiet" onclick={() => wb.chosen.clear()}>{words.choose.clear}</button>
		</div>
	{/if}
</div>
