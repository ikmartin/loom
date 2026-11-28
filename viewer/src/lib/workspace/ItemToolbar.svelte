<script lang="ts">
	// A pane's toolbar, one row in the pane's own flow beneath its tabs, drawn by every pane for every kind, dimmer in the one not focused. At its left the item's views; at its right **Ask your agent**, which opens the box that copies a request about the item (`agents/AskAgent`), then **New note**, for the whole item, where the kind can be linked to and a publisher runs it, then **Annotate**, where the kind has tools that write, which shows them right after it in the same row or puts them away, then the kind's bar, a document's **history ▾**, compare's counter and stop while the two panes are compared, then **view ▾**, the menu holding every other control in full words, which always ends with turning every annotation in this pane off or on, a control with no key, since a stray letter must never hide what a reader is looking at. What the tool in hand does is one quiet line under the row, over the page's head. Each control acts on its own pane only; compare, started from a draft's history, is the one that reaches across.
	//
	// The row never runs past its end: as it narrows, Ask your agent and New note lose their words, then Annotate, Changes, Comments and Notes, then the groups of tools move, the last first, into the menu a ˅ after the tools opens (`fold.ts`); the bar, clipped at its left, gives way only once every group is there.
	import { flushSync, untrack, type Snippet } from 'svelte';
	import Icon from '$lib/components/Icon.svelte';
	import Popover from '$lib/components/Popover.svelte';
	import { annotateTools } from './annotateTools.svelte';
	import CompareControls from './CompareControls.svelte';
	import { foldedAt, MOST, WORDS, type ToolsAt } from './fold';
	import PaneViews from './PaneViews.svelte';
	import ToolbarItem from './ToolbarItem.svelte';
	import ToolbarMenu from './ToolbarMenu.svelte';
	import { getPane } from './state.svelte';
	import { setStrip, strips } from './strip.svelte';
	import { workspace } from './store.svelte';
	import { newNote } from '$lib/notes/newNote';
	import { notes as notesWords } from '$lib/words/notes';
	import { agents as agentsWords } from '$lib/words/agents';
	import { frame } from '$lib/words/frame';
	import { askAbout } from '$lib/agents/asking.svelte';
	import type { Place } from '$lib/agents/ask';
	import { can } from '$lib/write';

	let {
		name,
		bar,
		tools,
		history,
		view,
		hint = '',
		on = false,
		note,
		ask
	}: {
		/** The item's name, for every control's accessible name. */
		name: string;
		/** What stands on the bar before *view*; omitted when nothing does, and then no divider is drawn. */
		bar?: Snippet;
		/** The tools that write, drawn after Annotate while it is on, given where (`ToolsAt`): rendered once for the row and once for the menu, each group in one of the two. Omitted where the kind has none, and then there is no Annotate. */
		tools?: Snippet<[ToolsAt]>;
		/** A document's history menu (HistoryMenu), after the bar. */
		history?: Snippet;
		/** The kind's lines of the *view* menu (ToolbarItem), an `hr` between groups; the pane's own line follows them. */
		view?: Snippet;
		/** A mode inside *view* is on: the dot on *view* says so. */
		on?: boolean;
		/** What the tool in hand does, one line under the row; '' for none. */
		hint?: string;
		/** The whole item as New note is given it: a `quilt:` link and a name; omitted where the kind has no link. */
		note?: { link: string; title: string };
		/** What Ask your agent is about, asked as it is pressed; omitted where the kind has no link. */
		ask?: () => Place[];
	} = $props();

	let notes = $state(false);
	$effect(() => {
		void can('new-note').then((ok) => (notes = ok));
	});

	const pane = getPane();
	const hidden = $derived(workspace.hidesNotes(pane.index));
	// the counter and stop while comparing, in the focused pane
	const comparing = $derived(workspace.comparing && workspace.focus === pane.index);
	// the line under the bar stays with the item it was first drawn for, and goes when the pane turns to another
	const strip = $derived(strips[pane.index]);
	let drawnFor = '';
	$effect(() => {
		const [s, n] = [strip, name];
		untrack(() => {
			if (!s) drawnFor = '';
			else if (!drawnFor) drawnFor = n;
			else if (drawnFor !== n) {
				drawnFor = '';
				setStrip(pane.index, undefined);
			}
		});
	});

	// how far the row is folded to fit (`fold.ts`), and whether the menu holding the folded tools is open
	let fold = $state(0);
	let more = $state(false);
	const terse = $derived(fold >= WORDS);
	const folded = $derived(foldedAt(fold));
	const shown = $derived(!!tools && annotateTools.open);
	$effect(() => {
		if (!shown || !folded) more = false;
	});

	let end = $state<HTMLElement | null>(null);
	let barBox = $state<HTMLElement | null>(null);

	/** Whether anything on the row is cut: the row past its end, or the bar clipped at its left. */
	function cut(): boolean {
		const over = (el: HTMLElement | null) => !!el && el.scrollWidth > el.clientWidth + 1;
		return over(end) || over(barBox);
	}

	// fold the row as far as it must and no further, measured on every change of its width or of what stands on it; a change inside a menu or popup open from it moves nothing, and none is made while a pointer is pressed, so a control never slides from under a press between its down and its up
	$effect(() => {
		const el = end;
		const row = el?.parentElement;
		if (!el || !row) return;
		const inside = (n: Node) => !!(n instanceof Element ? n : n.parentElement)?.closest('.more-box, .floating, [role="menu"], [role="dialog"]');
		let fitting = false;
		let pressed = false;
		let owed = false;
		const fit = () => {
			if (fitting) return;
			if (pressed) {
				owed = true;
				return;
			}
			fitting = true;
			try {
				while (fold > 0) {
					fold -= 1;
					flushSync();
					if (cut()) {
						fold += 1;
						flushSync();
						break;
					}
				}
				while (fold < MOST && cut()) {
					fold += 1;
					flushSync();
				}
			} finally {
				mo.takeRecords();
				fitting = false;
			}
		};
		const down = () => (pressed = true);
		// after the click the release makes, which a fit before it could move off its control
		const up = () => {
			pressed = false;
			if (!owed) return;
			owed = false;
			setTimeout(fit);
		};
		const ro = new ResizeObserver(() => fit());
		const mo = new MutationObserver((records) => {
			if (records.some((r) => !inside(r.target))) fit();
		});
		ro.observe(row);
		ro.observe(el);
		mo.observe(el, { childList: true, subtree: true, characterData: true });
		window.addEventListener('pointerdown', down, true);
		window.addEventListener('pointerup', up, true);
		window.addEventListener('pointercancel', up, true);
		return () => {
			ro.disconnect();
			mo.disconnect();
			window.removeEventListener('pointerdown', down, true);
			window.removeEventListener('pointerup', up, true);
			window.removeEventListener('pointercancel', up, true);
		};
	});
