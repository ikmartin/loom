<script lang="ts">
	// The notes tab (8b, 8b work): every note of the quilt, 760 pixels wide whatever its order. By work, the notes that lost their place first, each with `place it again` and `delete`, then a group for each document and each work with its latest notes and how many more; by date, the newest twenty and how many older. A note draws its colour, the words it is on, its text, who wrote it and when, and its tags; a placed note opens at its place in Docs.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { Note, NotesAnswer, NotesGroup } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { docs as words } from '$lib/words/docs';
	import { shortNames } from '$lib/views/docs/names.svelte';
	import { workspace } from '../store.svelte';
	import type { Item } from '../item';

	// the one notes tab has no place of its own to go to
	let {}: { item: Item } = $props();
	let sort = $state<'work' | 'date'>('work');
	let orphaned = $state(true);
	const read = new Read<NotesAnswer>();
	/** The rest of a group, or of the list by date, read when asked for. */
	let rest = $state<Record<string, Note[]>>({});

	$effect(() => {
		const s = sort;
		const o = orphaned;
		void gen.gen;
		rest = {};
		void read.load(`${s}:${o}`, (since) => api.notes(s, o, undefined, since));
	});

	const keyOf = (g: NotesGroup) => (g.group === 'orphaned' ? 'orphaned' : 'doc' in g.group ? g.group.doc : g.group.ref);
	const headOf = (g: NotesGroup) => (g.group === 'orphaned' ? words.notes.orphaned : 'doc' in g.group ? (g.group.doc.split('/').pop() ?? g.group.doc) : g.group.short);
	const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

	async function more(g: NotesGroup | null): Promise<void> {
		const key = g ? keyOf(g) : 'date';
		const offset = g ? g.notes.length : (read.value?.notes?.length ?? 0) + (rest.date?.length ?? 0);
		const a = await api.notes(sort, orphaned, { ...(g ? { group: key } : {}), offset });
		if (a.ok) rest = { ...rest, [key]: [...(rest[key] ?? []), ...(a.value.notes ?? [])] };
	}
	function go(n: Note): void {
		const at = n.at_place;
		if (!at) return;
		if ('doc' in at) workspace.here({ kind: 'document', id: at.doc, note: n.annotation });
		else {
			if (at.short) shortNames.set(at.ref, at.short);
			workspace.beside({ kind: 'work', id: at.ref, place: { page: at.page } }, workspace.focus);
		}
	}
	async function remove(n: Note): Promise<void> {
		const done = await api.deleteNote(n.annotation);
		message.post(done.ok ? words.notes.deleted : done.error.message);
	}
</script>

