<script lang="ts">
	// One row waiting for the person: its two marks, its words, a quiet line at the right and a chevron; it opens in place to its body. A paper to fetch does not open: it offers the work's page, and a file dropped anywhere in loom (or on this row) is taken for it.
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import type { ReviewRow } from '$lib/library/types';
	import { review as words } from '$lib/words/review';
	import { line, marks, opens, question, quiet } from './rows';
	import { rv } from './state.svelte';
	import Question from './rows/Question.svelte';
	import Change from './rows/Change.svelte';
	import Check from './rows/Check.svelte';
	import Correction from './rows/Correction.svelte';
	import Cited from './rows/Cited.svelte';
	import Citation from './rows/Citation.svelte';
	import Attest from './rows/Attest.svelte';
	import AttestedChanged from './rows/AttestedChanged.svelte';

	let { row }: { row: ReviewRow } = $props();
	const open = $derived(rv.open.has(row.row));
	const [paper, lean] = $derived(marks(row));
	const asked = $derived(row.kind === 'questions' ? question(row) : null);
	const meta = $derived(quiet(row));
	const openable = $derived(opens(row));
</script>

{#snippet head()}
	<span class="slot">{#if paper}<Mark kind={paper} />{/if}</span>
	<span class="slot">{#if lean}<Mark kind={lean} />{/if}</span>
	<span class="tx">{#if asked}<span class="who">{asked.by}</span>{asked.rest}{:else}{line(row)}{/if}</span>
	{#if meta}<span class="meta" class:problem={row.kind === 'edits' && row.broke}>{meta}</span>{/if}
{/snippet}

<div class="rr" class:open data-testid="review-row" data-kind={row.kind}>
	{#if openable}
		<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(row.row)}>
			{@render head()}<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
		</button>
	{:else}
		<div class="rr-h">
			{@render head()}
			{#if row.kind === 'fetch'}<a class="linkish meta" href={row.link} target="_blank" rel="noopener noreferrer" title={words.fetch.openTitle(row.link)}>{words.fetch.open}</a>{/if}
			<span class="chev"></span>
		</div>
	{/if}
	{#if open}
		<div class="rr-b">
			{#if row.kind === 'questions'}<Question {row} />{:else if row.kind === 'edits' || row.kind === 'accepted-changed'}<Change {row} />{:else if row.kind === 'check' && row.correction !== undefined}<Correction {row} />{:else if row.kind === 'check'}<Check {row} />{:else if row.kind === 'cited' && row.citation !== undefined}<Citation {row} />{:else if row.kind === 'cited'}<Cited {row} />{:else if row.kind === 'attest'}<Attest {row} />{:else if row.kind === 'attested-changed'}<AttestedChanged {row} />{/if}
		</div>
	{/if}
</div>
