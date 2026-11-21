<script lang="ts">
	// A result in the Web's lists: its two marks, its name and title, and its source where it is not under its source's row; a click puts it in focus.
	import type { Row } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import { web as words } from '$lib/words/web';
	import { wb } from './state.svelte';

	let { row, source = true, indent = false }: { row: Row; source?: boolean; indent?: boolean } = $props();
	const from = $derived(!row.source ? '' : 'doc' in row.source ? words.file(row.source.doc) : row.source.short);
</script>

<button type="button" class="wl" class:in={indent} class:sel={wb.at === row.result} data-testid="web-row" onclick={() => wb.follow(row)}>
	<span class="slot">{#if row.paper}<Mark kind={paperMark(row.paper)} />{/if}</span>
	<span class="slot">{#if row.lean}<Mark kind={leanMark(row.lean)} />{/if}</span>
	<span class="nm">{row.name}{#if row.title}<span class="tl">{' ' + row.title}</span>{/if}</span>
	{#if source && from}<span class="src">{from}</span>{/if}
</button>
