<script lang="ts">
	// The home page's window for New quilt: it asks only the quilt's name, says where it goes, shows the create's steps, and gives way to its outcome, which offers Open it. Closing the window while the steps run leaves the create to finish, its quilt then on the list (`docs/specs/write-api.md` §7). A quilt made here is empty; the person brings a paper into it on its own page.
	import { onMount } from 'svelte';
	import { call } from './api';
	import { homePage, shortPath } from './listing.svelte';
	import { outcomeOf, saidOf, STEPS, stepAt, type Said } from './flow';
	import CopyDetails from './CopyDetails.svelte';
	import { home as words } from '$lib/words/home';

	let { onclose }: { onclose: () => void } = $props();

	let name = $state('');
	let at = $state<'form' | 'steps' | 'done' | 'said'>('form');
	let said = $state<Said | null>(null);
	let jobKey = $state('');
	let busy = $state(false);
	let field = $state<HTMLInputElement>();

	onMount(() => field?.focus());

	const listing = $derived(homePage.listing);
	const where = $derived(listing?.home_folder ? `${listing.home_folder}/Quilts` : '~/Quilts');
	const job = $derived(jobKey ? listing?.jobs.find((j) => j.job === jobKey) : undefined);
	const row = $derived(job?.quilt ? listing?.quilts.find((q) => q.quilt === job.quilt) : undefined);
	const outcome = $derived(jobKey ? outcomeOf(job, row) : 'running');
	const stepNow = $derived(job ? (job.state === 'done' ? STEPS.length - 1 : stepAt(job.step)) : 0);

	/** Whether a create of this name is running, which `exists` then means. */
	function making(): boolean {
		return !!listing?.jobs.some((j) => j.kind === 'create' && j.state === 'running' && j.folder === `${where}/${name.trim()}`);
	}

	function refuse(code: string): void {
		said = saidOf(code, making());
		at = 'under' in said ? 'form' : 'said';
	}

	async function create(): Promise<void> {
		if (!name.trim()) return field?.focus();
		if (busy) return;
		busy = true;
		said = null;
		const r = await call<{ job?: string }>('quilt-create', { name: name.trim() });
		busy = false;
		if (!r.ok) return refuse(r.code);
		jobKey = r.value.job ?? '';
		at = 'steps';
		await homePage.refresh();
	}

	// a job that ended: its outcome, or its failure said where it belongs
	$effect(() => {
		if (at !== 'steps') return;
		if (outcome === 'served' || outcome === 'unserved') at = 'done';
		else if (outcome === 'failed' && job) refuse(job.why ?? 'failed');
	});

	const madeName = $derived(job?.name ?? name);

	function onkey(e: KeyboardEvent): void {
		if (e.key === 'Escape') onclose();
	}
</script>

<svelte:window onkeydown={onkey} />

<div class="scrim" data-testid="quilt-window-scrim">
	<div class="win" role="dialog" aria-modal="true" aria-label={words.window.title} data-testid="quilt-window" data-at={at}>
		<div class="wh">
			<b>{words.window.title}</b>
			<button type="button" class="ib" title={words.window.close} aria-label={words.window.close} onclick={onclose} data-testid="quilt-window-close">
				<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
			</button>
		</div>
		<div class="wb">
			{#if at === 'form'}
				<div class="frm">
					<label class="lab" for="quilt-name-field">{words.window.name}</label>
					<input id="quilt-name-field" class="field" class:err={said && 'under' in said} bind:this={field} bind:value={name} placeholder={words.window.namePlaceholder} onkeydown={(e) => e.key === 'Enter' && void create()} data-testid="quilt-window-name" />
					{#if said && 'under' in said}<span class="errline" data-testid="quilt-window-error">{words.window[said.under]}</span>{/if}
					<span></span><span class="grey">{words.window.place(shortPath(where, listing?.home_folder))}</span>
				</div>
			{:else if at === 'steps'}
				<ul class="steps" data-testid="quilt-window-steps">
					{#each STEPS as s, i (s)}
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
							<span>{words.window.steps[s]}</span>
						</li>
					{/each}
				</ul>
			{:else if at === 'done'}
				{#if outcome === 'unserved'}
					<div class="said" data-testid="quilt-window-done">{words.window.madeNotOpen(madeName)}</div>
				{:else}
					<p class="ready" data-testid="quilt-window-done">{words.window.ready(madeName)}</p>
				{/if}
			{:else if said && 'refused' in said}
				<div class="said bad" data-testid="quilt-window-refused">
					{words.window[said.refused]}
					{#if said.refused === 'stopping' || said.refused === 'unreachable'}
						<div class="hint">{words.window.stoppingHint}</div>
					{/if}
				</div>
			{:else if said && 'failed' in said}
				<div class="said bad" data-testid="quilt-window-failed">
					{words.window.failed}
					<div><CopyDetails said={job?.said ?? ''} /></div>
				</div>
			{/if}
		</div>
		<div class="wf">
			{#if at === 'form'}
				<button type="button" class="btn quiet" onclick={onclose} data-testid="quilt-window-cancel">{words.window.cancel}</button>
				<button type="button" class="btn primary" disabled={busy} onclick={() => void create()} data-testid="quilt-window-create">{words.window.create}</button>
			{:else if at === 'done'}
				{#if row?.url}
					<a class="btn primary" href={row.url} target="_blank" rel="noopener" onclick={() => setTimeout(onclose)} data-testid="quilt-window-open">{words.window.open}</a>
				{:else}
					<button type="button" class="btn" onclick={onclose}>{words.window.closeButton}</button>
				{/if}
			{:else if at === 'said'}
				<button type="button" class="btn" onclick={onclose} data-testid="quilt-window-close-button">{words.window.closeButton}</button>
			{/if}
		</div>
	</div>
</div>

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
		font-family: var(--sans);
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink);
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
	.ready {
		margin: 0 0 4px;
		font-weight: 500;
	}
</style>
