<script lang="ts">
	// What `add work…` opens (1 add), and what an empty library's box holds (1c): choose files, paste an arXiv number or DOI, or drop files anywhere in loom. Either goes through the one intake, and the column's message says what came in.
	import { addFiles, addText } from '$lib/library/intake';
	import { library as words } from '$lib/words/library';
	import { menus } from './menus.svelte';

	let { inline = false }: { inline?: boolean } = $props();
	let picker = $state<HTMLInputElement | null>(null);
	let pasted = $state('');

	async function chosen(): Promise<void> {
		const files = [...(picker?.files ?? [])];
		if (picker) picker.value = '';
		menus.open = null;
		await addFiles(files);
	}

	async function paste(e: SubmitEvent): Promise<void> {
		e.preventDefault();
		const text = pasted;
		pasted = '';
		menus.open = null;
		await addText(text);
	}
</script>

<div class="add" class:inline data-testid="add-work-panel">
	<button type="button" class="btn primary" onclick={() => picker?.click()} data-testid="choose-files">{words.add.choose}</button>
	<input bind:this={picker} type="file" multiple hidden accept=".pdf,.bib,.tex,.zip,.gz,.tgz" onchange={() => void chosen()} data-testid="choose-files-input" />
	<form class="row2" onsubmit={(e) => void paste(e)}>
		<input class="search" type="text" placeholder={words.add.paste} bind:value={pasted} data-testid="paste-identifier" />
	</form>
	{#if !inline}<div class="small grey hint">{words.add.drop}</div>{/if}
</div>

<style>
	.row2 {
		display: flex;
		gap: 8px;
		margin-top: 10px;
	}
	.row2 .search {
		width: 100%;
	}
	.inline .row2 {
		justify-content: center;
		margin-top: 14px;
	}
	.inline .row2 .search {
		width: 280px;
	}
	.hint {
		margin-top: 10px;
	}
</style>