{#snippet note(n: Note, where: boolean)}
	<div class="note" class:orph={!n.at_place} data-testid="note">
		<span class="sw" style:background={n.color}></span>
		<div class="nb">
			{#if n.at_place}<button type="button" class="open" onclick={() => go(n)}>{#if n.quote}<span class="q">“{n.quote}”</span>{/if}{#if n.message}<span class="t">{n.message}</span>{/if}</button>
			{:else}{#if n.quote}<span class="q">“{n.quote}”</span>{/if}{#if n.message}<span class="t">{n.message}</span>{/if}{/if}
			{#if n.tags.length}<span class="tags">{#each n.tags as t (t)}<span class="tag">{t}</span>{/each}</span>{/if}
			{#if where && n.at_place}<span class="where">{'doc' in n.at_place ? n.at_place.doc.split('/').pop() : n.at_place.short}</span>{/if}
			{#if n.was}<span class="where">{words.notes.was(n.was)}</span>{/if}
			{#if !n.at_place}
				<span class="acts">
					<button type="button" class="as-link" onclick={() => message.post(words.notes.placeHow)}>{words.notes.place}</button>
					<button type="button" class="as-link quiet" onclick={() => remove(n)}>{words.notes.delete}</button>
				</span>
			{/if}
		</div>
		<span class="w">{words.notes.byAt(n.by, day(n.at))}</span>
	</div>
{/snippet}

<div class="notes-page" data-testid="notes-tab">
	<div class="bar">
		<span>{words.notes.sortBy}</span>
		<span class="seg">
			<button type="button" class:on={sort === 'work'} aria-pressed={sort === 'work'} onclick={() => (sort = 'work')}>{words.notes.work}</button>
			<button type="button" class:on={sort === 'date'} aria-pressed={sort === 'date'} onclick={() => (sort = 'date')}>{words.notes.date}</button>
		</span>
		<span class="grow"></span>
		<label><input type="checkbox" bind:checked={orphaned} data-testid="notes-orphaned" />{words.notes.showOrphaned(read.value?.orphaned ?? 0)}</label>
	</div>
	{#if read.value?.groups}
		{#each read.value.groups as g (keyOf(g))}
			<section class="ng" data-testid="notes-group">
				<h2>{headOf(g)}<span class="n">{g.n}</span></h2>
				{#each [...g.notes, ...(rest[keyOf(g)] ?? [])] as n (n.annotation)}{@render note(n, false)}{/each}
				{#if g.more && !rest[keyOf(g)]}<button type="button" class="as-link quiet more" onclick={() => more(g)}>{words.notes.more(g.more)}</button>{/if}
			</section>
		{/each}
	{:else if read.value?.notes}
		<section class="ng">
			{#each [...read.value.notes, ...(rest.date ?? [])] as n (n.annotation)}{@render note(n, true)}{/each}
			{#if read.value.more && !rest.date}<button type="button" class="as-link quiet more" onclick={() => more(null)}>{words.notes.older(read.value.more)}</button>{/if}
		</section>
	{/if}
</div>

<style>
	.notes-page {
		width: 760px;
		max-width: 100%;
		margin: 0 auto;
		padding: 18px 24px 80px;
		font-size: 13px;
	}
	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 18px;
		color: var(--ink-soft);
	}
	.grow {
		flex: 1;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--rule);
		border-radius: 7px;
		overflow: hidden;
		background: var(--sheet);
	}
	.seg button {
		font: inherit;
		font-size: 11.5px;
		border: 0;
		background: none;
		padding: 2px 10px;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.seg button + button {
		border-left: 1px solid var(--rule);
	}
	.seg button.on {
		background: var(--leaf);
		color: var(--ink);
		font-weight: 500;
	}
	label {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}
	.ng {
		margin-bottom: 26px;
	}
	h2 {
		margin: 0 0 4px;
		padding-bottom: 6px;
		font-size: 11.5px;
		font-weight: 400;
		color: var(--ink-soft);
		border-bottom: 1px solid var(--rule-strong);
	}
	h2 .n {
		margin-left: 8px;
	}
	.note {
		display: flex;
		gap: 14px;
		padding: 10px 4px;
		border-bottom: 1px solid var(--rule);
	}
	.sw {
		flex: none;
		width: 3px;
		height: 16px;
		margin-top: 3px;
		border-radius: 2px;
	}
	.nb {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.open {
		display: flex;
		flex-direction: column;
		gap: 4px;
		padding: 0;
		font: inherit;
		text-align: left;
		color: inherit;
		background: none;
		border: 0;
		cursor: pointer;
	}
	.q {
		font-family: var(--font-text, serif);
		font-size: 15px;
		color: var(--ink-soft);
	}
	.tags {
		display: flex;
		gap: 6px;
	}
	.tag {
		padding: 0 6px;
		font-size: 11px;
		color: var(--ink-soft);
		border: 1px solid var(--rule);
		border-radius: 4px;
	}
	.where {
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.acts {
		display: flex;
		gap: 12px;
	}
	.quiet {
		color: var(--ink-faint);
	}
	.w {
		flex: none;
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.more {
		margin: 8px 4px 0;
		font-size: 12px;
	}
</style>
