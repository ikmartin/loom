<script lang="ts">
	// The formalize panel (11a, 11b; from the Web, 11c, 11e), over the view it was opened from: the results asked for in full, the sentence of what an agent will do, what stops the request and what keeps the result from reading formalized, each under its own head and drawn only when it holds something, what is to be stated, proved (or assumed for now) and assumed, what is formalized already, folded, each item's statement a click away; and the button, which asks an agent, one task a result. The plan is `formal-plan`'s, asked again as the person chooses to prove or assume.
	import * as api from '$lib/library/api';
	import type { FormalPlan, NodeAnswer, PlanRow as Row } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { THEOREMS } from '$lib/node/taxa';
	import { message } from '$lib/shell/message.svelte';
	import Statement from '$lib/views/Statement.svelte';
	import { docs } from '$lib/words/docs';
	import { review } from '$lib/words/review';
	import { formalize } from './state.svelte';

	let { left }: { left: number } = $props();
	const words = docs.formalize;
	let plan = $state<FormalPlan | null>(null);
	let busy = $state(false);
	let shownDone = $state(false);
	/** Items whose statement is shown, by result; a library node's read when first shown. */
	let open = $state<Record<string, NodeAnswer | true | null>>({});

	$effect(() => {
		const t = formalize.targets;
		const a = formalize.assume;
		if (!t) return;
		void api.formalPlan(t, a).then((r) => {
			if (r.ok && formalize.targets === t) plan = r.value;
		});
	});

	const one = $derived((plan?.targets.length ?? 0) === 1);
	const name = $derived(plan ? (one ? plan.targets[0].name : words.these(plan.targets.length)) : '');
	const lead = $derived.by(() => {
		if (!plan) return '';
		const proving = plan.prove.filter((r) => !r.assume).length;
		const assuming = plan.prove.filter((r) => r.assume).length;
		const parts = [plan.state.length ? words.state(plan.state.length) : '', proving ? words.prove(proving, one) : '', assuming ? words.assumeOwn(assuming, one) : '', plan.assume.length ? words.assumeLibrary(plan.assume.length) : ''].filter(Boolean);
		return words.lead(one, parts);
	});
	/** Rows named a work at a time: "Lemmas 5.7 and 5.9 of Arden 2024 and Theorem 5.1 of Arden 2025". */
	const byWork = (rows: Row[]) => {
		const works = [...new Set(rows.map((r) => (r.source && 'short' in r.source ? r.source.short : '')))];
		return review.listed(works.map((w) => { const names = rows.filter((r) => (r.source && 'short' in r.source ? r.source.short : '') === w).map((r) => r.name); return w ? words.of(review.results(names), w) : review.results(names); }));
	};
	const doc = $derived(plan?.targets[0]?.doc ?? '');

	async function show(r: Row): Promise<void> {
		if (open[r.result] !== undefined) {
			const { [r.result]: _, ...rest } = open;
			open = rest;
			return;
		}
		if (r.fragment) open = { ...open, [r.result]: true };
		else {
			open = { ...open, [r.result]: null };
			const a = await api.node({ node: r.result, brief: true });
			open = { ...open, [r.result]: a.ok ? a.value : null };
		}
	}
	function choose(r: Row, assume: boolean): void {
		formalize.assume = assume ? [...formalize.assume, r.result] : formalize.assume.filter((x) => x !== r.result);
	}
	async function ask(): Promise<void> {
		if (!plan || !formalize.targets) return;
		busy = true;
		const done = await api.formalAsk(formalize.targets, formalize.assume);
		busy = false;
		if (!done.ok) return message.post(done.error.message);
		message.post(words.asked(name, one));
		formalize.close();
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && formalize.close()} />

