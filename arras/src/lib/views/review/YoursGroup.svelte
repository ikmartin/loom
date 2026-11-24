<script lang="ts">
	// Under Everything, the group of a kind today's Your Changes draws: its name, the count of what its section lists as waiting, folding, and beneath it the section.
	import Icon from '$lib/components/Icon.svelte';
	import YourChanges from '$lib/review/YourChanges.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';
	import { PARTS, type YoursKind } from './yours';

	let { kind, n }: { kind: YoursKind; n: number } = $props();
	const folded = $derived(rv.folded.has(kind));
</script>

<div class="rg" data-testid="review-group" data-kind={kind}>
	<button type="button" class="fold" aria-expanded={!folded} aria-label={words.kinds[kind].name} onclick={() => rv.fold(kind)}><Icon name={folded ? 'right' : 'caret'} size={16} /></button>
	<span>{words.kinds[kind].name}</span><span class="n">{n}</span>
</div>
{#if !folded}<YourChanges part={PARTS[kind]} />{/if}
