<script lang="ts">
	// Loom's home page, drawn in place of a quilt when `GET /_api` says `home` (`listing.svelte.ts`): the person's quilts, each with its state and controls, Open a quilt… and New quilt, the TeX notice with Repair TeX, and the list that cannot be read. It asks for the list once a second while it is in view. Files dragged over any part of it cover it with a sheet saying what they will make; dropped, they open the window for a new quilt (`QuiltWindow.svelte`), as New quilt does with no paper.
	import { onDestroy, onMount } from 'svelte';
	import { call } from './api';
	import { homePage, repairOf, rowsOf, shortPath } from './listing.svelte';
	import QuiltRow from './QuiltRow.svelte';
	import CopyDetails from './CopyDetails.svelte';
	import QuiltWindow from './QuiltWindow.svelte';
	import { draggingPdf, readDrop, type Drop } from './drop';
	import { home as words } from '$lib/words/home';

	onDestroy(() => homePage.stop());

	/** The window for a new quilt: closed, from New quilt (no drop), or from a drop. */
	let win = $state<{ drop: Drop | null } | null>(null);
	/** Whether the window shows a create's steps, which another drop does not replace. */
	let creating = $state(false);
	/** The sheet over the page while files are dragged over it, saying what they will make; null when none are. */
	let cover = $state<'paper' | 'pdf' | null>(null);

	onMount(() => {
		homePage.start();
		let timer: ReturnType<typeof setTimeout> | null = null;
		const carries = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');
		// the sheet stays while the drag moves over the window, and goes a moment after the moves stop: leaving the window, or Escape
		const move = (e: DragEvent) => {
			if (!carries(e) || unreadable) return;
			e.preventDefault();
			if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
			cover = draggingPdf(e.dataTransfer?.items) ? 'pdf' : 'paper';
			if (timer) clearTimeout(timer);
			timer = setTimeout(() => (cover = null), 200);
		};
		const drop = async (e: DragEvent) => {
			cover = null;
			if (!carries(e)) return;
			e.preventDefault();
			// a create under way keeps its window; another drop waits for it to be put away
			if (unreadable || (win && creating)) return;
			const read = await readDrop(e.dataTransfer!);
			if (read) win = { drop: read };
		};
		window.addEventListener('dragover', move);
		window.addEventListener('drop', drop);
		return () => {
			window.removeEventListener('dragover', move);
			window.removeEventListener('drop', drop);
			if (timer) clearTimeout(timer);
		};
	});

	const listing = $derived(homePage.listing);
	const unreadable = $derived(listing?.list === 'unreadable');
	const rows = $derived(listing ? rowsOf(listing) : []);
	const repair = $derived(repairOf(listing));
	const repairing = $derived(repair?.state === 'running');

	/** The notice under the heading, from Open a quilt…; '' when none. */
	let note = $state('');

	async function openQuilt(): Promise<void> {
		note = '';
		const r = await call<{ quilt?: string; cancelled?: boolean }>('quilt-choose', { purpose: 'open' });
		if (!r.ok) note = r.code === 'no-dialog' ? words.noDialog : r.code === 'not-a-quilt' ? words.notAQuilt : words.control.refusedNow;
		await homePage.refresh();
	}

	async function repairTex(): Promise<void> {
		await call('quilt-repair');
		await homePage.refresh();
	}
</script>

<svelte:head>
	<title>{words.title}</title>
</svelte:head>

