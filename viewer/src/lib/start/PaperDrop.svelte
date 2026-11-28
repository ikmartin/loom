<script lang="ts">
	// The drop area on the page of a quilt with nothing to read (`routes/+page.svelte`): a paper, its folder or its source archive dropped anywhere on the window while it shows comes into the quilt as its paper, and a PDF into its library; "or choose a file…" opens the system's file dialog for one (`bring.ts`). Once it is in, the page opens on the paper, or on the library. While it is mounted it holds the window's drops (`held`), so the library's sheet (`DropZone.svelte`) neither covers the page nor takes the files, wherever they land.
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { landed } from '$lib/manifest/updating.svelte';
	import { made } from '$lib/shell/made.svelte';
	import { masterUrl } from '$lib/nav';
	import { route } from '$lib/paths';
	import { held, readDrop } from './drop';
	import { answer, bringDrop, choose, saidOf, type Answer, type Brought, type Said } from './bring';
	import { docs } from '$lib/words/docs';

	const words = docs.start;

	let stage = $state<'ready' | 'bringing' | 'question'>('ready');
	/** What is coming in, for the line said while it does. */
	let kind = $state<'paper' | 'pdf' | 'chosen'>('paper');
	let over = $state(false);
	let said = $state<Said | null>(null);
	let choices = $state<string[]>([]);
	let chosen = $state('');
	/** The drop that waits for the question's answer. */
	let waiting = '';

	const carries = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');

	onMount(() => {
		held.byStart = true;
		return () => (held.byStart = false);
	});

	function dragover(e: DragEvent): void {
		if (!carries(e)) return;
		e.preventDefault();
		if (e.dataTransfer) e.dataTransfer.dropEffect = stage === 'ready' ? 'copy' : 'none';
		over = stage === 'ready';
	}

	/** A drag leaving the window, which names nothing it entered. */
	function dragleave(e: DragEvent): void {
		if (!e.relatedTarget) over = false;
	}

	async function drop(e: DragEvent): Promise<void> {
		over = false;
		if (!carries(e)) return;
		e.preventDefault();
		if (stage !== 'ready') return;
		const read = await readDrop(e.dataTransfer!);
		if (!read) return;
		begin(read.kind);
		await land(await bringDrop(read.files));
	}

	async function pick(): Promise<void> {
		if (stage !== 'ready') return;
		begin('chosen');
		await land(await choose());
	}

	async function bring(): Promise<void> {
		if (!chosen) return;
		begin('paper');
		await land(await answer(waiting, chosen));
	}

	function begin(what: 'paper' | 'pdf' | 'chosen'): void {
		kind = what;
		said = null;
		stage = 'bringing';
	}

	/** What loom answered: the question asked, or the page opened on what came in once the manifest carries it, or the refusal said. */
	async function land(r: Answer<Brought>): Promise<void> {
		if (!r.ok) {
			said = saidOf(r.code, r.message);
			stage = 'ready';
			return;
		}
		const v = r.value;
		if (v.question) {
			choices = v.question.choices;
			waiting = v.drop ?? '';
			chosen = '';
			stage = 'question';
			return;
		}
		if (!v.document && !v.read) {
			stage = 'ready';
			return;
		}
		await landed();
		if (v.document) {
			if (v.differs) made.differs = true;
			await goto(masterUrl(v.document));
		} else await goto(route('/library'));
	}
</script>

<svelte:window ondragover={dragover} ondragleave={dragleave} ondrop={(e) => void drop(e)} />

