<script lang="ts">
	// A Lean statement to attest, open (6): the whole statement as the draft has it beside the Lean that states it, as loom's check had Lean print it; each definition the Lean's statement names, its Lean beside the result it stands for or said to be the Lean's alone; part by part what was written and the agent's reading; folded, what it uses that the person attested already and the declarations that serve only the proof; the agent's note of a difference; then "Does the Lean say what you wrote?" and what the yes covers. The Lean drawn is loom's, never an agent's.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { AttestRow, ReviewBody, RowBody } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Lean from '../Lean.svelte';
	import Statement from '$lib/views/Statement.svelte';
	import Restate from './Restate.svelte';

	type Part = { part: string; draft?: string; reading: string; by?: string; from?: 'statement' | 'macros' };
	/** A declaration of the Lean record, as loom's check had Lean print it; `shown` null where the printer failed. */
	type Decl = { name: string; kind: string; shown: string | null };
	/** The result a definition's marker names: its statement, and when the person attested its own Lean. */
	type Stands = { result: string | null; name: string; statement: { fragment?: string | null; body?: string } | null; attested: string | null };
	type Body = ReviewBody & { body: RowBody & { observation?: string; lean?: Decl[]; definitions?: (Decl & { stands_for: Stands | null })[]; parts?: Part[] | null; notation?: Part[] | null; uses_attested?: { result: string; name: string; title?: string; at: string }[]; supporting?: string[]; difference?: { by: string; text: string } | null } };

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

	const b = $derived(body.value?.body);
	/** The result's statement: a draft's fragment, or a library node's body. */
	const stmt = $derived(b?.statement as { fragment?: string; body?: string } | undefined);
	const by = $derived(b?.parts?.[0]?.by ?? '');
	const where = $derived('doc' in row.source ? words.file(row.source.doc) : row.source.short);
	/** A result of a work, which the person did not write: its words are the paper's. */
	const library = $derived('ref' in row.source);
	const named = $derived((b?.parts ?? []).filter((p) => p.part));
	/** The Lean's own definitions, standing for no result, which the person's word on this result covers. */
	const alone = $derived((b?.definitions ?? []).filter((d) => !d.stands_for).map((d) => d.name));

	async function yes(): Promise<void> {
		if (!b?.observation) return;
		busy = true;
		const done = await api.attest(row.result, b.observation);
		busy = false;
		message.post(done.ok ? words.attest.attested(row.name) : said(done.error));
	}
</script>

{#if b}
	<div class="beside" data-testid="attest-beside">
		<div>
			<div class="crop-cap">{library ? words.attest.asPaper(where) : words.attest.asWritten(where)}</div>
			{#if stmt?.fragment}<div class="citebox"><Statement fragment={stmt.fragment} /></div>{:else if stmt?.body}<div class="citebox"><NodeBody body={stmt.body} /></div>{/if}
		</div>
		<div>
			<div class="crop-cap">{words.attest.leanStates}</div>
			{#each b.lean ?? [] as d (d.name)}<Lean code={d.shown ?? `${d.kind} ${d.name}`} />{:else}<p class="note">{words.attest.noLean}</p>{/each}
		</div>
	</div>
	{#if b.definitions?.length}
		<div class="crop-cap gap">{library ? words.attest.definitionsPaper : words.attest.definitions}</div>
		<table class="att defs" data-testid="attest-definitions">
			<thead><tr><th>{words.attest.lean}</th><th>{library ? words.attest.standsPaper : words.attest.stands}</th></tr></thead>
			<tbody>
				{#each b.definitions as d (d.name)}
					<tr data-lean={d.name}>
						<td class="ll"><Lean code={d.shown ?? `${d.kind} ${d.name}`} /></td>
						<td class="pp">
							{#if d.stands_for}
								{#if !d.stands_for.result}<span class="lbl">{words.attest.standsNowhere(d.stands_for.name)}</span>{:else if !d.stands_for.statement?.fragment}<span class="lbl">{d.stands_for.name}</span>{/if}
								{#if d.stands_for.statement?.fragment}<Statement fragment={d.stands_for.statement.fragment} />{:else if d.stands_for.statement?.body}<NodeBody body={d.stands_for.statement.body} />{/if}
								{#if d.stands_for.result}<span class="lbl">{d.stands_for.attested ? words.attest.itsLeanAttested(words.day(d.stands_for.attested)) : words.attest.itsLeanNot}</span>{/if}
							{:else}
								<span class="only">{words.attest.leanOnly}</span>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}
	{#if b.parts?.length}
		<div class="crop-cap gap">{library ? words.attest.partByPaper(by) : words.attest.partByPart(by)}</div>
		<table class="att">
			<thead><tr><th></th><th>{library ? words.attest.paper : words.attest.draft}</th><th class="ag">{words.attest.reading(by)}</th></tr></thead>
			<tbody>
				{#each [...b.parts, ...(b.notation ?? [])] as p (p.part)}
					<tr>
						<td class="k">{p.part}</td>
						<td class="pp">
							{#if p.from === 'statement'}<span class="lbl">{words.attest.inStatement}</span>{:else if p.from === 'macros'}<span class="lbl">{words.attest.fromMacros}</span>{/if}
							{#if p.draft}<NodeBody body={p.draft} italic={!p.from} />{/if}
						</td>
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
		<span class="note inline">{named.length ? words.attest.covers(named.map((p) => p.part), (b.notation ?? []).map((p) => p.part), row.name) : words.attest.coversAll(row.name)}{alone.length ? ` ${words.attest.coversAlone(alone)}` : ''}</span>
	</div>
{/if}
