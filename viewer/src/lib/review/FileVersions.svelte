<script lang="ts">
	// Review › History › Versions, under a document's versions: each version of a file no document's version holds, newest first, each opened, compared with the file now, or put back after asking. A text opens as its text and compares as a line diff; an image as itself and beside the file now; anything else by its bytes, to download.
	import type { HistoryFile } from '$lib/manifest/types';
	import { landed } from '$lib/manifest/updating.svelte';
	import { dataUrl, filesUrl } from '$lib/paths';
	import { shortDate } from '$lib/badges';
	import { review } from '$lib/words/review';
	import { write } from '$lib/write';
	import DiffView from '$lib/components/DiffView.svelte';
	import Said from './Said.svelte';

	let { files, restores }: { files: HistoryFile[]; restores: boolean } = $props();
	const words = review.fileVersions;

	const rows = $derived([...files].reverse());
	const name = (p: string) => p.split('/').pop() ?? p;
	const day = (iso: string) => (iso ? shortDate(iso) : '');
	/** A row's own name, so what is shown and said under it stays with it when a newer row arrives above. */
	const id = (f: HistoryFile) => `${f.path}@${f.version}@${f.when}`;

	let shown = $state<{ at: string; what: 'open' | 'compare' } | null>(null);
	let text = $state<{ at: string; body: string } | null>(null);
	let asking = $state('');
	let busy = $state('');
	let said = $state<{ at: string; text: string; refused: boolean } | null>(null);

	function show(f: HistoryFile, what: 'open' | 'compare'): void {
		const at = id(f);
		shown = shown?.at === at && shown.what === what ? null : { at, what };
		if (shown?.what === 'open' && f.kind === 'text' && f.kept && text?.at !== at) {
			void fetch(dataUrl(f.kept))
				.then((r) => (r.ok ? r.text() : Promise.reject(new Error(String(r.status)))))
				.then((body) => (text = { at, body }))
				.catch(() => (text = { at, body: '' }));
		}
	}

	const capital = (t: string) => t.charAt(0).toUpperCase() + t.slice(1) + (t.endsWith('.') ? '' : '.');
	async function restore(f: HistoryFile): Promise<void> {
		const at = id(f);
		busy = at;
		said = null;
		const done = await write('history-restore', { file: f.path, version: f.version });
		if (done.ok) await landed();
		said = { at, text: done.ok ? capital(done.result ?? '') : (done.error?.message ?? ''), refused: !done.ok };
		busy = '';
		asking = '';
	}
</script>

<section class="files" data-testid="history-files">
	<h2>{words.heading}</h2>
	<p class="muted">{words.lead}</p>
	<ul>
		{#each rows as f (id(f))}
			{@const at = id(f)}
			<li data-testid="history-file" data-path={f.path}>
				<div class="row">
					<span class="name" title={f.path}>{name(f.path)}</span>
					<span class="muted">{f.message ?? ''}</span>
					<span class="when">{day(f.when)}</span>
					<span class="acts">
						{#if f.kept}
							<button class="btn small" aria-pressed={shown?.at === at && shown.what === 'open'} data-testid="history-file-open" onclick={() => show(f, 'open')}>{words.open}</button>
							{#if f.same}
								<span class="muted">{words.same}</span>
							{:else}
								<button class="btn small" aria-pressed={shown?.at === at && shown.what === 'compare'} data-testid="history-file-compare" onclick={() => show(f, 'compare')}>{words.compare}</button>
							{/if}
						{/if}
						{#if restores && !f.cannot_restore && !f.same}
							<button class="btn small" data-testid="history-file-restore" onclick={() => ((asking = at), (said = null))}>{words.restore}</button>
						{/if}
					</span>
				</div>
				{#if f.cannot_restore}<p class="cannot" data-testid="history-file-cannot">{f.cannot_restore}</p>{/if}
				{#if asking === at}
					<p class="ask" data-testid="history-file-ask">
						{words.ask(name(f.path), day(f.when))}
						<button class="btn small primary" disabled={busy === at} data-testid="history-file-restore-go" onclick={() => void restore(f)}>{busy === at ? words.going : words.go}</button>
						<button class="btn small quiet" onclick={() => (asking = '')}>{words.cancel}</button>
					</p>
				{/if}
				{#if said?.at === at}<Said text={said.text} refused={said.refused} testid="history-file-said" />{/if}
				{#if shown?.at === at && f.kept}
					<div class="shown" data-testid="history-file-shown">
						{#if shown.what === 'open'}
							{#if f.kind === 'text'}
								{#if text?.at === at}<pre>{text.body || words.unread}</pre>{/if}
							{:else if f.kind === 'image'}
								<img src={dataUrl(f.kept)} alt={name(f.path)} />
							{:else}
								<a href={dataUrl(f.kept)} download={name(f.path)}>{words.download(name(f.path))}</a>
							{/if}
						{:else if f.kind === 'text'}
							{#if f.diff}<DiffView path={f.diff} />{:else}<p class="muted">{words.gone}</p>{/if}
						{:else if f.kind === 'image'}
							<div class="pair">
								<figure><img src={dataUrl(f.kept)} alt={name(f.path)} /><figcaption>{words.then}</figcaption></figure>
								<figure><img src={filesUrl(f.path)} alt={name(f.path)} /><figcaption>{words.now}</figcaption></figure>
							</div>
						{:else}
							<p class="muted">{words.differs}</p>
						{/if}
					</div>
				{/if}
			</li>
		{/each}
	</ul>
</section>

<style>
	.files h2 {
		font-size: 14px;
		font-weight: 500;
		margin: var(--gap) 0 2px;
	}
	ul {
		list-style: none;
		margin: 6px 0 var(--gap-wide);
		padding: 0;
	}
	li {
		padding: 6px 0;
		border-bottom: 1px solid var(--rule);
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}
	.name {
		font-weight: 500;
	}
	.when,
	.muted,
	.cannot,
	.ask {
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.acts {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.cannot,
	.ask {
		margin: 4px 0 0;
	}
	.shown {
		margin-top: 8px;
	}
	pre {
		margin: 0;
		max-height: 24em;
		overflow: auto;
		font-size: 11.5px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	img {
		max-width: 100%;
		max-height: 20em;
	}
	.pair {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
	}
	figure {
		margin: 0;
		flex: 1 1 14em;
	}
	figcaption {
		font-size: 11.5px;
		color: var(--ink-soft);
	}
</style>
