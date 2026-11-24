<script lang="ts">
	// Under Proposed edits, the agents' copies waiting to be taken in, a card each, those into the draft the column chooses: a copy opens on its own page in Review (`/review/proposed?copy=`), where it is taken in and applied.
	import { store } from '$lib/manifest/client.svelte';
	import { route } from '$lib/paths';
	import { itemsOf, tally } from '$lib/review/contribution';
	import { copySays } from '$lib/review/proposed';
	import { review as words } from '$lib/words/review';
	import { copiesOf } from './yours';

	let { doc = null }: { doc?: string | null } = $props();
	const m = $derived(store.manifest!);
	const copies = $derived(copiesOf(m, doc));
	const name = (path: string) => (path.split('/').pop() ?? path).replace(/\.tex$/, '');
</script>

{#if copies.length}
	<ul class="copies" data-testid="review-copies">
		{#each copies as c (c.copy)}
			<li class="card" data-testid="proposed-card" data-kind="copy" data-id={c.copy}>
				<div class="line">
					<span class="tag">{words.yours.copy}</span>
					<span class="name">{name(c.copy)}</span>
					<span class="of">{words.yours.into(c.source)}</span>
					<span class="acts"><a class="btn small primary" href="{route('/review/proposed')}?copy={encodeURIComponent(c.copy)}" data-testid="proposed-open">{words.yours.openCopy}</a></span>
				</div>
				<p class="why" data-testid="proposed-tally">{copySays(tally(c, itemsOf(m, c)))}.</p>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.copies {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.card {
		padding: 12px 14px;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--review-paper);
	}
	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 8px;
	}
	.name {
		font-size: 14px;
		overflow-wrap: anywhere;
	}
	.of,
	.why {
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.tag {
		padding: 1px 8px;
		border-radius: 999px;
		background: var(--leaf);
		color: var(--ink-soft);
		font-size: 11.5px;
	}
	.acts {
		margin-left: auto;
		display: flex;
		gap: 6px;
	}
	.why {
		margin: 4px 0 0;
	}
</style>
