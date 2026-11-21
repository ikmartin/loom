<script lang="ts">
	// A citation that names no result, open: the draft's sentence with the citation marked, what to add with an example in the person's own key, `ask an agent which result` (its answer comes back as a proposed edit) and `only a mention`, which is remembered.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { CitedRow, ReviewBody } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Statement from '$lib/views/Statement.svelte';
	import SeeItLink from '../SeeItLink.svelte';

	let { row }: { row: Extract<CitedRow, { citation: string }> } = $props();
	const body = new Read<ReviewBody & { cite?: { where: string; fragment: string; nth: number } }>();
	let busy = $state(false);

	$effect(() => {
		const id = row.row;
		void gen.gen;
		void body.load(id, (s) => api.reviewRow(id, s));
	});

	async function which(): Promise<void> {
		busy = true;
		const done = await api.ask('which-result', { citation: row.citation }, { cites: row.ref }, row.docs);
		busy = false;
		message.post(done.ok ? words.citation.askedWhich : done.error.message);
	}
	async function mention(): Promise<void> {
		busy = true;
		const done = await api.mention(row.citation);
		busy = false;
		message.post(done.ok ? words.citation.mentioned : done.error.message);
	}
</script>

{#if body.value?.cite}
	<div class="crop-cap">{body.value.cite.where}</div>
	<div class="citebox"><Statement fragment={body.value.cite.fragment} hot={body.value.cite.nth} /></div>
{/if}
<p class="ask">{words.citation.explain(row.short, row.doc)} <code>{words.citation.example(row.citekey)}</code>.</p>
<div class="answers">
	<button type="button" class="btn" disabled={busy} onclick={which}>{words.citation.which}</button>
	<button type="button" class="btn" disabled={busy} onclick={mention}>{words.citation.mention}</button>
	<SeeItLink doc={row.doc} key={row.key} name={row.where} />
</div>
<p class="note after">{words.citation.comesBack(row.doc)}</p>
