<script lang="ts">
	// The list of works drawn as a table (1): the columns the person keeps (Title, Authors, Year and Digested by default; Loom has and Used in from the columns menu), any of them sorting, the title breaking ties. A click opens a work in its tab; ⌘-click selects it for "everything in the papers I select". On a row, its own `digest…` and a menu: its source, its entry, delete. A row being looked up, or made while the network was off, says so in its title's place; one a quilt that has not said whether loom may use the network refuses to look up asks whether to, this once.
	import { said } from '$lib/library/said';
	import Icon from '$lib/components/Icon.svelte';
	import * as api from '$lib/library/api';
	import type { Work } from '$lib/library/types';
	import { asking, lastAdded } from '$lib/library/added.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { library as words } from '$lib/words/library';
	import { COLUMNS, lib, type Column } from './state.svelte';
	import { menus } from './menus.svelte';
	import DigestMenu from './DigestMenu.svelte';
	import { served } from '$lib/library/served.svelte';

	let { works }: { works: Work[] } = $props();

	const WIDTH: Record<Column, string> = { title: '52%', authors: '20%', year: '64px', digested: '170px', holds: '120px', used: '120px' };
	const shownCols = $derived(COLUMNS.filter((c) => lib.cols[c]));

	function sortBy(c: Column): void {
		lib.sort = lib.sort.key === c ? { key: c, dir: lib.sort.dir === 1 ? -1 : 1 } : { key: c, dir: 1 };
	}

	function opened(e: MouseEvent | KeyboardEvent, w: Work): void {
		if (e.metaKey || e.ctrlKey || e.shiftKey) {
			if (lib.multi.has(w.ref)) lib.multi.delete(w.ref);
			else lib.multi.add(w.ref);
			return;
		}
		lib.openWork(w.ref);
	}

	const holds = (w: Work) => (w.holds.pdf && w.holds.tex ? words.column.holds.both : w.holds.pdf ? words.column.holds.pdf : w.holds.tex ? words.column.holds.tex : words.column.holds.none);
	const used = (w: Work) => w.used_in.map((d) => d.split('/').pop()).join(', ');
	const digested = (w: Work) => (w.digested ? words.works.digested(w.digested.statements, w.digested.of, w.digested.compared) : '');

	async function remove(w: Work): Promise<void> {
		menus.open = null;
		const done = await api.remove(w.ref);
		if (!done.ok) return message.post(said(done.error));
		lib.closeWork(w.ref);
		message.post(words.works.deleted(w.short), () => api.restore(done.value.undo));
	}

	// a quilt that has not said whether loom may use the network, or keeps it offline, refuses a plain look-up; the row then asks whether to look it up this once
	async function lookUp(w: Work, once = false): Promise<void> {
		asking.delete(w.ref);
		const done = await api.lookUp(w.ref, once);
		if (done.ok) return;
		if (done.error.code === 'network-unasked' || done.error.code === 'offline') asking.add(w.ref);
		else message.post(said(done.error));
	}
</script>

