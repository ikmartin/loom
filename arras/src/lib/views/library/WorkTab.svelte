<script lang="ts">
	// A work's tab (2, 3): the work's paper in the one reader (`pdf/Reading`), the very reader a pane of Docs draws for the work, with the same annotations and place, and the Library's layers over it, each where the source serves its read: the `view` menu's digest marks, which draw beside each node on the pages in view a chip with its paper mark and number and a bar down its margin (a click puts the node beside the page), offered where places and digesting are both served, since a node's place comes with the digest; every annotation, a mark to digest among them, is the reader's own to draw; on words selected, `mark to digest` and `ask an agent…` beside Quote; the result chosen beside the page; and the outline's jumps (`lib.go`). A work loom holds no document of says so, with its own page to open.
	import { untrack } from 'svelte';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import { said } from '$lib/library/said';
	import { served } from '$lib/library/served.svelte';
	import type { NodePlace, PlacesAnswer, Rect } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { paperMark } from '$lib/marks/marks';
	import PdfBar from '$lib/pdf/PdfBar.svelte';
	import Reading from '$lib/pdf/Reading.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { library as words } from '$lib/words/library';
	import type { Item } from '$lib/workspace/item';
	import { workState } from '$lib/workspace/state.svelte';
	import { can } from '$lib/write';
	import { menus } from './menus.svelte';
	import NodeSide from './NodeSide.svelte';
	import { lib } from './state.svelte';

	let { ref }: { ref: string } = $props();

	const w = $derived(lib.work.value?.ref === ref ? lib.work.value : null);
	const beside = $derived(lib.beside[ref] ?? null);
	/** The work as Docs' workspace keys it, so its annotations, its desk and its place are the pane's own. */
	const item = $derived<Item>({ kind: 'work', id: ref });
	const held = $derived(workState(item));

	// the tools write, so a corpus served without a write API does not offer them
	let writes = $state(false);
	$effect(() => {
		void can('annotate').then((ok) => (writes = ok));
	});

	// the digest marks: the places of the work's nodes on the page in view and its neighbours, asked for only while they are on
	const digests = $derived(served.has('library-places') && served.has('library-digest'));
	const marks = $derived(lib.overlay && digests);
	let page = $state(1);
	const places = new Read<PlacesAnswer>();
	$effect(() => {
		const on = marks;
		const near = [page - 1, page, page + 1].filter((n) => n > 0);
		void gen.gen;
		if (!on) return untrack(() => places.clear());
		void places.load(`${ref}:${near.join(',')}`, (s) => api.places({ ref, pages: near }, s));
	});
	const byPage = $derived.by(() => {
		const out: Record<number, NodePlace[]> = {};
		for (const p of places.value?.places ?? []) if ('node' in p) (out[p.page] ??= []).push(p);
		return out;
	});
	const chosen = $derived(lib.beside[ref]);

	// beside Quote on words selected: mark to digest, and ask an agent with a field of its own
	let asking = $state(false);
	let question = $state('');

	async function mark(o: { page: number; text: string; rects: number[][]; done: () => void }): Promise<void> {
		o.done();
		const done = await api.call<{ gen: number; annotation?: string }>('annotate', { target: ref, page: o.page, quote: o.text, rects: o.rects, purpose: 'to-digest' });
		if (!done.ok) return message.post(said(done.error));
		const id = done.value.annotation;
		message.post(words.reader.marked(o.page), id ? () => api.call('delete', { annotation: id }) : undefined);
	}

	async function ask(e: SubmitEvent, o: { page: number; text: string; done: () => void }): Promise<void> {
		e.preventDefault();
		if (!question.trim()) return;
		const text = question.trim();
		o.done();
		asking = false;
		question = '';
		const done = await api.ask('ask', { ref, page: o.page, quote: o.text }, text, lib.works.value?.works.find((x) => x.ref === ref)?.used_in ?? []);
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

{#if lib.work.error && !w}
	<p class="note" role="alert">{said(lib.work.error)}</p>
{:else if !w}
	<p class="note grey">{words.works.loading}</p>
{:else if !w.holds.pdf}
	<div class="nodoc" data-testid="work-no-document">
		<p class="grey">{words.reader.noDocument}</p>
		{#if w.link}<button type="button" class="btn" onclick={() => window.open(w.link!, '_blank', 'noopener')}>{words.works.openSource}</button>{/if}
	</div>
{:else}
	<div class="body">
		<div class="reader" data-testid="work-reader">
			<div class="tb">
				<PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={w.short} part="read" {writes} disabled={!held.desk} />
				<span class="grow"></span>
				<!-- the digest marks where the source serves their places -->
				{#if digests}<span class="menuwrap">
					<button type="button" class="btn quiet" aria-expanded={menus.open === `view:${ref}`} onclick={() => menus.toggle(`view:${ref}`)} data-testid="reader-view">{words.reader.view}</button>
					{#if menus.open === `view:${ref}`}
						<div class="menu viewmenu">
							<button type="button" class="mi" role="menuitemcheckbox" aria-checked={lib.overlay} onclick={() => (lib.overlay = !lib.overlay)} data-testid="overlay-toggle"><span class="chk">{lib.overlay ? '✓' : ''}</span>{words.reader.overlay}</button>
						</div>
					{/if}
				</span>{/if}
			</div>
			{#if writes}<div class="tb tools"><PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={w.short} part="write" {writes} disabled={!held.desk} /></div>{/if}
			<div class="doc">
				<Reading {ref} pdf={w.holds.pdf} short={w.short} page={lib.goto[ref]?.page ?? 1} seq={lib.goto[ref]?.seq ?? 0} view={held.pdf} overlay={marks ? overlay : undefined} onpage={(e) => (page = e.page)} {more} />
			</div>
		</div>
		{#if beside}<NodeSide {ref} {beside} />{/if}
	</div>
{/if}

{#snippet more(o: { page: number; text: string; rects: number[][]; hold: () => void; done: () => void })}
	<!-- marking to digest and asking an agent where the source serves digesting and asking -->
	{#if served.has('library-digest')}<button type="button" class="chip" onclick={() => void mark(o)} data-testid="mark-to-digest"><Mark kind="marked" size={11} /> {words.reader.mark}</button>{/if}
	{#if served.has('review-task')}<button type="button" class="chip" aria-expanded={asking} onmousedown={() => o.hold()} onclick={() => ((asking = !asking), o.hold())} data-testid="ask-agent">{words.reader.ask}</button>{/if}
	{#if asking}
		<form class="askrow" onsubmit={(e) => void ask(e, o)}>
			<input class="search" type="text" bind:value={question} placeholder={words.reader.askPlaceholder} aria-label={words.reader.askPlaceholder} use:focused data-testid="ask-field" />
			<button type="submit" class="chip">{words.reader.send}</button>
		</form>
	{/if}
{/snippet}

{#snippet overlay({ page: n, at }: { page: number; at: (r: Rect) => { left: string; top: string; width: string; height: string } })}
	{#each byPage[n] ?? [] as p (p.node)}
		{@const b = at(bar(p.rects))}
		{@const first = at(p.rects[0])}
		<span class="dbr {p.paper}" style:left={b.left} style:top={b.top} style:height={b.height}></span>
		<button type="button" class="dchip" class:on={chosen && 'node' in chosen && chosen.node === p.node} style:top={first.top} aria-label={words.reader.chip(p.name ?? '')} data-testid="digest-chip" data-node={p.node} onclick={() => (lib.beside = { ...lib.beside, [ref]: { node: p.node } })}><Mark kind={paperMark(p.paper)} size={11} />{#if p.number}<span>{p.number}</span>{/if}</button>
	{/each}
{/snippet}

<style>
	.note {
		padding: 20px;
	}
	.nodoc {
		padding: 24px 28px;
		max-width: 560px;
	}
	.nodoc p {
		margin: 0 0 12px;
	}
	.body {
		flex: 1;
		min-height: 0;
		display: flex;
	}
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
	.askrow {
		display: flex;
		gap: 6px;
		padding: 4px;
	}
	.askrow .search {
		flex: 1;
		width: auto;
	}
</style>
