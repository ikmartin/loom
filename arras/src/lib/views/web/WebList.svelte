<script lang="ts">
	// The Web's list (7a, 7a draft, 7a search): a search, how many results, and by document or by status. By document, the draft's results, then the library's it rests on a work at a time; under everything, the drafts and the works folded. Drawn in a window (`window.ts`): only the lines in view are drawn, a group whose rows were not sent is read (`web-group`) when it comes into view open, and by status the next two hundred are read as the list's end comes into view. A search shows its hits, each with the words around the match drawn as the statement is.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import type { Row, WebGroup, WebSearch, WebSection } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import { web as words } from '$lib/words/web';
	import { wb } from './state.svelte';
	import WebRow from './WebRow.svelte';
	import Snippet from './Snippet.svelte';
	import { inView, lay } from './window';
	import { formalize } from '$lib/formalize/state.svelte';

	let found = $state<WebSearch | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;

	$effect(() => {
		const w = wb.where;
		const sort = wb.sort;
		void gen.gen;
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
	const rowsOf = (g: WebGroup): Row[] | null => g.rows ?? wb.groups.get(g.group) ?? null;

	// the window: the list's scroll and height, and the lines in view
	let scroller = $state<HTMLElement | null>(null);
	let scrolled = $state(0);
	let tall = $state(600);
	const laid = $derived(list ? lay(list, isOpen, rowsOf) : { lines: [], height: 0 });
	const shown = $derived(inView(laid.lines, scrolled, scrolled + tall));

	/** Groups being read, so one in view is asked for once. */
	const reading = new Set<string>();
	$effect(() => {
		for (const l of shown) if (l.kind === 'pending' && !reading.has(l.group)) void readGroup(l.group);
		// by status, the next two hundred as the list's end comes into view
		if (list?.rows && list.more && shown.some((l) => l.kind === 'note')) void more();
	});

	async function readGroup(group: string): Promise<void> {
		reading.add(group);
		const a = await api.webGroup(wb.where, group);
		if (a.ok) wb.groups.set(group, a.value.rows);
		reading.delete(group);
	}

	function turn(g: WebGroup): void {
		if (wb.turned.has(g.group)) wb.turned.delete(g.group);
		else wb.turned.add(g.group);
	}

	let fetching = false;
	async function more(): Promise<void> {
		if (fetching || !list?.rows) return;
		fetching = true;
		const at = list.rows.length;
		const a = await api.webList(wb.where, 'status', [], at);
		if (a.ok && wb.list.value?.rows) wb.list.value = { ...wb.list.value, rows: [...wb.list.value.rows, ...(a.value.rows ?? [])], more: a.value.more };
		fetching = false;
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
	<div class="wscroll" bind:this={scroller} bind:clientHeight={tall} onscroll={() => (scrolled = scroller?.scrollTop ?? 0)}>
		{#if found}
			{#each found.hits as h (h.row.result)}
				<WebRow row={h.row} choosing />
				{#if h.snippet}<Snippet snippet={h.snippet} />{/if}
			{:else}<p class="outscope">{words.list.nothing}</p>{/each}
		{:else if wb.list.error}
			<p class="outscope">{wb.list.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(wb.list.error))}</p>
		{:else if !list}
			<p class="outscope">{words.list.loading}</p>
		{:else}
			<div class="window" style:height="{laid.height}px" data-testid="web-window">
				{#each shown as l (l.kind === 'row' ? `r:${l.row.result}:${l.top}` : `${l.kind}:${l.top}`)}
					<div class="line" style:top="{l.top}px">
						{#if l.kind === 'head'}
							<p class="whead">{l.sec.head === 'draft' ? words.file(l.sec.doc ?? '') : l.sec.head === 'uses' ? words.list.uses(l.sec.doc ?? '') : l.sec.head === 'drafts' ? words.list.drafts : words.list.library}</p>
						{:else if l.kind === 'group'}
							<button type="button" class="wdoc" aria-expanded={l.open} data-testid="web-group" onclick={() => turn(l.group)}>
								<Icon name={l.open ? 'caret' : 'right'} size={15} /><span>{l.group.short ?? words.file(l.group.group)}</span>{#if l.group.title}<span class="wt">{l.group.title}</span>{/if}<span class="n">{l.group.n}</span>
							</button>
						{:else if l.kind === 'row'}
							<WebRow row={l.row} source={l.source} indent={l.indent} choosing />
						{:else if l.kind === 'pending'}
							<span class="pending"></span>
						{:else}
							<p class="outscope">{list.rows ? words.list.more(list.more ?? 0) : words.list.undigested(list.undigested ?? 0)}</p>
						{/if}
					</div>
				{/each}
			</div>
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
