<script lang="ts">
	// A work's head in the Library's column (2, 3): its title, its byline and year with what loom holds of it, a fold showing its BibTeX entry as text, which `edit` turns into a field that `library-entry` saves (Open 4), and its `digest…` menu. The row menu's `edit its entry…` opens the fold as the field.
	import * as api from '$lib/library/api';
	import { said } from '$lib/library/said';
	import type { WorkAnswer } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { menus } from '$lib/views/library/menus.svelte';
	import DigestMenu from '$lib/views/library/DigestMenu.svelte';
	import { served } from '$lib/library/served.svelte';
	import { library as words } from '$lib/words/library';

	let { work }: { work: WorkAnswer } = $props();
	let entry = $state(false);
	const editing = $derived(lib.editingEntry === work.ref);
	let draft = $state('');
	let refused = $state('');
	let saving = $state(false);
	// opened to edit, the fold shows and the field starts from the entry as it stands
	$effect(() => {
		if (!editing) return;
		entry = true;
		draft = work.entry;
		refused = '';
	});

	async function save(e: SubmitEvent): Promise<void> {
		e.preventDefault();
		saving = true;
		const done = await api.entry(work.ref, draft);
		saving = false;
		if (!done.ok) return void (refused = said(done.error));
		lib.editingEntry = null;
		message.post(words.column.entrySaved(work.short));
	}

	/** Gives the keyboard to the field as it appears. */
	const focused = (el: HTMLElement) => void queueMicrotask(() => el.focus());

	const holds = $derived(work.holds.pdf && work.holds.tex ? words.column.holds.both : work.holds.pdf ? words.column.holds.pdf : work.holds.tex ? words.column.holds.tex : words.column.holds.none);
	const meta = $derived([words.byline(work.authors), work.year, holds].filter(Boolean).join(' · '));
</script>

<div class="wk-title" data-testid="work-title">{work.title}</div>
<!-- the entry's fold where the work's read gives the entry -->
<div class="wk-meta">{meta}{#if work.entry} · <button type="button" class="linkish" aria-expanded={entry} onclick={() => (entry = !entry)} data-testid="work-entry">{words.column.entry} {entry ? '▾' : '▸'}</button>{/if}</div>
{#if entry && editing}
	<form class="edit" onsubmit={(e) => void save(e)} data-testid="entry-form">
		<textarea class="entry" bind:value={draft} rows="8" spellcheck="false" aria-label={words.column.entryField} use:focused data-testid="entry-field"></textarea>
		{#if refused}<p class="refused" role="alert" data-testid="entry-refused">{refused}</p>{/if}
		<div class="acts">
			<button type="submit" class="btn" disabled={saving || !draft.trim() || draft === work.entry} data-testid="entry-save">{words.column.saveEntry}</button>
			<button type="button" class="btn quiet" onclick={() => (lib.editingEntry = null)} data-testid="entry-cancel">{words.column.cancelEntry}</button>
		</div>
	</form>
{:else if entry}
	<pre class="entry">{work.entry}</pre>
	{#if served.has('library-entry')}<button type="button" class="linkish edit-entry" onclick={() => (lib.editingEntry = work.ref)} data-testid="entry-edit">{words.column.editEntry}</button>{/if}
{/if}
{#if (work.holds.pdf || work.holds.tex) && served.has('library-digest')}
	<span class="menuwrap">
		<button type="button" class="btn" aria-expanded={menus.open === `work:${work.ref}`} onclick={() => menus.toggle(`work:${work.ref}`)} data-testid="work-digest">{words.works.digest}</button>
		{#if menus.open === `work:${work.ref}`}<DigestMenu target={work} left />{/if}
	</span>
{/if}

<style>
	.wk-title {
		font-family: var(--serif);
		font-size: 17px;
		line-height: 1.25;
		margin: 2px 0 4px;
	}
	.wk-meta {
		color: var(--ink-faint);
		font-size: 11px;
		margin-bottom: 8px;
	}
	.wk-meta .linkish {
		font-size: 11px;
	}
	.edit {
		margin: 0 0 8px;
	}
	.edit .entry {
		display: block;
		width: 100%;
		box-sizing: border-box;
		resize: vertical;
		color: var(--ink);
	}
	.acts {
		display: flex;
		gap: 8px;
	}
	.refused {
		color: var(--state-conflicted);
		font-size: 12px;
		margin: 0 0 6px;
	}
	.edit-entry {
		font-size: 11px;
		min-height: 28px;
		margin: -4px 0 8px;
	}
	.entry {
		font: 11px/1.5 var(--mono);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 6px;
		padding: 8px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		margin: 0 0 8px;
	}
</style>