</script>

<div class="toolbars" role="group" aria-label={frame.toolbar.controls(name)} data-testid="item-controls">
<div class="toolbar" class:brief={fold >= 1} class:terse data-testid="toolbar-row" data-fold={fold}>
	<PaneViews index={pane.index} />
	<span class="end" bind:this={end}>
		{#if ask}
			{@const a = ask}
			<button type="button" class="row-toggle first" title={agentsWords.ask.hover} aria-label={agentsWords.ask.label(name)} data-testid="toolbar-ask" onclick={() => askAbout(a())}><Icon name="ask" size={14} /><span class="fold-word first">{agentsWords.ask.open}</span></button>
		{/if}
		{#if note && notes}
			{@const n = note}
			<button type="button" class="row-toggle first" title={notesWords.toolbar.hover(n.title)} aria-label={notesWords.toolbar.hover(n.title)} data-testid="toolbar-new-note" onclick={() => void newNote(n)}><Icon name="note" size={14} /><span class="fold-word first">{notesWords.toolbar.label}</span></button>
		{/if}
		{#if tools}
			<button type="button" class="row-toggle" class:on={annotateTools.open} aria-expanded={annotateTools.open} title={frame.toolbar.annotate.hover(annotateTools.open)} aria-label={frame.toolbar.annotate.name(name)} data-testid="toggle-annotation-row" onclick={() => annotateTools.set(!annotateTools.open)}
				><Icon name="highlighter" size={14} /><span class="fold-word">{frame.toolbar.annotate.label}</span></button
			>
		{/if}
		{#if tools && shown}
			<span class="tools" data-testid="annotate-tools">
				{@render tools({ menu: false, folded })}
				{#if folded}
					<Popover bind:open={more} placement="below" align="start" testid="annotate-menu" role="group" label={frame.toolbar.annotate.menu(name)}>
						{#snippet trigger()}
							<button type="button" class="more" class:on={more} aria-haspopup="true" aria-expanded={more} title={frame.toolbar.annotate.more} aria-label={frame.toolbar.annotate.moreName(name)} data-testid="annotate-more" onclick={() => (more = !more)}><Icon name="caret" size={12} /></button>
						{/snippet}
						<span class="more-box">{@render tools({ menu: true, folded })}</span>
					</Popover>
				{/if}
			</span>
			{#if bar}<span class="sep" aria-hidden="true"></span>{/if}
		{/if}
		{#if bar}<span class="bar" bind:this={barBox}>{@render bar()}</span>{/if}
		{#if history}{@render history()}{/if}
		{#if comparing}<CompareControls />{/if}
		<ToolbarMenu label={frame.toolbar.view} name={frame.toolbar.viewName(name)} menuName={frame.toolbar.viewMenu(name)} testid="toolbar-view" menuTestid="toolbar-menu" divided={!!bar || !!history || comparing} dot={on || hidden}>
			{#if view}{@render view()}<hr />{/if}
			<ToolbarItem label={frame.toolbar.hide(hidden)} name={frame.toolbar.hideName(hidden, name)} testid="toggle-hide-notes" onclick={() => workspace.hideNotes(pane.index, !hidden)} />
		</ToolbarMenu>
	</span>
</div>
	{#if hint && !strip}<div class="hint" role="status" data-testid="annotate-hint">{hint}</div>{/if}
	{#if strip}
		<div class="strip" class:refused={strip.refused} role={strip.refused ? 'alert' : 'status'} data-testid={strip.testid}>
			<span class="said">{strip.text}</span>
			{#each strip.acts ?? [] as a (a.testid)}<button type="button" class="btn small" class:primary={a.primary} disabled={strip.busy} data-testid={a.testid} onclick={a.run}>{a.label}</button>{/each}
			{#if !strip.acts?.length}<button type="button" class="close" aria-label={frame.toolbar.close} data-testid="strip-close" onclick={() => setStrip(pane.index, undefined)}>×</button>{/if}
		</div>
	{/if}
</div>

<style>
	/* the toolbar's row in the pane's flow under its tabs, never over the page */
	.toolbars {
		position: relative;
		flex: none;
	}
	/* the row that reads: the views at its left, the controls at its right */
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		box-sizing: border-box;
		height: var(--toolbar-h);
		padding: 0 8px 0 0;
		font-family: var(--sans);
		font-size: 12.5px;
		color: var(--ink-soft);
		white-space: nowrap;
		background: var(--sheet);
		border-bottom: 1px solid var(--rule);
		transition: opacity 0.15s ease;
	}
	/* in a narrow pane the row folds first (the script's fit), then the bar gives way, clipped at its left, so view ▾ is always whole */
	.end {
		margin-left: auto;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 2px;
		min-width: 0;
		overflow: hidden;
	}
	.bar {
		display: flex;
		align-items: center;
		gap: 2px;
		min-width: 0;
		overflow: hidden;
		flex: 0 1 auto;
		direction: rtl;
	}
	.bar > :global(*) {
		direction: ltr;
	}
	.end > :global(:not(.bar)) {
		flex: none;
	}
	.row-toggle {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		height: 24px;
		margin-right: 6px;
		padding: 0 7px;
		font: inherit;
		color: var(--ink-soft);
		background: none;
		border: 1px solid transparent;
		border-radius: 6px;
		cursor: pointer;
	}
	/* folded: a control's icon alone, its word in its hover and accessible name; Ask your agent's and New note's (`.first`) first, then every `.fold-word` on the row, Annotate's and the bar's Changes, Comments and Notes */
	.brief .row-toggle.first,
	.terse .row-toggle {
		margin-right: 2px;
		padding: 0 6px;
	}
	.brief .first .fold-word,
	.terse :global(.fold-word) {
		display: none;
	}
	.row-toggle:hover {
		color: var(--ink);
		background: var(--leaf);
	}
	.row-toggle.on {
		color: var(--ink);
		background: var(--accent-wash);
		border-color: color-mix(in srgb, var(--accent) 35%, transparent);
	}
	/* the tools that write, right after Annotate, then the ˅ to those that did not fit */
	.tools {
		display: inline-flex;
		align-items: center;
		gap: 2px;
		margin-right: 2px;
	}
	.more {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 24px;
		padding: 0;
		color: var(--ink-soft);
		background: none;
		border: 0;
		border-radius: 4px;
		cursor: pointer;
	}
	.more:hover,
	.more.on {
		color: var(--ink);
		background: var(--leaf);
	}
	.more-box {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 2px;
		padding: 4px;
	}
	.sep {
		width: 1px;
		height: 16px;
		margin: 0 6px 0 4px;
		background: var(--rule);
	}
	/* under the bar, over the page's head, at the bar's right where the control that asked stands */
	.strip {
		position: absolute;
		top: calc(100% + 4px);
		right: 8px;
		z-index: 5;
		display: flex;
		align-items: center;
		gap: 8px;
		max-width: calc(100% - 16px);
		padding: 6px 8px 6px 12px;
		white-space: normal;
		color: var(--ink);
		background: var(--sheet);
		border: 1px solid var(--rule-strong);
		border-radius: 8px;
		box-shadow: 0 2px 8px rgb(0 0 0 / 0.08);
	}
	/* the hint: one quiet line under the bar, across it, over the page's head */
	.hint {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		z-index: 5;
		box-sizing: border-box;
		padding: 4px 12px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 12px;
		color: var(--ink-soft);
		background: var(--leaf);
		border-bottom: 1px solid var(--rule);
		pointer-events: none;
	}
	.strip.refused .said {
		color: var(--state-stale);
	}
	.close {
		font: inherit;
		font-size: 15px;
		line-height: 1;
		color: var(--ink-soft);
		background: none;
		border: 0;
		cursor: pointer;
	}
</style>
