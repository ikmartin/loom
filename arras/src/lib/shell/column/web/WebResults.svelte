<script lang="ts">
	// In graph form, the Web's column under Show as: a search, then the scope's results in paper order grouped by document as the list's "by document" draws them, every group folded until opened; a search shows its hits instead. A row puts its result in focus; the result in focus is marked, its group opened, and kept scrolled into view, whether it was chosen here or in the graph.
	import { tick } from 'svelte';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import type { Row, WebGroup, WebSearch } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { hasLean, leanMark, paperMark } from '$lib/marks/marks';
	import { said } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import { isAgentDocument } from '$lib/manifest/documents';
	import { wb } from '$lib/views/web/state.svelte';
	import { web as words } from '$lib/words/web';

	let found = $state<WebSearch | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let scroller = $state<HTMLElement | null>(null);

	$effect(() => {
		const w = wb.where;
		void gen.gen;
		if (wb.named) void wb.picks.load(`${w.scope}:${w.doc}`, (s) => api.webList(w, 'document', [], 0, s));
	});
	$effect(() => {
		const q = wb.pq.trim();
		const w = wb.where;
		void gen.gen;
		clearTimeout(timer);
		if (!q || !wb.named) return void (found = null);
		timer = setTimeout(async () => {
			const a = await api.webSearch(w, q);
			if (a.ok && wb.pq.trim() === q) found = a.value;
		}, 200);
	});

	const list = $derived(wb.picks.value);
	/** How many drafts of the person's the quilt holds, for the sentence where it names no main draft. */
	const drafts = $derived((store.manifest?.masters ?? []).filter((d) => !isAgentDocument(d)).length);
	const rowsOf = (g: WebGroup): Row[] | null => g.rows ?? wb.groups.get(g.group) ?? null;
	const from = (r: Row) => (!r.source ? '' : 'doc' in r.source ? words.file(r.source.doc) : r.source.short);

	/** Groups being read, so one opened is asked for once. */
	const reading = new Set<string>();
	async function readGroup(group: string): Promise<void> {
		if (reading.has(group)) return;
		reading.add(group);
		const a = await api.webGroup(wb.where, group);
		if (a.ok) wb.groups.set(group, a.value.rows);
		reading.delete(group);
	}
	$effect(() => {
		for (const sec of list?.sections ?? []) for (const g of sec.groups ?? []) if (wb.picksOpen.has(g.group) && !rowsOf(g)) void readGroup(g.group);
	});

	function turn(g: WebGroup): void {
		if (wb.picksOpen.has(g.group)) wb.picksOpen.delete(g.group);
		else wb.picksOpen.add(g.group);
	}

	// the focus's group opens, by the document or the work its source names, wherever the focus was chosen
	$effect(() => {
		const f = wb.focus.value?.row;
		if (!f || f.result !== wb.at || !f.source) return;
		const g = 'doc' in f.source ? f.source.doc : f.source.ref;
		if ((list?.sections ?? []).some((s) => s.groups?.some((x) => x.group === g))) wb.picksOpen.add(g);
	});

	// the focus's row is scrolled into view once each time the focus moves, as soon as the row is drawn
	let shown: string | null = null;
	$effect(() => {
		const at = wb.at;
		void found;
		void list;
		void wb.groups.size;
		void wb.picksOpen.size;
		if (!at || at === shown) return;
		void tick().then(() => {
			const el = scroller?.querySelector(`[data-result="${CSS.escape(at)}"]`);
			if (!el || wb.at !== at) return;
			shown = at;
			el.scrollIntoView({ block: 'nearest' });
		});
	});
</script>

