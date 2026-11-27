<script lang="ts">
	// Annotating on the corpus's own text, a node's or a document's: what the toolbar's tools do here.
	//
	// **Annotate** on, selected words, widened to whole words where a drag stops partway through one, are marked at once in the look in hand, and Add comment stands at their end until the next selection: typing there starts the comment, so a letter meant for it never reaches a shortcut. A type that stays open until resolved asks something, so its words open the popup to say it first, since loom takes such an annotation only with words; that draft is not saved until its button is pressed, and leaving it with words in it asks first. **Comment** on, a click leaves a comment at the place clicked, on the result it is in, and words selected open the comment box on exactly them; either turns the tool off. With neither on, a selection offers its actions (`SelectionMenu`): **Quote**, which copies the words and where they came from and writes nothing, **Annotate**, which opens the comment box on them, and **New note**; after the tool's Annotate, Add comment stands at the words with the actions beside it, Annotate left out. Alt-drag draws a box round what a selection cannot hold: a labelled equation is noted as itself, anything else as the words of the block under the box.
	//
	// A quote is what was selected with each formula it touches given as its TeX, the form loom finds in the source, so a selection across `$c$` anchors where the words on screen alone would not.
	import { refusalOf } from '$lib/library/said';
	import { untrack, type Snippet } from 'svelte';
	import { onDestroy } from 'svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { landed } from '$lib/manifest/updating.svelte';
	import { can } from '$lib/write';
	import { annotate as record } from '$lib/review/history.svelte';
	import { linkName } from '$lib/workspace/names';
	import AnnotationPopup from '$lib/review/AnnotationPopup.svelte';
	import SelectionMenu from '$lib/review/SelectionMenu.svelte';
	import { quoteLink } from '$lib/notes/link';
	import { commentSeed, hand, handPayload, typeById, type Annotating, type Draft } from '$lib/review/annotating.svelte';
	import { say } from '$lib/review/toasts.svelte';
	import { placeAt } from './popup';
	import { quoteOf, keyOf, texOf } from './quote';
	import { clearPending, showPending } from './pending';
	import { snapToWords } from './snap';

	let {
		notes,
		fallback,
		in: inDoc = '',
		children
	}: {
		/** The item's annotating: the tool in hand, and the popup's opening. */
		notes: Annotating;
		/** The key a place belongs to when no result encloses it: the node shown, or the document. */
		fallback: string;
		/** The document being read, when the fragment is one: every annotation written here is filed with it. A node's own page passes nothing. */
		in?: string;
		children: Snippet;
	} = $props();

	type Box = { left: number; top: number; width: number; height: number };
	const MIN_BOX = 6;

	let root = $state<HTMLElement | null>(null);
	let allowed = $state(false);
	$effect(() => {
		void can('annotate').then((ok) => (allowed = ok));
	});

	const m = $derived(store.manifest);

	/** A bare selection, offered its actions. */
	let offered = $state<{ words: string; target: string; at: Box; range: Range } | null>(null);
	/** A new annotation being written in the popup, and where the popup stands. */
	let drafting = $state<{ draft: Draft; at: Box } | null>(null);
	/** The draft's popup, which says whether it may close. */
	let popup = $state<ReturnType<typeof AnnotationPopup> | undefined>();
	/** Words just marked by Annotate, with Add comment and the actions at their end until the next selection. */
	let marked = $state<{ id: string; at: Box; words: string; target: string } | null>(null);
	/** Keys typed after words were marked and before loom answered the mark, kept for its comment; `live` goes false when the reader moves on first. */
	let awaiting = $state.raw<{ started: boolean; text: string; live: boolean } | null>(null);

	// what the hint under the toolbar says follows the draft and the words just marked
	$effect(() => {
		notes.drafting = drafting ? (drafting.draft.quote ? 'annotate' : 'comment') : null;
	});
	$effect(() => {
		notes.marked = marked?.id ?? null;
	});

	onDestroy(() => {
		clearPending();
		notes.drafting = null;
		notes.marked = null;
	});

	/** Close the draft unless it holds words, which its popup asks about first. */
	function leaveDraft(): void {
		if (popup?.leave() ?? true) closeDraft();
	}

	/** The tool goes off with Escape, as a highlighter is put down; a draft is left first. */
	$effect(() => {
		const key = (e: KeyboardEvent) => {
			if (e.key !== 'Escape' || e.defaultPrevented) return;
			if (drafting) {
				e.preventDefault();
				return leaveDraft();
			}
			marked = null;
			drop();
			if (notes.tool && !notes.open) notes.tool = null;
		};
		document.addEventListener('keydown', key);
		return () => document.removeEventListener('keydown', key);
	});

	/** Typing while Add comment stands starts the comment: the keys are kept until the popup opens and its field takes them (`commentSeed`). A number still switches type and a space still scrolls, until the first letter. Listened for before anything else, so no key meant for the comment reaches a shortcut. Keys typed while loom has yet to answer the mark are kept in `awaiting`, and start the comment once the answer names it. */
	$effect(() => {
		const id = marked?.id;
		const early = awaiting;
		if (!id && !early) return;
		const typed = (e: KeyboardEvent) => {
			if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;
			if ((e.target as HTMLElement | null)?.closest('input, textarea, select, [contenteditable]')) return;
			if (!id && early) {
				if (e.key === 'Backspace' && early.started) early.text = early.text.slice(0, -1);
				else if (e.key === 'Enter' && !early.started) early.started = true;
				else if (e.key.length === 1 && (early.started || !/[\s0-9]/.test(e.key))) {
					early.started = true;
					early.text += e.key;
				} else return;
				e.preventDefault();
				e.stopPropagation();
				return;
			}
			if (!id) return;
			const started = commentSeed.id === id;
			if (e.key === 'Backspace' && started) commentSeed.text = commentSeed.text.slice(0, -1);
			else if (e.key === 'Enter' && !started) {
				commentSeed.id = id;
				commentSeed.text = '';
				void openWritten(id);
			} else if (e.key.length === 1 && (started || !/[\s0-9]/.test(e.key))) {
				if (started) commentSeed.text += e.key;
				else {
					commentSeed.id = id;
					commentSeed.text = e.key;
					void openWritten(id);
				}
			} else return;
			e.preventDefault();
			e.stopPropagation();
		};
		document.addEventListener('keydown', typed, true);
		return () => document.removeEventListener('keydown', typed, true);
	});

	$effect(() => {
		const drop = () => {
			if (offered && !window.getSelection()?.toString().trim()) offered = null;
		};
		document.addEventListener('selectionchange', drop);
		return () => document.removeEventListener('selectionchange', drop);
	});

	// choosing a tool ends whatever the last one offered
	$effect(() => {
		void notes.tool;
		untrack(() => {
			offered = null;
			marked = null;
			drop();
		});
	});

	/** What stands in the fragment without being its text: a popup, the margin, and what compare draws or swaps in. */
	const NOT_TEXT = 'aside, .ann-gutter, .ann-popup-host, .compare-swap, .compare-tag, .compare-gutter';

	function notText(n: Node): boolean {
		const el = n instanceof Element ? n : n.parentElement;
		return !!el?.closest(NOT_TEXT);
	}

	/** A place's name, as the popup's head and a quote's source say it: an equation by its number in its result; else the document and the result in it, or the result alone on its own page. */
	function nameFor(key: string): string {
		if (!m) return key;
		const region = m.regions?.[key];
		if (region) {
			const n = Object.values(region.numbers ?? {})[0]?.number;
			const of = linkName(m, `quilt:${region.container}`);
			return n ? `equation (${n}) in ${of}` : `an equation in ${of}`;
		}
		// a result in a document by the number the document shows
		if (inDoc && key !== inDoc) return `${linkName(m, `quilt:${inDoc}`)}, ${linkName(m, `quilt:${inDoc}#${key}`)}`;
		return linkName(m, `quilt:${key}`);
	}

	/** A link to words at a place: in a document, the document at the result; on a node's page, the result. */
	function linkFor(key: string, words: string): string {
		if (inDoc && key !== inDoc) return quoteLink(inDoc, key, words);
		return quoteLink(key, '', words);
	}

	function rectOfRange(range: Range): Box {
		const r = range.getBoundingClientRect();
		return { left: r.left, top: r.top, width: r.width, height: r.height };
	}

	function endOf(range: Range): Box {
		const last = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0).at(-1) ?? range.getBoundingClientRect();
		return { left: last.left, top: last.top, width: last.width, height: last.height };
	}

	function selected(): void {
		if (!root || drawing) return;
		const sel = window.getSelection();
		if (!sel || sel.isCollapsed || !sel.rangeCount) return;
		const range = sel.getRangeAt(0);
		if (!root.contains(range.commonAncestorContainer)) return;
		// only the text's own words: a popup, the margin or compare's drawing stands in the fragment without being its text
		if ([range.startContainer, range.endContainer, range.commonAncestorContainer].some(notText)) return;
		marked = null;
		drop();
		// Annotate and Comment take whole words: a drag that stops partway through one takes the rest of it, and the selection shows what is taken
		if (notes.tool && allowed && snapToWords(range)) {
			sel.removeAllRanges();
			sel.addRange(range);
		}
		const words = quoteOf(range);
		if (!words) return;
		const target = keyOf(range.commonAncestorContainer, fallback);
		if (notes.tool === 'annotate' && allowed) return void annotate(target, words, range);
		if (notes.tool === 'comment') {
			if (allowed) {
				notes.tool = null;
				// the click this press ends in lands on the words' block, and must not leave a comment there too
				swallow = true;
				setTimeout(() => (swallow = false));
				commentOn(target, words, range);
			}
			return;
		}
		offered = { words, target, at: rectOfRange(range), range: range.cloneRange() };
	}

	/** Set once a selection's press has opened the comment box, for the click that ends the same press. */
	let swallow = false;

	/** Open the comment box on exactly the words selected: the draft holds them as its quote, and they stay lit while it is written. */
	function commentOn(target: string, quote: string, range: Range): void {
		showPending(range);
		window.getSelection()?.removeAllRanges();
		openDraft({ target, quote, ...(inDoc ? { in: inDoc } : {}), name: nameFor(target) }, rectOfRange(range));
	}

	/** Mark the selected words in the look in hand; a type that asks something opens the popup for its words first. */
	async function annotate(target: string, quote: string, range: Range): Promise<void> {
		const h = hand.value;
		if (typeById(m, h.type)?.open) {
			showPending(range);
			window.getSelection()?.removeAllRanges();
			openDraft({ target, quote, ...(inDoc ? { in: inDoc } : {}), name: nameFor(target) }, rectOfRange(range));
			return;
		}
		const at = endOf(range);
		window.getSelection()?.removeAllRanges();
		const early = { started: false, text: '', live: true };
		awaiting = early;
		let res: Awaited<ReturnType<typeof record>>;
		try {
			res = await record({ target, quote, ...(inDoc ? { in: inDoc } : {}), ...handPayload(m, h) });
		} finally {
			if (awaiting === early) awaiting = null;
		}
		if (!res.ok) {
			say({ title: 'Not annotated', lines: [refusalOf(res.error)] });
			return;
		}
		const id = (res.result ?? '').split(/\s+/)[0] ?? '';
		if (!early.live) return;
		marked = id ? { id, at, words: quote, target } : null;
		if (id && early.started) {
			commentSeed.id = id;
			commentSeed.text = early.text;
			void openWritten(id);
		}
	}

	/** Forget the keys kept for a mark loom has yet to answer: the reader moved on first. */
	function drop(): void {
		if (awaiting) awaiting.live = false;
		awaiting = null;
	}

	/** Open the popup on an annotation just written, once the manifest that holds it has been drawn; a draft opened meanwhile ends the trying. Add comment stands, and keeps the keys typed, until it opens. */
	async function openWritten(id: string): Promise<void> {
		await landed();
		for (let i = 0; i < 20; i++) {
			// a draft opened meanwhile is the reader's next step, and no popup opens over it
			if (drafting) break;
			if (notes.show(id)) {
				if (marked?.id === id) marked = null;
				return;
			}
			await new Promise((r) => setTimeout(r, 100));
		}
		if (marked?.id === id) marked = null;
		if (commentSeed.id === id) commentSeed.id = '';
	}

	/** Annotate, from the actions at a bare selection: its words widened to whole words, and the comment box opened on them. */
	function annotateOffered(): void {
		const o = offered;
		if (!o) return;
		offered = null;
		snapToWords(o.range);
		commentOn(o.target, quoteOf(o.range) || o.words, o.range);
	}

	function openDraft(draft: Draft, at: Box): void {
		notes.close();
		offered = null;
		marked = null;
		drafting = { draft, at };
	}

	function closeDraft(): void {
		drafting = null;
		clearPending();
	}

	/** A click while Comment is on leaves a comment there: caught before a mark under it opens its popup. */
	function clicked(e: MouseEvent): void {
		if (swallow) {
			swallow = false;
			e.preventDefault();
			e.stopPropagation();
			return;
		}
		if (notes.tool !== 'comment' || !allowed || !root || e.button !== 0) return;
		const on = e.target as Element;
		if (notText(on) || on.closest('a, button, input, textarea, select')) return;
		e.preventDefault();
		e.stopPropagation();
		const target = keyOf(on, fallback);
		notes.tool = null;
		const block = on.closest<HTMLElement>('p, li, .math.display, figure, table, h1, h2, h3, h4, h5, h6');
		if (block) showPending(null, block);
		openDraft({ target, ...(inDoc ? { in: inDoc } : {}), name: nameFor(target) }, { left: e.clientX, top: e.clientY, width: 0, height: 0 });
	}

	/** The box being drawn, in window coordinates. */
	let drawing = $state<{ x: number; y: number; x2: number; y2: number } | null>(null);
	/** A press on a mark while Alt is held: a click on the mark until the pointer moves, a box once it does. */
	let pressed: { x: number; y: number } | null = null;

	function down(e: PointerEvent): void {
		if (!allowed || e.button !== 0 || !e.altKey) return;
		const on = e.target as Element;
		// a press on a link or a control is a click on it, never the start of a box; one in a popup or the margin is not on the text
		if (on.closest('a, button, input, textarea, select') || notText(on)) return;
		if (on.closest('mark.annotation, .annotation-block')) {
			pressed = { x: e.clientX, y: e.clientY };
			return;
		}
		start(e, e.clientX, e.clientY);
	}

	function start(e: PointerEvent, x: number, y: number): void {
		e.preventDefault();
		window.getSelection()?.removeAllRanges();
		offered = null;
		drawing = { x, y, x2: e.clientX, y2: e.clientY };
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function move(e: PointerEvent): void {
		if (pressed && Math.hypot(e.clientX - pressed.x, e.clientY - pressed.y) > 4) {
			const from = pressed;
			pressed = null;
			start(e, from.x, from.y);
			return;
		}
		if (drawing) drawing = { ...drawing, x2: e.clientX, y2: e.clientY };
	}

	function up(e: PointerEvent): void {
		pressed = null;
		if (!drawing || !root) return;
		(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
		const box = rectOf(drawing);
		drawing = null;
		if (box.width < MIN_BOX && box.height < MIN_BOX) return;
		const { el, target, text } = placeUnder(root, box);
		showPending(null, el);
		openDraft({ target, ...(text ? { quote: text } : {}), ...(inDoc ? { in: inDoc } : {}), name: nameFor(target) }, box);
	}

	function rectOf(d: { x: number; y: number; x2: number; y2: number }): Box {
		return { left: Math.min(d.x, d.x2), top: Math.min(d.y, d.y2), width: Math.abs(d.x2 - d.x), height: Math.abs(d.y2 - d.y) };
	}

	function overlap(a: DOMRect, b: Box): number {
		const w = Math.min(a.right, b.left + b.width) - Math.max(a.left, b.left);
		const h = Math.min(a.bottom, b.top + b.height) - Math.max(a.top, b.top);
		return w > 0 && h > 0 ? w * h : 0;
	}

	/** What a box was drawn round: a labelled equation as itself, else the words of the block it covers most, else the result it is in. */
	function placeUnder(at: HTMLElement, box: Box): { target: string; text: string; el: HTMLElement | null } {
		let best: { el: HTMLElement; score: number } | null = null;
		for (const el of at.querySelectorAll<HTMLElement>('.math.display[data-label], figure[data-label]')) {
			const score = overlap(el.getBoundingClientRect(), box);
			if (score > (best?.score ?? 0)) best = { el, score };
		}
		if (best) {
			const region = `${keyOf(best.el, fallback)}#${best.el.dataset.label}`;
			if (m?.regions?.[region]) return { target: region, text: '', el: best.el };
			return { target: keyOf(best.el, fallback), text: texOf(best.el), el: best.el };
		}
		let block: { el: HTMLElement; score: number } | null = null;
		for (const el of at.querySelectorAll<HTMLElement>('p[data-src], li[data-src], .math.display[data-src], figure[data-src], table[data-src]')) {
			const score = overlap(el.getBoundingClientRect(), box);
			if (score > (block?.score ?? 0)) block = { el, score };
		}
		if (block) {
			const range = document.createRange();
			range.selectNodeContents(block.el);
			return { target: keyOf(block.el, fallback), text: quoteOf(range), el: block.el };
		}
		return { target: fallback, text: '', el: null };
	}

	/** Put the draft's popup at its place once it is drawn, and again as it grows. */
	function placed(host: HTMLElement, at: Box) {
		let r = at;
		const go = () => placeAt(host, { left: r.left, top: r.top, bottom: r.top + r.height });
		const sized = new ResizeObserver(go);
		sized.observe(host);
		go();
		return {
			update(next: Box) {
				r = next;
				go();
			},
			destroy: () => sized.disconnect()
		};
	}

	/** A press outside the draft's popup puts it away, as a press outside any popup does, once its words have been asked about. */
	$effect(() => {
		if (!drafting) return;
		const away = (e: PointerEvent) => {
			const t = e.target as Element | null;
			if (!t?.closest?.('.ann-popup-host, [data-testid="settings-window"], [data-testid="name-ask"]')) leaveDraft();
		};
		document.addEventListener('pointerdown', away, true);
		return () => document.removeEventListener('pointerdown', away, true);
	});
</script>

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_click_events_have_key_events -->
<div class="fragment-notes" class:armed={notes.tool === 'annotate' && allowed} class:placing={notes.tool === 'comment' && allowed} bind:this={root} onmouseup={selected} onclickcapture={clicked} onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={() => (drawing = null)} data-testid="fragment-notes">
	{@render children()}
</div>

{#if drawing}
	{@const b = rectOf(drawing)}
	<div class="drawn" style="left: {b.left}px; top: {b.top}px; width: {b.width}px; height: {b.height}px;" data-testid="drawn-box"></div>
{/if}
{#if offered && !drafting}
	<SelectionMenu at={offered.at} range={offered.range} text={offered.words} name={nameFor(offered.target)} link={linkFor(offered.target, offered.words)} annotate={allowed ? annotateOffered : undefined} ondone={() => (offered = null)} />
{/if}
{#if marked && !drafting}
	{@const id = marked.id}
	<SelectionMenu at={marked.at} text={marked.words} name={nameFor(marked.target)} link={linkFor(marked.target, marked.words)} ondone={() => (marked = null)}>
		{#snippet before()}<button type="button" class="chip" data-testid="add-comment" onclick={() => void openWritten(id)}>Add comment</button>{/snippet}
	</SelectionMenu>
{/if}
{#if drafting}
	{@const mine = drafting}
	<!-- each draft its own popup, so a write still on its way from the last one neither holds this one's button nor closes it -->
	{#key mine}
		<aside class="ann-popup-host" use:placed={mine.at} data-testid="draft-host">
			<AnnotationPopup
				bind:this={popup}
				draft={mine.draft}
				onclose={closeDraft}
				onwritten={(id) => {
					// written after the reader moved on: the draft open now, or none, stays as it is
					if (drafting !== mine) return;
					closeDraft();
					if (id) void openWritten(id);
				}}
			/>
		</aside>
	{/key}
{/if}

<style>
	.fragment-notes.armed {
		cursor: text;
	}
	.fragment-notes.placing {
		cursor: copy;
	}
	.drawn {
		position: fixed;
		z-index: 30;
		pointer-events: none;
		border: 1.5px dashed var(--accent);
		background: var(--accent-wash);
		border-radius: 2px;
	}
</style>
