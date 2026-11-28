<script lang="ts">
	// A text's annotating, in two halves (`part`), both on the toolbar's one row. The half that writes stands after the toolbar's Annotate while it is on, where the publisher takes writes, in two groups (`where`, `fold.ts`): Annotate, Comment and the format menu beside them, then Undo and Redo; a group that does not fit the row is drawn in the menu the toolbar's ˅ opens instead. The half that reads stands on the bar: a document's Changes menu where its text has pending changes (`changes`); the stepper over the annotations and changes in reading order (the arrows, J and K); Comments, counting the annotations here, and Notes, counting and listing the files of the quilt that link here (`backlinks.ts`), which open the list beside the text. The keys are the reading half's, since it is always drawn, and turning the toolbar's Annotate off puts the tool in hand down.
	//
	// Annotate stays on until it is turned off, and selecting words while it is on marks them in the look in hand. Comment leaves a comment at the next place clicked. The format menu sets the look in hand: the Type list (Add new… starts a type the hand takes), the look controls, the line saying what the look was changed from, a type or Plain (Reset, Update it), Save as new type, and Customize, which opens Settings › Annotations. Number keys choose a type while Annotate is on, 0 for Plain. Undo and Redo, and ⌘Z and ⇧⌘Z, go back and forth over this page's annotation writes (`history.svelte.ts`); Delete or Backspace removes the annotation open, with the same undo.
	import { refusalOf } from '$lib/library/said';
	import Icon from '$lib/components/Icon.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { getPane } from '$lib/workspace/state.svelte';
	import { workspace } from '$lib/workspace/store.svelte';
	import { openSettings } from '$lib/shell/settings/opener.svelte';
	import { annotateTools } from '$lib/workspace/annotateTools.svelte';
	import { drawnAt, ROW, type ToolsAt } from '$lib/workspace/fold';
	import { frame } from '$lib/words/frame';
	import { untrack } from 'svelte';
	import { can, write } from '$lib/write';
	import { linkName } from '$lib/workspace/names';
	import type { Snippet } from 'svelte';
	import { entries, hand, lookOf, typeById, typesPayload, withLook, withType, type Annotating, type Side } from './annotating.svelte';
	import { noteFiles } from './backlinks';
	import { docs as docsWords } from '$lib/words/docs';
	import { history, nextRedo, nextUndo, redo, remove, undo } from './history.svelte';
	import { say } from './toasts.svelte';
	import Changed from './Changed.svelte';
	import LookControls from './LookControls.svelte';
	import Sample from './Sample.svelte';
	import TypeList from './TypeList.svelte';

	let {
		notes,
		of,
		part,
		writes = false,
		changes,
		where = ROW,
		groups = 2
	}: {
		notes: Annotating;
		/** Which half: the tools that write, after the toolbar's Annotate, or what reads, on its bar. */
		part: 'read' | 'write';
		/** Where the half that writes is drawn, the row or the menu, and how much of it the menu holds. */
		where?: ToolsAt;
		/** How many groups the host's tools have in all, these two first: 2 alone, 3 in a PDF's bar. */
		groups?: number;
		/** What the tools act on, for their accessible names. */
		of: string;
		/** Whether the publisher takes annotations, which the tools need. */
		writes?: boolean;
		/** A document's Changes menu, first on the reading half. */
		changes?: Snippet;
	} = $props();

	const pane = getPane();
	const m = $derived(store.manifest);
	const types = $derived(m?.annotation_types ?? []);
	const look = $derived(lookOf(m, hand.value));
	/** Plain as the hand holds it, whatever type is held now. */
	const plain = $derived(lookOf(m, withType(m, hand.value, null)));
	const current = $derived(hand.type && types.some((t) => t.id === hand.type) ? hand.type : null);
	const seq = $derived(entries(m, notes));
	const at = $derived(notes.open ? seq.findIndex((e) => e.id === notes.open) : -1);
	/** What the stepper and the list count: annotations, or items where changes are among them. */
	const things = $derived((n: number) => frame.toolbar.reading.count(n, seq.some((e) => e.c)));
	/** What Comments counts: the annotations here; the changes among them in the list have their own count. */
	const said = $derived(seq.filter((e) => e.a).length);
	/** How many files link here: what the Notes list beside the item holds. */
	const notesN = $derived(noteFiles(m, notes.on).length);
	/** What the look in hand was changed from, while it differs from it: the type held, or Plain. */
	const from = $derived(current ? (Object.keys(hand.over).length ? (typeById(m, current)?.name ?? null) : null) : Object.keys(hand.plain).length ? 'Plain' : null);

	let saves = $state(false);
	let deletes = $state(false);
	$effect(() => {
		void can('types-save').then((ok) => (saves = ok));
		void can('delete').then((ok) => (deletes = ok));
	});

	let menu = $state(false);
	let caret = $state<HTMLElement | null>(null);
	let menuEl = $state<HTMLElement | null>(null);
	let place = $state({ left: 0, top: 0 });

	function toggle(tool: 'annotate' | 'comment'): void {
		notes.tool = notes.tool === tool ? null : tool;
	}

	function openMenu(): void {
		menu = !menu;
		if (!menu || !caret) return;
		const r = caret.getBoundingClientRect();
		place = { left: r.left - 24, top: r.bottom + 6 };
	}
	// kept inside the window once its size is known
	$effect(() => {
		const el = menuEl;
		if (!el) return;
		const w = el.offsetWidth;
		const h = el.offsetHeight;
		const left = Math.min(Math.max(12, place.left), window.innerWidth - w - 12);
		const top = Math.min(place.top, Math.max(8, window.innerHeight - h - 12));
		if (left !== place.left || top !== place.top) place = { left, top };
	});
	$effect(() => {
		if (!menu) return;
		const away = (e: PointerEvent) => {
			const t = e.target as Element | null;
			if (!t?.closest?.('.format-menu, [data-testid="format-toggle"]')) menu = false;
		};
		// Escape closes the menu first, before anything else it would close
		const key = (e: KeyboardEvent) => {
			if (e.key !== 'Escape') return;
			e.preventDefault();
			menu = false;
		};
		document.addEventListener('pointerdown', away, true);
		document.addEventListener('keydown', key, true);
		return () => {
			document.removeEventListener('pointerdown', away, true);
			document.removeEventListener('keydown', key, true);
		};
	});

	/** Open Settings › Annotations; with `fork`, a new type started in the look given, which the hand takes once it is saved. */
	function customize(fork?: { look?: import('$lib/manifest/types').Look }): void {
		menu = false;
		openSettings('annotations', fork ? { ...fork, take: { kind: 'hand' } } : null);
	}

	/** Update the type in hand, or the quilt's plain look, to the look in hand, and hold it as it now is. */
	async function update(): Promise<void> {
		if (!from) return;
		const res = await write('types-save', current ? { types: typesPayload(m, current, look) } : { types: typesPayload(m), plain: look });
		if (!res.ok) return say({ title: 'Not updated', lines: [refusalOf(res.error)] });
		void store.refresh();
		reset();
	}

	/** Back to the look under the hand's: its type's, or the quilt's plain look. */
	function reset(): void {
		hand.set(current ? { ...hand.value, over: {} } : { ...hand.value, plain: {} });
	}

	/** Undo or redo, saying loom's refusal where there is one. */
	async function back(d: 'undo' | 'redo'): Promise<void> {
		const why = await (d === 'undo' ? undo() : redo());
		if (why) say({ title: d === 'undo' ? 'Not undone' : 'Not done again', lines: [why] });
	}

	/** Delete the annotation open, as its popup's Delete does; a change open is kept or discarded, never deleted. */
	async function removeOpen(): Promise<void> {
		const id = notes.open;
		if (!id || !m?.annotations[id]) return;
		notes.close();
		const why = await remove(id, m ? linkName(m, `quilt:${id}`) : 'an annotation');
		if (why) say({ title: 'Not deleted', lines: [why] });
	}

	/** Open the next or the previous annotation or change in reading order, scrolled to; one with no mark here is shown in the list. */
	function step(d: number): void {
		const list = seq;
		if (!list.length) return;
		const i = at < 0 ? (d > 0 ? 0 : list.length - 1) : (at + d + list.length) % list.length;
		const id = list[i].id;
		if (!notes.show(id)) {
			notes.close();
			notes.open = id;
			notes.side = 'comments';
		}
	}

	function side(which: Exclude<Side, null>): void {
		notes.side = notes.side === which ? null : which;
	}

	// Annotate turned off puts the tool in hand down, so none is armed out of sight
	$effect(() => {
		if (part !== 'read' || annotateTools.open) return;
		untrack(() => {
			if (notes.tool) notes.tool = null;
		});
	});

	// J and K step, from anywhere in the focused pane but a field; while Annotate is on, a number chooses a type
	$effect(() => {
		if (part !== 'read') return;
		const key = (e: KeyboardEvent) => {
			if (e.altKey || e.defaultPrevented) return;
			if ((e.target as HTMLElement | null)?.closest('input, textarea, select, [contenteditable], [role="dialog"][aria-modal="true"]')) return;
			if (workspace.focus !== pane.index || document.querySelector('[data-testid="settings-window"][open], dialog[open]')) return;
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') {
				if (!writes) return;
				e.preventDefault();
				void back(e.shiftKey ? 'redo' : 'undo');
				return;
			}
			if (e.metaKey || e.ctrlKey) return;
			if ((e.key === 'Delete' || e.key === 'Backspace') && notes.open && m?.annotations[notes.open] && deletes) {
				e.preventDefault();
				void removeOpen();
				return;
			}
			if (e.key === 'j' || e.key === 'k') {
				e.preventDefault();
				step(e.key === 'j' ? 1 : -1);
				return;
			}
			if (notes.tool === 'annotate' && /^[0-9]$/.test(e.key)) {
				const n = Number(e.key);
				const t = n === 0 ? null : types[n - 1];
				if (n > 0 && !t) return;
				e.preventDefault();
				hand.set(withType(m, hand.value, t ? t.id : null));
			}
		};
		window.addEventListener('keydown', key);
		return () => window.removeEventListener('keydown', key);
	});
