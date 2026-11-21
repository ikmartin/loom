<script lang="ts">
	// One digested result open under its work: how its text was made and so how to compare it, its name, its text rendered or plain, "Does loom's copy match the paper?" with the person's yes and no; beside it the paper cropped at the result's place.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { NodeAnswer, PlacesAnswer } from '$lib/library/types';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { THEOREMS } from '$lib/node/taxa';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from '../state.svelte';
	import Crop from './Crop.svelte';

	let { node, pdf }: { node: string; pdf: string | null } = $props();
	const read = new Read<NodeAnswer>();
	const at = new Read<PlacesAnswer>();
	let busy = $state(false);

	$effect(() => {
		const id = node;
		void gen.gen;
		void read.load(id, (s) => api.node({ node: id }, s));
		void at.load(id, (s) => api.places({ node: id }, s));
	});

	const n = $derived(read.value);
	const place = $derived(at.value?.places.find((p) => p.node === node) ?? null);
	const how = $derived.by(() => {
		const d = n?.digested;
		if (!d) return '';
		return d.how === 'transcribed' ? words.check.how.transcribed(d.by, n?.pages ?? '') : d.how === 'extracted' || d.how === 'written' ? words.check.how[d.how]() : words.check.how[d.how](d.by);
	});

	async function yes(): Promise<void> {
		if (!n?.node || !n.hash) return;
		busy = true;
		const done = await api.check(n.node, n.hash);
		busy = false;
		message.post(done.ok ? words.check.matched(n.name) : said(done.error));
	}
</script>

{#if read.error}
	<p class="note">{words.check.missing}</p>
{:else if n}
	<div class="cmp">
		<div>
			{#if how}<p class="note how" class:agent={n.digested?.how !== 'extracted'}>{how}</p>{/if}
			<div class="nh">
				<span class="name">{n.name}{#if n.title}<span class="tl">{n.title}</span>{/if}</span>
				<span class="seg">
					<button type="button" class:on={!rv.plain} onclick={() => (rv.plain = false)}>{words.check.rendered}</button>
					<button type="button" class:on={rv.plain} onclick={() => (rv.plain = true)}>{words.check.plain}</button>
				</span>
			</div>
			{#if n.body !== undefined}
				<div class="stmt"><NodeBody body={n.body} macros={n.macros?.body ?? null} points={n.points ?? {}} plain={rv.plain} italic={THEOREMS.has(n.taxon)} drawn={n.hash ? api.drawnUrl(n.hash, n.macros?.hash ?? null) : null} /></div>
			{/if}
			{#if n.paper === 'unchecked'}
				<p class="ask">{words.check.ask}</p>
				<div class="answers">
					<button type="button" class="btn" disabled={busy} onclick={yes}>{words.check.yes}</button>
					<button type="button" class="btn" onclick={() => message.post(words.check.noLater)}>{words.check.no}</button>
				</div>
			{/if}
		</div>
		<div>
			{#if pdf && place}
				<Crop {pdf} {place} caption={words.check.page(n.work.short, place.page)} />
			{:else if at.value}
				<p class="note">{words.check.noPlace}</p>
			{/if}
		</div>
	</div>
{/if}
