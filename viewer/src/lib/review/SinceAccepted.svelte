<script lang="ts">
	// What changed in a block since it was accepted: why it waits, a choice among its reasons where it has several, and for the reason chosen the block as last accepted (its own text edited) or what it rests on as it is now, else the change's diff. Drawn beside a document in Docs (`ReviewPanel`), over Review with the document (`SeeIt`) and in Results to accept's open row; the choice is the caller's to keep.
	import { store } from '$lib/manifest/client.svelte';
	import { displayNode } from '$lib/nodes/display';
	import Fragment from '$lib/fragments/Fragment.svelte';
	import DiffView from '$lib/components/DiffView.svelte';
	import { review as words } from '$lib/words/review';
	import { causeLabel } from './evidence';

	let { reviewKey, index = 0, master, onchoose, inReview = false }: { reviewKey: string; index?: number; master?: string; onchoose: (i: number) => void; /** In Review, whose references stay the in-page anchors the build gave them, so none opens another view. */ inReview?: boolean } = $props();

	const m = $derived(store.manifest!);
	const causes = $derived(m.keys[reviewKey]?.acceptance?.causes ?? []);
	const cause = $derived(causes[index] ?? causes[0]);
	const comparison = $derived(cause?.comparison);
	const acceptedSide = $derived(cause?.kind === 'own-text-changed');
	// the side drawn is the block's own as accepted, or the result it rests on as it is now
	const named = $derived(displayNode(m, acceptedSide || !cause?.id ? reviewKey : cause.id, master).name);
</script>

{#if cause}
	<div class="since" data-testid="since-accepted">
		{#if causes.length > 1}
			<select aria-label={words.since.choose} value={causes.indexOf(cause)} onchange={(e) => onchoose(Number(e.currentTarget.value))}>{#each causes as c, i (i)}<option value={i}>{words.since.option(causeLabel(m, c), i + 1, causes.length)}</option>{/each}</select>
		{:else}<p class="why">{causeLabel(m, cause)}</p>{/if}
		{#if comparison}
			<div data-testid="review-comparison">
				<h4>{acceptedSide ? words.since.accepted(named) : words.since.current(named)}</h4>
				<Fragment path={acceptedSide ? comparison.accepted : comparison.current} macroSet={acceptedSide ? comparison.accepted_macros : ''} isolatedMacros={acceptedSide} standalone={inReview} />
			</div>
		{:else if cause.diff}<DiffView path={cause.diff} />{/if}
	</div>
{/if}

<style>
	.why {
		font-size: 13px;
		margin: 0 0 var(--gap-tight);
		color: var(--ink-soft);
	}
	h4 {
		margin: var(--gap-tight) 0;
		font-size: 12.5px;
		font-weight: 500;
		color: var(--ink-soft);
	}
	select {
		max-width: 100%;
		margin-bottom: var(--gap-tight);
	}
</style>
