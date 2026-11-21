<script lang="ts">
	// `locate…` on a cited result: the draft's sentence that cites it, its citation marked; beside it a find bar filled with the result's name and what loom found, and the page, the words found washed. The person selects the passage and marks it to digest, which names the result, and in the same gesture asks an agent to read it from there; the result then waits for the agent, and the column says where it was marked.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { CitedRow, CitedStub, Rect, ReviewBody } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Statement from '../Statement.svelte';
	import Crop from './Crop.svelte';

	type Cite = { doc: string; key: string; where: string; fragment: string; nth: number };
	type Find = { query: string; hits: { page: number; rects: Rect[] }[]; pages: number };

	let { row, stub }: { row: Extract<CitedRow, { stubs: unknown }>; stub: CitedStub } = $props();
	const body = new Read<ReviewBody & { cite?: Cite; find?: Find; pdf?: string | null }>();
	let hit = $state(0);
	let page = $state(1);
	let chosen = $state<{ page: number; text: string; rects: number[][]; left: number; top: number } | null>(null);
	let area = $state<HTMLElement | null>(null);

	$effect(() => {
		const id = row.row;
		const node = stub.node;
		void gen.gen;
		void body.load(`${id}#${node}`, (s) => api.reviewRow(id, s, node));
	});

	const find = $derived(body.value?.find);
	const at = $derived(find?.hits.length ? find.hits[hit % find.hits.length] : { page, rects: [] as Rect[] });

	function selected(e: { page: number; text: string; rects: number[][]; client: { left: number; top: number; width: number; height: number } }): void {
		const box = area?.getBoundingClientRect();
		if (!box || !e.text.trim()) return;
		chosen = { page: e.page, text: e.text, rects: e.rects, left: e.client.left - box.left, top: e.client.top - box.top + e.client.height + 6 };
	}

	async function mark(): Promise<void> {
		const c = chosen;
		if (!c) return;
		chosen = null;
		const done = await api.call<{ gen: number; annotation?: string }>('annotate', { target: row.ref, page: c.page, quote: c.text, rects: c.rects, purpose: 'to-digest', node: stub.node });
		if (!done.ok) return message.post(done.error.message);
		const asked = await api.ask('read', { node: stub.node }, { nodes: [stub.node] }, stub.rests.docs);
		message.post(asked.ok ? words.cited.markedOn(c.page) : asked.error.message);
	}
</script>

{#if body.value?.cite}
	{@const cite = body.value.cite}
	<div class="cmp">
		<div>
			<div class="crop-cap">{words.cited.citesHere(cite.where)}</div>
			<div class="citebox"><Statement fragment={cite.fragment} hot={cite.nth} /></div>
		</div>
		<div class="locate" bind:this={area}>
			{#if find}
				<div class="findbar">
					<input class="field" value={find.query} aria-label={words.cited.find} readonly />
					{#if find.hits.length}
						<span>{words.cited.hit(at.page, (hit % find.hits.length) + 1, find.hits.length)}</span>
						{#if find.hits.length > 1}<button type="button" class="linkish" onclick={() => (hit += 1)}>{words.cited.next}</button>{/if}
					{:else}
						<span>{words.cited.noHit(page, find.pages)}</span>
						<button type="button" class="linkish" onclick={() => (page = (page % find.pages) + 1)}>{words.cited.nextPage}</button>
					{/if}
				</div>
				{#if body.value.pdf}<Crop pdf={body.value.pdf} place={at} pad={at.rects.length ? 110 : 0} onselect={selected} />{/if}
				{#if chosen}
					<div class="selpop" style:left="{chosen.left}px" style:top="{chosen.top}px">
						<button type="button" class="btn primary" onclick={mark}><Mark kind="marked" size={11} /> {words.cited.mark}</button>
					</div>
				{/if}
				<p class="note hint">{find.hits.length ? words.cited.unmarked : words.cited.unfound}</p>
			{/if}
		</div>
	</div>
{/if}
