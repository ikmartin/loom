<script lang="ts">
	// A Lean statement to attest, open (6): the whole statement as the draft has it; part by part what was written, the Lean that states it and the agent's reading; folded, what it uses that the person attested already and the declarations that serve only the proof; the agent's note of a difference; then "Does the Lean say what you wrote?" and what the yes covers.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { AttestRow, ReviewBody } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Lean from '../Lean.svelte';
	import Statement from '$lib/views/Statement.svelte';
	import Restate from './Restate.svelte';

	type Part = { part: string; draft?: string; lean: string; reading: string; by?: string; from?: 'statement' | 'macros' };
	type Body = ReviewBody & { observation?: string; parts?: Part[]; notation?: Part[]; uses_attested?: { result: string; name: string; title?: string; at: string }[]; supporting?: string[]; difference?: { by: string; text: string } };

	let { row }: { row: AttestRow } = $props();
	const body = new Read<Body>();
	let busy = $state(false);
	let usesOpen = $state(false);
	let auxOpen = $state(false);

	$effect(() => {
		const id = row.row;
		void gen.gen;
		void body.load(id, (s) => api.reviewRow(id, s));
	});

	const b = $derived(body.value);
	const by = $derived(b?.parts?.[0]?.by ?? '');
	const where = $derived('doc' in row.source ? words.file(row.source.doc) : row.source.short);
	/** A result of a work, which the person did not write: its words are the paper's. */
	const library = $derived('ref' in row.source);
	const named = $derived((b?.parts ?? []).filter((p) => p.part));

	async function yes(): Promise<void> {
		if (!b?.observation) return;
		busy = true;
		const done = await api.attest(row.result, b.observation);
		busy = false;
		message.post(done.ok ? words.attest.attested(row.name) : said(done.error));
	}
</script>

{#if b}
	{#if b.statement}
		<div class="crop-cap">{library ? words.attest.asPaper(where) : words.attest.asWritten(where)}</div>
		<div class="citebox"><Statement fragment={b.statement.fragment} /></div>
	{/if}
	{#if b.parts?.length}
		<div class="crop-cap gap">{library ? words.attest.partByPaper(by) : words.attest.partByPart(by)}</div>
		<table class="att">
			<thead><tr><th></th><th>{library ? words.attest.paper : words.attest.draft}</th><th>{words.attest.lean}</th><th class="ag">{words.attest.reading(by)}</th></tr></thead>
			<tbody>
				{#each [...b.parts, ...(b.notation ?? [])] as p (p.part + p.lean)}
					<tr>
						<td class="k">{p.part}</td>
						<td class="pp">
							{#if p.from === 'statement'}<span class="lbl">{words.attest.inStatement}</span>{:else if p.from === 'macros'}<span class="lbl">{words.attest.fromMacros}</span>{/if}
							{#if p.draft}<NodeBody body={p.draft} italic={!p.from} />{/if}
						</td>
						<td class="ll"><Lean code={p.lean} /></td>
						<td class="ag"><NodeBody body={p.reading} /></td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
	{#if b.uses_attested?.length}
		{@const first = b.uses_attested[0]}
		<button type="button" class="foldline" aria-expanded={usesOpen} onclick={() => (usesOpen = !usesOpen)}><Icon name={usesOpen ? 'caret' : 'right'} size={14} />{words.attest.usesAttested(words.results(b.uses_attested.map((u) => u.name)), words.day(first.at))}</button>
		{#if usesOpen}<div class="fold-b">{#each b.uses_attested as u (u.result)}<span><Mark kind="formalized" /> {u.title ? `${u.name}, ${u.title}` : u.name}</span>{/each}</div>{/if}
	{/if}
	{#if b.supporting?.length}
		<button type="button" class="foldline" aria-expanded={auxOpen} onclick={() => (auxOpen = !auxOpen)}><Icon name={auxOpen ? 'caret' : 'right'} size={14} />{words.attest.supporting(b.supporting.length)}</button>
		{#if auxOpen}<div class="fold-b"><Lean code={b.supporting.join('\n')} /></div>{/if}
	{/if}
	{#if b.difference}
		<div class="diverge"><span class="w">{words.attest.found(b.difference.by)}</span><div>{b.difference.text}</div></div>
	{/if}
	<p class="ask">{library ? words.attest.askPaper : words.attest.ask}</p>
	<div class="answers">
		<button type="button" class="btn" disabled={busy} onclick={yes}>{words.attest.yes}</button>
		<Restate result={row.result} docs={row.docs} label={words.attest.no} />
		<span class="note inline">{named.length ? words.attest.covers(named.map((p) => p.part), (b.notation ?? []).map((p) => p.part), row.name) : words.attest.coversAll(row.name)}</span>
	</div>
{/if}
