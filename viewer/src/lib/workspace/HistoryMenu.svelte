<script lang="ts">
	// **history ▾** on a document's toolbar (plan 0.20.6, 0.25.5): `record this version…`, which names and records the version in place, its live text, and its versions newest first, each named by the act it was kept at and with a `compare` at its right, the newest twelve and then a line that lists the rest in the menu; then its live agent copies to compare with. A landmark of the draft carries the same menu, and an agent copy one line, for its source. Choosing a version shows it in this tab's place, at the result the reader was at; choosing `compare` opens the other beside and compares the two, and choosing it again stops. Nothing here leaves Docs: Review › History holds the same versions, and none of its lines go there. Drawn only where there is a history to list (`historyOf`).
	import { tick } from 'svelte';
	import { shortDate } from '$lib/badges';
	import { said } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import { landed } from '$lib/manifest/updating.svelte';
	import type { CanonDoc } from '$lib/manifest/types';
	import { message } from '$lib/shell/message.svelte';
	import { docs } from '$lib/words/docs';
	import { uncomparable } from './compare.svelte';
	import { historyOf } from './history';
	import type { Item } from './item';
	import { getPane } from './state.svelte';
	import { workspace } from './store.svelte';
	import ToolbarItem from './ToolbarItem.svelte';
	import ToolbarMenu from './ToolbarMenu.svelte';
	import { compareWith, comparingWith, turnTo } from './versions';
	import { versionLabel } from '$lib/review/timeline';
	import { can, write } from '$lib/write';

	/** How many versions the menu lists before its line for the older ones. */
	const SHOWN = 12;
	const w = docs.history;

	let { item, name, divided = false }: { item: Item; name: string; divided?: boolean } = $props();

	const m = $derived(store.manifest!);
	const pane = getPane();
	const history = $derived(historyOf(m, item.id));
	let records = $state(false);
	$effect(() => {
		void can('history-record').then((yes) => (records = yes));
	});
	/** The older versions are listed in the menu. */
	let all = $state(false);
	/** The field that names a version to record is open. */
	let naming = $state(false);
	let label = $state('');
	let field = $state<HTMLInputElement | null>(null);
	let go = $state<HTMLButtonElement | null>(null);
	// the menu lists only what pairs, so the one reason compare cannot start is the window's width
	const why = $derived(workspace.narrow ? uncomparable(true) : '');
	const file = (p: string) => p.split('/').pop() ?? p;
	const stem = (p: string) => file(p).replace(/\.tex$/, '');
	const when = (c: CanonDoc) => [c.step ? `step ${Number(c.step)}` : '', c.when ? shortDate(c.when) : ''].filter(Boolean).join(' · ');

	async function startNaming(): Promise<void> {
		naming = !naming;
		await tick();
		field?.focus();
	}

	/** Records the draft as it stands under the name given, and says so in the column's message. The field is put away only after the click has closed the menu, which a line greyed by then would not. */
	async function record(doc: string): Promise<void> {
		const named = label.trim();
		if (!named) return;
		const done = await write('history-record', { document: doc, name: named });
		naming = false;
		label = '';
		if (done.ok) {
			await landed();
			message.post(w.recorded(file(doc), named));
		} else message.post(said({ code: done.error?.code ?? 'failed', message: '' }));
	}
</script>