<div class="area" class:over role="region" aria-label={words.heading} data-testid="paper-drop" data-stage={stage}>
	<h2>{words.heading}</h2>
	<p>{words.paper[0]}<span class="mono">{words.paper[1]}</span>{words.paper[2]}</p>
	<p>{words.pdf}</p>
	{#if stage === 'bringing'}
		<div class="now" role="status" data-testid="paper-drop-bringing">
			<svg class="spin" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--rule)" stroke-width="1.6" /><path d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round" /></svg>
			<span>{kind === 'pdf' ? words.bringingPdf : kind === 'chosen' ? words.bringingChosen : words.bringingPaper}{#if kind === 'paper'}<span class="sub">{words.bringingSub}</span>{/if}</span>
		</div>
	{:else if stage === 'question'}
		<div class="ask" data-testid="paper-drop-question">
			<div>{words.question}</div>
			<div class="choices" role="radiogroup" aria-label={words.question}>
				{#each choices as c (c)}
					<label class="choice"><input type="radio" name="main" value={c} bind:group={chosen} data-testid="paper-drop-choice" /><span class="mono">{c}</span></label>
				{/each}
			</div>
			<div class="acts">
				<button type="button" class="btn quiet" onclick={() => (stage = 'ready')} data-testid="paper-drop-cancel">{words.cancel}</button>
				<button type="button" class="btn primary" disabled={!chosen} title={chosen ? undefined : words.chooseFirst} onclick={() => void bring()} data-testid="paper-drop-bring">{words.bring}</button>
			</div>
		</div>
	{:else}
		<button type="button" class="link" onclick={() => void pick()} data-testid="paper-drop-choose">{words.choose}</button>
	{/if}
	{#if said}
		<div class="said" role="status" data-testid="paper-drop-said">
			{#if 'refused' in said}
				{words[said.refused]}
				{#if said.refused === 'noPaper'}
					<div class="hint">{words.noPaperHint[0]}<span class="mono">{words.noPaperHint[1]}</span>{words.noPaperHint[2]}</div>
				{:else if said.refused === 'badArchive'}
					<div class="hint">{words.badArchiveHint}</div>
				{:else if said.refused === 'tooLarge'}
					<div class="hint">{words.tooLargeHint}</div>
				{/if}
			{:else if said.failed}
				{words.failed}
				<div class="logbox">{said.failed}</div>
			{:else}
				{words.failedPlain}
			{/if}
		</div>
	{/if}
</div>

<style>
	.area {
		max-width: 640px;
		margin: 48px auto 0;
		border: 1.5px dashed var(--rule-strong);
		border-radius: 12px;
		padding: 40px 44px;
		text-align: center;
		background: var(--sheet);
		font-family: var(--sans);
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink);
	}
	.area.over {
		border-color: var(--link);
		background: color-mix(in srgb, var(--link-wash) 50%, var(--sheet));
	}
	h2 {
		font-size: 16px;
		font-weight: 500;
		margin: 0 0 8px;
	}
	p {
		margin: 0 auto 6px;
	}
	.mono {
		font-family: var(--mono);
	}
	.link {
		all: unset;
		margin-top: 14px;
		color: var(--link);
		cursor: pointer;
	}
	.link:hover,
	.link:focus-visible {
		text-decoration: underline;
	}
	.now {
		display: inline-flex;
		gap: 10px;
		align-items: flex-start;
		margin-top: 14px;
		text-align: left;
	}
	.sub {
		display: block;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.spin {
		flex: none;
		margin-top: 1px;
		animation: spin 1.1s linear infinite;
		transform-origin: 50% 50%;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.ask {
		margin: 14px auto 0;
		max-width: 420px;
		text-align: left;
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
	.acts {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
		margin-top: 8px;
	}
	.acts .btn {
		padding: 4px 11px;
		border-radius: 7px;
	}
	.said {
		margin: 16px auto 0;
		max-width: 520px;
		text-align: left;
		border: 1px solid var(--rule);
		border-left: 3px solid var(--state-incomplete);
		border-radius: 8px;
		padding: 8px 12px;
	}
	.hint {
		font-size: 11px;
		color: var(--ink-faint);
		margin-top: 4px;
	}
	.logbox {
		font: 12px/1.5 var(--mono);
		background: var(--leaf);
		border: 1px solid color-mix(in srgb, var(--rule) 55%, transparent);
		border-radius: 6px;
		padding: 5px 9px;
		margin: 4px 0 0;
		white-space: pre-wrap;
		word-break: break-word;
		color: var(--ink-soft);
	}
</style>
