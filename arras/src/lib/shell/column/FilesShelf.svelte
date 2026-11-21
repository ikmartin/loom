<script lang="ts">
	// The project's files in the column: the quilt's directory as it is (`FileTree`: its directories and the files the viewer shows, each agent copy beneath the document it copies), in a shelf open until the reader folds it. A publisher that lists no files gets the research state's row here where it has one, and its documents from `DocumentList`.
	import { page } from '$app/state';
	import { store } from '$lib/manifest/client.svelte';
	import type { Master } from '$lib/manifest/types';
	import { route } from '$lib/paths';
	import FileTree from '../FileTree.svelte';
	import { filesShelf } from './files.svelte';
	import Shelf from './Shelf.svelte';

	let { masters, own, copiesOf, section }: { masters: Master[]; own: Master[]; copiesOf: (path: string) => Master[]; section: (m: Master) => string } = $props();
</script>

{#if store.manifest?.files}
	<!-- Files is the quilt's directory as it is, in a shelf that folds -->
	<Shelf label="Files" testid="files-shelf" toggle="files-toggle" title="View of files in {store.manifest.corpus.directory ?? store.manifest.corpus.name}/" bind:open={filesShelf.open}>
		<FileTree files={store.manifest.files} {masters} {own} {copiesOf} {section} />
	</Shelf>
{:else if store.manifest?.research_state}
	<!-- the quilt's research state: a page about the whole quilt, so above every document, and no heading of its own -->
	{@const onState = page.route.id === '/page/[id]'}
	<ul class="plain docs state" data-testid="docs-state">
		<li><a href={route('/page/state')} class:here={onState} aria-current={onState ? 'page' : undefined}>Research state</a></li>
	</ul>
{/if}

<style>
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
