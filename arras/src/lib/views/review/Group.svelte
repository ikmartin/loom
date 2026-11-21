<script lang="ts">
	// One kind's group under Everything: its name and count, folding; the tasks waiting for an agent start folded.
	import Icon from '$lib/components/Icon.svelte';
	import type { ReviewGroup } from '$lib/library/types';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';
	import Row from './Row.svelte';
	import Task from './Task.svelte';
	import ReadAll from './ReadAll.svelte';

	let { group }: { group: ReviewGroup } = $props();
	const folded = $derived(rv.folded.has(group.kind));
</script>

<div class="rg" data-testid="review-group" data-kind={group.kind}>
	<button type="button" class="fold" aria-expanded={!folded} aria-label={words.kinds[group.kind].name} onclick={() => rv.fold(group.kind)}><Icon name={folded ? 'right' : 'caret'} size={16} /></button>
	<span>{words.kinds[group.kind].name}</span><span class="n">{group.rows.length}</span>
	{#if group.kind === 'cited'}<ReadAll rows={group.rows} />{/if}
</div>
{#if !folded}
	{#each group.rows as r (r.row)}
		{#if r.kind === 'agents'}<Task row={r} />{:else}<Row row={r} />{/if}
	{/each}
{/if}
