<script lang="ts">
	// Results to accept's rows (`AcceptRow`), every draft's or the one the column chooses, from the manifest (`acceptList`): the blocks waiting, changed since accepted or taken in, each once; while some are chosen, a line over them with `accept N`; then, folded and counting nothing, the never accepted, which are accepted here too, and the accepted. Says once that the reviewer's name is git's, and where the person cannot accept, why. A link to one block's row (`#review-…`) unfolds what holds it, opens it and brings it into view.
	import { tick } from 'svelte';
	import { page } from '$app/state';
	import Icon from '$lib/components/Icon.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { anchorId } from '$lib/nav';
	import SaidOnce from '$lib/review/SaidOnce.svelte';
	import { review as words } from '$lib/words/review';
	import { can } from '$lib/write';
	import { acceptKeys, accepting } from './accept.svelte';
	import AcceptRow from './rows/AcceptRow.svelte';
	import { rv } from './state.svelte';
	import { acceptList } from './yours';

	const m = $derived(store.manifest!);
	const list = $derived(acceptList(m, rv.doc));
	const reviewer = $derived(m.reviewer?.name ?? '');
	let served = $state(false);
	$effect(() => {
		void can('review-accept').then((yes) => (served = yes));
	});
	const acts = $derived(served && !!reviewer);
	// the chosen still listed, each with the document that names it
	const docs = $derived(Object.fromEntries([...list.waiting, ...list.never].map((b) => [b.key, b.doc])));
	const chosen = $derived([...rv.picked].filter((k) => k in docs));

	$effect(() => {
		const hash = page.url.hash.slice(1);
		if (!hash.startsWith('review-')) return;
		const at = (b: { key: string }) => `review-${anchorId(b.key)}` === hash;
		const fold = list.never.some(at) ? 'accept:never' : list.accepted.some(at) ? 'accept:accepted' : null;
		const found = [...list.waiting, ...list.never, ...list.accepted].find(at);
		if (!found) return;
		if (fold) rv.folded.delete(fold);
		rv.open.add(`accept:${found.key}`);
		void tick().then(() => window.document.getElementById(hash)?.scrollIntoView({ block: 'center' }));
	});
</script>

{#snippet fold(id: string, title: string, n: number)}
	<div class="rg sub" data-testid="review-fold" data-fold={id}>
		<button type="button" class="fold" aria-expanded={!rv.folded.has(id)} aria-label={title} onclick={() => rv.fold(id)}><Icon name={rv.folded.has(id) ? 'right' : 'caret'} size={16} /></button>
		<span>{title}</span><span class="n">{n}</span>
	</div>
{/snippet}

<div class="yours" data-testid="review-accept-list">
	{#if reviewer && m.reviewer?.source === 'git config user.name'}<SaidOnce text={words.once.nameFromGit(reviewer)} testid="review-name-from-git" />{/if}
	{#if !reviewer}<p class="note" data-testid="review-no-reviewer">{words.accepted.noReviewer}</p>
	{:else if !served}<p class="note" data-testid="review-read-only">{words.accepted.readOnly}</p>{/if}
	{#if acts && chosen.length}
		<div class="rg head acts" data-testid="review-picked">
			<span class="says">{words.accepted.picked(chosen.length)}</span>
			<button type="button" class="btn primary" disabled={!!accepting.at} onclick={() => void acceptKeys(chosen, '*', docs)} data-testid="review-accept-picked">{accepting.at === '*' ? words.accepted.accepting : words.accepted.acceptPicked(chosen.length)}</button>
			<button type="button" class="btn" onclick={() => rv.picked.clear()} data-testid="review-clear">{words.accepted.clear}</button>
		</div>
	{/if}
	{#each list.waiting as b (b.key)}<AcceptRow key={b.key} doc={b.doc} row={b.row} taken={b.taken} {acts} />{/each}
	{#if list.never.length}
		{@render fold('accept:never', words.accepted.never, list.never.length)}
		{#if !rv.folded.has('accept:never')}{#each list.never as b (b.key)}<AcceptRow key={b.key} doc={b.doc} row={b.row} {acts} />{/each}{/if}
	{/if}
	{#if list.accepted.length}
		{@render fold('accept:accepted', words.accepted.done, list.accepted.length)}
		{#if !rv.folded.has('accept:accepted')}{#each list.accepted as b (b.key)}<AcceptRow key={b.key} doc={b.doc} />{/each}{/if}
	{/if}
</div>
