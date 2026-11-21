<script lang="ts">
	// A work's cited results to digest, open: a row for each under it, tied by a line, each with `ask an agent to read it` and `locate…`, which opens the draft's sentence citing it beside the paper at what loom found of its name, where the person marks the passage.
	import Mark from '$lib/marks/Mark.svelte';
	import * as api from '$lib/library/api';
	import type { CitedRow } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from '../state.svelte';
	import Locate from './Locate.svelte';

	let { row }: { row: Extract<CitedRow, { stubs: unknown }> } = $props();
	const open = $derived(rv.sub[row.row] ?? null);
	const toggle = (node: string) => (rv.sub = { ...rv.sub, [row.row]: open === node ? null : node });

	async function read(node: string, docs: string[]): Promise<void> {
		const done = await api.ask('read', { node }, { nodes: [node] }, docs);
		message.post(done.ok ? words.cited.asked : done.error.message);
	}
</script>

<div class="subtree">
	{#each row.stubs as s (s.node)}
		<div class="sr" class:open={open === s.node} data-testid="review-sub">
			<div class="sr-h static">
				<span class="slot"><Mark kind={s.marked ? 'marked' : 'stub'} /></span>
				<span class="tx">{s.name}<span class="tl quiet">{s.marked ? words.cited.marked : words.check.rests(s.rests.docs)}</span></span>
				<span class="acts">
					<button type="button" class="linkish" onclick={() => read(s.node, s.rests.docs)}>{words.cited.read}</button>
					<button type="button" class="linkish" aria-expanded={open === s.node} onclick={() => toggle(s.node)}>{words.cited.locate}</button>
				</span>
			</div>
			{#if open === s.node}<div class="sr-b"><Locate {row} stub={s} /></div>{/if}
		</div>
	{/each}
</div>
