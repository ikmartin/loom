<script lang="ts">
	// A Lean statement to attest, open (6): the whole statement as the draft has it beside the Lean that states it, as loom's check had Lean print it; each definition the Lean's statement names, its Lean beside the result it stands for or said to be the Lean's alone; the latest agent's reading, part by part, what was written beside the declaration the part reads and the reading, drawn as that agent's and said to be of an earlier Lean once loom checked it again; folded, what it uses that the person attested already and the declarations that serve only the proof; the agent's note of a difference; then "Does the Lean say what you wrote?" and what the yes covers. The Lean drawn is loom's, never an agent's.
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

	/** A part of the agent's reading: what the statement says there, the declaration of loom's record it reads, and the reading. */
	type Part = { part: string; draft: string; declaration: string; reading: string };
	/** The latest agent's reading of the Lean; `stale` once loom recorded a newer Lean for the result. */
	type Account = { by: string; at: string; observation: string; stale: boolean; parts: Part[]; difference: string | null };
	/** A row of notation a person defined that the statement uses. */
	type Notation = { part: string; from: 'preamble' | 'macros'; attested: boolean };
	/** A declaration of the Lean record, as loom's check had Lean print it; `shown` null where the printer failed. */
	type Decl = { name: string; kind: string; shown: string | null };
	/** The result a definition's marker names: its statement, and when the person attested its own Lean. */
	type Stands = { result: string | null; name: string; statement: { fragment?: string | null; body?: string } | null; attested: string | null };
	type Body = ReviewBody & { body: RowBody & { observation?: string; lean?: Decl[]; definitions?: (Decl & { stands_for: Stands | null })[]; notation?: Notation[] | null; uses_attested?: { result: string; name: string; title?: string; at: string }[]; supporting?: string[]; account?: Account | null } };

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
	const account = $derived(b?.account ?? null);
	const by = $derived(account?.by ?? '');
	const where = $derived('doc' in row.source ? words.file(row.source.doc) : row.source.short);
	/** A result of a work, which the person did not write: its words are the paper's. */
	const library = $derived('ref' in row.source);
	const named = $derived((account?.parts ?? []).filter((p) => p.part));
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
	{#if account?.parts.length}
		<div class="crop-cap gap">{library ? words.attest.partByPaper(by) : words.attest.partByPart(by)}</div>
		<p class="note agent-reading" data-testid="attest-reading">{account.stale ? words.attest.readingStale(by, words.day(account.at)) : words.attest.readingBy(by, words.day(account.at))}</p>
		<table class="att" data-testid="attest-parts">
			<thead><tr><th></th><th>{library ? words.attest.paper : words.attest.draft}</th><th>{words.attest.reads}</th><th class="ag">{words.attest.reading(by)}</th></tr></thead>
			<tbody>
				{#each account.parts as p (p.part)}
					<tr data-lean={p.declaration}>
						<td class="k">{p.part}</td>
						<td class="pp">{#if p.draft}<NodeBody body={p.draft} italic />{/if}</td>
						<td class="dn"><code>{p.declaration}</code></td>
						<td class="ag" class:stale={account.stale}><NodeBody body={p.reading} /></td>
					</tr>
				{/each}
				{#each b.notation ?? [] as n (n.part)}
					<tr>
						<td class="k">{n.part}</td>
						<td class="pp"><span class="lbl">{words.attest.fromMacros}</span></td>
						<td class="dn"></td>
						<td class="ag"></td>
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
	{#if account?.difference}
		<div class="diverge"><span class="w">{words.attest.found(by)}</span><div>{account.difference}</div></div>
	{/if}
	<p class="ask">{library ? words.attest.askPaper : words.attest.ask}</p>
	<div class="answers">
		<button type="button" class="btn" disabled={busy} onclick={yes}>{words.attest.yes}</button>
		<Restate result={row.result} docs={row.docs} label={words.attest.no} />
		<span class="note inline">{named.length ? words.attest.covers(named.map((p) => p.part), (b.notation ?? []).map((p) => p.part), row.name) : words.attest.coversAll(row.name)}{alone.length ? ` ${words.attest.coversAlone(alone)}` : ''}</span>
	</div>
{/if}
