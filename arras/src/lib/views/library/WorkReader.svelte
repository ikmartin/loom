<script lang="ts">
	// A work's paper in the one reader (`pdf/MarkedDoc`), in a Library tab or beside a draft in Docs, where it draws no digest marks: today's toolbar and annotation tools, and the Library's own: a `view` menu holding the digest marks, which, while on, draw beside each node of the work on the pages in view a chip with its paper mark and number and a bar down its margin (a click puts the node beside the page), and on words selected with no tool in hand, round six's popup: mark to digest, highlight, ask an agent (a note beside the words comes with the reader's own annotations re-keyed to the work). Places are asked for only while the marks are on, for the page in view and its neighbours.
	import { said } from '$lib/library/said';
	import { untrack } from 'svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { paperMark } from '$lib/marks/marks';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { Place, PlacesAnswer, Rect, WorkAnswer } from '$lib/library/types';
	import MarkedDoc from '$lib/pdf/MarkedDoc.svelte';
	import PdfBar from '$lib/pdf/PdfBar.svelte';
	import { paperPlace } from '$lib/pdf/place.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { library as words } from '$lib/words/library';
	import { lib } from './state.svelte';
	import { menus } from './menus.svelte';

	let { work, beside = false }: { work: WorkAnswer; /** Beside a draft in Docs: the reader without the digest marks or their menu. */ beside?: boolean } = $props();
	const marks = $derived(!beside && lib.overlay);

	const ref = $derived(work.ref);
	const url = $derived(work.holds.pdf ? api.pdfUrl(work.holds.pdf) : '');
	const reader = $derived(lib.reader(ref));
	$effect(() => lib.paper(ref, url, `${work.short}.pdf`));
	const desk = $derived(lib.desk(ref));
	const place = paperPlace(
		() => reader.view,
		() => ({ seq: lib.goto[ref]?.seq ?? 0, page: lib.goto[ref]?.page ?? 1 })
	);

	// the digest marks: the places of the work's nodes and marks on the page in view and its neighbours
	let page = $state(1);
	const places = new Read<PlacesAnswer>();
	$effect(() => {
		const on = marks;
		const r = ref;
		const near = [page - 1, page, page + 1].filter((n) => n > 0);
		void gen.gen;
		if (!on) return untrack(() => places.clear());
		void places.load(`${r}:${near.join(',')}`, (s) => api.places({ ref: r, pages: near }, s));
	});
	const byPage = $derived.by(() => {
		const out: Record<number, Place[]> = {};
		for (const p of places.value?.places ?? []) (out[p.page] ??= []).push(p);
		return out;
	});
	const chosen = $derived(lib.beside[ref]);

	// round six's popup on words selected with no tool in hand
	let offered = $state<{ page: number; text: string; rects: number[][]; at: { left: number; top: number; width: number; height: number } } | null>(null);
	let asking = $state(false);
	let question = $state('');
	$effect(() => {
		const gone = () => {
			if (offered && !asking && !window.getSelection()?.toString().trim()) offered = null;
		};
		document.addEventListener('selectionchange', gone);
		return () => document.removeEventListener('selectionchange', gone);
	});

	async function mark(): Promise<void> {
		const o = offered;
		if (!o) return;
		offered = null;
		const done = await api.call<{ gen: number; annotation?: string }>('annotate', { target: ref, page: o.page, quote: o.text, rects: o.rects, purpose: 'to-digest' });
		if (!done.ok) return message.post(said(done.error));
		const id = done.value.annotation;
		message.post(words.reader.marked(o.page), id ? () => api.call('delete', { annotation: id }) : undefined);
	}

	async function highlight(): Promise<void> {
		const o = offered;
		if (!o) return;
		offered = null;
		const done = await api.call('annotate', { target: ref, page: o.page, quote: o.text, rects: o.rects });
		if (!done.ok) message.post(said(done.error));
	}

	async function ask(e: SubmitEvent): Promise<void> {
		e.preventDefault();
		const o = offered;
		if (!o || !question.trim()) return;
		const text = question.trim();
		offered = null;
		asking = false;
		question = '';
		const done = await api.ask('ask', { ref, page: o.page }, { text, quote: o.text }, lib.works.value?.works.find((w) => w.ref === ref)?.used_in ?? []);
		message.post(done.ok ? words.reader.asked : said(done.error));
	}

	/** Gives the keyboard to the field as it appears, which `autofocus` does not once the page has loaded. */
	const focused = (el: HTMLElement) => void queueMicrotask(() => el.focus());

	const bar = (rects: Rect[]) => {
		const top = Math.min(...rects.map((r) => r[1]));
		const bottom = Math.max(...rects.map((r) => r[3]));
		const left = Math.min(...rects.map((r) => r[0]));
		return [left - 10, top, left - 8, bottom] as Rect;
	};
</script>

