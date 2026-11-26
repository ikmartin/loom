<script lang="ts">
	// An agent's correction to a result the person compared, open: the two texts as one, what it takes out struck and what it puts in marked, each run drawn as a result's text is; the text compared stands until the person takes it, or declines it.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { CheckRow, CorrectionBody, ReviewBody, RowBody } from '$lib/library/types';
	import { store } from '$lib/manifest/client.svelte';
	import { typeset } from '$lib/math/mathjax';
	import { toHtml } from '$lib/node/latexlite';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';

	let { row }: { row: Extract<CheckRow, { correction: string }> } = $props();
	const body = new Read<ReviewBody & { body: RowBody & Partial<CorrectionBody> }>();
	let busy = $state(false);
	let box = $state<HTMLElement | null>(null);

	$effect(() => {
		const id = row.row;
		void gen.gen;
		void body.load(id, (s) => api.reviewRow(id, s));
	});

	const SIDE = { '-': 'old', '+': 'new' } as const;
	/** Each run drawn apart, so a run taken out or put in is marked whole. */
	const runs = $derived((body.value?.body.runs ?? []).map(([op, tex]) => ({ op, html: toHtml(tex, {}).html })));
	$effect(() => {
		void runs;
		if (box) void typeset(box, store.manifest?.macros?.default ?? []);
	});

	async function act(take: boolean): Promise<void> {
		busy = true;
		const done = take ? await api.takeCorrection(row.correction) : await api.declineCorrection(row.correction);
		busy = false;
		message.post(done.ok ? (take ? words.check.taken(row.name) : words.check.declined) : said(done.error));
	}
</script>

{#if body.value?.body.runs}
	<div class="stmt changes-markup fragment" bind:this={box} data-testid="review-correction">
		{#each runs as r, i (i)}{#if r.op === '='}{@html r.html}{:else}<span class="change" data-change="c" data-side={SIDE[r.op]}>{@html r.html}</span>{/if}{' '}{/each}
	</div>
	{#if body.value.body.compared_at}<p class="note">{words.check.stands(words.day(body.value.body.compared_at))}</p>{/if}
	<div class="answers">
		<button type="button" class="btn" disabled={busy} onclick={() => act(true)}>{words.check.take}</button>
		<button type="button" class="btn" disabled={busy} onclick={() => act(false)}>{words.check.decline}</button>
	</div>
{/if}