<div class="homepage" data-testid="home">
	<div class="scroll">
		<div class="hwrap">
			<div class="hhead">
				<h1>{words.heading}</h1>
				<button type="button" class="btn" disabled={unreadable} onclick={() => void openQuilt()} data-testid="home-open-quilt">{words.openQuilt}</button>
				<button type="button" class="btn primary" disabled={unreadable} onclick={() => (win = { drop: null })} data-testid="home-new-quilt">{words.newQuilt}</button>
			</div>

			{#if note}
				<div class="hnote bad" role="status" data-testid="home-note">
					<div class="t">{note}</div>
					<button type="button" class="ib" title={words.close} aria-label={words.close} onclick={() => (note = '')}>
						<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
					</button>
				</div>
			{/if}

			{#if repairing}
				<div class="hnote plain" role="status" data-testid="home-tex-repairing">
					<span class="spin-wrap"><svg class="spin" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--rule)" stroke-width="1.6" /><path d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round" /></svg></span>
					<div class="t">{words.tex.repairing}{#if repair?.step}<div class="lines">{repair.step}</div>{/if}</div>
				</div>
			{:else if listing?.tex === 'none'}
				<div class="hnote" data-testid="home-tex-none">
					<div class="t">{repair?.state === 'failed' ? words.tex.failed : words.tex.none}</div>
					<button type="button" class="btn" onclick={() => void repairTex()} data-testid="home-repair-tex">{words.tex.repair}</button>
				</div>
			{/if}

			{#if unreadable}
				<div class="hnote bad flat" role="status" data-testid="home-unreadable">
					<div class="t">{words.unreadable}</div>
					<CopyDetails />
				</div>
			{:else if listing && rows.length === 0}
				<div class="empty" data-testid="home-empty">
					<h2>{words.empty.heading}</h2>
					<p>{words.empty.paper[0]}<span class="mono">{words.empty.paper[1]}</span>{words.empty.paper[2]}</p>
					<p>{words.empty.pdf}</p>
					<p class="what">{words.empty.what}</p>
				</div>
			{:else if listing}
				<div class="qlist" data-testid="home-list">
					{#each rows as r ('quilt' in r ? r.quilt.quilt : r.making.job)}
						{#if 'quilt' in r}
							<QuiltRow q={r.quilt} />
						{:else}
							<div class="qrow making" data-testid="quilt-row" data-state="making">
								<div class="qn">
									<span class="st" aria-hidden="true"></span>
									<div class="who">
										<div class="nm" data-testid="quilt-row-name">{r.making.name}</div>
										<div class="fd">{shortPath(r.making.folder ?? '', listing.home_folder)}</div>
									</div>
								</div>
								<div class="qs"><span class="soft">{words.state.making}</span></div>
								<div></div>
							</div>
						{/if}
					{/each}
				</div>
				<p class="drophint">{words.hint[0]}<span class="mono">{words.hint[1]}</span>{words.hint[2]}</p>
			{/if}
		</div>
	</div>
</div>

{#if cover}
	<div class="dragcover" aria-hidden="true" data-testid="home-drop-cover" data-kind={cover}>
		<div>{cover === 'pdf' ? words.cover.pdf : words.cover.paper}</div>
	</div>
{/if}

{#if win}
	{#key win}
		<QuiltWindow drop={win.drop} onclose={() => ((win = null), (creating = false))} onsteps={(r) => (creating = r)} />
	{/key}
{/if}

<style>
	.dragcover {
		position: fixed;
		inset: 0;
		z-index: 300;
		pointer-events: none;
		background: color-mix(in srgb, var(--leaf) 82%, transparent);
		backdrop-filter: blur(2px);
		display: flex;
		align-items: center;
		justify-content: center;
		font-family: var(--sans);
	}
	.dragcover div {
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 12px;
		box-shadow: var(--float-shadow);
		padding: 16px 24px;
		font-size: 16px;
		color: var(--ink);
	}
	.homepage {
		position: fixed;
		inset: 0;
		display: flex;
		flex-direction: column;
		background: var(--paper);
		color: var(--ink);
		font-family: var(--sans);
		font-size: 13px;
		line-height: 1.45;
	}
	.scroll {
		flex: 1;
		min-height: 0;
		overflow: auto;
	}
	.hwrap {
		width: 880px;
		max-width: calc(100% - 32px);
		margin: 0 auto;
		padding: 44px 0 40px;
	}
	.hhead {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0 0 18px;
	}
	.hhead h1 {
		font-size: 16px;
		font-weight: 500;
		margin: 0 auto 0 0;
	}
	.homepage :global(.btn) {
		padding: 4px 11px;
		border-radius: 7px;
	}
	.hnote {
		display: flex;
		align-items: center;
		gap: 12px;
		border: 1px solid var(--rule);
		border-left: 3px solid var(--state-stale);
		border-radius: 8px;
		padding: 8px 8px 8px 12px;
		margin: 0 0 14px;
		background: var(--sheet);
	}
	.hnote.bad {
		border-left-color: var(--state-incomplete);
	}
	.hnote.plain {
		border-left-color: var(--rule);
	}
	.hnote.flat {
		margin: 0;
	}
	.hnote .t {
		flex: 1;
	}
	.hnote .lines {
		font-size: 11px;
		color: var(--ink-faint);
		margin-top: 3px;
		line-height: 1.6;
	}
	.spin-wrap {
		display: flex;
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
	.qlist {
		border-top: 1px solid var(--rule);
	}
	.qrow {
		display: grid;
		grid-template-columns: 300px 1fr auto;
		align-items: start;
		gap: 20px;
		padding: 12px 6px 12px 4px;
		border-bottom: 1px solid color-mix(in srgb, var(--rule) 55%, transparent);
		min-height: 58px;
	}
	.qn {
		display: flex;
		gap: 10px;
		align-items: flex-start;
	}
	.nm {
		font-weight: 500;
	}
	.fd {
		font-size: 11px;
		color: var(--ink-faint);
	}
	.st {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex: none;
		margin-top: 4px;
		border: 1.5px dashed var(--state-stale);
	}
	.qs {
		padding-top: 2px;
	}
	.soft {
		color: var(--ink-faint);
	}
	.mono {
		font-family: var(--mono);
	}
	.drophint {
		margin: 14px 4px 0;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.empty {
		border: 1.5px dashed var(--rule-strong);
		border-radius: 12px;
		padding: 40px 44px;
		text-align: center;
		margin: 6px 0 0;
		background: var(--sheet);
	}
	.empty h2 {
		font-size: 16px;
		font-weight: 500;
		margin: 0 0 8px;
	}
	.empty p {
		margin: 0 auto 6px;
		max-width: 640px;
	}
	.empty .what {
		margin-top: 18px;
		color: var(--ink-faint);
		font-size: 11px;
	}
</style>
