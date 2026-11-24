<script lang="ts">
	// Review › Your Changes: the mathematics first, then what waits to be kept. One document at a time, the blocks waiting to be accepted (changed since accepted, or taken in from a copy or a pull): Accept records the person's reading, for one block or a selection; what loom cannot accept says why in its row. Never accepted and accepted blocks are folded beneath, uncounted. Then every change waiting in the person's text, quilt-wide, a card each (`ChangeCard`) grouped by the document that lists it: suggestions not yet kept or discarded and, where the quilt tracks edits (`[review] track_edits`), edits made in their files since their look. Keep and Discard act as they do in the document, one change or all of a document's at once, and the last keep or discard of a suggestion is undone from the bar; neither says whether the mathematics is right. To do adds, beside each document's changes, the open annotations from others, each linking to its place. Each answer is said in its row while the row stands, else in the bar. On a served quilt Review draws it in two parts (`part`): Waiting to be accepted under Accepted results that changed, every document's blocks by document with no choice of document, each block once (`acceptSections`); Changes to keep with the agents' copies under Proposed edits; each narrowed to the draft the column chooses (`views/review/yours.ts`).
	import { barShown } from '$lib/shell/scrollbars';
	import '$lib/review/review.css';
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { store } from '$lib/manifest/client.svelte';
	import { can, write } from '$lib/write';
	import { displayNode } from '$lib/nodes/display';
	import { anchorId, readUrl, reviewReadUrl } from '$lib/nav';
	import { causeLabel } from '$lib/review/evidence';
	import { notesOf } from '$lib/review/queue';
	import { acceptanceOf, todoOf, waitingIn, type BlockRow } from '$lib/review/yourChanges';
	import { acted } from '$lib/review/acted.svelte';
	import { allSays, ready } from '$lib/review/changes';
	import { discardChanges, history, keepChanges, nextUndo, undo, type ChangeAnswer } from '$lib/review/history.svelte';
	import { itemLabel, dotVars } from '$lib/fragments/gutter';
	import { reviewRowBadge, shortDate } from '$lib/badges';
	import NoDrafts from '$lib/components/NoDrafts.svelte';
	import Badge from '$lib/components/Badge.svelte';
	import HelpDot from '$lib/components/HelpDot.svelte';
	import ActionBar from '$lib/review/ActionBar.svelte';
	import ChangeCard from '$lib/review/ChangeCard.svelte';
	import Empty from '$lib/review/Empty.svelte';
	import ReviewHeading from '$lib/review/ReviewHeading.svelte';
	import Said from '$lib/review/Said.svelte';
	import Copies from '$lib/views/review/Copies.svelte';
	import { rv } from '$lib/views/review/state.svelte';
	import { acceptSections, blockDocuments, changeGroups, type AcceptSection, type Part } from '$lib/views/review/yours';
	import { review as reviewWords } from '$lib/words/review';

	let { part }: { part?: Part } = $props();
	// which sections are drawn: both on the page of its own, one under its kind in Review
	const accepts = $derived(part !== 'changes');
	const keeps = $derived(part !== 'accept');
	// the draft Review's column narrows to, which either part follows
	const draft = $derived(part ? rv.doc : null);

	type Answer = { accepted?: string[]; refused?: { key: string; why: string }[] };

	/** How many rows of a list are drawn open; past it each group is folded until asked for. */
	const OPEN = 12;

	const m = $derived(store.manifest!);
	// every pending change, by document, those just kept or discarded gone at once; in a draft, those in its text
	const groups = $derived(changeGroups(m, acted.map, draft));
	const changeCount = $derived(groups.reduce((n, g) => n + g.changes.length, 0));
	const todo = $derived(todoOf(m).filter((t) => !draft || t.path === draft));
	const todoCount = $derived(todo.reduce((n, g) => n + g.annotations.length, 0));
	// To do: the open annotations from others, beside the changes of the document they are in, and in a group of their own where it has none
	let todoOn = $state(false);
	const todoAlone = $derived(todo.filter((t) => !groups.some((g) => g.path === t.path)));

	// the documents with blocks to accept: in Review every one, or the draft the column chooses; on the page of its own one at a time, asked for by name, else the first with something waiting, else the default
	const mine = $derived(blockDocuments(m));
	const waiting = (path: string) => waitingIn(acceptanceOf(m, path));
	const all = $derived(part === 'accept' && !draft);
	const doc = $derived(draft ? mine.find((x) => x.path === draft) : mine.find((x) => x.path === page.url.searchParams.get('document')) ?? mine.find((x) => waiting(x.path) > 0) ?? mine.find((x) => x.default) ?? mine[0]);
	const file = $derived(doc ? doc.path.split('/').pop()! : '');
	// what is drawn, by document, each block once
	const sections = $derived<AcceptSection[]>(all ? acceptSections(m) : doc ? [{ path: doc.path, file, a: acceptanceOf(m, doc.path) }] : []);
	const y = $derived(all ? null : (sections[0]?.a ?? null));
	const lists = $derived(y ? [...y.changed, ...y.taken.flatMap((t) => t.rows)] : []);
	const changedCount = $derived(sections.reduce((n, s) => n + s.a.changed.length, 0));
	const takenCount = $derived(sections.reduce((n, s) => n + s.a.taken.reduce((k, t) => k + t.rows.length, 0), 0));
	// the document each drawn block is listed under, which names it
	const home = $derived(new Map(sections.flatMap((s) => [...s.a.changed, ...s.a.taken.flatMap((t) => t.rows), ...s.a.never, ...s.a.accepted].map((b) => [b.key, s.path] as const))));
	const reviewer = $derived(m.reviewer?.name ?? '');
	const since = $derived(m.changes_since ? m.changes_since.when.slice(0, 16).replace('T', ' ') : '');
	// whether edits in place since the person's look wait here too, as well as suggestions
	const tracked = $derived(m.config?.review?.track_edits === true);

	let served = $state(false);
	let writes = $state({ keep: false, discard: false });
	const acts = $derived(served && !!reviewer);
	let picked = $state<Set<string>>(new Set());
	// what is running, by where it was asked: '*' for the page, a block's key, or a group's path
	let busy = $state('');
	let said = $state<{ at: string; text: string; refused: boolean } | null>(null);
	onMount(() => {
		void can('review-accept').then((yes) => (served = yes));
		void can('change-keep').then((yes) => (writes.keep = yes));
		void can('change-discard').then((yes) => (writes.discard = yes));
	});

	const name = (key: string) => displayNode(m, key, home.get(key) ?? doc?.path).name;
	/** In Review's sections, a block a row names is laid over Review at it (see it, `SeeIt`) where the quilt has the draft, never opened in Docs; null where it has not, and the block is named in words. */
	const seeIn = (path: string | null | undefined): ((key: string) => void) | null => (path && m.masters.some((x) => x.path === path) ? (key: string) => (rv.over = { doc: path, key, name: name(key) }) : null);
	const lower = (t: string) => t.charAt(0).toLowerCase() + t.slice(1);
	const some = (n: number, words: string) => (n ? `${n} ${words}` : '');

	/** Why a block changed since it was accepted: its first cause, and how many more. */
	function why(key: string): string {
		const causes = m.keys[key]?.acceptance?.causes ?? [];
		if (!causes.length) return '';
		const first = causes[0].kind === 'own-text-changed' ? 'changed since you accepted' : causeLabel(m, causes[0]);
		return first + (causes.length > 1 ? `, and ${causes.length - 1} more` : '');
	}
	const acceptable = (rows: BlockRow[]) => rows.filter((b) => b.row && !b.row.refusal).map((b) => b.key);
	function toggle(key: string): void {
		const next = new Set(picked);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		picked = next;
	}
	function toggleGroup(rows: BlockRow[]): void {
		const keys = acceptable(rows);
		const all = keys.every((k) => picked.has(k));
		const next = new Set(picked);
		for (const k of keys) {
			if (all) next.delete(k);
			else next.add(k);
		}
		picked = next;
	}
	const allPicked = (rows: BlockRow[]) => acceptable(rows).length > 0 && acceptable(rows).every((k) => picked.has(k));

	/** Whether the row asked from, a block's key, is still drawn. */
	function stands(at: string): boolean {
		const now = store.manifest;
		if (!now || (!all && !doc)) return false;
		return acceptSections(now, all ? null : doc!.path).some((s) => [...s.a.changed, ...s.a.taken.flatMap((t) => t.rows), ...s.a.never].some((b) => b.key === at));
	}

	/** Accept `keys` at once; what loom accepts leaves its row, and each refusal is said by the block it refuses, in the row when one was pressed, in the bar for a selection. */
	async function accept(keys: string[], at: string): Promise<void> {
		busy = at;
		said = null;
		const done = (await write('review-accept', { keys })) as Awaited<ReturnType<typeof write>> & Answer;
		let text: string;
		let refused: boolean;
		if (!done.ok) {
			text = done.error?.message ?? 'The publisher refused it.';
			refused = true;
		} else {
			const ok = done.accepted ?? [];
			const no = done.refused ?? [];
			const lines = ok.length ? [ok.length === 1 ? `Accepted ${name(ok[0])}.` : `Accepted ${ok.length} blocks.`] : [];
			for (const r of no) lines.push(at === '*' ? `${name(r.key)}: ${lower(r.why)}` : r.why);
			text = lines.join('\n');
			refused = !ok.length;
			picked = new Set([...picked].filter((k) => !ok.includes(k)));
			await store.refresh();
		}
		said = { at: at !== '*' && stands(at) ? at : '*', text, refused };
		busy = '';
	}

	/** Keep or discard every ready change of one group, as the document's Changes menu does; what is refused is said in the bar. */
	async function every(how: 'keep' | 'discard', g: (typeof groups)[number]): Promise<void> {
		busy = g.path;
		said = null;
		const which = g.document ? { all: true as const, document: g.path } : { changes: g.changes.filter(ready).map((c) => c.id) };
		const res: ChangeAnswer = how === 'keep' ? await keepChanges(which) : await discardChanges(which);
		const done = res.done?.length;
		const refused = res.refused ?? [];
		const verb = how === 'keep' ? 'Kept' : 'Discarded';
		const text = !res.ok ? (res.error?.message ?? 'The publisher refused it.') : [done !== undefined ? `${verb} ${done} ${done === 1 ? 'change' : 'changes'} in ${g.label}.` : `${verb} the changes in ${g.label}.`, ...refused.map((r) => r.why)].join('\n');
		said = { at: '*', text, refused: !res.ok || (done === 0 && refused.length > 0) };
		busy = '';
	}

	/** Undo the last keep or discard, saying loom's refusal where there is one. */
	async function back(): Promise<void> {
		const why = await undo();
		said = why ? { at: '*', text: why, refused: true } : null;
	}

	// a link to one block's row (a block's "See this block in Review") opens the fold it is in
	$effect(() => {
		const hash = page.url.hash.slice(1);
		if (!hash || !sections.length) return;
		void tick().then(() => {
			const row = window.document.getElementById(hash);
			const fold = row?.closest('details');
			if (fold && !fold.open) fold.open = true;
			row?.scrollIntoView({ block: 'center' });
		});
	});
