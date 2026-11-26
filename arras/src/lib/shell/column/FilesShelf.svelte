<script lang="ts">
	// The project's files in Docs' column (8): the quilt's directory as it is (`FileTree`: its directories and the files the viewer shows, each agent copy beneath the document it copies), under a `Files` head with a rule, open until the reader folds it. Folded, the head says how many files there are, and a hover slides what is below it down a little to show the top edge of the first row, a hint that a click on the head opens the shelf whole. A publisher that lists no files gets the research state's row here where it has one, and its documents from `DocumentList`.
	import { page } from '$app/state';
	import { store } from '$lib/manifest/client.svelte';
	import type { Master } from '$lib/manifest/types';
	import { route } from '$lib/paths';
	import { docs as words } from '$lib/words/docs';
	import FileTree from '../FileTree.svelte';
	import { filesShelf } from './files.svelte';

	let { masters, own, copiesOf, section }: { masters: Master[]; own: Master[]; copiesOf: (path: string) => Master[]; section: (m: Master) => string } = $props();
	// `peek` is the hover; `shown` keeps the hinted row drawn until the gap has closed again
	let peek = $state(false);
	let shown = $state(false);
	// under reduced motion the gap snaps shut and no transition ends, so the row goes with the pointer
	function leave() {
		peek = false;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) shown = false;
	}
	const dir = $derived(store.manifest?.corpus.directory ?? store.manifest?.corpus.name ?? '');
</script>

{#if store.manifest?.files}
	<div class="files" role="group" aria-label={words.files.head} data-testid="files-shelf" onpointerleave={leave}>
		<button type="button" class="head" aria-expanded={filesShelf.open} title={words.files.title(dir)} data-testid="files-toggle" onpointerenter={() => (peek = shown = !filesShelf.open)} onclick={() => ((filesShelf.open = !filesShelf.open), (peek = shown = false))}>
			<span>{words.files.head}</span>{#if !filesShelf.open}<span class="count">{store.manifest.files.length}</span>{/if}
		</button>
		{#if filesShelf.open}
			<div class="rows"><FileTree files={store.manifest.files} {masters} {own} {copiesOf} {section} /></div>
		{:else}
			<!-- the hint: a gap that opens under the folded head on hover, showing the first row's top edge; it is not a way in, so it is hidden from the keyboard and from a screen reader -->
			<div class="peek" class:on={peek} aria-hidden="true" inert data-testid="files-peek" ontransitionend={(e) => e.target === e.currentTarget && (shown = peek)}>
				{#if shown}<FileTree files={store.manifest.files} {masters} {own} {copiesOf} {section} />{/if}
			</div>
		{/if}
	</div>
{:else if store.manifest?.research_state}
	<!-- the quilt's research state: a page about the whole quilt, so above every document, and no heading of its own -->
	{@const onState = page.route.id === '/page/[id]'}
	<ul class="plain docs state" data-testid="docs-state">
		<li><a href={route('/page/state')} class:here={onState} aria-current={onState ? 'page' : undefined}>{words.files.researchState}</a></li>
	</ul>
{/if}

<style>
	.files {
		position: relative;
		margin: 0 0 var(--gap-tight);
	}
	/* the head stands as tall as today's shelf head, its rule within that height, so the tree's rows stand where they always have */
	.head {
		display: flex;
		align-items: center;
		width: 100%;
		box-sizing: border-box;
		height: calc(12px * 1.4 + 6px);
		margin: 0;
		padding: 3px 6px 2px 4px;
		font: inherit;
		font-size: 12px;
		line-height: 1.4;
		font-weight: 500;
		color: var(--ink);
		text-align: left;
		background: none;
		border: 0;
		border-bottom: 1px solid var(--rule);
		cursor: pointer;
	}
	.count {
		margin-left: auto;
		font-size: 11px;
		font-weight: 400;
		color: var(--ink-faint);
		font-variant-numeric: tabular-nums;
	}
	/* a top-level row starts where the head's word does, as in today's shelf */
	.rows {
		padding: 0 6px 6px 4px;
	}
	/* folded, the gap under the head: closed, and opened about 12 px on hover, which moves everything below it down */
	.peek {
		height: 0;
		overflow: hidden;
		padding: 0 6px 0 4px;
		transition: height 180ms ease;
		mask-image: linear-gradient(to bottom, #000 40%, transparent);
	}
	.peek.on {
		height: 12px;
	}
	@media (prefers-reduced-motion: reduce) {
		.peek {
			transition: none;
		}
	}
	ul.plain {
		list-style: none;
		margin: 0 0 var(--gap-tight);
		padding: 0;
	}
	ul.plain a {
		display: block;
		font-size: 11px;
		color: var(--ink-soft);
		padding: 1px 6px;
		border-radius: var(--rad-pill);
	}
	ul.plain a:hover {
		color: var(--ink);
		text-decoration: none;
	}
	/* The page being read carries the same weight as the current section in the contents, because they are the same fact told twice: where you are. */
	.docs a.here {
		color: var(--ink);
		font-weight: 600;
	}
</style>