<div class="reader" data-testid="work-reader">
	<!-- beside a draft, the pane's toolbar is the reader's bar (`ReadingControls`), so one row stands over the paper -->
	{#if !beside}<div class="tb">
		<PdfBar view={reader.view} notes={reader.notes} {desk} of={work.short} part="read" writes={desk.writes} />
		<span class="grow"></span>
		<span class="menuwrap">
			<button type="button" class="btn quiet" aria-expanded={menus.open === `view:${ref}`} onclick={() => menus.toggle(`view:${ref}`)} data-testid="reader-view">{words.reader.view}</button>
			{#if menus.open === `view:${ref}`}
				<div class="menu viewmenu">
					<button type="button" class="mi" role="menuitemcheckbox" aria-checked={lib.overlay} onclick={() => (lib.overlay = !lib.overlay)} data-testid="overlay-toggle"><span class="chk">{lib.overlay ? '✓' : ''}</span>{words.reader.overlay}</button>
				</div>
			{/if}
		</span>
	</div>{/if}
	<div class="doc">
		<MarkedDoc
			{desk}
			view={reader.view}
			notes={reader.notes}
			{url}
			name={`${work.short}.pdf`}
			page={place.opening.page}
			share={place.opening.share}
			seq={place.opening.seq}
			lands={!place.spent}
			onmoved={place.moved}
			onpage={(e) => (page = e.page)}
			onselect={(e) => {
				asking = false;
				offered = { page: e.page, text: e.text, rects: e.rects, at: e.client };
			}}
			overlay={marks ? overlay : undefined}
		/>
		{#if offered}
			<div class="selpop" style:left="{offered.at.left}px" style:top="{offered.at.top + offered.at.height + 8}px" data-testid="selection-popup">
				<button type="button" class="pri" onclick={() => void mark()} data-testid="mark-to-digest"><Mark kind="marked" size={11} /> {words.reader.mark}</button>
				<button type="button" onclick={() => void highlight()}>{words.reader.highlight}</button>
				<button type="button" onclick={() => (asking = !asking)}>{words.reader.ask}</button>
				{#if asking}
					<form class="askrow" onsubmit={(e) => void ask(e)}>
						<input class="search" type="text" bind:value={question} placeholder={words.reader.askPlaceholder} aria-label={words.reader.askPlaceholder} use:focused data-testid="ask-field" />
						<button type="submit" class="pri">{words.reader.send}</button>
					</form>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#snippet overlay({ page: n, at }: { page: number; at: (r: Rect) => { left: string; top: string; width: string; height: string } })}
	{#each byPage[n] ?? [] as p (p.node ?? p.mark)}
		{@const b = at(bar(p.rects))}
		{@const first = at(p.rects[0])}
		<span class="dbr {p.paper}" style:left={b.left} style:top={b.top} style:height={b.height}></span>
		{#if p.node}
			<button type="button" class="dchip" class:on={chosen && 'node' in chosen && chosen.node === p.node} style:top={first.top} aria-label={words.reader.chip(p.name ?? '')} data-testid="digest-chip" data-node={p.node} onclick={() => (lib.beside = { ...lib.beside, [ref]: { node: p.node! } })}><Mark kind={paperMark(p.paper)} size={11} />{#if p.number}<span>{p.number}</span>{/if}</button>
		{:else}
			<span class="dchip mark" style:top={first.top}><Mark kind="marked" size={11} /></span>
		{/if}
	{/each}
{/snippet}

<style>
	.reader {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}
	.tb {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 12px;
		min-height: 36px;
		border-bottom: 1px solid var(--rule);
		background: var(--paper);
	}
	.grow {
		flex: 1;
	}
	.btn.quiet {
		background: transparent;
		border-color: transparent;
		color: var(--ink-faint);
	}
	.viewmenu {
		right: 0;
		top: calc(100% + 4px);
		width: 230px;
	}
	.doc {
		flex: 1;
		min-height: 0;
		position: relative;
		display: flex;
		flex-direction: column;
	}
	.doc :global(.overlay) {
		overflow: visible;
	}
	.dbr {
		position: absolute;
		width: 3px;
		border-left: 2px dashed var(--mark-wait);
		pointer-events: none;
	}
	.dbr.matches {
		border-left: 2px solid var(--mark-yes);
	}
	.dbr.stub {
		border-left-color: var(--mark-none);
	}
	.dbr.marked {
		border-left: 3px solid var(--mark-person);
	}
	.dchip {
		position: absolute;
		left: -62px;
		display: inline-flex;
		align-items: center;
		gap: 3px;
		height: 18px;
		padding: 0 5px;
		font: 11px var(--sans);
		color: var(--ink);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 9px;
		cursor: pointer;
		pointer-events: auto;
	}
	.dchip.on {
		border-color: var(--link);
		box-shadow: 0 0 0 2px var(--link-wash);
	}
	.dchip.mark {
		left: -34px;
		cursor: default;
	}
	.selpop {
		position: fixed;
		z-index: 60;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 2px;
		max-width: 420px;
		padding: 4px;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 8px;
		box-shadow: var(--float-shadow);
		font-size: 13px;
	}
	.selpop button {
		font: inherit;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		border: 0;
		background: none;
		color: var(--ink);
		padding: 5px 10px;
		border-radius: 6px;
		cursor: pointer;
	}
	.selpop button:hover {
		background: var(--leaf);
	}
	.selpop .pri {
		background: var(--ink);
		color: var(--sheet);
	}
	.selpop .pri:hover {
		background: var(--ink-soft);
	}
	.askrow {
		display: flex;
		gap: 6px;
		width: 100%;
		padding: 4px;
	}
	.askrow .search {
		flex: 1;
		width: auto;
	}
</style>
