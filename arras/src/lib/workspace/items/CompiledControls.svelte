<script lang="ts">
	// A document's compiled PDF's toolbar: under *view*, `Open in browser`, the file at its own address in a new tab, for the browser's own viewer, and `Save as…`, which hands it to the browser's download named by the document (`main.pdf`), never by the build's path; both greyed while there is no PDF yet. The page and the zoom stand over the paper (`CompiledItem`).
	import { store } from '$lib/manifest/client.svelte';
	import { compiledUrl, dataUrl } from '$lib/paths';
	import { download } from '$lib/pdf/desk.svelte';
	import { say } from '$lib/review/toasts.svelte';
	import type { Item } from '../item';
	import ItemToolbar from '../ItemToolbar.svelte';
	import ToolbarItem from '../ToolbarItem.svelte';
	import { pdfFileName } from '../names';

	let { item, name }: { item: Item; name: string } = $props();

	const m = $derived(store.manifest!);
	const master = $derived(m.masters.find((x) => x.path === item.id));
	const file = $derived(pdfFileName(m.masters, item.id));
	let busy = $state(false);
	const none = $derived(master?.pdf ? undefined : 'There is no compiled PDF yet');

	async function save(): Promise<void> {
		if (!master?.pdf) return;
		busy = true;
		try {
			const res = await fetch(compiledUrl(master));
			if (!res.ok) throw new Error(`the publisher answered ${res.status} ${res.statusText}`.trim());
			download(new Uint8Array(await res.arrayBuffer()), file);
		} catch (exc) {
			say({ title: 'Could not save the PDF', lines: [exc instanceof Error ? exc.message : String(exc)] });
		} finally {
			busy = false;
		}
	}
</script>

<ItemToolbar {name}>
	{#snippet view()}
		<ToolbarItem label="Open in browser" name="open {name} in the browser's own viewer, in a new tab" href={master?.pdf ? dataUrl(master.pdf) : undefined} off={none} testid="pdf-open-browser" />
		<ToolbarItem label="Save as…" name="save {name} as {file}" about="Save a copy of this PDF as {file}" off={none ?? (busy ? 'Saving…' : undefined)} testid="pdf-save" onclick={() => void save()} />
	{/snippet}
</ItemToolbar>
