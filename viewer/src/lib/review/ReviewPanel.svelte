<script lang="ts">
	// Beside a document opened from Your Changes (`?review=KEY`), inside the document's side panel: the block, why it waits, the change when it changed since it was accepted (`SinceAccepted`), and Accept, its answer said here. A block loom cannot accept says why instead. It stands in Docs, so it links nowhere outside Docs: its `close` puts the panel away in place.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { store } from '$lib/manifest/client.svelte';
	import { landed } from '$lib/manifest/updating.svelte';
	import { can, write } from '$lib/write';
	import { displayNode } from '$lib/nodes/display';
	import { shortDate } from '$lib/badges';
	import { here } from '$lib/here.svelte';
	import Cannot from './Cannot.svelte';
	import { causeLabel } from './evidence';
	import { takenLabel } from './queue';
	import Said from './Said.svelte';
	import SinceAccepted from './SinceAccepted.svelte';

	let { reviewKey, causeIndex, master, plain, causeHref }: { reviewKey: string; causeIndex: number; master: string; plain: string; causeHref: (i: number) => string } = $props();

	const m = $derived(store.manifest!);
	const key = $derived(m.keys[reviewKey]);
	const row = $derived((m.unresolved ?? []).find((r) => r.key === reviewKey));
	const causes = $derived(key?.acceptance?.causes ?? []);
	const cause = $derived(causes[causeIndex] ?? causes[0]);
	const name = $derived(displayNode(m, reviewKey, master).name);
	let served = $state(false);
	let busy = $state(false);
	let said = $state<{ text: string; refused: boolean } | null>(null);
	onMount(() => {
		void can('review-accept').then((yes) => (served = yes));
	});
	// the block under review and why, for `loom here`
	$effect(() => {
		here.review = { key: reviewKey, cause: cause ? causeLabel(m, cause) : null };
		return () => {
			here.review = null;
		};
	});

	const status = $derived(
		!row
			? key?.acceptance?.fresh
				? `Accepted by ${key.acceptance.author}, ${shortDate(key.acceptance.date)}.`
				: 'Not waiting to be accepted.'
			: row.cause === 'never-accepted'
				? 'Never accepted.'
				: row.cause === 'earlier-change'
					? 'Changed since you accepted it.'
					: `${takenLabel(row)}.`
	);

	async function accept(): Promise<void> {
		busy = true;
		said = null;
		const done = (await write('review-accept', { keys: [reviewKey] })) as Awaited<ReturnType<typeof write>> & { accepted?: string[]; refused?: { why: string }[] };
		if (!done.ok) said = { text: done.error?.message ?? 'The publisher refused it.', refused: true };
		else {
			await landed();
			said = done.accepted?.length ? { text: `Accepted ${name}.`, refused: false } : { text: done.refused?.[0]?.why ?? 'Not accepted.', refused: true };
		}
		busy = false;
	}
</script>

<div class="panel">
	<header><strong>{name}</strong><a href={plain} data-testid="review-panel-close">close</a></header>
	<p class="status" data-testid="review-panel-status">{status}</p>
	<SinceAccepted {reviewKey} index={causes.indexOf(cause)} {master} onchoose={(i) => goto(causeHref(i), { noScroll: true, keepFocus: true })} />
	{#if row?.refusal}<Cannot {row} testid="review-panel-refusal" />
	{:else if row && served && m.reviewer?.name}<button class="btn primary" disabled={busy} onclick={() => void accept()} data-testid="review-panel-accept">{busy ? 'Accepting…' : 'Accept'}</button>{/if}
	{#if said}<Said text={said.text} refused={said.refused} testid="review-panel-said" />{/if}
</div>

<style>
	.status {
		font-size: 13px;
		margin: 0 0 var(--gap-tight);
	}
</style>