{#snippet row(id: string, label: string, testid: string, aside = '', title = '')}
	<div class="row" role="none" title={title || undefined}>
		<button type="button" class="version" role="menuitemradio" tabindex="-1" aria-checked={id === item.id} aria-label={w.versionName(label, name)} data-testid="history-version-{testid}" onclick={() => turnTo(pane.index, item, id)}
			><span class="mark" aria-hidden="true">{id === item.id ? '●' : ''}</span><span class="lab">{label}</span>{#if aside}<span class="aside">{aside}</span>{/if}</button
		>
		{#if id !== item.id}
			<button
				type="button"
				class="cmp"
				role="menuitemcheckbox"
				tabindex="-1"
				aria-checked={comparingWith(item, id)}
				aria-disabled={why ? 'true' : undefined}
				aria-label={w.compareName(name, label)}
				title={why || undefined}
				data-testid="history-compare-{testid}"
				onclick={() => !why && compareWith(pane.index, item, id)}>{w.compare}</button
			>
		{/if}
	</div>
{/snippet}

{#if history}
	<ToolbarMenu label={w.label} name={w.name(name)} menuName={w.menu(name)} testid="toolbar-history" menuTestid="history-menu" {divided} width={320}>
		{#if history.of === 'draft'}
			{@const doc = history.draft}
			{#if records}
				<button type="button" class="line" role="menuitem" tabindex="-1" aria-expanded={naming} aria-label={w.recordName(name)} data-testid="history-record" onclick={() => void startNaming()}>{w.record}</button>
				{#if naming}
					<div class="naming" role="none">
						<input
							class="name"
							bind:this={field}
							bind:value={label}
							placeholder={w.recordField}
							aria-label={w.recordFieldName(name)}
							data-testid="history-record-name"
							onkeydown={(e) => {
								if (e.key === 'Home' || e.key === 'End') e.stopPropagation();
								// the menu closes onto its word, which the same Enter would otherwise press and open again
								if (e.key === 'Enter') e.preventDefault();
								if (e.key === 'Enter' && label.trim()) go?.click();
							}}
						/>
						<button type="button" class="go" role="menuitem" tabindex="-1" bind:this={go} aria-disabled={label.trim() ? undefined : 'true'} aria-label={w.recordGoName(name)} data-testid="history-record-go" onclick={() => void record(doc)}>{w.recordGo}</button>
					</div>
				{/if}
				<hr />
			{/if}
			{@render row(doc, w.live, 'live')}
			{#each all ? history.landmarks : history.landmarks.slice(0, SHOWN) as c (c.path)}{@render row(c.path, versionLabel(c), c.name ?? c.stem, when(c))}{/each}
			{#if history.landmarks.length > SHOWN}
				<button type="button" class="line quiet" role="menuitem" tabindex="-1" aria-expanded={all} aria-label={w.olderName(name)} data-testid="history-older" onclick={() => (all = !all)}
					>{all ? w.fewer(SHOWN) : w.older(history.landmarks.length - SHOWN)}</button
				>
			{/if}
			{#if history.copies.length}
				<hr />
				{#each history.copies as x (x.path)}
					<ToolbarItem
						label={w.compareWith(file(x.path))}
						name={w.compareName(name, file(x.path))}
						checked={comparingWith(item, x.path)}
						off={why || undefined}
						testid="history-compare-{stem(x.path)}"
						onclick={() => compareWith(pane.index, item, x.path)}
					/>
				{/each}
			{/if}
		{:else}
			<ToolbarItem
				label={w.compareWith(file(history.source))}
				name={w.compareName(name, file(history.source))}
				checked={comparingWith(item, history.source)}
				off={why || undefined}
				testid="history-compare-{stem(history.source)}"
				onclick={() => compareWith(pane.index, item, history.source)}
			/>
		{/if}
	</ToolbarMenu>
{/if}

<style>
	.row {
		display: flex;
		align-items: stretch;
	}
	.version,
	.cmp,
	.line,
	.go {
		font: inherit;
		color: var(--ink);
		text-align: left;
		background: none;
		border: 0;
		cursor: pointer;
	}
	.version {
		flex: 1 1 auto;
		min-width: 0;
		display: flex;
		align-items: baseline;
		gap: 6px;
		padding: 5px 8px 5px 10px;
	}
	.mark {
		flex: none;
		width: 0.8em;
		color: var(--link);
		font-size: 0.8em;
	}
	.lab {
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.aside {
		margin-left: auto;
		padding-left: 10px;
		font-size: 11px;
		color: var(--ink-faint);
		font-variant-numeric: tabular-nums;
	}
	.cmp {
		flex: none;
		padding: 5px 12px 5px 8px;
		font-size: 11.5px;
		color: var(--link);
	}
	.cmp[aria-checked='true'] {
		color: var(--ink);
		background: var(--link-wash);
	}
	.cmp[aria-disabled='true'] {
		color: var(--ink-faint);
		opacity: 0.6;
		cursor: default;
	}
	.line {
		display: block;
		width: 100%;
		padding: 5px 12px;
	}
	.line.quiet {
		color: var(--ink-soft);
	}
	.naming {
		display: flex;
		align-items: center;
		gap: 6px;
		padding: 4px 12px 6px;
	}
	.name {
		flex: 1 1 auto;
		min-width: 0;
		font: inherit;
		padding: 4px 8px;
		color: var(--ink);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 6px;
	}
	.name:focus-visible {
		outline: 2px solid var(--link);
		outline-offset: 0;
	}
	.go {
		flex: none;
		padding: 4px 10px;
		color: var(--link);
		border-radius: 6px;
	}
	.go[aria-disabled='true'] {
		color: var(--ink-faint);
		cursor: default;
	}
	.line:hover,
	.line:focus-visible,
	.go:hover:not([aria-disabled='true']),
	.go:focus-visible,
	.version:hover,
	.version:focus-visible,
	.cmp:hover:not([aria-disabled='true']),
	.cmp:focus-visible {
		background: var(--leaf);
		outline: none;
	}
</style>
