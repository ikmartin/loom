<script lang="ts">
	// A result in the Web's lists: its two marks, its name and title, and its source where it is not under its source's row; a click puts it in focus. In the list, a box chooses one of the person's results not formalized for the formalize panel.
	import type { Row } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark, hasLean } from '$lib/marks/marks';
	import { web as words } from '$lib/words/web';
	import { choosable, wb } from './state.svelte';
	import { web as webWords } from '$lib/words/web';

	let { row, source = true, indent = false, choosing = false }: { row: Row; source?: boolean; indent?: boolean; /** In the list: a box on each row, live on the person's results not formalized. */ choosing?: boolean } = $props();
	const from = $derived(!row.source ? '' : 'doc' in row.source ? words.file(row.source.doc) : row.source.short);
</script>

<div class="wrow" class:in={indent}>
	<button type="button" class="wl" class:sel={wb.at === row.result} data-testid="web-row" onclick={() => wb.follow(row)}>
		<span class="slot">{#if row.paper}<Mark kind={paperMark(row.paper)} />{/if}</span>
		<span class="slot">{#if hasLean(row.lean)}<Mark kind={leanMark(row.lean)} />{/if}</span>
		<span class="nm">{row.name}{#if row.title}<span class="tl">{' ' + row.title}</span>{/if}</span>
		{#if source && from}<span class="src">{from}</span>{/if}
	</button>
	{#if choosing}<input type="checkbox" class="pick" checked={wb.chosen.has(row.result)} disabled={!choosable(row)} aria-label={webWords.choose.box} title={choosable(row) ? webWords.choose.box : undefined} data-testid="web-choose" onchange={(e) => ((e.currentTarget as HTMLInputElement).checked ? wb.chosen.add(row.result) : wb.chosen.delete(row.result))} />{/if}
</div>
