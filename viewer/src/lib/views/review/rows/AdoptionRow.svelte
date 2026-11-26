<script lang="ts">
	// An adoption as one row of Results to accept: the blocks one agent's copy brought in, "main.tex · aidoc", how many it took in and how many of them cannot be accepted yet, a chevron. Open: `accept all N` for those that can be, then each block as a row of its own (`AcceptRow`), its box choosing it with others, a block that cannot be accepted saying why at its right. The column's message says what was accepted, in the viewer's words (`acceptSaid`).
	import Icon from '$lib/components/Icon.svelte';
	import { review as words } from '$lib/words/review';
	import { acceptKeys, accepting } from '../accept.svelte';
	import { rv } from '../state.svelte';
	import type { AcceptRowItem } from '../yours';
	import AcceptRow from './AcceptRow.svelte';

	let { item, acts = false }: { item: Extract<AcceptRowItem, { type: 'adoption' }>; acts?: boolean } = $props();
	const id = $derived(`adopt:${item.copy}`);
	const open = $derived(rv.open.has(id));
	const cannot = $derived(item.blocks.filter((b) => b.row.refusal).length);
	const ready = $derived(acts ? item.blocks.filter((b) => !b.row.refusal) : []);
	const docs = $derived(Object.fromEntries(item.blocks.map((b) => [b.key, b.doc])));
</script>

<div class="rr" class:open data-testid="review-row" data-kind="accepted-changed" data-adoption={item.copy}>
	<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(id)}>
		<span class="slot"></span><span class="slot"></span>
		<span class="tx">{words.at(words.file(item.doc), item.name)}</span>
		<span class="meta" data-testid="review-row-why">{words.quiet([words.accepted.adoption(item.blocks.length), cannot ? words.accepted.cannotCount(cannot) : ''])}</span>
		<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
	</button>
	{#if open}
		<div class="rr-b">
			{#if acts}
				<div class="answers all">
					<button type="button" class="btn primary" disabled={!ready.length || !!accepting.at} title={words.accepted.acceptAllHover} data-testid="adoption-accept-all" onclick={() => void acceptKeys(ready.map((b) => b.key), id, docs)}>{accepting.at === id ? words.accepted.accepting : words.accepted.acceptAll(ready.length)}</button>
				</div>
			{/if}
			<div class="blocks">
				{#each item.blocks as b (b.key)}<AcceptRow key={b.key} doc={b.doc} row={b.row} {acts} within />{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.all {
		margin-bottom: 10px;
	}
	.blocks :global(.rr:last-child) {
		border-bottom: 0;
	}
</style>