</script>

{#if part === 'write'}
	{#if writes}
	{@const w = frame.toolbar.annotate}
	{@const marks = drawnAt(where, 0, groups)}
	{@const backs = drawnAt(where, 1, groups)}
	{#if marks || backs}
	<span class="annotate-bar" role="group" aria-label={w.group(of)}>
		{#if marks}
		<span class="split">
			<button type="button" class="tool main" class:on={notes.tool === 'annotate'} aria-pressed={notes.tool === 'annotate'} title={w.mark} aria-label={w.markName(of)} data-testid="tool-annotate" onclick={() => toggle('annotate')}><Icon name="highlighter" size={15} /><Sample {look} /></button>
			<button type="button" class="tool" class:on={notes.tool === 'comment'} aria-pressed={notes.tool === 'comment'} title={w.comment} aria-label={w.commentName(of)} data-testid="tool-comment" onclick={() => toggle('comment')}><Icon name="pin" size={14} /></button>
			<button type="button" class="tool caret" class:on={menu} bind:this={caret} aria-expanded={menu} aria-haspopup="dialog" title={w.format} aria-label={w.formatName(of)} data-testid="format-toggle" onclick={openMenu}><Icon name="caret" size={12} /></button>
		</span>
		{/if}
		{#if marks && backs}<span class="sep" aria-hidden="true"></span>{/if}
		{#if backs}
		<button type="button" class="tool" title={w.undo(nextUndo() ?? '')} aria-label={w.undoName(of)} aria-keyshortcuts="Control+Z Meta+Z" disabled={!history.done.length || history.busy} data-testid="annotate-undo" onclick={() => void back('undo')}><Icon name="undo" size={14} /></button>
		<button type="button" class="tool" title={w.redo(nextRedo() ?? '')} aria-label={w.redoName(of)} aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z" disabled={!history.undone.length || history.busy} data-testid="annotate-redo" onclick={() => void back('redo')}><Icon name="redo" size={14} /></button>
		{/if}
	</span>
	{/if}
	{/if}
{:else}
{@const r = frame.toolbar.reading}
<span class="annotate-bar" role="group" aria-label={r.group(of)}>
	{#if changes}{@render changes()}{/if}
	{#if seq.length}
		{#if changes}<span class="sep" aria-hidden="true"></span>{/if}
		<button type="button" class="tool" title={r.prev} aria-label={r.prevName(of)} aria-keyshortcuts="k" data-testid="step-prev" onclick={() => step(-1)}><Icon name="left" size={14} /></button>
		<span class="count" data-testid="step-count">{at >= 0 ? r.at(at + 1, seq.length) : things(seq.length)}</span>
		<button type="button" class="tool" title={r.next} aria-label={r.nextName(of)} aria-keyshortcuts="j" data-testid="step-next" onclick={() => step(1)}><Icon name="right" size={14} /></button>
	{/if}
	{#if changes || seq.length}<span class="sep" aria-hidden="true"></span>{/if}
	<button type="button" class="tool words" class:on={notes.side === 'comments'} aria-pressed={notes.side === 'comments'} title={r.commentsHover} aria-label={r.commentsName(of, said)} data-testid="open-comments" onclick={() => side('comments')}><Icon name="panel" size={14} /><span class="fold-word">{r.comments}</span><span class="badge">{said}</span></button>
	<button type="button" class="tool words" class:on={notes.side === 'notes'} aria-pressed={notes.side === 'notes'} title={docsWords.beside.hover} aria-label={docsWords.beside.named(of, notesN)} data-testid="open-notes" onclick={() => side('notes')}><Icon name="note" size={14} /><span class="fold-word">{docsWords.beside.title}</span><span class="badge">{notesN}</span></button>
</span>
{/if}

{#if menu && part === 'write'}
	{@const w = frame.toolbar.annotate}
	<div class="format-menu" bind:this={menuEl} role="dialog" aria-label={w.format} style="left: {place.left}px; top: {place.top}px;" data-testid="format-menu">
		<div class="sec">{w.type}</div>
		<TypeList {types} {current} {plain} keys onpick={(id) => hand.set(withType(m, hand.value, id))} onadd={saves ? () => customize({}) : undefined} />
		<div class="sec">{w.look}</div>
		<LookControls {look} onpick={(c) => hand.set(withLook(m, hand.value, c))} />
		{#if from}<Changed name={from} onreset={reset} onupdate={saves ? () => void update() : undefined} />{/if}
		<div class="mfoot">
			{#if saves}<button type="button" class="lnk" data-testid="format-save-type" onclick={() => customize({ look })}>{w.saveType}</button>{/if}
			<button type="button" class="lnk" data-testid="format-customize" onclick={() => customize()}>{w.customize}</button>
		</div>
	</div>
{/if}

<style>
	.annotate-bar {
		display: inline-flex;
		align-items: center;
		gap: 2px;
	}
	.split {
		display: inline-flex;
		align-items: center;
		border: 1px solid var(--rule);
		border-radius: 6px;
	}
	.split .tool {
		border-radius: 0;
	}
	.split .tool + .tool {
		border-left: 1px solid var(--rule);
	}
	.tool {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 5px;
		height: 28px;
		min-width: 28px;
		padding: 0 6px;
		font: inherit;
		color: var(--ink-soft);
		background: none;
		border: 0;
		border-radius: 4px;
		cursor: pointer;
	}
	.tool.caret {
		min-width: 28px;
		padding: 0 2px;
	}
	.tool:hover:not(:disabled) {
		color: var(--ink);
		background: var(--leaf);
	}
	.tool:disabled {
		opacity: 0.35;
		cursor: default;
	}
	.tool.on {
		color: var(--ink);
		background: var(--accent-wash);
	}
	.tool.main :global(.ann-sample) {
		font-family: var(--body-face);
		font-size: 12px;
	}
	.sep {
		width: 1px;
		height: 16px;
		margin: 0 5px;
		background: var(--rule);
	}
	/* a document with no pending changes draws no Changes menu, and nothing then stands before the divider */
	.annotate-bar > .sep:first-child {
		display: none;
	}
	.count {
		min-width: 3.2em;
		text-align: center;
		font-variant-numeric: tabular-nums;
		color: var(--ink-soft);
	}
	.badge {
		min-width: 16px;
		padding: 0 5px;
		font-size: 10.5px;
		line-height: 15px;
		text-align: center;
		color: var(--ink-soft);
		background: var(--leaf);
		border: 1px solid var(--rule);
		border-radius: 8px;
	}
	.format-menu {
		position: fixed;
		z-index: 45;
		display: grid;
		gap: 6px;
		box-sizing: border-box;
		width: 400px;
		max-width: calc(100vw - 24px);
		max-height: calc(100vh - 24px);
		overflow: auto;
		padding: 10px 12px;
		font-family: var(--sans);
		font-size: 12.5px;
		white-space: normal;
		color: var(--ink);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 9px;
		box-shadow: var(--float-shadow);
	}
	.sec {
		margin-top: 2px;
		font-size: 10.5px;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--ink-faint);
	}
	.mfoot {
		display: flex;
		justify-content: flex-end;
		gap: 14px;
		padding-top: 6px;
		border-top: 1px solid var(--rule);
	}
	.lnk {
		padding: 0;
		font: inherit;
		color: var(--link);
		background: none;
		border: 0;
		cursor: pointer;
	}
	.lnk:hover {
		text-decoration: underline;
	}
</style>
