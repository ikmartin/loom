<script lang="ts">
	// The left column's frame: the quilt's name, Settings and the fold at its head; the four views' names, **Docs**, **Library**, **Web** and **Review**, each with a hover card, the only controls that change view (beside ⌘K's palette, which is a person naming where to go and says the view each result opens in); beneath them that view's column; and a foot, in every view: the column's message, the legend of the marks, and the agent's row. Folded, it is a strip of the four names with the fold above them and, at its foot, a dot for a message and the agent's.
	//
	// What stands in the frame is drawn by its children in `column/`, each its own to change. Under **Review**, the sections (`ReviewNav`). Under **Docs**, a page's own panel where it registers one (the graph's filters), else the project's files (`FilesShelf`) and the documents listed by name (`DocumentList`), and beneath them, past a line the reader drags up and down, the Outline of the document in the focused pane; the two scroll apart. The Library's and the Web's columns are theirs. At the foot, `Message`, `Legend` and `AgentStatus`. Every word the frame says is in `$lib/words/frame.ts`.
	import Contents from './Contents.svelte';
	import HoverCard from './HoverCard.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import AgentStatus from './column/AgentStatus.svelte';
	import Legend from './column/Legend.svelte';
	import Message from './column/Message.svelte';
	import LibraryColumn from './column/library/LibraryColumn.svelte';
	import DocumentList from './column/DocumentList.svelte';
	import FilesShelf from './column/FilesShelf.svelte';
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
	import { hovercard } from './hovercards.svelte';
	import { message } from './message.svelte';
	import { VIEWS, type Primary } from './views';
	import { frame } from '$lib/words/frame';
	import { docs } from '$lib/words/docs';

	let { label, primary, docsHref, indexes, masters, currentDoc, onDocument, contents, currentSection, children, rail, panel, panelLabel }: ShellProps = $props();

	let readOnly = $state(false);
	onMount(() => { void can('review-accept').then((yes) => readOnly = !yes); });
	const reviewPerspective = $derived(store.manifest?.reviewer?.name
		? frame.column.perspective(store.manifest.reviewer.name)
		: Object.values(store.manifest?.keys ?? {}).some((key) => key.acceptance) ? frame.column.perspectiveUnnamed : '');

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

	// Each view's name goes to its view: Docs to the reading address, where it was left; Review to its landing; the Library and the Web to their own pages, which keep their place themselves. A corpus that declares no review has no Review; one that says nothing either way keeps it.
	const hrefOf = (v: Primary): string => (v === 'docs' ? docsHref || route('/') : v === 'review' ? reviewLanding(sections) : route(`/${v}`));
	const shownViews = $derived(VIEWS.filter((v) => v !== 'review' || store.manifest?.publishes?.review !== false));

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

<!-- what was just done, said to a screen reader whether the column is open or folded: the region stays mounted and only its words change -->
<div class="sr-only" role="status" aria-live="polite" data-testid="column-message-live">{message.said?.text ?? ''}</div>