<div class="scroll">
	<table class="works" data-testid="works-table">
		<thead>
			<tr>
				{#each shownCols as c (c)}
					<th style:width={WIDTH[c]} class:sorted={lib.sort.key === c} aria-sort={lib.sort.key === c ? (lib.sort.dir > 0 ? 'ascending' : 'descending') : 'none'}>
						<button type="button" class="head" onclick={() => sortBy(c)} data-testid="sort-{c}">{words.works.cols[c]}{lib.sort.key === c ? (lib.sort.dir > 0 ? ' ↑' : ' ↓') : ''}</button>
					</th>
				{/each}
				<th class="act" style:width="88px">
					<span class="menuwrap">
						<button type="button" class="ib" title={words.works.colsOpen} aria-label={words.works.colsOpen} data-testid="works-columns" onclick={() => menus.toggle('cols')}><Icon name="caret" size={16} /></button>
						{#if menus.open === 'cols'}
							<div class="menu cols">
								<div class="mh">{words.works.colsHead}</div>
								{#each COLUMNS as c (c)}
									<button type="button" class="mi" disabled={c === 'title'} onclick={() => (lib.cols = { ...lib.cols, [c]: !lib.cols[c] })} data-testid="col-{c}"><span class="chk">{lib.cols[c] ? '✓' : ''}</span>{words.works.cols[c]}</button>
								{/each}
							</div>
						{/if}
					</span>
				</th>
			</tr>
		</thead>
		<tbody>
			{#each works as w (w.ref)}
				{@const hot = menus.open === `row:${w.ref}` || menus.open === `more:${w.ref}`}
				<tr class:sel={lastAdded.ref === w.ref} class:multi={lib.multi.has(w.ref)} class:hot onclick={(e) => opened(e, w)} data-testid="work-row" data-ref={w.ref}>
					{#each shownCols as c (c)}
						{#if c === 'title'}
							<td class="t">
								{#if asking.has(w.ref) && w.lookup?.state === 'unconfirmed'}
									<span>{words.works.identifier(w.lookup.identifier)}</span><span class="found ask">{words.works.lookAsk}</span>
									<button type="button" class="linkish small" onclick={(e) => { e.stopPropagation(); void lookUp(w, true); }} data-testid="look-yes">{words.works.yes}</button>
									<button type="button" class="linkish small quiet" onclick={(e) => { e.stopPropagation(); asking.delete(w.ref); }} data-testid="look-not">{words.works.notNow}</button>
								{:else if w.lookup?.state === 'looking'}
									<span class="grey">{w.title}</span><span class="found">{words.works.lookingUp}</span>
								{:else if w.lookup?.state === 'unconfirmed'}
									<span>{words.works.identifier(w.lookup.identifier)}</span><span class="found">{words.works.unconfirmed}</span>
									<button type="button" class="linkish small" onclick={(e) => { e.stopPropagation(); void lookUp(w); }}>{words.works.lookUp}</button>
								{:else}
									<button type="button" class="open" onclick={(e) => { e.stopPropagation(); opened(e, w); }} data-testid="work-open">{w.title}</button>{#if w.version}<span class="found">· {words.works.version(w.version)}</span>{/if}
								{/if}
							</td>
						{:else if c === 'authors'}
							<td>{words.byline(w.authors)}</td>
						{:else if c === 'year'}
							<td>{w.year}</td>
						{:else if c === 'digested'}
							<td class="d">{digested(w)}</td>
						{:else if c === 'holds'}
							<td class="d">{holds(w)}</td>
						{:else}
							<td class="d">{used(w)}</td>
						{/if}
					{/each}
					<td class="act">
						{#if served.has('library-digest')}<span class="menuwrap">
							<button type="button" class="ctl" onclick={(e) => { e.stopPropagation(); menus.toggle(`row:${w.ref}`); }} data-testid="row-digest">{words.works.digest}</button>
							{#if menus.open === `row:${w.ref}`}<DigestMenu target={w} />{/if}
						</span>{/if}
						<span class="menuwrap">
							<button type="button" class="ctl ib" title={words.works.rowMenu} aria-label={words.works.rowMenu} onclick={(e) => { e.stopPropagation(); menus.toggle(`more:${w.ref}`); }} data-testid="row-more"><span aria-hidden="true">⋯</span></button>
							{#if menus.open === `more:${w.ref}`}
								<!-- svelte-ignore a11y_click_events_have_key_events -->
								<!-- svelte-ignore a11y_no_static_element_interactions -->
								<div class="menu more" onclick={(e) => e.stopPropagation()}>
									<button type="button" class="mi" disabled={!w.link} onclick={() => { menus.open = null; if (w.link) window.open(w.link, '_blank', 'noopener'); }}>{words.works.openSource}</button>
									<button type="button" class="mi" onclick={() => { menus.open = null; lib.openWork(w.ref); }}>{words.works.editEntry}</button>
									<hr />
									<button type="button" class="mi" data-testid="row-delete" onclick={() => void remove(w)}>{words.works.delete}</button>
								</div>
							{/if}
						</span>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.scroll {
		flex: 1;
		overflow: auto;
		padding: 0 20px 20px;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		table-layout: fixed;
	}
	th {
		position: sticky;
		top: 0;
		background: var(--paper);
		font-size: 11px;
		color: var(--ink-faint);
		font-weight: 400;
		text-align: left;
		padding: 0;
		border-bottom: 1px solid var(--rule);
		white-space: nowrap;
		z-index: 2;
	}
	th .head {
		font: inherit;
		color: inherit;
		background: none;
		border: 0;
		padding: 7px 10px 6px;
		cursor: pointer;
		width: 100%;
		text-align: left;
	}
	th:hover,
	th.sorted {
		color: var(--ink);
	}
	th.act {
		text-align: right;
	}
	td {
		height: 28px;
		line-height: 18px;
		padding: 0 10px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		cursor: default;
	}
	tbody tr:nth-child(even) td {
		background: var(--leaf);
	}
	tbody tr:hover td {
		background: var(--ann-neutral-wash);
	}
	tbody tr.sel td {
		background: var(--link-wash);
	}
	tbody tr.multi td {
		background: var(--link-wash);
	}
	td.t {
		font-family: var(--serif);
		font-size: 14px;
	}
	td.d {
		color: var(--ink-faint);
		font-size: 11px;
	}
	td.act {
		text-align: right;
		padding: 0 2px 0 0;
		overflow: visible;
		line-height: 0;
		vertical-align: middle;
	}
	/* a row's own controls show on the row under the pointer or holding the keyboard, and are in the tab order always */
	td.act .ctl {
		opacity: 0;
	}
	tr:hover td.act .ctl,
	tr.hot td.act .ctl,
	tr:focus-within td.act .ctl {
		opacity: 1;
	}
	.open {
		font: inherit;
		color: inherit;
		text-align: left;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}
	.open:focus-visible {
		outline: 2px solid var(--link);
		outline-offset: 2px;
	}
	.found.ask {
		color: var(--ink);
	}
	.quiet {
		color: var(--ink-faint);
	}
	.found {
		font-family: var(--sans);
		font-size: 11px;
		color: var(--ink-faint);
		margin-left: 8px;
	}
	.ctl {
		font: inherit;
		border: 0;
		background: none;
		color: var(--ink-faint);
		cursor: pointer;
		padding: 0 8px;
		min-width: 28px;
		height: 28px;
		border-radius: 6px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	.ctl:hover {
		background: var(--ann-neutral-wash);
		color: var(--ink);
	}
	.cols {
		right: 0;
		top: calc(100% + 4px);
		width: 190px;
		line-height: 1.45;
	}
	.more {
		right: 0;
		top: calc(100% + 4px);
		width: 200px;
		line-height: 1.45;
	}
</style>
