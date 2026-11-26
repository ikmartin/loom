<script lang="ts">
	// A change waiting in the person's text, as round six draws a row of Proposed edits: "main.tex · proof of Theorem 3.1", who proposed it or that it was edited in place since the look, a chevron. Open: the change as a card drawn bare (`ChangeCard`), its words out and in, what it answers, why it cannot be kept or discarded where it cannot, and Keep and Discard, the history offering their undo; then `see it in main.tex`. A change in no draft's text names no draft and offers no see it.
	import Icon from '$lib/components/Icon.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import ChangeCard from '$lib/review/ChangeCard.svelte';
	import { whoMade } from '$lib/review/changes';
	import { keyName } from '$lib/workspace/names';
	import { review as words } from '$lib/words/review';
	import SeeItLink from '../SeeItLink.svelte';
	import { rv } from '../state.svelte';
	import type { ChangeItem } from '../yours';

	let { item }: { item: ChangeItem } = $props();
	const m = $derived(store.manifest!);
	const c = $derived(item.c);
	const id = $derived(`edit:${c.id}`);
	const open = $derived(rv.open.has(id));
	const what = $derived(c.key ? keyName(m, c.key) : words.file(c.path));
	// where it is: the draft, or the file in no draft's text; then the block, or a file of the draft's that is not the draft itself
	const where = $derived(item.doc ? words.file(item.doc) : item.label);
	const line = $derived(c.key || (where !== c.path && where !== what) ? words.at(where, what) : where);
	const who = $derived(whoMade(m, c));
	const meta = $derived(c.kind === 'suggested' ? (who ? words.edits.by(who) : '') : words.edits.sinceLook);
	/** A block the card names (the note it answers) is laid over Review in the draft that holds the change, else named in words. */
	const see = $derived(item.doc ? (key: string, said: string) => (rv.over = { doc: item.doc!, key, name: said }) : null);
</script>

<div class="rr" class:open data-testid="review-row" data-kind="edits" data-change={c.id}>
	<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(id)}>
		<span class="slot"></span><span class="slot"></span>
		<span class="tx">{line}</span>
		{#if meta}<span class="meta">{meta}</span>{/if}
		<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
	</button>
	{#if open}
		<div class="rr-b">
			<ChangeCard {c} {see} bare />
			{#if item.doc && c.key}<SeeItLink doc={item.doc} key={c.key} name={what} />{/if}
		</div>
	{/if}
</div>
