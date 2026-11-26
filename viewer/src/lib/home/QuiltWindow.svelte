<script lang="ts">
	// The home page's window for a new quilt: from a drop (a paper, its folder or archive, or a PDF), or from New quilt with no paper. A drop's files are sent as the window opens (`quilt-receive`); the form asks only the name, with where it goes; the one question asks which file is the paper; the steps show the create's progress, and give way to its outcome, which offers Open it. Closing the window while the steps run leaves the create to finish, its quilt then on the list (`docs/specs/write-api.md` §7).
	import { onMount, untrack } from 'svelte';
	import { call, receive, type Answer, type Job } from './api';
	import { homePage, shortPath } from './listing.svelte';
	import { outcomeOf, openingOf, saidOf, stepAt, stepsOf, type Said } from './flow';
	import type { Drop } from './drop';
	import CopyDetails from './CopyDetails.svelte';
	import { importSaidOf, untypesetOf } from './said';
	import { home as words } from '$lib/words/home';

	let { drop, onclose, onsteps }: { drop: Drop | null; onclose: () => void; onsteps?: (running: boolean) => void } = $props();

	const kind = $derived(!drop ? 'empty' : drop.kind);
	// a window is drawn afresh for each drop, so the name it is given is the drop's as it opened
	let name = $state(untrack(() => drop?.name ?? ''));
	/** Where the quilt goes, as the folder dialog chose it; '' for `~/Quilts`. */
	let place = $state('');
	let at = $state<'form' | 'question' | 'steps' | 'done' | 'said'>('form');
	let said = $state<Said | null>(null);
	let choices = $state<string[]>([]);
	let chosen = $state('');
	let jobKey = $state('');
	let busy = $state(false);
	let field = $state<HTMLInputElement>();

	/** The drop's files as sent: the drop's key, or the refusal. */
	let received: Promise<Answer<string>> | null = null;
	let sent = $state(false);

	onMount(() => {
		if (drop) {
			received = send(drop);
			void received.then(() => (sent = true));
		}
		field?.focus();
		field?.select();
	});

	/** Send every dropped file into one drop, one after another; the first refusal ends it. */
	async function send(d: Drop): Promise<Answer<string>> {
		let key = '';
		for (const f of d.files) {
			const r = await receive(f.file, f.path, key || undefined);
			if (!r.ok) return r;
			key = r.value.drop;
		}
		return { ok: true, value: key };
	}

	const listing = $derived(homePage.listing);
	const where = $derived(place || (listing?.home_folder ? `${listing.home_folder}/Quilts` : '~/Quilts'));
	const job = $derived(jobKey ? listing?.jobs.find((j) => j.job === jobKey) : undefined);
	const row = $derived(job?.quilt ? listing?.quilts.find((q) => q.quilt === job.quilt) : undefined);
	const outcome = $derived(jobKey ? outcomeOf(job, row) : 'running');
	const steps = $derived(stepsOf(kind));
	const stepNow = $derived(job ? (job.state === 'done' ? steps.length - 1 : stepAt(kind, job.step)) : 0);

	/** Whether a create of this name in this place is running, which `exists` then means. */
	function making(): boolean {
		return !!listing?.jobs.some((j) => j.kind === 'create' && j.state === 'running' && j.folder === `${where}/${name.trim()}`);
	}

	function refuse(code: string, message = ''): void {
		said = saidOf(code, making(), message);
		at = 'under' in said ? 'form' : 'said';
	}

	async function create(): Promise<void> {
		if (busy || !name.trim()) return;
		busy = true;
		said = null;
		let key = '';
		if (received) {
			const got = await received;
			if (!got.ok) {
				busy = false;
				return refuse(got.code, got.message);
			}
			key = got.value;
		}
		const r = await call<{ job?: string; question?: { choices: string[] } }>('quilt-create', {
			name: name.trim(),
			...(place ? { place } : {}),
			...(key ? { drop: key } : {}),
			...(chosen ? { main: chosen } : {})
		});
		busy = false;
		if (!r.ok) return refuse(r.code, r.message);
		if (r.value.question) {
			choices = r.value.question.choices;
			at = 'question';
			return;
		}
		jobKey = r.value.job ?? '';
		at = 'steps';
		await homePage.refresh();
	}

	$effect(() => onsteps?.(at === 'steps'));

	// a job that ended: its outcome, or its failure said where it belongs
	$effect(() => {
		if (at !== 'steps') return;
		if (outcome === 'served' || outcome === 'unserved') at = 'done';
		else if (outcome === 'failed' && job) refuse(job.why ?? 'failed', job.said ?? '');
	});

	async function choosePlace(): Promise<void> {
		const r = await call<{ folder?: string }>('quilt-choose', { purpose: 'place' });
		if (r.ok && r.value.folder) place = r.value.folder;
	}

	async function repairTex(): Promise<void> {
		await call('quilt-repair');
		await homePage.refresh();
	}

	const title = $derived(kind === 'pdf' ? words.window.pdf : kind === 'empty' ? words.window.empty : words.window.paper);
	const shownName = $derived(drop?.shown.name ?? '');
	const opening = $derived(job && row?.url ? openingOf(row.url, job as Job, kind === 'pdf') : '');
	const madeName = $derived(job?.name ?? name);

	function onkey(e: KeyboardEvent): void {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={onkey} />

<div class="scrim" data-testid="quilt-window-scrim">
	<div class="win" role="dialog" aria-modal="true" aria-label={title} data-testid="quilt-window" data-at={at}>
		<div class="wh">
			<b>{title}</b>
			<button type="button" class="ib" title={words.window.close} aria-label={words.window.close} onclick={onclose} data-testid="quilt-window-close">
				<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
			</button>
		</div>
		<div class="wb">
			{#if drop}
				<div class="dropped" data-testid="quilt-window-dropped">
					{#if drop.shown.folder}
						<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="M1.8 4.2c0-.7.5-1.2 1.2-1.2h3.2l1.4 1.6H13c.7 0 1.2.5 1.2 1.2v6.2c0 .7-.5 1.2-1.2 1.2H3c-.7 0-1.2-.5-1.2-1.2z" /></svg>
					{:else}
						<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="M4 1.8h5.2L12.5 5v9.2H4z" /><path d="M9 1.8V5.2h3.5" /></svg>
					{/if}
					<span>{@render droppedLine()}</span>
				</div>
			{/if}

			{#if at === 'form'}
				<div class="frm">
					<label class="lab" for="quilt-name-field">{words.window.name}</label>
					<input id="quilt-name-field" class="field" class:err={said && 'under' in said} bind:this={field} bind:value={name} placeholder={kind === 'empty' ? words.window.namePlaceholder : undefined} onkeydown={(e) => e.key === 'Enter' && void create()} data-testid="quilt-window-name" />
					{#if said && 'under' in said}<span class="errline" data-testid="quilt-window-error">{words.window[said.under]}</span>{/if}
					{#if kind === 'empty'}
						<span></span><span class="grey">{words.window.place(shortPath(where, listing?.home_folder))}</span>
					{:else}
						<span class="lab">{words.window.folder}</span>
						<span>{words.window.place(shortPath(where, listing?.home_folder))} <button type="button" class="linkbtn" title={words.window.changeTip} onclick={() => void choosePlace()} data-testid="quilt-window-place">{words.window.change}</button></span>
					{/if}
				</div>
			{:else if at === 'question'}
				<div class="ask">{words.window.question}</div>
				<div class="choices" role="radiogroup" aria-label={words.window.question}>
					{#each choices as c (c)}
						<label class="choice"><input type="radio" name="main" value={c} bind:group={chosen} data-testid="quilt-window-choice" /><span class="p">{c}</span></label>
					{/each}
				</div>
			{:else if at === 'steps'}
				<ul class="steps" data-testid="quilt-window-steps">
					{#each steps as s, i (s)}
						<li class:todo={i > stepNow} data-step={s} data-now={i === stepNow}>
							<span class="ic">
								{#if i < stepNow}
									<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="7.2" fill="var(--state-accepted)" /><path d="M4.6 8.2l2.3 2.4 4.5-4.8" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
								{:else if i === stepNow}
									<svg class="spin" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--rule)" stroke-width="1.6" /><path d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round" /></svg>
								{:else}
									<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--rule)" stroke-width="1.5" /></svg>
								{/if}
							</span>
							<span>{s === 'reading' ? words.window.reading : words.window.steps[s]}{#if s === 'importing' && i === stepNow}<span class="sub">{words.window.importingSub}</span>{/if}</span>
						</li>
					{/each}
				</ul>
			{:else if at === 'done'}
				{#if outcome === 'unserved'}
					<div class="said" data-testid="quilt-window-done">{words.window.madeNotOpen(madeName)}</div>
				{:else if job?.typeset === false}
					<div class="said" data-testid="quilt-window-done">{words.window.untypeset} {untypesetOf(job.untypeset ?? '', job.tex)}</div>
				{:else}
					<p class="ready" data-testid="quilt-window-done">{words.window.ready(madeName)}</p>
				{/if}
			{:else if said && 'refused' in said}
				<div class="said bad" data-testid="quilt-window-refused">
					{words.window[said.refused]}
					{#if said.refused === 'stopping' || said.refused === 'unreachable'}
						<div class="hint">{words.window.stoppingHint}</div>
					{:else if said.refused === 'noPaper'}
						<div class="hint">{words.window.noPaperHint[0]}<span class="mono">{words.window.noPaperHint[1]}</span>{words.window.noPaperHint[2]}</div>
					{:else if said.refused === 'badArchive'}
						<div class="hint">{words.window.badArchiveHint}</div>
					{:else if said.refused === 'tooLarge'}
						<div class="hint">{words.window.tooLargeHint}</div>
					{/if}
				</div>
			{:else if said && 'failed' in said}
				<div class="said bad" data-testid="quilt-window-failed">
					{#if said.failed}
						{words.window.failed}
						<div class="logbox">{importSaidOf(said.failed, listing?.home_folder)}</div>
						<CopyDetails said={said.failed} />
					{:else}
						{words.window.failedPlain}
						<div><CopyDetails /></div>
					{/if}
				</div>
			{/if}
		</div>
		<div class="wf">
			{#if at === 'form' || at === 'question'}
				<button type="button" class="btn quiet" onclick={onclose} data-testid="quilt-window-cancel">{words.window.cancel}</button>
				<button type="button" class="btn primary" disabled={busy || !name.trim() || (drop !== null && !sent) || (at === 'question' && !chosen)} title={at === 'question' && !chosen ? words.window.chooseFirst : undefined} onclick={() => void create()} data-testid="quilt-window-create">{words.window.create}</button>
			{:else if at === 'done'}
				{#if job?.typeset === false && job.tex === 'none'}
					<button type="button" class="btn" onclick={() => void repairTex()} data-testid="quilt-window-repair">{words.tex.repair}</button>
				{/if}
				{#if opening}
					<a class="btn primary" href={opening} target="_blank" rel="noopener" onclick={() => setTimeout(onclose)} data-testid="quilt-window-open">{words.window.open}</a>
				{:else}
					<button type="button" class="btn" onclick={onclose}>{words.window.closeButton}</button>
				{/if}
			{:else if at === 'said'}
				<button type="button" class="btn" onclick={onclose} data-testid="quilt-window-close-button">{words.window.closeButton}</button>
			{/if}
		</div>
	</div>
</div>

{#snippet droppedLine()}
	{@const n = drop?.shown.count ?? 0}
	{#if drop?.shown.folder}
		{@const parts = words.window.droppedFolder(n)}
		{parts[0]}<b>{shownName}</b>{parts[1]}
	{:else if shownName}
		{words.window.droppedFile[0]}<b>{shownName}</b>{words.window.droppedFile[1]}
	{:else}
		{words.window.droppedMany(n)}
	{/if}
{/snippet}

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: color-mix(in srgb, var(--ink) 18%, transparent);
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 120px;
	}
	.win {
		width: 560px;
		max-width: calc(100% - 32px);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 14px;
		box-shadow: 0 12px 40px rgb(0 0 0 / 18%);
	}
	.wh {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 10px 10px 20px;
		border-bottom: 1px solid color-mix(in srgb, var(--rule) 55%, transparent);
	}
	.wh b {
		font-weight: 500;
		font-size: 16px;
		margin-right: auto;
	}
	.wb {
		padding: 16px 20px 6px;
	}
	.wf {
		display: flex;
		justify-content: flex-end;
		align-items: center;
		gap: 8px;
		padding: 12px 20px 16px;
	}
	.wf :global(.btn),
	.wf a.btn {
		padding: 4px 11px;
		border-radius: 7px;
		text-decoration: none;
	}
	.ib {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 28px;
		height: 28px;
		border: 0;
		background: none;
		border-radius: 6px;
		color: var(--ink-faint);
		cursor: pointer;
		flex: none;
		padding: 0;
	}
	.ib:hover {
		background: color-mix(in srgb, var(--ink) 6%, transparent);
		color: var(--ink);
	}
	.dropped {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--ink-faint);
		margin: 0 0 16px;
	}
	.dropped b {
		color: var(--ink);
		font-weight: 500;
	}
	.frm {
		display: grid;
		grid-template-columns: 70px 1fr;
		gap: 10px 12px;
		align-items: center;
	}
	.lab,
	.grey {
		color: var(--ink-faint);
	}
	.field {
		border: 1px solid var(--rule);
		border-radius: 7px;
		padding: 4px 9px;
		background: var(--sheet);
		color: var(--ink);
		font: inherit;
		width: 100%;
		height: 28px;
	}
	.field:focus {
		outline: 2px solid var(--link-wash);
		border-color: color-mix(in srgb, var(--link) 45%, var(--rule));
	}
	.field.err {
		border-color: var(--state-incomplete);
		outline: 2px solid color-mix(in srgb, var(--state-incomplete) 12%, transparent);
	}
	.errline {
		grid-column: 2;
		color: var(--state-incomplete);
		margin-top: -4px;
	}
	.linkbtn {
		all: unset;
		color: var(--link);
		cursor: pointer;
		margin-left: 6px;
	}
	.linkbtn:hover {
		text-decoration: underline;
	}
	.ask {
		margin: 0 0 2px;
	}
	.choices {
		margin: 8px 0 4px;
	}
	.choice {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 30px;
		padding: 0 8px;
		border-radius: 6px;
		cursor: pointer;
	}
	.choice:hover {
		background: color-mix(in srgb, var(--ink) 6%, transparent);
	}
	.choice input {
		margin: 0;
		accent-color: var(--ink);
	}
	.p {
		font-family: var(--mono);
		font-size: 12.5px;
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.steps li {
		display: grid;
		grid-template-columns: 22px 1fr;
		gap: 10px;
		align-items: start;
		padding: 5px 0;
	}
	.steps li.todo {
		color: var(--ink-faint);
	}
	.ic {
		width: 22px;
		height: 22px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.sub {
		display: block;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.spin {
		animation: spin 1.1s linear infinite;
		transform-origin: 50% 50%;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.said {
		border: 1px solid var(--rule);
		border-left: 3px solid var(--state-stale);
		border-radius: 8px;
		padding: 8px 12px;
		margin: 0 0 4px;
	}
	.said.bad {
		border-left-color: var(--state-incomplete);
	}
	.hint {
		font-size: 11px;
		color: var(--ink-faint);
		margin-top: 4px;
	}
	.mono {
		font-family: var(--mono);
	}
	.logbox {
		font: 12px/1.5 var(--mono);
		background: var(--leaf);
		border: 1px solid color-mix(in srgb, var(--rule) 55%, transparent);
		border-radius: 6px;
		padding: 5px 9px;
		margin: 4px 0;
		white-space: pre-wrap;
		word-break: break-word;
		color: var(--ink-soft);
	}
	.ready {
		margin: 0 0 4px;
		font-weight: 500;
	}
</style>
