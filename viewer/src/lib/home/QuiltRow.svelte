<script lang="ts">
	// One row of the home page's list: the quilt's state as a dot, its name and folder, its state in words, and the controls its state allows (`docs/specs/write-api.md` §7). Open on a stopped quilt opens its tab at once, on the click, and sends it to the quilt's address once its server answers, since a browser opens a tab only on a click.
	import { call, type QuiltRow } from './api';
	import { homePage, shortPath } from './listing.svelte';
	import CopyDetails from './CopyDetails.svelte';
	import { cannotStartOf, refusalOf } from './said';
	import { home as words } from '$lib/words/home';

	let { q, disabled = false }: { q: QuiltRow; disabled?: boolean } = $props();

	let busy = $state(false);
	let refused = $state('');

	const dot = $derived(q.state === 'failed' ? 'failed' : q.state);
	const folder = $derived(shortPath(q.folder, homePage.listing?.home_folder));
	/** A refusal worded for the person (`said.ts`): a port lost as the server started is the row of a port another program holds. */
	const refusal = $derived(q.why === 'refused' ? refusalOf(q.said ?? '', q.folder, homePage.listing?.home_folder) : null);
	const why = $derived(refusal && 'port' in refusal ? 'port-taken' : q.why);
	const newer = $derived(refusal && 'newer' in refusal ? refusal.newer : null);

	/** Run one of the row's requests, then ask for the list again. */
	async function act(endpoint: string, body: Record<string, unknown> = {}): Promise<boolean> {
		busy = true;
		refused = '';
		const r = await call(endpoint, { quilt: q.quilt, ...body });
		if (!r.ok) refused = words.control.refusedNow;
		await homePage.refresh();
		busy = false;
		return r.ok;
	}

	/** Start the quilt and open it in its own tab, which waits blank until the quilt answers. */
	async function openStopped(move = false): Promise<void> {
		const tab = window.open('', '_blank');
		if (!(await act('quilt-open', move ? { move: true } : {}))) {
			tab?.close();
			return;
		}
		const end = Date.now() + 60_000;
		while (Date.now() < end) {
			const row = homePage.listing?.quilts.find((x) => x.quilt === q.quilt);
			if (row?.state === 'running' && row.url) {
				if (tab) tab.location.href = row.url;
				return;
			}
			if (!row || row.state === 'failed' || row.state === 'missing' || row.state === 'stopped') break;
			await new Promise((r) => setTimeout(r, 300));
			await homePage.refresh();
		}
		tab?.close();
	}
</script>

<div class="qrow" data-testid="quilt-row" data-state={q.state} data-why={why ?? ''}>
	<div class="qn">
		<span class="st {dot}" aria-hidden="true">{#if q.state === 'missing'}?{/if}</span>
		<div class="who">
			<div class="nm" data-testid="quilt-row-name">{q.name}</div>
			<div class="fd" title={folder}>{folder}</div>
		</div>
	</div>
	<div class="qs" data-testid="quilt-row-state">
		{#if q.state === 'running'}
			<span class="w">{words.state.running}</span>
		{:else if q.state === 'starting'}
			<span class="w soft">{words.state.starting}</span>
		{:else if q.state === 'stopped'}
			<span class="w soft">{words.state.stopped}</span>
		{:else if q.state === 'missing'}
			<span class="w">{words.state.missing}</span>
		{:else if why === 'port-taken'}
			<span class="w">{words.state.portTaken}</span>
		{:else if refusal}
			<span class="w">{words.state.refused}</span>
			<div class="logbox" data-testid="quilt-row-said">{newer ? words.state.formatNewer(newer.found, newer.reads) : 'text' in refusal ? refusal.text : ''}</div>
			<CopyDetails quilt={q.quilt} />
			{#if newer}<div class="sub" data-testid="quilt-row-newer">{words.state.newer}</div>{/if}
		{:else if q.why === 'exited'}
			<span class="w">{words.state.exited}</span>
			<div><CopyDetails quilt={q.quilt} /></div>
		{:else}
			<span class="w">{words.state.cannotStart}</span>
			<div class="logbox" data-testid="quilt-row-said">{cannotStartOf(q.said ?? '', homePage.listing?.home_folder)}</div>
			<CopyDetails quilt={q.quilt} />
		{/if}
		{#if refused}<div class="sub bad">{refused}</div>{/if}
	</div>
	<div class="qc">
		{#if q.state === 'running'}
			<a class="btn" href={q.url} target="_blank" rel="noopener" title={words.control.openRunning} data-testid="quilt-open">{words.control.open}</a>
			<button type="button" class="btn" disabled={busy || disabled} title={words.control.stopTip} onclick={() => void act('quilt-stop')} data-testid="quilt-stop">{words.control.stop}</button>
		{:else if q.state === 'stopped'}
			<button type="button" class="btn" disabled={busy || disabled} title={words.control.openStopped} onclick={() => void openStopped()} data-testid="quilt-open">{words.control.open}</button>
			{@render forget()}
		{:else if q.state === 'missing'}
			{@render forget()}
		{:else if why === 'port-taken'}
			<div class="move">
				<button type="button" class="btn" disabled={busy || disabled} onclick={() => void openStopped(true)} data-testid="quilt-move">{words.control.move}</button>
				<div class="sub">{words.control.moveSaid}</div>
			</div>
		{:else if q.why === 'exited'}
			{@render again()}
		{:else if newer}
			<!-- this loom cannot open what a newer one made: Open again would only refuse -->
			{@render forget()}
		{:else if q.state === 'failed'}
			{@render again()}
			{@render forget()}
		{/if}
	</div>
</div>

{#snippet forget()}
	<button type="button" class="btn" disabled={busy || disabled} title={words.control.forgetTip} onclick={() => void act('quilt-forget')} data-testid="quilt-forget">{words.control.forget}</button>
{/snippet}

{#snippet again()}
	<button type="button" class="btn" disabled={busy || disabled} onclick={() => void openStopped()} data-testid="quilt-again">{words.control.again}</button>
{/snippet}

<style>
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
		min-width: 0;
	}
	.who {
		min-width: 0;
	}
	.nm {
		font-weight: 500;
	}
	.fd {
		font-size: 11px;
		color: var(--ink-faint);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.st {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex: none;
		margin-top: 4px;
		border: 1.5px solid var(--ink-faint);
		background: none;
	}
	.st.running {
		background: var(--state-accepted);
		border-color: var(--state-accepted);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--state-accepted) 14%, transparent);
	}
	.st.starting {
		border-color: var(--state-stale);
		border-style: dashed;
	}
	.st.failed {
		background: var(--state-incomplete);
		border-color: var(--state-incomplete);
	}
	.st.missing {
		border: 0;
		margin-top: 1px;
		color: var(--ink-faint);
		font-size: 14px;
		line-height: 14px;
		text-align: center;
	}
	.qs {
		padding-top: 2px;
		min-width: 0;
	}
	.w.soft {
		color: var(--ink-faint);
	}
	.sub {
		font-size: 11px;
		color: var(--ink-faint);
		margin-top: 3px;
	}
	.sub.bad {
		color: var(--state-incomplete);
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
	.qc {
		display: flex;
		gap: 6px;
		align-items: center;
		justify-content: flex-end;
		min-width: 200px;
	}
	.move {
		text-align: right;
	}
	.qc .btn {
		padding: 4px 11px;
		border-radius: 7px;
		text-decoration: none;
		white-space: nowrap;
		display: inline-flex;
		align-items: center;
	}
</style>
