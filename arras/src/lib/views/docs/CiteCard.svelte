<script lang="ts">
	// A citation's card in a draft (8c): the cited result's name and title, its work and page, its marks with their words, its statement, and `open at its place`, which opens the work beside the draft there; on a stub, that loom knows it only by its number, `locate in PDF`, which opens the work where loom finds its name, and `ask an agent to read it`.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { Read } from '$lib/library/read.svelte';
	import type { NodeAnswer } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { THEOREMS } from '$lib/node/taxa';
	import { message } from '$lib/shell/message.svelte';
	import { frame } from '$lib/words/frame';
	import { docs as words } from '$lib/words/docs';
	import { workspace } from '$lib/workspace/store.svelte';
	import { shortNames } from './names.svelte';

	let { node, pane, doc, onsized, ondone }: { node: string; pane: number; doc: string | null; onsized: () => void; ondone: () => void } = $props();
	const read = new Read<NodeAnswer>();

	$effect(() => {
		const id = node;
		void read.load(id, (s) => api.node({ node: id, brief: true }, s));
	});
	$effect(() => {
		if (read.value) onsized();
	});

	const n = $derived(read.value?.node === node ? read.value : null);

	function beside(page: number): void {
		if (!n) return;
		shortNames.set(n.work.ref, n.work.short);
		workspace.beside({ kind: 'work', id: n.work.ref, ...(page ? { place: { page } } : {}) }, Math.max(pane, 0));
		ondone();
	}
	async function atPlace(): Promise<void> {
		const at = await api.places({ node });
		beside(at.ok ? (at.value.places.find((p) => 'node' in p && p.node === node)?.page ?? Number(n?.pages) ?? 0) : Number(n?.pages) || 0);
	}
	async function locate(): Promise<void> {
		if (!n) return;
		const found = await api.find(n.work.ref, n.name);
		beside(found.ok ? (found.value.hits[0]?.page ?? 1) : 1);
	}
	async function ask(): Promise<void> {
		const done = await api.ask('read', { nodes: [node] }, '', doc ? [doc] : []);
		message.post(done.ok ? words.card.asked : said(done.error));
		ondone();
	}
</script>

{#if n}
	<div class="cite-card" data-testid="cite-card">
		<div class="ch">{n.name}{#if n.title}<span class="tl">{' ' + n.title}</span>{/if}</div>
		<div class="cs">
			<span>{words.card.at(n.work.short, n.pages ?? '')}</span>
			{#if n.paper}<span class="chip"><Mark kind={paperMark(n.paper)} hidden />{frame.marks[paperMark(n.paper)]}</span>{/if}
			{#if n.lean}<span class="chip"><Mark kind={leanMark(n.lean)} hidden />{frame.marks[leanMark(n.lean)]}</span>{/if}
		</div>
		{#if n.paper === 'stub'}
			<p class="quiet">{words.card.stub}</p>
			<div class="acts">
				<button type="button" class="as-link" onclick={locate}>{words.card.locate}</button>
				<button type="button" class="as-link" onclick={ask}>{words.card.read}</button>
			</div>
		{:else}
			{#if n.body !== undefined}<div class="cb"><NodeBody body={n.body} macros={n.macros?.body ?? null} points={n.points ?? {}} italic={THEOREMS.has(n.taxon)} /></div>{/if}
			<div class="acts"><button type="button" class="as-link" onclick={atPlace}>{words.card.open}</button></div>
		{/if}
	</div>
{/if}

<style>
	.cite-card {
		width: 420px;
		max-width: 100%;
		padding: 2px 4px;
	}
	.ch {
		font-family: var(--font-text, serif);
		font-size: 16px;
	}
	.tl {
		color: var(--ink-faint);
	}
	.cs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
		margin: 2px 0 8px;
		font-size: 12px;
		color: var(--ink-soft);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--ink-faint);
	}
	.cb {
		padding-left: 10px;
		border-left: 2px solid var(--ink-soft);
		font-family: var(--font-text, serif);
		font-size: 14.5px;
		line-height: 1.5;
	}
	.quiet {
		margin: 0;
		font-size: 13px;
		color: var(--ink-soft);
	}
	.acts {
		display: flex;
		gap: 14px;
		margin-top: 8px;
		font-size: 12.5px;
	}
</style>
