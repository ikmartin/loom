<script lang="ts">
	// A cited work: its paper, read full bleed in its pane (`Reading`), at the place a link names, else where the reader last was. With no copy to read, `Reading` says so.
	import { store } from '$lib/manifest/client.svelte';
	import Reading from '$lib/pdf/Reading.svelte';
	import { resultPlace, type WorkLink } from '$lib/worklink';
	import { itemKey, type Item } from '../item';
	import { workState } from '../state.svelte';
	import { workspace } from '../store.svelte';

	let { item }: { item: Item } = $props();

	const m = $derived(store.manifest!);
	const citekey = $derived(item.id);
	const ref = $derived(m.references[citekey]);
	/** Whether a link names a place on this work's pages; an empty one, as a `cited:` link with no keys gives, names none. */
	const named = $derived(Object.keys(item.place ?? {}).length > 0);
	/** The page a link sends the paper to: whatever the item's place names, the page of the result it names, else the first. With no place named it opens where the reader last was (`Reading`). */
	const reading = $derived(item.place?.page || (item.place?.result ? resultPlace(m, item.place.result)?.page : undefined) || 1);
	// The place the item points at, in the one locator syntax `cited:` links share (plan 0.13 item 6).
	const locator = $derived<WorkLink | null>(ref?.work ? { id: ref.work, ...(item.place ?? {}) } : null);
	/** The reader's view of the paper, shared with the controls, which the focused pane draws for its item. */
	const pdf = $derived(workState(item).pdf);
</script>

{#if !ref}
	<div class="page item"><h1>Unknown reference</h1></div>
{:else}
	<div class="page item work reading">
		<div class="reader" data-testid="reader">
			<Reading {citekey} {ref} page={reading} seq={named ? (item.seq ?? 0) : 0} {locator} view={pdf} onleft={() => workspace.update(itemKey(item), { place: undefined })} />
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
