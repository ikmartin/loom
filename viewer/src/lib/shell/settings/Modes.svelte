<script lang="ts">
	// Settings › Modes: the quilt's modes in the order its agents are shown them, from the manifest's `agents.modes`, the list at the left and the chosen one at the right: its "When it fits" line, whether its text is loom's or edited here, whether a newer version from loom waits beside it, and the text as its file holds it.
	import { store } from '$lib/manifest/client.svelte';
	import { modes as words } from '$lib/words/modes';
	import Row from './Row.svelte';

	const list = $derived(store.manifest?.agents?.modes ?? []);
	const layer = $derived(!!store.manifest?.config?.agents.layer);
	let chosen = $state('');
	const current = $derived(list.find((m) => m.name === chosen) ?? list[0]);

	function rows(e: KeyboardEvent): void {
		if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
		e.preventDefault();
		const at = list.findIndex((m) => m.name === current?.name);
		const next = list[Math.max(0, Math.min(list.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)))];
		if (next) chosen = next.name;
	}
</script>

<div class="card">
	<Row id="modes.list" stack>
		{#if !list.length || !current}
			<p class="aside" data-testid="modes-none">{words.none}</p>
		{:else}
			{#if !layer}<p class="aside" data-testid="modes-no-layer">{words.noLayer}</p>{/if}
			<div class="grid" data-testid="modes">
				<div class="list" role="tablist" aria-label={words.list} aria-orientation="vertical" tabindex="-1" onkeydown={rows}>
					{#each list as m (m.name)}
						<button type="button" class="row" class:on={m.name === current.name} role="tab" aria-selected={m.name === current.name} data-testid="mode-tab" data-mode={m.name} onclick={() => (chosen = m.name)}>
							<span class="name">{m.name}</span>
							<span class="state" class:edited={m.edited}>{m.edited ? words.state.edited : words.state.loom}{#if m.newer}<span class="newer" data-testid="mode-tab-newer"> · {words.newer}</span>{/if}</span>
						</button>
					{/each}
				</div>
				<div class="detail" role="tabpanel" data-testid="mode-detail" data-mode={current.name}>
					<div class="top">
						<h4 class="title">{current.name}</h4>
						<span class="badge" class:edited={current.edited} data-testid="mode-state">{current.edited ? words.state.edited : words.state.loom}</span>
					</div>
					{#if current.newer}<p class="note info" data-testid="mode-newer">{words.newerWhat(current.path)}</p>{/if}
					<section>
						<h5>{words.fits}</h5>
						<p class="fits" data-testid="mode-fits">{current.fits || words.noFits}</p>
					</section>
					<section>
						<h5>{words.text}</h5>
						{#if current.text !== undefined}
							<pre class="text" data-testid="mode-text">{current.text}</pre>
							<p class="hint">{words.types}</p>
						{:else}
							<p class="aside" data-testid="mode-no-text">{words.noText}</p>
						{/if}
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
	.detail .note {
		margin: 0;
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
