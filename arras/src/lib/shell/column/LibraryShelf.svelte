<script lang="ts">
	// The Library in the column: a work is one thing a reader opens, so the shelf lists them, one row each however many documents it has. A row carries the work's author and title alone, sorted by author: what each holds and needs is said on its Info and on the library's page, not beside every row. A choice opens in the focused pane, as every choice in the column does.
	import { needsYou, shelf } from '$lib/library';
	import { store } from '$lib/manifest/client.svelte';
	import { workUrl } from '$lib/nav';
	import { route } from '$lib/paths';
	import { libraryShelf } from './library.svelte';
	import Shelf from './Shelf.svelte';

	const works = $derived(store.manifest ? shelf(store.manifest) : []);
	const library = $derived.by(() => {
		const q = libraryShelf.filter.trim().toLowerCase();
		return q ? works.filter((r) => r.text.includes(q)) : works;
	});
	// the works wanting something of the person beyond results to check, which Review's Proposed Changes counts
	const wanted = $derived(store.manifest ? needsYou(store.manifest) : 0);
	// adding a work by hand, where the publisher writes the library
	const add = $derived(libraryShelf.canAdd ? { label: 'Add a work', testid: 'library-add', press: () => (libraryShelf.adding = true) } : undefined);
</script>

{#if works.length || libraryShelf.canAdd}
	<Shelf label="Library" testid="library-shelf" toggle="library-toggle" count={works.length} {add} bind:open={libraryShelf.open}>
		<input class="filter" type="search" placeholder="narrow by title, author or key" aria-label="Narrow the works" bind:value={libraryShelf.filter} data-testid="library-filter" />
		<ul class="plain library" data-testid="library-list">
			{#each library as r (r.citekey)}
				<li>
					<a href={workUrl(r.opens)} data-testid="library-work-{r.citekey}">{r.authors ? `${r.authors}, ${r.title}` : r.title}</a>
					{#if r.unreadable}<span class="aside">unreadable</span>{/if}
				</li>
			{:else}
				<li class="aside">nothing matches</li>
			{/each}
			<li><a href={route('/review/library')} data-testid="manage-link">Manage the library</a>{#if wanted}<a class="aside wanted" href={route('/review/library') + '?show=needs-you'} data-testid="manage-wanted">{wanted} {wanted === 1 ? 'needs' : 'need'} you</a>{/if}</li>
		</ul>
	</Shelf>
{/if}

<style>
	.filter {
		width: 100%;
		box-sizing: border-box;
		font: inherit;
		font-size: 11px;
		padding: 2px 5px;
		margin: 0 0 var(--gap-hair);
		border: 1px solid var(--rule);
		border-radius: 3px;
		background: var(--sheet);
		color: var(--ink);
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
	.library .aside {
		margin-left: 0.3em;
		color: var(--ink-faint);
		font-size: 0.9em;
	}
</style>