{#snippet item(r: Row, extra?: import('svelte').Snippet)}
	{@const o = open[r.result]}
	<div class="fzi" data-testid="formalize-item">
		<button type="button" class="fold" aria-expanded={o !== undefined} aria-label={r.name} onclick={() => show(r)}><Icon name={o !== undefined ? 'caret' : 'right'} size={14} /></button>
		<span class="slot">{#if r.paper}<Mark kind={paperMark(r.paper)} />{/if}</span>
		<span class="slot">{#if r.lean}<Mark kind={leanMark(r.lean)} />{/if}</span>
		<span class="nm">{r.name}{#if r.title}<span class="tl">{' ' + r.title}</span>{/if}{#if r.source && 'short' in r.source}<span class="src">{' · ' + r.source.short}</span>{/if}</span>
		{#if extra}{@render extra()}{/if}
	</div>
	{#if o !== undefined}
		<div class="fzst">
			{#if o === true && r.fragment}<Statement fragment={r.fragment} />
			{:else if o && o !== true && o.body}<NodeBody body={o.body} macros={o.macros?.body ?? null} points={o.points ?? {}} italic={THEOREMS.has(r.taxon)} />
			{:else if o}<p class="quiet">{words.numberOnly}</p>{/if}
		</div>
	{/if}
{/snippet}

{#if formalize.targets}
	<section class="fz" style:left="{left + 24}px" data-testid="formalize-panel" aria-label={name ? words.title(name) : words.close}>
		<header>
			<b>{name ? words.title(name) : ''}</b>
			<span class="quiet">{doc.split('/').pop()}</span>
			<button type="button" class="ib" title={words.close} aria-label={words.close} onclick={() => formalize.close()}><Icon name="close" size={18} /></button>
		</header>
		{#if plan}
			<div class="fzb">
				{#each plan.targets as t (t.key)}<div class="citebox"><Statement fragment={t.statement.fragment} /></div>{/each}
				<p class="lead" data-testid="formalize-lead">{lead}</p>
				{#if plan.stops.length}
					<h4>{words.stops}<span class="n">{plan.stops.length}</span></h4>
					{#each plan.stops as r (r.result)}<div class="need block">{words.noLabel(r.name, doc)}<span class="w">{words.stopsLine}</span></div>{/each}
				{/if}
				{#if plan.before.length}
					<h4>{words.before}<span class="n">{plan.before.length}</span></h4>
					{#each plan.before as b (b.why)}
						{@const many = b.results.length > 1}
						<div class="need">
							{#if b.why === 'not-read'}{words.notRead(byWork(b.results), many)}<span class="w">{words.notReadWhere(many)}</span>
							{:else if b.why === 'not-checked'}{words.notChecked(byWork(b.results), many)}<span class="w">{words.notCheckedWhere(many)}</span>
							{:else if b.why === 'attest'}{words.attest(review.listed(b.results.map((r) => r.name)), many)}<span class="w">{words.attestWhere}</span>
							{:else}{words.attestedChanged(review.listed(b.results.map((r) => r.name)), many)}<span class="w">{words.attestedChangedWhere}</span>{/if}
						</div>
					{/each}
					<p class="note">{words.beforeNote(one ? plan.targets[0].name : null)}</p>
				{/if}
				{#if plan.state.length}<h4>{words.toState}<span class="n">{plan.state.length}</span></h4>{#each plan.state as r (r.result)}{@render item(r)}{/each}{/if}
				{#if plan.prove.length}
					<h4>{words.toProve}<span class="n">{plan.prove.length}</span></h4>
					{#each plan.prove as r (r.result)}
						{#snippet seg()}<span class="seg"><button type="button" class:on={!r.assume} onclick={() => choose(r, false)}>{words.proveIt}</button><button type="button" class:on={r.assume} onclick={() => choose(r, true)}>{words.assumeForNow}</button></span>{/snippet}
						{@render item(r, seg)}
					{/each}
				{/if}
				{#if plan.assume.length}
					<h4>{words.toAssume}<span class="n">{plan.assume.length}</span></h4>
					{#each plan.assume as r (r.result)}
						{#snippet why()}<span class="why">{r.why === 'not-read' ? words.notReadYet : r.why === 'not-checked' ? words.notCheckedYet : ''}</span>{/snippet}
						{@render item(r, why)}
					{/each}
				{/if}
				{#if plan.formalized.length}
					<h4><button type="button" class="foldhead" aria-expanded={shownDone} onclick={() => (shownDone = !shownDone)}><Icon name={shownDone ? 'caret' : 'right'} size={14} />{words.formalized}</button><span class="n">{plan.formalized.length}</span></h4>
					{#if shownDone}{#each plan.formalized as r (r.result)}{@render item(r)}{/each}{/if}
				{/if}
				<div class="fzbtn">
					<button type="button" class="btn primary" disabled={busy || plan.stops.length > 0} onclick={ask} data-testid="formalize-ask">{plan.stops.length ? words.needsLabel(plan.stops[0].name) : words.ask(name)}</button>
					<span class="note">{words.task(one)}</span>
				</div>
			</div>
		{/if}
	</section>
{/if}

<style>
	.fz {
		position: fixed;
		top: 44px;
		right: 24px;
		bottom: 16px;
		z-index: 65;
		display: flex;
		flex-direction: column;
		background: var(--paper);
		border: 1px solid var(--rule);
		border-radius: 12px;
		box-shadow: var(--float-shadow);
		font-size: 13px;
		color: var(--ink);
	}
	header {
		flex: none;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 12px 10px 16px;
		border-bottom: 1px solid var(--rule);
	}
	header b {
		font-weight: 500;
		font-size: 14px;
	}
	.ib {
		margin-left: auto;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-soft);
		cursor: pointer;
	}
	.ib:hover {
		background: var(--ann-neutral-wash);
	}
	.fzb {
		flex: 1;
		min-height: 0;
		overflow: auto;
		padding: 14px 28px 24px;
	}
	.citebox {
		margin-bottom: 10px;
		padding-left: 12px;
		border-left: 2px solid var(--rule-strong);
		font-family: var(--font-text, serif);
		font-size: 15px;
	}
	.lead {
		margin: 12px 0 18px;
		font-size: 14.5px;
	}
	h4 {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 18px 0 8px;
		font-size: 13px;
		font-weight: 500;
	}
	h4 .n {
		font-weight: 400;
		color: var(--ink-faint);
	}
	.need {
		display: flex;
		flex-direction: column;
		gap: 2px;
		margin-bottom: 8px;
		padding: 9px 14px;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-left: 3px solid var(--mark-wait, #b5772e);
		border-radius: 6px;
	}
	.need.block {
		border-left-color: var(--state-incomplete);
	}
	.need .w,
	.note,
	.quiet,
	.why,
	.src {
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.note {
		margin: 4px 0 0;
	}
	.fzi {
		display: flex;
		align-items: center;
		min-height: 30px;
		border-bottom: 1px solid var(--rule);
	}
	.fold,
	.foldhead {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 0;
		font: inherit;
		color: var(--ink-soft);
		background: none;
		border: 0;
		cursor: pointer;
	}
	.fold {
		width: 28px;
		height: 28px;
		justify-content: center;
	}
	.foldhead {
		color: var(--ink);
		font-weight: 500;
	}
	.slot {
		flex: none;
		width: 18px;
		display: inline-flex;
		justify-content: center;
	}
	.nm {
		flex: 1;
		margin-left: 8px;
	}
	.tl {
		color: var(--ink-faint);
	}
	.why {
		margin-right: 4px;
	}
	.fzst {
		padding: 8px 12px 10px 54px;
		font-family: var(--font-text, serif);
		font-size: 15px;
	}
	.seg {
		display: inline-flex;
		border: 1px solid var(--rule);
		border-radius: 7px;
		overflow: hidden;
		background: var(--sheet);
	}
	.seg button {
		font: inherit;
		font-size: 11.5px;
		border: 0;
		background: none;
		padding: 2px 9px;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.seg button + button {
		border-left: 1px solid var(--rule);
	}
	.seg button.on {
		background: var(--leaf);
		color: var(--ink);
		font-weight: 500;
	}
	.fzbtn {
		display: flex;
		align-items: center;
		gap: 14px;
		margin-top: 22px;
	}
	.btn {
		font: inherit;
		padding: 6px 14px;
		border-radius: 7px;
		border: 1px solid var(--ink);
		background: var(--ink);
		color: var(--sheet);
		cursor: pointer;
	}
	.btn:disabled {
		opacity: 0.45;
		cursor: default;
	}
</style>
