<script lang="ts">
	// A work's outline in the Library's column (2, 2 choose, 3): the paper's sections with their pages and its results under the section they stand in, each with its marks; a click on either goes to its place, and a result opens beside the page. From the TeX source it lists every result, digested or not; while choosing, a box on each one not digested and on each stub, and a button that digests those ticked. From a PDF alone it is the PDF's own outline, the person's marks under the section their page falls in, and then the stubs no place is known for, with "locate in PDF".
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import * as api from '$lib/library/api';
	import { said } from '$lib/library/said';
	import type { OutlineItem, WorkAnswer } from '$lib/library/types';
	import { pdfOutline, sectionOf, type OutlineEntry } from '$lib/pdf/outline';
	import { message } from '$lib/shell/message.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { library as words } from '$lib/words/library';

	let { work }: { work: WorkAnswer } = $props();

	const ref = $derived(work.ref);
	const outline = $derived(work.outline);
	const choosing = $derived(lib.choosing === ref);
	const beside = $derived(lib.beside[ref]);

	// the PDF's own outline, for a work held only as a PDF
	let pdfOwn = $state<OutlineEntry[]>([]);
	$effect(() => {
		const pdf = work.holds.pdf;
		if (outline?.from !== 'pdf' || !pdf) return void (pdfOwn = []);
		void pdfOutline(api.pdfUrl(pdf)).then((o) => (pdfOwn = o));
	});

	const keyOf = (it: OutlineItem) => it.item ?? it.node ?? it.name;
	const chooseable = (it: OutlineItem) => !it.paper || it.paper === 'stub';
	const isOn = (it: OutlineItem) => !!beside && (('node' in beside && it.node === beside.node) || ('item' in beside && it.item === beside.item));

	function open(it: OutlineItem): void {
		lib.beside = { ...lib.beside, [ref]: it.node ? { node: it.node } : { item: it.item! } };
		const page = it.page ?? outline?.sections.find((s) => s.section === it.section)?.page ?? null;
		if (page) lib.go(ref, page);
	}

	function tick(it: OutlineItem): void {
		const k = keyOf(it);
		if (lib.ticks.has(k)) lib.ticks.delete(k);
		else lib.ticks.add(k);
	}

	async function digestTicked(): Promise<void> {
		const chosen = [...lib.ticks];
		lib.stopChoosing();
		const done = await api.digest([ref], 'chosen', chosen);
		if (!done.ok) return message.post(said(done.error));
		message.post(done.value.job ? words.digest.reading : words.digest.made(done.value.made));
	}

	async function locate(): Promise<void> {
		const first = work.unplaced[0];
		if (!first) return;
		const found = await api.find(ref, first.name);
		if (found.ok && found.value.hits[0]) lib.go(ref, found.value.hits[0].page);
	}
	/** The person's marks in page order, whatever order they were made in. */
	const byPage = $derived([...work.marks].sort((a, b) => a.page - b.page));
</script>

