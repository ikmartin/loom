<script lang="ts">
	// A block in Results to accept, drawn as round six's row: a box to choose it with others where it can be accepted, "main.tex · Lemma 3.3", why it waits at the right, a chevron. Open: what changed since it was accepted (`SinceAccepted`), else its text, each reference in them the in-page anchor the build gave it; the person's open notes on it; why loom cannot accept it yet, or `accept`; and `see it in main.tex`, which lays the draft over Review with that change. An accepted block, folded beneath, opens to its text alone. Within an adoption's row, a block that cannot be accepted says why at its right.
	import Icon from '$lib/components/Icon.svelte';
	import Fragment from '$lib/fragments/Fragment.svelte';
	import { shortDate } from '$lib/badges';
	import { store } from '$lib/manifest/client.svelte';
	import type { UnresolvedReview } from '$lib/manifest/types';
	import { anchorId } from '$lib/nav';
	import { displayNode } from '$lib/nodes/display';
	import Cannot from '$lib/review/Cannot.svelte';
	import SinceAccepted from '$lib/review/SinceAccepted.svelte';
	import { causeLabel } from '$lib/review/evidence';
	import { notesOf } from '$lib/review/queue';
	import { review as words } from '$lib/words/review';
	import { acceptKeys, accepting } from '../accept.svelte';
	import SeeItLink from '../SeeItLink.svelte';
	import { rv } from '../state.svelte';

	let {
		key,
		doc,
		row,
		taken,
		acts = false,
		within = false
	}: {
		key: string;
		/** The document it is listed under, which names it. */
		doc: string;
		/** Why it waits; absent for one accepted. */
		row?: UnresolvedReview;
		/** Where one taken in came from. */
		taken?: string;
		/** Whether the person can accept here: the quilt served for writing and a reviewer named. */
		acts?: boolean;
		/** Whether it is drawn within its adoption's row, which says where it came from. */
		within?: boolean;
	} = $props();

	const m = $derived(store.manifest!);
	const id = $derived(`accept:${key}`);
	const open = $derived(rv.open.has(id));
	const k = $derived(m.keys[key]);
	const node = $derived(displayNode(m, key, doc));
	const changed = $derived(row?.cause === 'earlier-change');
	const causes = $derived(k?.acceptance?.causes ?? []);
	const can = $derived(acts && !!row && !row.refusal);
	let cause = $state(0);

	const meta = $derived.by(() => {
		if (!row) return k?.acceptance ? words.accepted.by(k.acceptance.author, shortDate(k.acceptance.date)) : '';
		if (within && row.refusal) return words.accepted.cannotRow(row.refusal_code);
		if (changed) return words.accepted.more(!causes.length || causes[0].kind === 'own-text-changed' ? words.accepted.changed : causeLabel(m, causes[0]), Math.max(causes.length - 1, 0));
		return taken ?? node.context ?? '';
	});

	function pick(): void {
		if (rv.picked.has(key)) rv.picked.delete(key);
		else rv.picked.add(key);
	}
</script>

<div class="rr" class:open id={`review-${anchorId(key)}`} data-testid="review-row" data-kind="accepted-changed" data-key={key}>
	<div class="rr-line">
		<span class="slot">{#if can}<input type="checkbox" checked={rv.picked.has(key)} onchange={pick} aria-label={words.accepted.pick(node.name)} data-testid="review-pick" />{/if}</span>
		<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(id)}>
			<span class="slot"></span>
			<span class="tx">{words.at(words.file(doc), node.name)}</span>
			{#if meta}<span class="meta" data-testid="review-row-why">{meta}</span>{/if}
			<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
		</button>
	</div>
	{#if open}
		<div class="rr-b">
			{#if changed}<SinceAccepted reviewKey={key} index={cause} master={doc} onchoose={(i) => (cause = i)} inReview />
			{:else if k?.review_fragment}<div class="stmt"><Fragment path={k.review_fragment} master={doc} macroSet={k.review_macros ?? ''} isolatedMacros={!!k.review_macros} standalone /></div>{/if}
			{#each notesOf(m, key) as note (note)}<p class="note" data-testid="review-note">{note}</p>{/each}
			{#if row?.refusal}<Cannot {row} testid="review-refusal" />{/if}
			{#if can}
				<div class="answers"><button type="button" class="btn primary" disabled={!!accepting.at} onclick={() => void acceptKeys([key], key, { [key]: doc })} data-testid="review-accept">{accepting.at === key ? words.accepted.accepting : words.accepted.accept}</button></div>
			{/if}
			<SeeItLink {doc} {key} name={node.name} since={changed} />
		</div>
	{/if}
</div>
