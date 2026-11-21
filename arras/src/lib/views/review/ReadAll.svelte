<script lang="ts">
	// Over the cited results: `ask an agent to read all N`, a task for each.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import type { ReviewRow, TaskRow } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { stubsOf } from './rows';

	let { rows }: { rows: (ReviewRow | TaskRow)[] } = $props();
	const stubs = $derived(stubsOf(rows));
	let busy = $state(false);

	async function all(): Promise<void> {
		busy = true;
		for (const s of stubs) {
			const done = await api.ask('read', { node: s.node }, { nodes: [s.node] }, s.docs);
			if (!done.ok) {
				busy = false;
				return message.post(said(done.error));
			}
		}
		busy = false;
		message.post(words.cited.askedAll);
	}
</script>

{#if stubs.length}<button type="button" class="btn act" disabled={busy} onclick={all} data-testid="read-all">{words.cited.readAll(stubs.length)}</button>{/if}