{#if outline?.from === 'tex'}
	<div class="rl">{words.column.contents}</div>
	{#if outline.state === 'reading'}<p class="small grey pad">{words.column.reading}</p>{/if}
	{#if outline.uncounted}<p class="small grey pad" data-testid="outline-uncounted">{words.column.uncounted[outline.uncounted]}</p>{/if}
	{#each outline.sections as s (s.section)}
		{@const items = outline.items.filter((it) => it.section === s.section)}
		<button type="button" class="osec" onclick={() => s.page && lib.go(ref, s.page)} data-testid="outline-section"><span class="num">{s.number}</span> {s.title}{#if s.page}<span class="pg">{words.column.page(s.page)}</span>{/if}</button>
		{#if items.length}
			<ul class="olist">
				{#each items as it (keyOf(it))}
					<li class:on={isOn(it)} class:avail={!it.paper}>
						{#if choosing && chooseable(it)}<input type="checkbox" checked={lib.ticks.has(keyOf(it))} onchange={() => tick(it)} aria-label={it.name} data-testid="outline-tick" />{/if}
						<button type="button" class="row" onclick={() => open(it)} data-testid="outline-item">
							<span class="slot">{#if it.paper}<Mark kind={paperMark(it.paper)} />{/if}</span><span class="slot">{#if it.lean}<Mark kind={leanMark(it.lean)} />{/if}</span>
							<span class="nm">{it.name.split(' ').pop()}</span><span class="rt">{it.name.split(' ').slice(0, -1).join(' ')}{it.title ? ` · ${it.title}` : ''}</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	{/each}
	{#each outline.items.filter((it) => !it.section) as it (keyOf(it))}
		<ul class="olist">
			<li class:on={isOn(it)}>
				{#if choosing && chooseable(it)}<input type="checkbox" checked={lib.ticks.has(keyOf(it))} onchange={() => tick(it)} aria-label={it.name} />{/if}
				<button type="button" class="row" onclick={() => open(it)}><span class="slot">{#if it.paper}<Mark kind={paperMark(it.paper)} />{/if}</span><span class="slot"></span><span class="nm">{it.name.split(' ').pop()}</span><span class="rt">{it.name.split(' ').slice(0, -1).join(' ')}</span></button>
			</li>
		</ul>
	{/each}
	{#if choosing}
		<div class="tickbar">
			<button type="button" class="btn primary" disabled={lib.ticks.size === 0} onclick={() => void digestTicked()} data-testid="digest-chosen">{words.column.digestChosen(lib.ticks.size)}</button>
			<button type="button" class="linkish grey" onclick={() => lib.stopChoosing()}>{words.column.cancel}</button>
		</div>
	{/if}
{:else if outline?.from === 'pdf'}
	<div class="rl">{words.column.contentsFromPdf}</div>
	{#each pdfOwn.filter((e) => e.level === 1) as e, i (i)}
		{@const at = pdfOwn.indexOf(e)}
		<button type="button" class="osec" onclick={() => e.page && lib.go(ref, e.page)}>{e.title}{#if e.page}<span class="pg">{words.column.page(e.page)}</span>{/if}</button>
		{@const marks = byPage.filter((m) => sectionOf(pdfOwn, m.page) === at)}
		{@const items = outline.items.filter((it) => it.page !== null && sectionOf(pdfOwn, it.page) === at)}
		{#if marks.length || items.length}
			<ul class="olist">
				{#each items as it (keyOf(it))}
					<li class:on={isOn(it)}><button type="button" class="row" onclick={() => open(it)}><span class="slot">{#if it.paper}<Mark kind={paperMark(it.paper)} />{/if}</span><span class="slot"></span><span class="nm">{it.name.split(' ').pop()}</span><span class="rt">{it.name.split(' ').slice(0, -1).join(' ')}</span></button></li>
				{/each}
				{#each marks as m (m.mark)}
					<li><button type="button" class="row" onclick={() => lib.go(ref, m.page)} data-testid="outline-mark"><span class="slot"><Mark kind="marked" /></span><span class="slot"></span><span class="nm">{words.column.page(m.page)}</span><span class="mk">“{m.words}”</span></button></li>
				{/each}
			</ul>
		{/if}
	{/each}
	{#if pdfOwn.length === 0 && work.marks.length}
		<ul class="olist">
			{#each byPage as m (m.mark)}
				<li><button type="button" class="row" onclick={() => lib.go(ref, m.page)} data-testid="outline-mark"><span class="slot"><Mark kind="marked" /></span><span class="slot"></span><span class="nm">{words.column.page(m.page)}</span><span class="mk">“{m.words}”</span></button></li>
			{/each}
		</ul>
	{/if}
	{#if pdfOwn.length === 0 && !work.marks.length && !outline.items.length && !work.unplaced.length}<p class="small grey pad">{words.column.nothingDigested}</p>{/if}
	{#if work.unplaced.length}
		<div class="rl">{words.column.unplaced}</div>
		<ul class="olist flat">
			{#each work.unplaced as u (u.node)}
				<li><span class="row still"><span class="slot"><Mark kind={paperMark(u.paper)} /></span><span class="slot"></span><span class="nm">{u.name.split(' ').pop()}</span><span class="rt">{u.name.split(' ').slice(0, -1).join(' ')}</span></span></li>
			{/each}
		</ul>
		<div class="small grey pad">{words.column.notRead} · <button type="button" class="linkish small" onclick={() => void locate()} data-testid="locate-in-pdf">{words.column.locate}</button></div>
	{/if}
{:else}
	<p class="small grey pad" data-testid="outline-not-read">{words.column.notReadYet}</p>
{/if}

<style>
	.rl {
		font-size: 11px;
		color: var(--ink-faint);
		margin: 14px 2px 5px;
	}
	.pad {
		padding: 2px 6px;
	}
	.osec {
		font: inherit;
		display: flex;
		align-items: baseline;
		gap: 6px;
		width: 100%;
		min-height: 26px;
		padding: 3px 6px;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink);
		font-weight: 500;
		text-align: left;
		cursor: pointer;
	}
	.osec:hover {
		background: var(--ann-neutral-wash);
	}
	.osec .num {
		color: var(--ink-faint);
		font-weight: 400;
	}
	.pg {
		margin-left: auto;
		color: var(--ink-faint);
		font-weight: 400;
		font-size: 11px;
	}
	.olist {
		list-style: none;
		margin: 0 0 4px;
		padding: 0;
	}
	.olist li {
		display: flex;
		align-items: center;
		gap: 2px;
		border-radius: 6px;
	}
	.olist li.on {
		background: var(--link-wash);
	}
	.olist li.avail .row {
		color: var(--ink-soft);
	}
	.olist input {
		margin: 0 0 0 4px;
	}
	.row {
		font: inherit;
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 4px;
		height: 26px;
		padding: 0 6px;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink);
		text-align: left;
		cursor: pointer;
	}
	.row:hover {
		background: var(--ann-neutral-wash);
	}
	.row.still {
		cursor: default;
	}
	.slot {
		width: 14px;
		display: inline-flex;
		justify-content: center;
		flex: none;
	}
	.nm {
		color: var(--ink-faint);
		min-width: 30px;
		font-variant-numeric: tabular-nums;
	}
	.rt,
	.mk {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.tickbar {
		position: sticky;
		bottom: 0;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 2px;
		background: var(--leaf);
	}
</style>
