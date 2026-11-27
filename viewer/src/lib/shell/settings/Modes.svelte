<script lang="ts">
	// Settings › Modes: the quilt's modes in the order its agents are shown them, from the manifest's `agents.modes`, the list at the left and the chosen one at the right: its "When it fits" line, whether its text is loom's or edited here, whether a newer version from loom waits beside it, and the text as its file holds it. Where loom can save one (`agents-mode-save`) and the quilt has an agent layer, Edit opens the text, kept for each mode until Save or Cancel, and Put back loom's, asked first, replaces an edit with loom's text. Each is the author's act; loom refuses an agent.
	import { store } from '$lib/manifest/client.svelte';
	import { write } from '$lib/write';
	import { modes as words } from '$lib/words/modes';
	import Row from './Row.svelte';

	let { editable = false, served = false }: { editable?: boolean; served?: boolean } = $props();

	const list = $derived(store.manifest?.agents?.modes ?? []);
	const layer = $derived(!!store.manifest?.config?.agents.layer);
	const canEdit = $derived(editable && layer);
	let chosen = $state('');
	const current = $derived(list.find((m) => m.name === chosen) ?? list[0]);
	/** Each mode's edit not yet saved: the text as edited, and the text it was opened on, which loom checks the file still holds. */
	let drafts = $state<Record<string, { text: string; was: string }>>({});
	const draft = $derived(current ? drafts[current.name] : undefined);
	let asking = $state(false);
	let busy = $state(false);
	let said = $state('');

	function rows(e: KeyboardEvent): void {
		if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
		e.preventDefault();
		const at = list.findIndex((m) => m.name === current?.name);
		const next = list[Math.max(0, Math.min(list.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)))];
		if (next) choose(next.name);
	}
	function choose(name: string): void {
		chosen = name;
		asking = false;
		said = '';
	}
	function edit(): void {
		if (!current || current.text === undefined) return;
		drafts[current.name] = { text: current.text, was: current.text };
		asking = false;
		said = '';
	}
	function cancel(): void {
		if (current) delete drafts[current.name];
		said = '';
	}
	async function send(body: Record<string, unknown>): Promise<void> {
		if (!current || busy) return;
		const name = current.name;
		busy = true;
		said = '';
		const res = await write('agents-mode-save', { name, ...body });
		busy = false;
		if (!res.ok) {
			said = res.error?.message ?? words.refused;
			return;
		}
		delete drafts[name];
		asking = false;
		await store.refresh();
	}
</script>

