<script lang="ts">
	// The left column's frame: the quilt's name, the fold and Settings at its head; two tabs choosing the primary view, **Docs** (reading and writing) and **Review** (the quilt's management); beneath them that view's column; and a foot, in both views. Folded, it is a narrow rail keeping what must stay in reach: unfold and the foot. Search is ⌘K alone; what is wrong is Review › Problems, which counts it.
	//
	// What stands in the frame is drawn by its children in `column/`, each its own to change. Under **Review**, the sections (`ReviewNav`). Under **Docs**, a page's own panel where it registers one (the graph's filters), else the project's files (`FilesShelf`), the documents listed by name (`DocumentList`) and the Library (`LibraryShelf`, whose dialog is `LibraryAdd`), and beneath them, past a line the reader drags up and down, the Outline of the document in the focused pane; the two scroll apart. At the foot, `AgentStatus`. A result is read in the document that holds it (V7), so the column lists no nodes.
	import Contents from './Contents.svelte';
	import AgentStatus from './column/AgentStatus.svelte';
	import DocumentList from './column/DocumentList.svelte';
	import FilesShelf from './column/FilesShelf.svelte';
	import LibraryAdd from './column/LibraryAdd.svelte';
	import LibraryShelf from './column/LibraryShelf.svelte';
	import ReviewNav from './column/ReviewNav.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { isAgentDocument } from '$lib/manifest/documents';
	import { documentLabel } from '$lib/workspace/names';
	import { onMount } from 'svelte';
	import { can } from '$lib/write';
	import Settings from './Settings.svelte';
	import { COLUMN_MAX, COLUMN_MIN, prefs } from '$lib/prefs.svelte';
	import { route } from '$lib/paths';
	import type { ShellProps } from './props';
	import type { Master } from '$lib/manifest/types';
	import { reviewLanding, sectionsOf } from '$lib/review/sections';

	let { label, primary, docsHref, indexes, masters, currentDoc, onDocument, contents, currentSection, children, rail, panel, panelLabel }: ShellProps = $props();

	let readOnly = $state(false);
	onMount(() => { void can('review-accept').then((yes) => readOnly = !yes); });
	const reviewPerspective = $derived(store.manifest?.reviewer?.name
		? `Review status for ${store.manifest.reviewer.name}`
		: Object.values(store.manifest?.keys ?? {}).some((key) => key.acceptance) ? 'Review perspective unspecified' : '');

	// **On a narrow window the column goes first** (plan 0.13 §7): below 1200px the workspace needs the width, so the column shows folded whatever the reader's stored choice, and the fold opens it for this visit without rewriting that choice. A window widened again shows the stored choice.
	const SQUEEZED = 1200;
	let windowWidth = $state(typeof window === 'undefined' ? SQUEEZED : window.innerWidth);
	let peek = $state<boolean | null>(null);
	const squeezed = $derived(windowWidth < SQUEEZED);
	const shown = $derived(squeezed ? (peek ?? false) : prefs.panel);
	$effect(() => {
		if (!squeezed) peek = null;
	});
	function fold(): void {
		if (squeezed) peek = !shown;
		else prefs.panel = !prefs.panel;
	}

	// The documents by whose they are, which the files' tree and the list of documents both draw from: the person's drafts, the agent's copies, and the closed ones.
	const own = $derived(masters.filter((m) => !m.closed && !m.context_only && !isAgentDocument(m)));
	const withAgent = $derived(masters.filter((m) => !m.closed && !m.context_only && isAgentDocument(m)));
	const closed = $derived(masters.filter((m) => m.closed));
	// an agent's copy is read beside the document it copies, so it sits beneath that document's row; one whose document is not listed (closed, context-only, gone) stands on its own after them
	const copiesOf = (path: string) => withAgent.filter((m) => m.copy_of === path);
	const unplaced = $derived(withAgent.filter((m) => !own.some((o) => o.path === m.copy_of)));
	// a copy of one section says which, since several sections of one document may each have a copy
	const section = (m: Master) => (m.scope?.kind === 'section' ? m.scope.title ?? m.scope.key ?? '' : '');
	// The file name, not the typeset title: two drafts of one paper share a title and differ only in their path, which is what the author types and what the read view's URL names them by; the path itself where two files share a name.
	const filename = (path: string) => documentLabel(masters, path);
	const outline = $derived(onDocument && contents.length > 0);
	// Review's sections, each with what waits for the author there
	const sections = $derived(store.manifest ? sectionsOf(store.manifest) : []);

	// The line between the documents and the outline: where it stands is a preference, drawn at most once a frame while it is dragged and stored at the drop, as the pane divider is.
	const STEP = 0.03;
	let sectionsBox = $state<HTMLElement | null>(null);
	let live = $state<number | null>(null);
	let box: DOMRect | null = null;
	let next: number | null = null;
	let painting = 0;
	const clamp = (v: number) => Math.min(0.85, Math.max(0.15, v));
	const share = $derived(live ?? prefs.outline);
	function grab(e: PointerEvent): void {
		if (!sectionsBox) return;
		// the press's default would start a text selection, or a native drag of a link the line passes, which takes the pointer away mid-drag
		e.preventDefault();
		box = sectionsBox.getBoundingClientRect();
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		drag(e);
	}
	function drag(e: PointerEvent): void {
		if (!box) return;
		next = clamp((e.clientY - box.top) / (box.height || 1));
		painting ||= requestAnimationFrame(() => {
			painting = 0;
			live = next;
		});
	}
	function drop(e: PointerEvent): void {
		if (!box) return;
		(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
		cancelAnimationFrame(painting);
		painting = 0;
		if (next !== null) prefs.outline = next;
		live = next = box = null;
	}
	function nudge(e: KeyboardEvent): void {
		if (e.key === 'ArrowUp') prefs.outline = clamp(prefs.outline - STEP);
		else if (e.key === 'ArrowDown') prefs.outline = clamp(prefs.outline + STEP);
		else return;
		e.preventDefault();
	}

	// The line between the column and the panes moves as the outline's does, sideways: the column's width is a preference, drawn at most once a frame while it is dragged and stored at the drop.
	const WIDEN = 16;
	let panelBox = $state<HTMLElement | null>(null);
	let liveWidth = $state<number | null>(null);
	let left: number | null = null;
	let nextWidth: number | null = null;
	let sizing = 0;
	const fit = (v: number) => Math.round(Math.min(COLUMN_MAX, Math.max(COLUMN_MIN, v)));
	const width = $derived(liveWidth ?? prefs.column);
	function grabEdge(e: PointerEvent): void {
		if (!panelBox) return;
		e.preventDefault();
		left = panelBox.getBoundingClientRect().left;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		dragEdge(e);
	}
	function dragEdge(e: PointerEvent): void {
		if (left === null) return;
		nextWidth = fit(e.clientX - left);
		sizing ||= requestAnimationFrame(() => {
			sizing = 0;
			liveWidth = nextWidth;
		});
	}
	function dropEdge(e: PointerEvent): void {
		if (left === null) return;
		(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
		cancelAnimationFrame(sizing);
		sizing = 0;
		if (nextWidth !== null) prefs.column = nextWidth;
		liveWidth = nextWidth = left = null;
	}
	function nudgeEdge(e: KeyboardEvent): void {
		if (e.key === 'ArrowLeft') prefs.column = fit(prefs.column - WIDEN);
		else if (e.key === 'ArrowRight') prefs.column = fit(prefs.column + WIDEN);
		else return;
		e.preventDefault();
	}
</script>

<svelte:window bind:innerWidth={windowWidth} />

<div class="shell-c" style:--column-width="{width}px">
	<div class="panel" class:away={!shown} data-testid="column" bind:this={panelBox}>
		{#if !shown}
			<!-- folded: what must stay in reach, one above the other -->
			<button class="fold" title="Show the column" aria-label="Show the column" aria-expanded="false" data-testid="panel-fold" onclick={fold}>»</button>
			<AgentStatus folded />
		{:else}
			<div class="head">
				<a href={route('/')} class="name" data-testid="quilt-name">{label}</a>
				<Settings {indexes} />
				<button class="fold" title="Hide the column" aria-label="Hide the column" aria-expanded="true" data-testid="panel-fold" onclick={fold}>«</button>
			</div>
			<nav class="primary" aria-label="Primary views">
				<!-- back to Docs returns to the workspace's address, which names the place a link last sent a tab to; each pane puts the reader back where they were, so neither scrolling nor focus is let go to that place first -->
				<a
					href={docsHref || route('/')}
					class:on={primary === 'docs'}
					aria-current={primary === 'docs' ? 'page' : undefined}
					data-sveltekit-noscroll=""
					data-sveltekit-keepfocus=""
					data-testid="primary-docs">Docs</a
				>
				<!-- a corpus that declares no review has no Review; one that says nothing either way keeps it -->
				{#if store.manifest?.publishes?.review !== false}<a href={reviewLanding(sections)} class:on={primary === 'review'} aria-current={primary === 'review' ? 'page' : undefined} data-testid="primary-review">Review</a>{/if}
			</nav>
			<!-- Whose review a read-only view shows is said once, under the quilt it belongs to, and never above the document. -->
			{#if readOnly && reviewPerspective}<p class="review-perspective">{reviewPerspective}</p>{/if}
			<div class="sections" bind:this={sectionsBox}>
				{#if primary === 'review'}
					<ReviewNav {sections} />
				{/if}
				{#if panel}
					<p class="rail-label">{panelLabel}</p>
					<div class="page-panel rail-scroll">{@render panel()}</div>
				{:else if primary === 'docs'}
					<div class="part docs-part rail-scroll" data-testid="docs-part" style:flex={outline ? `0 0 ${share * 100}%` : '1 1 auto'}>
						<FilesShelf {masters} {own} {copiesOf} {section} />
						<DocumentList {own} {unplaced} {closed} {copiesOf} {section} {filename} {onDocument} {currentDoc} />
						<LibraryShelf />
					</div>
					{#if outline}
						<!-- A separator that takes focus is a widget in ARIA's own terms, with the arrow keys and aria-valuenow this one has. -->
						<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
						<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
						<div
							class="outline-divider"
							class:moving={live !== null}
							role="separator"
							tabindex="0"
							aria-label="Resize the outline"
							aria-orientation="horizontal"
							aria-valuenow={Math.round(share * 100)}
							aria-valuemin={15}
							aria-valuemax={85}
							data-testid="outline-divider"
							onpointerdown={grab}
							onpointermove={drag}
							onpointerup={drop}
							onpointercancel={drop}
							onkeydown={nudge}
						></div>
						<!-- the focused pane's document's sections, beneath the documents and scrolled apart from them -->
						<div class="part outline-part rail-scroll" data-testid="outline">
							<p class="rail-label outline-label">Outline <span class="aside">{filename(currentDoc)}</span></p>
							<Contents entries={contents} masterPath={currentDoc} current={currentSection} />
						</div>
					{/if}
				{/if}
			</div>
			<!-- Pinned outside the scroll (S5), in both views: writes land in the selected session whatever is shown, so a reader must never go looking for where their work will go. -->
			<AgentStatus />
			<!-- the column's edge, which the reader drags sideways as they drag the outline's line up and down -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<div
				class="column-divider"
				class:moving={liveWidth !== null}
				role="separator"
				tabindex="0"
				aria-label="Resize the column"
				aria-orientation="vertical"
				aria-valuenow={width}
				aria-valuemin={COLUMN_MIN}
				aria-valuemax={COLUMN_MAX}
				data-testid="column-divider"
				onpointerdown={grabEdge}
				onpointermove={dragEdge}
				onpointerup={dropEdge}
				onpointercancel={dropEdge}
				onkeydown={nudgeEdge}
			></div>
		{/if}
	</div>

	<div class="content">
		{@render children()}</div>
	{#if rail}<aside class="right rail-scroll">{@render rail()}</aside>{/if}
</div>

<LibraryAdd />

<style>
	.review-perspective { margin: 0 0 var(--gap-tight); font-size: 11.5px; color: var(--ink-soft); overflow-wrap: anywhere; }
	.shell-c {
		display: grid;
		grid-template-columns: var(--column-width, var(--rail-left)) minmax(0, 1fr) auto;
		min-height: 100vh;
	}
	/* The column's edge is its border, drawn by the line the reader drags, with room inside it to take hold of. It stands in the column's own stacking, so the boxes the column opens float over it. */
	.panel:not(.away) {
		border-right: 0;
	}
	.column-divider {
		position: absolute;
		top: 0;
		bottom: 0;
		right: 0;
		width: 8px;
		z-index: 1;
		cursor: col-resize;
		touch-action: none;
	}
	.column-divider::before {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		right: 0;
		border-right: 1px solid var(--rule);
	}
	.column-divider:hover::before,
	.column-divider.moving::before,
	.column-divider:focus-visible::before {
		border-right-color: var(--link);
	}
	.column-divider:focus-visible {
		outline: none;
	}
	/* folded, the column is a narrow rail, not a 252px empty gutter */
	.shell-c:has(.panel.away) {
		grid-template-columns: var(--rail-folded) minmax(0, 1fr) auto;
	}
	.panel {
		background: var(--leaf);
		border-right: 1px solid var(--rule);
		padding: var(--gap) 14px;
		position: sticky;
		z-index: 10;
		top: 0;
		height: 100vh;
		display: flex;
		flex-direction: column;
		gap: var(--gap-hair);
		overflow: hidden;
		z-index: 20;
	}
	.sections {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: var(--gap-hair);
	}
	/* A label keeps its own height; the documents and the outline take the rest and scroll apart, and a page's own panel takes all of it. */
	.sections > :global(*:not(.page-panel):not(.part)) {
		flex: 0 0 auto;
	}
	/* folded: unfold, and at the foot the session's dot */
	.panel.away {
		align-items: center;
		padding-left: 4px;
		padding-right: 4px;
		gap: 12px;
	}
	/* the two primary views: one line of two words, the current one underlined */
	.primary {
		display: flex;
		gap: 16px;
		margin: 0 0 var(--gap-tight);
		border-bottom: 1px solid var(--rule);
		font-size: 12.5px;
	}
	.primary a {
		padding: 4px 0 6px;
		color: var(--ink-soft);
		margin-bottom: -1px;
	}
	.primary a:hover {
		color: var(--ink);
		text-decoration: none;
	}
	.primary a.on {
		color: var(--ink);
		box-shadow: inset 0 -2px 0 var(--accent);
	}
	.fold {
		font: inherit;
		font-size: 11px;
		line-height: 1;
		color: var(--ink-faint);
		background: none;
		border: 0;
		padding: 2px 3px;
		cursor: pointer;
	}
	.fold:hover {
		color: var(--ink);
	}
	.page-panel {
		flex: 1;
		min-height: 0;
	}
	.head .name {
		font-size: 13px;
		color: var(--ink);
		font-weight: 500;
	}
	.head .name:hover {
		text-decoration: none;
	}
	.head {
		display: flex;
		align-items: center;
		gap: var(--gap-tight);
		margin-bottom: var(--gap-hair);
	}
	.head .name {
		margin-right: auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.content {
		min-width: 0;
	}
	aside.right {
		width: var(--rail-right);
		border-left: 1px solid var(--rule);
		padding: var(--gap);
		position: sticky;
		top: 0;
		max-height: 100vh;
	}
	/* the documents and the outline, each scrolling on its own, the line between them a few pixels of target round one hairline */
	.part {
		min-height: 0;
		overflow: auto;
	}
	.outline-part {
		flex: 1 1 0;
	}
	.outline-part :global(.contents) {
		margin: 0 0 var(--gap-tight) 6px;
	}
	.outline-divider {
		flex: none;
		height: 9px;
		margin: 0 -14px;
		cursor: row-resize;
		position: relative;
		touch-action: none;
	}
	.outline-divider::before {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		top: 4px;
		border-top: 1px solid var(--rule);
	}
	.outline-divider:hover::before,
	.outline-divider.moving::before,
	.outline-divider:focus-visible::before {
		border-top-color: var(--link);
	}
	.outline-divider:focus-visible {
		outline: none;
	}
	.outline-label .aside {
		text-transform: none;
		letter-spacing: 0;
	}
	/* A graph needs room beside its selection; on a narrow screen the selection follows it. */
	@media (max-width: 800px) {
		.shell-c:has(:global(main.graph)) > .panel { grid-row: 1 / span 2; }
		.shell-c:has(:global(main.graph)) > .content { grid-column: 2; grid-row: 1; }
		.shell-c:has(:global(main.graph)) > aside.right { grid-column: 2; grid-row: 2; width: auto; max-height: none; position: static; border-left: 0; border-top: 1px solid var(--rule); }
		.shell-c :global(main.graph) { height: 70vh; min-height: 400px; }
	}
</style>
