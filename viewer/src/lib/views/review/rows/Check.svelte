<script lang="ts">
	// A work's digested results to check, open: a row for each result under it, tied to it by a line, the first not yet compared open. An open result shows how loom has it, its text, the question and the person's answer, beside the paper cropped at its place.
	import Mark from '$lib/marks/Mark.svelte';
	import type { CheckRow } from '$lib/library/types';
	import { review as words } from '$lib/words/review';
	import { rv } from '../state.svelte';
	import CheckNode from './CheckNode.svelte';

	let { row }: { row: Extract<CheckRow, { nodes: unknown }> } = $props();
	// the result the person opened while it still waits, none where they closed it, else the first
	const open = $derived.by(() => {
		const chosen = rv.sub[row.row];
		if (chosen === null) return null;
		return chosen && row.nodes.some((n) => n.node === chosen) ? chosen : (row.nodes[0]?.node ?? null);
	});
	const toggle = (node: string) => (rv.sub = { ...rv.sub, [row.row]: open === node ? null : node });
</script>

<div class="subtree">
	{#each row.nodes as n (n.node)}
		<div class="sr" class:open={open === n.node} data-testid="review-sub">
			<button type="button" class="sr-h" aria-expanded={open === n.node} onclick={() => toggle(n.node)}>
				<span class="slot"><Mark kind="unchecked" /></span>
				<span class="tx">{n.number ? words.check.numbered(n.number, n.name) : n.name}{#if n.title}<span class="tl">{' · ' + n.title}</span>{/if}</span>
				<span class="meta">{words.check.rests(n.rests.docs, n.rests.through)}</span>
			</button>
			{#if open === n.node}<div class="sr-b"><CheckNode node={n.node} pdf={row.pdf} /></div>{/if}
		</div>
	{/each}
</div>
