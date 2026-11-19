<script lang="ts">
	// A document's compiled PDF's toolbar: on its bar **Save a copy**, which hands the file to the browser's own download named by the document (`main.pdf`), never by the build's path; greyed while there is no PDF yet. The page and the zoom stand over the paper (`CompiledItem`).
	import { store } from '$lib/manifest/client.svelte';
	import { compiledUrl } from '$lib/paths';
	import { download } from '$lib/pdf/desk.svelte';
	import { say } from '$lib/review/toasts.svelte';
	import type { Item } from '../item';
	import ItemToolbar from '../ItemToolbar.svelte';
	import { pdfFileName } from '../names';

	let { item, name }: { item: Item; name: string } = $props();

	const m = $derived(store.manifest!);
	const master = $derived(m.masters.find((x) => x.path === item.id));
	const url = $derived(master ? compiledUrl(master) : '');
	const file = $derived(pdfFileName(m.masters, item.id));
	let busy = $state(false);

	async function save(): Promise<void> {
		busy = true;
		try {
			const res = await fetch(url);
			if (!res.ok) throw new Error(`the publisher answered ${res.status} ${res.statusText}`.trim());
			download(new Uint8Array(await res.arrayBuffer()), file);
		} catch (exc) {
			say({ title: 'Could not save a copy', lines: [exc instanceof Error ? exc.message : String(exc)] });
		} finally {
			busy = false;
		}
	}
</script>

{#snippet bar()}
	<button
		type="button"
		class="save"
		disabled={!url || busy}
		title={url ? `Save a copy of this PDF as ${file}` : 'There is no compiled PDF to save yet'}
		aria-label="save a copy of {name} as {file}"
		data-testid="pdf-save"
		onclick={() => void save()}>Save a copy</button
	>
{/snippet}

<ItemToolbar {name} {bar} />

<style>
	.save {
		display: inline-flex;
		align-items: center;
		height: 22px;
		padding: 0 6px;
		font: inherit;
		color: var(--ink-soft);
		background: none;
		border: 0;
		border-radius: 4px;
		cursor: pointer;
	}
	.save:hover:not(:disabled) {
		color: var(--ink);
		background: var(--leaf);
	}
	.save:disabled {
		opacity: 0.35;
		cursor: default;
	}
</style>