</script>

{#snippet goes(text: string, href: string, path: string, key: string, cls: string, testid?: string)}
	{@const see = part ? seeIn(path) : undefined}
	{#if see === undefined}<a class={cls} {href} data-testid={testid}>{text}</a>{:else if see}<button type="button" class="see {cls}" data-testid={testid} onclick={() => see(key)}>{text}</button>{:else}<span class={cls} data-testid={testid}>{text}</span>{/if}
{/snippet}

{#snippet todoRows(list: import('$lib/manifest/types').Annotation[], path: string)}
	<ul class="todo" data-testid="todo-list">
		{#each list as a (a.id)}
			<li data-testid="todo-row" data-annotation={a.id}>
				<span class="dot" style={dotVars(a)}></span>
				{@render goes(itemLabel(m, a), `quilt:${a.id}`, path, a.target.key, 'open', 'todo-open')}
				<span class="of">{shortDate(a.created)}</span>
			</li>
		{/each}
	</ul>
{/snippet}

{#snippet blockRow(b: BlockRow, path: string)}
	{@const r = b.row}
	{@const cause = r?.cause === 'earlier-change' ? why(b.key) || 'changed since you accepted' : ''}
	{@const context = displayNode(m, b.key, path).context}
	<li class="block" id={`review-${anchorId(b.key)}`} data-testid="review-row" data-key={b.key}>
		<div class="line">
			{#if acts && r}<input type="checkbox" disabled={!!r.refusal} checked={picked.has(b.key)} onchange={() => toggle(b.key)} aria-label={`Select ${name(b.key)}`} data-testid="review-pick" />{/if}
			{@render goes(name(b.key), reviewReadUrl(path, b.key), path, b.key, 'name')}
			{#if context}<span class="of">{context}</span>{/if}
			{#if cause}<span class="tag changed" data-testid="tag-changed">{cause}</span>{/if}
			{#each notesOf(m, b.key) as note (note)}{@render goes(note, reviewReadUrl(path, b.key), path, b.key, 'note', 'review-note')}{/each}
			<span class="acts">
				<!-- See change opens the draft in Docs, where the change since acceptance is drawn with its causes; see it draws neither -->
				{#if r}
					{@const see = part ? seeIn(path) : undefined}
					{#if cause || see === undefined}<a class="btn quiet small" href={reviewReadUrl(path, b.key, cause ? 0 : undefined)} data-testid="review-read">{cause ? 'See change' : 'Read'}</a>{:else if see}<button type="button" class="btn quiet small" data-testid="review-read" onclick={() => see(b.key)}>Read</button>{/if}
				{/if}
				{#if acts && r && !r.refusal}<button class="btn small primary" disabled={!!busy} onclick={() => void accept([b.key], b.key)} data-testid="review-accept">{busy === b.key ? 'Accepting…' : 'Accept'}</button>{/if}
			</span>
		</div>
		{#if r?.refusal}<p class="cannot" data-testid="review-refusal">Can't be accepted yet: {lower(r.refusal)}</p>{/if}
		{#if said?.at === b.key}<Said text={said.text} refused={said.refused} testid="review-said" />{/if}
	</li>
{/snippet}

{#snippet group(id: string, title: string, rows: BlockRow[], open: boolean, path: string)}
	<details {open} class="group" data-testid="review-group" data-group={id}>
		<summary>
			{#if acts && acceptable(rows).length}<input type="checkbox" checked={allPicked(rows)} onclick={(e) => e.stopPropagation()} onchange={() => toggleGroup(rows)} aria-label={`Select every block ${title.toLowerCase()} that can be accepted`} data-testid="review-pick-group" />{/if}
			<span class="title">{title}</span> <span class="count" data-testid="review-group-count">{rows.length}</span>
		</summary>
		<ul>{#each rows as b (b.key)}{@render blockRow(b, path)}{/each}</ul>
	</details>
{/snippet}

{#snippet choice()}
	{#if mine.length > 1}<select aria-label="Document" data-testid="review-document" value={doc!.path} onchange={(e) => goto(`?document=${encodeURIComponent(e.currentTarget.value)}`)}>{#each mine as d (d.path)}<option value={d.path}>{d.path.split('/').pop()}{waiting(d.path) ? ` · ${waiting(d.path)}` : ''}</option>{/each}</select>{:else}<strong>{file}</strong>{/if}
{/snippet}

{#snippet bar()}
	<ActionBar said={said?.at === '*' ? said.text : ''} refused={said?.refused} testid="review-bar">
		{#snippet lead()}
			{#if draft && part === 'accept'}{#if doc}<strong>{file}</strong>{/if}{:else if part !== 'changes'}<span class="muted" data-testid="review-summary">{[some(changedCount, 'changed since you accepted'), some(takenCount, 'taken in'), part ? '' : some(changeCount, changeCount === 1 ? 'change waiting' : 'changes waiting'), reviewer ? `reviewing as ${reviewer}` : ''].filter(Boolean).join(' · ') || (part ? '' : 'Nothing waits')}</span>{/if}
		{/snippet}
		{#snippet actions()}
			<!-- a keep or a discard, here or in a document, is undone as the document's toolbar undoes it -->
			{#if keeps && (nextUndo().startsWith('discard') || nextUndo().startsWith('keep'))}<button type="button" class="btn small quiet" disabled={history.busy} data-testid="review-undo" onclick={() => void back()}>Undo {nextUndo()}</button>{/if}
			{#if keeps}<button type="button" class="btn small" class:on={todoOn} aria-pressed={todoOn} title="To do: the open annotations from others, beside the changes" data-testid="your-todo" onclick={() => (todoOn = !todoOn)}>To do <span class="badge">{changeCount + todoCount}</span></button>{/if}
			{#if accepts && acts && picked.size}
				<span data-testid="review-picked">{picked.size} selected</span>
				<button class="btn primary" disabled={!!busy} onclick={() => void accept([...picked], '*')} data-testid="review-accept-picked">{busy === '*' ? 'Accepting…' : `Accept ${picked.size}`}</button>
				<button class="btn quiet" onclick={() => (picked = new Set())} data-testid="review-clear">Clear</button>
			{/if}
		{/snippet}
	</ActionBar>
{/snippet}

{#snippet accepting()}
	{#if !reviewer}<p class="muted" data-testid="review-no-reviewer">Choose your reviewer name in Settings to accept.</p>
	{:else if !served}<p class="muted" data-testid="review-read-only">This copy of the quilt only reads; accepting needs the quilt served for writing.</p>{/if}
	{#if !mine.length}<NoDrafts what="blocks to review" />
	{:else if draft && !doc}<Empty text={reviewWords.yours.none(draft)} testid="review-empty" />
	{:else if all}
		{#if !changedCount && !takenCount}<Empty text={reviewWords.yours.nothing} testid="review-empty" />{/if}
		{#each sections as s (s.path)}
			<section class="document" data-testid="accept-document" data-path={s.path}>
				<div class="dhead"><span class="title">{s.file}</span>{#if waitingIn(s.a)}<span class="count" data-testid="accept-document-count">{waitingIn(s.a)}</span>{/if}</div>
				{@render blocks(s)}
			</section>
		{/each}
	{:else if y && doc}
		{#if !part}<p class="pick">{@render choice()}</p>{/if}
		{#if !lists.length && !y.never.length}<Empty text={`Every block of ${file} is accepted.`} testid="review-empty" />{/if}
		{@render blocks(sections[0])}
	{/if}
{/snippet}

{#snippet blocks(s: AcceptSection)}
	{#if s.a.changed.length}{@render group('changed', 'Changed', s.a.changed, s.a.changed.length <= OPEN, s.path)}{/if}
	{#each s.a.taken as t (t.label)}{@render group('taken', t.label, t.rows, true, s.path)}{/each}
	{#if s.a.never.length}{@render group('never', 'Never accepted', s.a.never, false, s.path)}{/if}
	{#if s.a.accepted.length}
		<details class="group" data-testid="review-group" data-group="accepted">
			<summary><span class="title">Accepted</span> <span class="count" data-testid="review-group-count">{s.a.accepted.length}</span></summary>
			<ul>
				{#each s.a.accepted as k (k.key)}
					<li class="block" id={`review-${anchorId(k.key)}`} data-testid="review-row" data-key={k.key}>
						<div class="line">
							{@render goes(name(k.key), readUrl(s.path, k.key), s.path, k.key, 'name')}
							<Badge parts={reviewRowBadge(m, k)} />
							{#if k.acceptance}<span class="of">by {k.acceptance.author}, {shortDate(k.acceptance.date)}</span>{/if}
						</div>
					</li>
				{/each}
			</ul>
		</details>
	{/if}
{/snippet}

{#snippet keeping()}
	<section class="changes" data-testid="your-change-list">
		{#each groups as g (g.path)}
			{@const says = allSays(g.changes.filter(ready))}
			{@const n = g.changes.filter(ready).length}
			<section class="cgroup" data-testid="change-group" data-path={g.path}>
				<div class="chead">
					<span class="title">{g.label}</span>
					<span class="count" data-testid="change-group-count">{g.changes.length}</span>
					{#if !g.document}<span class="muted">in no document's text</span>{/if}
					<span class="acts">
						<button type="button" class="btn small" disabled={!n || !writes.keep || !!busy} title={says.keep} data-testid="group-keep-all" onclick={() => void every('keep', g)}>{busy === g.path ? 'Working…' : `Keep all ${n}`}</button>
						<button type="button" class="btn small quiet" disabled={!n || !writes.discard || !!busy} title={says.discard} data-testid="group-discard-all" onclick={() => void every('discard', g)}>Discard all {n}</button>
					</span>
				</div>
				<div class="cards">{#each g.changes as c (c.id)}<ChangeCard {c} place see={part ? seeIn(g.document ? g.path : null) : undefined} />{/each}</div>
				{#if todoOn}
					{@const here = todo.find((t) => t.path === g.path)}
					{#if here}{@render todoRows(here.annotations, g.path)}{/if}
				{/if}
			</section>
		{:else}
			<Empty text="No changes wait in your text." testid="changes-empty" />
		{/each}
		{#if part}<Copies doc={draft} />{/if}
		{#if todoOn}
			{#each todoAlone as t (t.path)}
				<section class="cgroup" data-testid="todo-group" data-path={t.path}>
					<div class="chead"><span class="title">{t.label}</span><span class="count">{t.annotations.length}</span><span class="muted">open annotations from others</span></div>
					{@render todoRows(t.annotations, t.path)}
				</section>
			{/each}
			{#if !todoCount}<p class="muted" data-testid="todo-none">No open annotations from others.</p>{/if}
		{/if}
	</section>
{/snippet}

{#if part}
	<section class="yours" data-testid="your-changes" data-part={part}>
		{@render bar()}
		{#if part === 'accept'}{@render accepting()}{:else}{@render keeping()}{/if}
	</section>
{:else}
	<main class="page review-page" use:barShown data-testid="your-changes">
		<ReviewHeading title="Your Changes">{#snippet aside()}<HelpDot label="what the Your Changes page shows" topic="review" />{/snippet}</ReviewHeading>
		{@render bar()}
		<p class="lead">The mathematics first: the blocks of your documents changed since you accepted them, or taken in from a copy or a pull, and <b>Accept</b> records that you have read one and vouch for it. Then what waits to be kept: {tracked ? `suggestions not yet kept or discarded, and every edit made in your files since your look${since ? ` of ${since}` : ''}` : 'suggestions not yet kept or discarded'}. <b>Keep</b> one to take it into your text, or <b>Discard</b> it {tracked ? 'to put your words back or drop the suggestion' : 'to drop it'}; neither says whether the mathematics is right.</p>

		<h2 class="part">Waiting to be accepted</h2>
		{@render accepting()}

		<h2 class="part">Changes to keep</h2>
		{@render keeping()}
	</main>
{/if}

<style>
	.lead {
		margin: 0 0 var(--gap);
		font-size: 13px;
		color: var(--ink-soft);
	}
	.lead b {
		font-weight: 500;
		color: var(--ink);
	}
	.changes {
		display: grid;
		gap: var(--gap);
		margin: 0 0 var(--gap-wide);
	}
	.cgroup {
		display: grid;
		gap: 8px;
		min-width: 0;
	}
	.chead {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 4px 10px;
		font-size: 13.5px;
	}
	.chead .title {
		font-weight: 600;
	}
	.chead .count {
		color: var(--ink-soft);
		font-variant-numeric: tabular-nums;
	}
	.cards {
		display: grid;
		gap: 8px;
		min-width: 0;
	}
	.todo {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 4px;
		font-size: 13px;
	}
	.todo li {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}
	.todo .dot {
		flex: none;
		width: 10px;
		height: 10px;
		box-sizing: border-box;
		background: var(--fill);
		border: 1.5px solid var(--edge);
		border-radius: 50%;
	}
	.todo a {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.part {
		margin: var(--gap-wide) 0 var(--gap-tight);
		font-size: 15px;
		font-weight: 600;
	}
	.pick {
		margin: 0 0 var(--gap-tight);
	}
	.dhead {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 0 0 var(--gap-tight);
		font-size: 13.5px;
	}
	.dhead .title {
		font-weight: 600;
	}
	.dhead .count {
		color: var(--ink-soft);
		font-variant-numeric: tabular-nums;
	}
	.group {
		margin: 0 0 var(--gap);
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--review-paper);
	}
	.group > summary {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 14px;
		cursor: pointer;
		font-size: 13.5px;
	}
	.group > summary .count {
		color: var(--ink-soft);
		font-variant-numeric: tabular-nums;
	}
	.group ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.block {
		border-top: 1px solid var(--rule);
		padding: 8px 14px;
		/* a row a link scrolls to stops below the held bar, which a hash's own scroll would put it under */
		scroll-margin-top: 64px;
	}
	.line {
		display: flex;
		align-items: baseline;
		gap: 4px 10px;
		flex-wrap: wrap;
	}
	.line input {
		align-self: center;
	}
	.name {
		font-size: 14px;
		overflow-wrap: anywhere;
	}
	.see {
		padding: 0;
		border: 0;
		background: none;
		font-family: inherit;
		color: var(--link);
		text-align: left;
		cursor: pointer;
	}
	.of,
	.note {
		font-size: 12.5px;
		color: var(--ink-soft);
	}
	.tag {
		padding: 1px 8px;
		border-radius: 999px;
		background: var(--leaf);
		color: var(--ink-soft);
		font-size: 11.5px;
	}
	.tag.changed {
		background: var(--state-stale-wash, var(--leaf));
		color: var(--state-stale);
	}
	.acts {
		margin-left: auto;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
	}
	.cannot {
		margin: 4px 0 0;
		font-size: 12.5px;
		color: var(--ink-soft);
	}
	.muted {
		color: var(--ink-soft);
		font-size: 12.5px;
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
	select {
		max-width: 100%;
	}
</style>