{#snippet pick(r: Row, source: boolean)}
	<button type="button" class="pk" class:sel={wb.at === r.result} aria-current={wb.at === r.result ? 'true' : undefined} data-testid="web-pick" data-result={r.result} onclick={() => wb.follow(r)}>
		<span class="slot">{#if r.paper}<Mark kind={paperMark(r.paper)} />{/if}</span>
		<span class="slot">{#if hasLean(r.lean)}<Mark kind={leanMark(r.lean)} />{/if}</span>
		<span class="nm">{r.name}{#if r.title}<span class="tl">{' ' + r.title}</span>{/if}</span>
		{#if source && from(r)}<span class="src">{from(r)}</span>{/if}
	</button>
{/snippet}

<div class="picks" data-testid="web-picks">
	<p class="rl">{words.column.results}</p>
	<input class="search" type="search" placeholder={words.column.find} aria-label={words.column.find} bind:value={wb.pq} data-testid="web-pick-search" />
	<div class="scroll" bind:this={scroller}>
		{#if found}
			{#each found.hits as h (h.row.result)}{@render pick(h.row, true)}{:else}<p class="quiet">{words.list.nothing}</p>{/each}
		{:else if wb.draftless}
			<p class="quiet">{words.list.draftless(drafts)}</p>
		{:else if wb.picks.error}
			<p class="quiet">{wb.picks.error.code === 'not-served' ? words.list.notServed : words.list.failed(said(wb.picks.error))}</p>
		{:else if !wb.named || !list}
			<p class="quiet">{words.list.loading}</p>
		{:else if !list.count}
			<p class="quiet">{words.list.empty(wb.scope, wb.doc ?? '')}</p>
		{:else}
			{#each list.sections ?? [] as sec, i (i)}
				<p class="head">{sec.head === 'draft' ? words.file(sec.doc ?? '') : sec.head === 'uses' ? words.list.uses(sec.doc ?? '') : sec.head === 'drafts' ? words.list.drafts : words.list.library}</p>
				{#each sec.rows ?? [] as r (r.result)}{@render pick(r, false)}{/each}
				{#each sec.groups ?? [] as g (g.group)}
					{@const open = wb.picksOpen.has(g.group)}
					<button type="button" class="grp" aria-expanded={open} data-testid="web-pick-group" onclick={() => turn(g)}>
						<Icon name={open ? 'caret' : 'right'} size={14} /><span class="gn">{g.short ?? words.file(g.group)}</span><span class="n">{g.n}</span>
					</button>
					{#if open}
						{@const rows = rowsOf(g)}
						{#if rows}<div class="in">{#each rows as r (r.result)}{@render pick(r, false)}{/each}</div>{:else}<p class="quiet in">{words.list.loading}</p>{/if}
					{/if}
				{/each}
			{/each}
		{/if}
	</div>
</div>

<style>
	.picks {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		margin-top: 16px;
	}
	.rl {
		margin: 4px 0 6px;
		padding: 0 2px;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.search {
		font: inherit;
		font-size: 12px;
		padding: 4px 8px;
		margin-bottom: 6px;
		border: 1px solid var(--rule);
		border-radius: 7px;
		background: var(--sheet);
		color: var(--ink);
	}
	.scroll {
		flex: 1;
		min-height: 120px;
		overflow: auto;
	}
	.head {
		margin: 10px 2px 2px;
		font-size: 11px;
		color: var(--ink-faint);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.pk,
	.grp {
		display: flex;
		align-items: center;
		gap: 4px;
		width: 100%;
		min-width: 0;
		min-height: 26px;
		padding: 0 6px;
		font: inherit;
		text-align: left;
		color: var(--ink);
		background: none;
		border: 0;
		border-radius: 6px;
		cursor: pointer;
		white-space: nowrap;
	}
	.pk:hover,
	.grp:hover {
		background: var(--ann-neutral-wash);
	}
	.pk.sel {
		background: var(--link-wash);
	}
	.in .pk,
	p.in {
		padding-left: 22px;
	}
	.slot {
		flex: none;
		width: 14px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	.nm,
	.gn {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		margin-left: 4px;
	}
	.tl {
		color: var(--ink-faint);
	}
	.n,
	.src {
		margin-left: auto;
		padding-left: 6px;
		flex: none;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.quiet {
		margin: 6px 2px;
		font-size: 12px;
		color: var(--ink-faint);
	}
</style>