<div class="shell-c" class:folded={!shown} style:--column-width="{width}px">
	<div class="panel" class:away={!shown} data-testid="column" bind:this={panelBox}>
		{#if !shown}
			<!-- folded: the fold, then the four names one above the other with their cards beside the strip, and at its foot a dot for the message and the agent's -->
			<button class="ib fold unfold" title={frame.column.show} aria-label={frame.column.show} aria-expanded="false" data-testid="panel-fold" onclick={fold}><Icon name="fold" size={18} /></button>
			<nav class="strip" aria-label={frame.views.nav}>
				{#each shownViews as v (v)}
					<a
						href={hrefOf(v)}
						class:on={primary === v}
						aria-current={primary === v ? 'page' : undefined}
						data-sveltekit-noscroll={v === 'docs' ? '' : undefined}
						data-sveltekit-keepfocus={v === 'docs' ? '' : undefined}
						data-testid="strip-{v}"
						use:hovercard={{ text: frame.views[v].hover, place: 'beside' }}>{frame.views[v].name}</a
					>
				{/each}
			</nav>
			{#if message.said}<button type="button" class="ib said" title={message.said.text} aria-label={message.said.text} data-testid="column-message-dot" onclick={fold}><span class="dot"></span></button>{/if}
			<AgentStatus folded />
		{:else}
			<div class="head">
				<!-- the quilt's name is its name, not a way anywhere: only the four views' names change view -->
				<span class="name" data-testid="quilt-name">{label}</span>
				<!-- the development shelf's links open Docs' pages, so they are offered only in Docs, where following one does not change view -->
				<Settings indexes={primary === 'docs' ? indexes : []} />
				<button class="ib fold" title={frame.column.hide} aria-label={frame.column.hide} aria-expanded="true" data-testid="panel-fold" onclick={fold}><Icon name="fold" size={18} /></button>
			</div>
			<nav class="primary" aria-label={frame.views.nav}>
				<!-- back to Docs returns to the workspace's address, which names the place a link last sent a tab to; each pane puts the reader back where they were, so neither scrolling nor focus is let go to that place first -->
				{#each shownViews as v (v)}
					<a
						href={hrefOf(v)}
						class:on={primary === v}
						aria-current={primary === v ? 'page' : undefined}
						data-sveltekit-noscroll={v === 'docs' ? '' : undefined}
						data-sveltekit-keepfocus={v === 'docs' ? '' : undefined}
						data-testid="primary-{v}"
						use:hovercard={{ text: frame.views[v].hover, place: 'below' }}>{frame.views[v].name}</a
					>
				{/each}
			</nav>
			<!-- Whose review a read-only view shows is said once, under the quilt it belongs to, and never above the document. -->
			{#if readOnly && reviewPerspective}<p class="review-perspective">{reviewPerspective}</p>{/if}
			<div class="sections" bind:this={sectionsBox}>
				{#if primary === 'review'}
					<ReviewNav {sections} />
				{:else if primary === 'library'}
					<LibraryColumn />
				{/if}
				{#if panel}
					<p class="rail-label">{panelLabel}</p>
					<div class="page-panel rail-scroll">{@render panel()}</div>
				{:else if primary === 'docs'}
					<div class="part docs-part rail-scroll" data-testid="docs-part" style:flex={outline ? `0 0 ${share * 100}%` : '1 1 auto'}>
						<FilesShelf {masters} {own} {copiesOf} {section} />
						<DocumentList {own} {unplaced} {closed} {copiesOf} {section} {filename} {onDocument} {currentDoc} />
						<!-- the Library's place in Docs' column is built with the Library view, in its own change -->
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
							aria-label={docs.column.resizeOutline}
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
							<p class="rail-label outline-label">{docs.column.outline} <span class="aside">{filename(currentDoc)}</span></p>
							<Contents entries={contents} masterPath={currentDoc} current={currentSection} />
						</div>
					{/if}
				{/if}
			</div>
			<!-- The foot, pinned outside the scroll in every view: what was just done, the legend of the marks, and the agent's row (S5: writes land in the selected session whatever is shown, so a reader must never go looking for where their work will go). -->
			<div class="foot">
				<Message />
				<Legend />
			</div>
			<AgentStatus />
			<!-- the column's edge, which the reader drags sideways as they drag the outline's line up and down -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<div
				class="column-divider"
				class:moving={liveWidth !== null}
				role="separator"
				tabindex="0"
				aria-label={frame.column.resize}
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

<HoverCard />

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
	/* folded, the column is a strip wide enough for the four names, not a 252px empty gutter */
	.shell-c.folded {
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
	.sections > :global(*:not(.page-panel):not(.part):not(.lv-col)) {
		flex: 0 0 auto;
	}
	/* folded: the fold, the four names, and at the foot a dot for the message and the session's */
	.panel.away {
		align-items: center;
		padding: 10px 0 0;
		gap: var(--gap-hair);
	}
	.strip {
		width: 100%;
		margin-top: var(--gap-tight);
	}
	.strip a {
		display: block;
		width: 100%;
		padding: 6px 0;
		text-align: center;
		font-size: 11px;
		color: var(--ink-faint);
		border-left: 2px solid transparent;
	}
	.strip a:hover {
		color: var(--ink);
		text-decoration: none;
	}
	.strip a.on {
		color: var(--ink);
		font-weight: 500;
		border-left-color: var(--accent);
	}
	/* folded, a message is a dot that opens the column on it, a 28px target */
	.said {
		margin-top: auto;
	}
	.said .dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--ink);
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		margin: -1px;
		padding: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		border: 0;
	}
	.said + :global(.rail-foot) {
		margin-top: var(--gap-tight);
	}
	/* the four views: one line of four words, the current one underlined */
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
	/* an icon control: a 28px target round a 16px glyph */
	.ib {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: none;
		width: 28px;
		height: 28px;
		padding: 0;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.ib:hover {
		color: var(--ink);
		background: var(--ann-neutral-wash);
	}
	/* the strip's fold points the other way, out */
	.unfold {
		transform: scaleX(-1);
	}
	/* the head's Settings toggle is a 28px target round its glyph, as the fold is */
	.head :global(.toggle) {
		width: 28px;
		height: 28px;
		padding: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	/* the foot: the message and the legend, above the agent's row */
	.foot {
		flex: none;
		margin: 0 -14px;
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
