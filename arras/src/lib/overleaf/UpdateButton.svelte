<script lang="ts">
	// Update from Overleaf on a mirrored document's toolbar, drawn only for a document in the folder that mirrors Overleaf: the word Overleaf with a dot when Overleaf has changes, its hover saying the document mirrors Overleaf and how the mirror stands; a press updates, and the answer hangs under the toolbar (`setStrip`), since a toolbar's row holds no sentence.
	import Icon from '$lib/components/Icon.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { getPane } from '$lib/workspace/state.svelte';
	import { setStrip } from '$lib/workspace/strip.svelte';
	import { overleaf as words } from '$lib/words/overleaf';
	import { can } from '$lib/write';
	import { mirror, updateNow } from './act.svelte';
	import { mirrors, paired, standing } from './said';

	let { doc }: { doc: string } = $props();
	const pane = getPane();
	const o = $derived(paired(store.manifest?.overleaf));
	const shown = $derived(!!o && mirrors(o, doc));
	const hover = $derived(o ? `${words.update.hover(doc)} ${o.waiting ? words.update.waiting : standing(o)}` : '');
	let served = $state(false);
	$effect(() => {
		void can('overleaf-update').then((ok) => (served = ok));
	});

	async function press(): Promise<void> {
		await updateNow();
		setStrip(pane.index, { text: mirror.said, testid: 'overleaf-strip', refused: mirror.refused });
	}
</script>

{#if shown && served}
	<button type="button" class="up" disabled={mirror.busy} title={hover} aria-label={words.update.label} data-testid="toolbar-overleaf-update" onclick={() => void press()}
		><Icon name="update" size={14} /><span>{mirror.busy ? words.update.busy : words.update.short}</span>{#if o?.waiting}<span class="dot" data-testid="toolbar-overleaf-waiting"></span>{/if}</button
	>
{/if}

<style>
	/* drawn as the toolbar's other word buttons are (New note, Annotate) */
	.up {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		height: 24px;
		margin-right: 6px;
		padding: 0 7px;
		font: inherit;
		color: var(--ink-soft);
		background: none;
		border: 1px solid transparent;
		border-radius: 6px;
		cursor: pointer;
	}
	.up:hover:not(:disabled) {
		color: var(--ink);
		background: var(--leaf);
	}
	.dot {
		width: 6px;
		height: 6px;
		margin-left: 2px;
		border-radius: 50%;
		background: var(--change);
	}
</style>
