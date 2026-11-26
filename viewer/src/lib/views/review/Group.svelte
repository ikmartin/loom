<script lang="ts">
	// One kind's group under Everything: its name and count, folding; the tasks waiting for an agent start folded. Loom's rows of a kind are given as `group`; a kind drawn from the manifest gives its kind, its count and its list as `children`.
	import type { Snippet } from 'svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';
	import Row from './Row.svelte';
	import Task from './Task.svelte';
	import ReadAll from './ReadAll.svelte';
	import type { ShownGroup, ShownKind } from './rows';

	let { group, kind = group?.kind ?? 'questions', n = group?.rows.length ?? 0, children }: { group?: ShownGroup; kind?: ShownKind; n?: number; children?: Snippet } = $props();
	const folded = $derived(rv.folded.has(kind));
</script>

<div class="rg" data-testid="review-group" data-kind={kind}>
	<button type="button" class="fold" aria-expanded={!folded} aria-label={words.kinds[kind].name} onclick={() => rv.fold(kind)}><Icon name={folded ? 'right' : 'caret'} size={16} /></button>
	<span>{words.kinds[kind].name}</span><span class="n">{n}</span>
	{#if group?.kind === 'cited'}<ReadAll rows={group.rows} />{/if}
</div>
{#if !folded}
	{#if group}
		{#each group.rows as r (r.row)}
			{#if r.kind === 'agents'}<Task row={r} />{:else}<Row row={r} />{/if}
		{/each}
	{:else}{@render children?.()}{/if}
{/if}
