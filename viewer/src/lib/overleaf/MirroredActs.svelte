<script lang="ts">
	// In place of Keep on a change to a document that mirrors Overleaf, which only an update writes: Copy new text, which puts the change's new words on the clipboard to paste in Overleaf, and Done in Overleaf, which updates and then keeps the change once Overleaf's text has it (`doneInOverleaf`); what either did is said beneath, kept by the change's id (`told`) so a card drawn again still says it. Drawn in Review's rows, a document's list of changes and a change's popup.
	import Icon from '$lib/components/Icon.svelte';
	import { copyText } from '$lib/clipboard';
	import type { PendingChange } from '$lib/manifest/types';
	import { overleaf as words } from '$lib/words/overleaf';
	import { can } from '$lib/write';
	import { doneInOverleaf, mirror, told } from './act.svelte';

	let { c, size = 12 }: { c: PendingChange; size?: number } = $props();
	const said = $derived(told[c.id]);
	let served = $state(false);
	$effect(() => {
		void can('overleaf-update').then((ok) => (served = ok));
	});

	async function copy(e: Event): Promise<void> {
		e.stopPropagation();
		const ok = await copyText(c.new);
		told[c.id] = { text: ok ? words.change.copied : words.change.notCopied, refused: !ok };
	}
	async function done(e: Event): Promise<void> {
		e.stopPropagation();
		delete told[c.id];
		const got = await doneInOverleaf(c.id);
		told[c.id] = { text: got.said, refused: !got.kept };
	}
</script>

<button type="button" class="btn small" disabled={!c.new} title={words.change.copyHover} data-testid="change-copy-new" onclick={(e) => void copy(e)}><Icon name="copy" {size} />{words.change.copy}</button>
<button type="button" class="btn small primary" disabled={!served || mirror.busy} title={words.change.doneHover} data-testid="change-done-in-overleaf" onclick={(e) => void done(e)}><Icon name="update" {size} />{mirror.busy ? words.change.doing : words.change.done}</button>
{#if said}<span class="said" class:refused={said.refused} role={said.refused ? 'alert' : 'status'} data-testid="change-overleaf-said">{said.text}</span>{/if}

<style>
	/* a line of its own after every act on the row, Discard among them */
	.said {
		order: 1;
		flex-basis: 100%;
		font-size: 12px;
		line-height: 1.4;
		color: var(--ink-soft);
	}
	.said.refused {
		color: var(--state-conflicted);
	}
</style>