<div class="card">
	<Row id="modes.list" stack>
		{#if !list.length || !current}
			<p class="aside" data-testid="modes-none">{words.none}</p>
		{:else}
			{#if !layer}<p class="aside" data-testid="modes-no-layer">{words.noLayer}</p>{:else if served && !editable}<p class="aside" data-testid="modes-older">{words.older}</p>{/if}
			<div class="grid" data-testid="modes">
				<div class="list" role="tablist" aria-label={words.list} aria-orientation="vertical" tabindex="-1" onkeydown={rows}>
					{#each list as m (m.name)}
						<button type="button" class="row" class:on={m.name === current.name} role="tab" aria-selected={m.name === current.name} data-testid="mode-tab" data-mode={m.name} onclick={() => choose(m.name)}>
							<span class="name">{m.name}</span>
							<span class="state" class:edited={m.edited}>{m.edited ? words.state.edited : words.state.loom}{#if m.newer}<span class="also newer" data-testid="mode-tab-newer">· {words.newer}</span>{/if}{#if drafts[m.name]}<span class="also unsaved" data-testid="mode-tab-unsaved">· {words.unsaved}</span>{/if}</span>
						</button>
					{/each}
				</div>
				<div class="detail" role="tabpanel" data-testid="mode-detail" data-mode={current.name}>
					<div class="top">
						<h4 class="title">{current.name}</h4>
						<span class="badge" class:edited={current.edited} data-testid="mode-state">{current.edited ? words.state.edited : words.state.loom}</span>
						{#if draft}
							<span class="acts">
								<button type="button" class="btn quiet" disabled={busy} data-testid="mode-cancel" onclick={cancel}>{words.cancel}</button>
								<button type="button" class="btn primary" disabled={busy || !draft.text.trim() || draft.text === draft.was} data-testid="mode-save" onclick={() => void send({ text: draft.text, was: draft.was })}>{busy ? words.saving : words.save}</button>
							</span>
						{:else if canEdit && current.text !== undefined}
							<span class="acts">
								{#if current.edited}<button type="button" class="btn" disabled={busy} data-testid="mode-put-back" onclick={() => ((asking = true), (said = ''))}>{words.putBack}</button>{/if}
								<button type="button" class="btn" disabled={busy} data-testid="mode-edit" onclick={edit}>{words.edit}</button>
							</span>
						{/if}
					</div>
					{#if asking}
						<div class="ask" role="alert" data-testid="mode-put-back-ask">
							<span>{words.putBackAsk(current.name)}</span>
							<button type="button" class="btn primary" disabled={busy} data-testid="mode-put-back-yes" onclick={() => void send({ loom: true })}>{busy ? words.saving : words.putBackYes}</button>
							<button type="button" class="btn quiet" disabled={busy} onclick={() => (asking = false)}>{words.keepEdit}</button>
						</div>
					{/if}
					{#if said}<p class="said" role="alert" data-testid="mode-said">{said}</p>{/if}
					{#if current.newer}<p class="note info" data-testid="mode-newer">{words.newerWhat}</p>{/if}
					<section>
						<h5>{words.fits}</h5>
						<p class="fits" data-testid="mode-fits">{current.fits || words.noFits}</p>
					</section>
					<section>
						<h5>{words.text}</h5>
						{#if draft}
							<p class="hint">{words.savedHint}</p>
							<textarea class="text" spellcheck="false" aria-label={words.field} bind:value={draft.text} data-testid="mode-field"></textarea>
						{:else if current.text !== undefined}
							<pre class="text" data-testid="mode-text">{current.text}</pre>
						{:else}
							<p class="aside" data-testid="mode-no-text">{words.noText}</p>
						{/if}
						{#if current.text !== undefined}<p class="hint">{words.types}</p>{/if}
						<p class="path">{current.path}</p>
					</section>
				</div>
			</div>
		{/if}
	</Row>
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: 11rem minmax(0, 1fr);
		gap: 14px;
		margin-top: 12px;
	}
	.list {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-right: 10px;
		border-right: 1px solid var(--rule);
		outline: none;
	}
	.row {
		display: grid;
		gap: 1px;
		padding: 6px 8px;
		font: inherit;
		text-align: left;
		color: var(--ink);
		background: none;
		border: 0;
		border-radius: 6px;
		cursor: pointer;
	}
	.row:hover {
		background: var(--leaf);
	}
	.row.on {
		background: var(--accent-wash);
	}
	.name {
		font-size: 13.5px;
		font-weight: 500;
	}
	.state {
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.state.edited {
		color: var(--state-stale);
	}
	.newer {
		color: var(--ink-soft);
	}
	.detail {
		display: grid;
		align-content: start;
		gap: 12px;
		min-width: 0;
	}
	.top {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
	}
	.title {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
		color: var(--ink);
	}
	.badge {
		font-size: 11.5px;
		padding: 1px 8px;
		border-radius: 999px;
		color: var(--ink-soft);
		background: var(--leaf);
	}
	.badge.edited {
		color: var(--state-stale);
		background: var(--state-stale-wash);
	}
	.acts {
		display: flex;
		gap: 8px;
		margin-left: auto;
	}
	.unsaved {
		color: var(--accent);
	}
	.detail .note,
	.said {
		margin: 0;
	}
	.said {
		font-size: 12.5px;
		color: var(--state-conflicted);
	}
	.ask {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 10px;
		padding: 8px 10px;
		font-size: 12.5px;
		background: color-mix(in srgb, var(--ann-orange-band) 35%, var(--sheet));
		border: 1px solid var(--ann-orange);
		border-radius: 6px;
	}
	.ask span {
		flex: 1 1 100%;
	}
	.also {
		margin-left: 0.3em;
	}
	section {
		display: grid;
		gap: 6px;
	}
	h5 {
		margin: 0;
		font-size: 10.5px;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-faint);
	}
	.fits {
		margin: 0;
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink);
	}
	.text {
		margin: 0;
		padding: 10px 12px;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 6px;
		font-family: var(--mono);
		font-size: 12px;
		line-height: 1.55;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		max-height: 26rem;
		overflow: auto;
	}
	textarea.text {
		width: 100%;
		box-sizing: border-box;
		min-height: 22rem;
		max-height: none;
		color: var(--ink);
		resize: vertical;
	}
	.hint {
		margin: 0;
		font-size: 12px;
		color: var(--ink-soft);
	}
	.path {
		margin: 0;
		font-family: var(--mono);
		font-size: 11px;
		color: var(--ink-faint);
	}
	@media (max-width: 640px) {
		.grid {
			grid-template-columns: minmax(0, 1fr);
		}
		.list {
			border-right: 0;
			padding-right: 0;
		}
	}
</style>
