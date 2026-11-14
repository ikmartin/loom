<script lang="ts">
	// The documents the column lists by name. Where the publisher lists no files: the drafts being worked on, as a list rather than a dropdown, because a dropdown shows one name at a time and cannot say which draft is conflicted, each agent copy beneath the document it copies. And always: a copy whose own document is not listed (closed, context-only, gone), under Agent documents, with the closed ones folded beneath. A landmark is reached from its draft's history, not listed here.
	import { store } from '$lib/manifest/client.svelte';
	import type { Master } from '$lib/manifest/types';
	import { masterUrl } from '$lib/nav';
	import { explain, says } from '../access';
	import AgentMark from '../AgentMark.svelte';

	let {
		own,
		unplaced,
		closed,
		copiesOf,
		section,
		filename,
		onDocument,
		currentDoc
	}: {
		own: Master[];
		/** The agent copies whose own document is not listed. */
		unplaced: Master[];
		closed: Master[];
		copiesOf: (path: string) => Master[];
		section: (m: Master) => string;
		filename: (path: string) => string;
		onDocument: boolean;
		currentDoc: string;
	} = $props();

	// a copy is one agents edit, said where the publisher says who edits its files at all
	const marks = $derived(says(store.manifest?.files));
</script>

{#snippet link(m: Master)}
	{@const here = onDocument && m.path === currentDoc}
	<a href={masterUrl(m.path)} class:here aria-current={here ? 'page' : undefined}>{filename(m.path)}{#if section(m)}<span class="aside">{section(m)}</span>{/if}</a>
{/snippet}
{#if own.length && !store.manifest?.files}
	<p class="rail-label">Documents</p>
	<ul class="plain docs" data-testid="docs-drafts">
		{#each own as m (m.path)}
			{@const copies = copiesOf(m.path)}
			<li>
				{@render link(m)}
				{#if copies.length}
					<!-- the agent's copies of this document, which the person and an agent both edit -->
					<ul class="plain docs copies" data-testid="docs-copies">
						{#each copies as c (c.path)}<li>{@render link(c)}{#if marks}<AgentMark agents={true} said={explain({ agents: true }, { copyOf: m.path })} testid="access-{c.path}" />{/if}</li>{/each}
					</ul>
				{/if}
			</li>
		{/each}
	</ul>
{/if}
{#if unplaced.length || closed.length}
	<p class="rail-label">Agent documents</p>
	{#if unplaced.length}
		<ul class="plain docs" data-testid="docs-agent">
			{#each unplaced as m (m.path)}<li>{@render link(m)}{#if marks && m.copy_of}<AgentMark agents={true} said={explain({ agents: true }, { copyOf: m.copy_of })} testid="access-{m.path}" />{/if}</li>{/each}
		</ul>
	{/if}
	{#if closed.length}
		<details class="closed" data-testid="docs-closed">
			<summary>Closed agent documents</summary>
			<ul class="plain docs">
				{#each closed as m (m.path)}<li>{@render link(m)}</li>{/each}
			</ul>
		</details>
	{/if}
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
	.closed summary {
		font-size: 10.5px;
		color: var(--ink-faint);
		margin: 0 0 var(--gap-hair) 6px;
		cursor: pointer;
	}
	/* The document being read carries the same weight as the current section in the contents, because they are the same fact told twice: where you are. */
	.docs a.here {
		color: var(--ink);
		font-weight: 600;
	}
	.docs .aside {
		margin-left: 0.4em;
		color: var(--ink-faint);
		font-size: 0.9em;
	}
</style>
