<script lang="ts">
	// The result in focus (7a): its name and title, its source and its marks with their words, its statement, one line on where it stands in Lean (verified relative to what it assumes, or what it rests on that is not read or not compared), and, folded, its proofs, Lean and record, with Check again beside its Lean where Lean is on for this quilt on this computer.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { Row, WebFocus } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark, hasLean } from '$lib/marks/marks';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { THEOREMS } from '$lib/node/taxa';
	import { frame } from '$lib/words/frame';
	import { web as words } from '$lib/words/web';
	import Statement from '$lib/views/Statement.svelte';
	import { choosable, wb } from './state.svelte';
	import { formalize } from '$lib/formalize/state.svelte';
	import { lean } from '$lib/formalize/lean.svelte';
	import { jobLines, offersCheck } from '$lib/formalize/said';
	import { lean as leanWords } from '$lib/words/lean';

	let { focus }: { focus: WebFocus } = $props();
	const more = new Read<WebFocus>();

	$effect(() => {
		const r = focus.row.result;
		const w = wb.where;
		void gen.gen;
		if (wb.more) void more.load(`${w.scope}:${w.doc}:${r}`, (s) => api.webFocus(w, r, true, s));
	});

	const row = $derived(focus.row);
	const from = $derived(!row.source ? '' : 'doc' in row.source ? words.file(row.source.doc) : row.source.short);
	const named = (r: Row) => (r.source && 'short' in r.source ? words.focus.of(r.name, r.source.short) : r.name);
	const m = $derived(more.value?.row.result === row.result ? more.value.more : null);
	const day = words.day;
	// Lean's state on this computer, asked once the fold shows a Lean
	$effect(() => {
		if (wb.more && m?.lean.length && lean.served === null) void lean.load();
	});
	const checking = $derived(lean.state?.job?.kind === 'check' ? jobLines(lean.state.job) : []);
</script>

{#snippet marked(r: Row)}{#if r.paper}<Mark kind={paperMark(r.paper)} />{/if}{#if hasLean(r.lean)}<Mark kind={leanMark(r.lean)} />{/if}{/snippet}

<section class="focus" data-testid="web-focus">
	<h2 class="fh">{row.name}{#if row.title}<span class="tl">{' ' + row.title}</span>{/if}</h2>
	<div class="fsrc">
		<span>{from}</span>
		{#if row.paper}<span class="chip"><Mark kind={paperMark(row.paper)} hidden />{frame.marks[paperMark(row.paper)]}</span>{/if}
		{#if hasLean(row.lean)}<span class="chip"><Mark kind={leanMark(row.lean)} hidden />{frame.marks[leanMark(row.lean)]}</span>{/if}
	</div>
	<div class="fbody">
		{#if !focus.statement}<p class="quiet">{words.focus.numberOnly}</p>
		{:else if 'fragment' in focus.statement}<Statement fragment={focus.statement.fragment} />
		{:else}<NodeBody body={focus.statement.body} macros={focus.statement.macros} points={focus.statement.points} italic={THEOREMS.has(row.taxon)} />{/if}
	</div>
	{#if focus.relative_to}
		<p class="vr" data-testid="web-standing">
			{#if focus.relative_to.length}{words.focus.relativeTo}
				{#each focus.relative_to as r, i (r.result)}{i ? ', ' : ' '}{@render marked(r)} <button type="button" class="linkish" onclick={() => wb.follow(r)}>{named(r)}</button>{/each}, {words.focus.assumed(focus.relative_to.length)}
			{:else}{words.focus.mathlib}{/if}
		</p>
	{:else if focus.rests_on.length}
		<p class="vr" data-testid="web-standing">
			{words.focus.restsOn}
			{#each focus.rests_on as r, i (r.result)}{i ? ', ' : ' '}{@render marked(r)} <button type="button" class="linkish" onclick={() => wb.follow(r)}>{r.name}</button> <span class="quiet">{r.source && 'short' in r.source ? r.source.short : ''}</span>{/each}.
		</p>
	{/if}
	<div class="foldrow">
		<button type="button" class="foldline" aria-expanded={wb.more} onclick={() => (wb.more = !wb.more)}><Icon name={wb.more ? 'caret' : 'right'} size={14} />{words.focus.more}</button>
		{#if choosable(row)}<button type="button" class="linkish" onclick={() => formalize.open([row.result])} data-testid="focus-formalize">{words.choose.formalize}</button>{/if}
	</div>
	{#if wb.more && m}
		<dl class="moreb">
			{#each m.proofs as p, i (i)}
				<dt>{words.focus.proof}</dt>
				<dd>{typeof p.where === 'string' ? words.focus.proofIn(p.where, p.uses.map((u) => u.name).join(', ') || words.focus.nothing) : words.focus.proofFrom(p.where.short, p.where.pages)}</dd>
			{/each}
			{#if m.lean.length}
				<dt>{words.focus.lean}</dt>
				<dd>
					<code>{m.lean.join(', ')}</code>
					{#if lean.state?.on}
						<div class="again">
							<button type="button" class="btn" disabled={lean.busy || !offersCheck(lean.state)} title={leanWords.checkAgainHover} onclick={() => void lean.check()} data-testid="focus-check-again">{leanWords.checkAgain}</button>
							{#if checking.length}<span class="quiet" aria-live="polite" data-testid="focus-check-said">{checking.join(' ')}</span>{/if}
						</div>
						{#if lean.refused}<p class="quiet" role="alert">{lean.refused}</p>{/if}
					{/if}
				</dd>
			{/if}
			{#if m.record.length}<dt>{words.focus.record}</dt><dd>{m.record.map((a) => words.focus.acts[a.act]?.(a.by, day(a.at)) ?? '').filter(Boolean).join(' · ')}</dd>{/if}
		</dl>
	{/if}
</section>
