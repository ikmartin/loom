<script lang="ts">
	// A work, by its reference, read in its pane in the one reader (`Reading`), the reader the Library's tab for the work draws too, at the place a link names, else where the reader last was: opened by its address, from a note on it, or beside a draft from Docs' picker or a citation's card. Its stored PDF's hash and its short name are the library's works list's, which the manifest does not carry.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { said } from '$lib/library/said';
	import Reading from '$lib/pdf/Reading.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { shortNames } from '$lib/views/docs/names.svelte';
	import { library } from '$lib/words/library';
	import type { WorkLink } from '$lib/worklink';
	import { itemKey, type Item } from '../item';
	import { workState } from '../state.svelte';
	import { workspace } from '../store.svelte';

	let { item }: { item: Item } = $props();

	$effect(() => {
		void gen.gen;
		void lib.works.load('works', (s) => api.works(undefined, s));
	});
	const row = $derived(lib.works.value?.works.find((w) => w.ref === item.id) ?? null);
	// the pane's tab names the work by its short name
	$effect(() => {
		if (row) shortNames.set(row.ref, row.short);
	});
	/** Whether a link names a place on this work's pages; an empty one, as a `cited:` link with no keys gives, names none. */
	const named = $derived(Object.keys(item.place ?? {}).length > 0);
	/** The page a link sends the paper to, else the first; with no place named it opens where the reader last was (`Reading`). */
	const reading = $derived(item.place?.page || 1);
	// The place the item points at, in the one locator syntax `cited:` links share (plan 0.13 item 6).
	const locator = $derived<WorkLink>({ id: item.id, ...(item.place ?? {}) });
	/** The reader's view of the paper, shared with the controls, which the focused pane draws for its item. */
	const pdf = $derived(workState(item).pdf);
</script>

{#if !row}
	<div class="page item work" data-work={item.id} data-testid="work-item">
		<p class="muted" data-testid="work-unread">{lib.works.error ? said(lib.works.error) : lib.works.value ? library.works.gone : library.works.loading}</p>
	</div>
{:else}
	<div class="page item work reading" data-work={item.id} data-testid="work-item">
		<div class="reader" data-testid="reader">
			<Reading ref={item.id} pdf={row.holds.pdf} identifier={row.lookup?.identifier ?? null} short={row.short} page={reading} seq={named ? (item.seq ?? 0) : 0} {locator} view={pdf} onleft={() => workspace.update(itemKey(item), { place: undefined })} />
		</div>
	</div>
{/if}

<style>
	/* Reading the paper is a full-height job, and full bleed (K4): the column fills the pane and scrolls inside itself, so the pane never scrolls and the reader never runs out of paper at the bottom of a screen. */
	.page.reading {
		display: flex;
		flex-direction: column;
		height: 100%;
		overflow: hidden;
		padding: 0;
		max-width: none;
	}
	.reader {
		flex: 1 1 auto;
		min-height: 0;
	}
</style>
