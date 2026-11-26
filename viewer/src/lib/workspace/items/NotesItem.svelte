<script lang="ts">
	// The notes tab, "All notes": every file of the quilt that links to a place in it (`docs/design/model.md`, "Notes"), by path, from the manifest's backlinks. A row opens the note, at its first link; under it each link names the place it points at, with the words it quotes, and opens that place. A note is a file of the person's own and nothing here writes one; the list is computed, so nobody edits it.
	import { store } from '$lib/manifest/client.svelte';
	import type { Backlink } from '$lib/manifest/types';
	import { noteHref } from '$lib/review/backlinks';
	import { notes as words } from '$lib/words/notes';
	import { linkName } from '../names';
	import type { Item } from '../item';

	// the one notes tab has no place of its own to go to
	let {}: { item: Item } = $props();
	const m = $derived(store.manifest);
	const files = $derived.by(() => {
		const by = new Map<string, Backlink[]>();
		for (const b of m?.backlinks ?? []) by.set(b.from, [...(by.get(b.from) ?? []), b]);
		return [...by.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([path, links]) => ({ path, links }));
	});
	const folder = (path: string) => (path.includes('/') ? path.slice(0, path.lastIndexOf('/') + 1) : '');
	const file = (path: string) => path.slice(path.lastIndexOf('/') + 1);
</script>

<div class="notes-page" data-testid="notes-tab">
	<h1>{words.all.heading}</h1>
	<p class="lede">{words.all.lede}</p>
	{#if !files.length}
		<p class="none" data-testid="notes-none">{words.all.none}</p>
	{/if}
	{#each files as f (f.path)}
		<section class="nf" data-testid="note-file" data-path={f.path}>
			<a class="head" href={m ? noteHref(m, f.links[0]) : undefined} title={words.all.open(f.path)}><span class="dir">{folder(f.path)}</span><span class="name">{file(f.path)}</span><span class="n">{words.all.links(f.links.length)}</span></a>
			<ul>
				{#each f.links as b (`${b.line}:${b.href}`)}
					<li><a href={b.href} data-testid="note-target"><span class="to">{m ? linkName(m, b.href) : b.key}</span>{#if b.quote}<span class="q">“{b.quote}”</span>{/if}</a></li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.notes-page {
		width: 760px;
		max-width: 100%;
		margin: 0 auto;
		padding: 18px 24px 80px;
		font-size: 13px;
	}
	h1 {
		margin: 0 0 4px;
		font-size: 18px;
		font-weight: 600;
	}
	.lede,
	.none {
		margin: 0 0 18px;
		color: var(--ink-soft);
	}
	.nf {
		margin-bottom: 16px;
		border-bottom: 1px solid var(--rule);
		padding-bottom: 10px;
	}
	.head {
		display: flex;
		align-items: baseline;
		gap: 2px;
		color: var(--ink);
		text-decoration: none;
		padding: 4px 6px;
		margin: 0 -6px;
		border-radius: 6px;
	}
	.head:hover {
		background: var(--leaf);
	}
	.dir {
		color: var(--ink-faint);
	}
	.name {
		font-weight: 600;
	}
	.n {
		margin-left: auto;
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	ul {
		list-style: none;
		margin: 2px 0 0;
		padding: 0 0 0 14px;
	}
	li a {
		display: flex;
		gap: 8px;
		padding: 3px 6px;
		border-radius: 6px;
		color: var(--ink-soft);
		text-decoration: none;
		min-width: 0;
	}
	li a:hover {
		background: var(--leaf);
		color: var(--ink);
	}
	.to {
		flex: none;
	}
	.q {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-style: italic;
		color: var(--ink-faint);
	}
</style>
