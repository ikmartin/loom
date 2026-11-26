<script lang="ts">
	// Proposed edits' rows, every draft's or the one the column chooses, from the manifest (`changeList`, `copiesOf`): over them a line with `keep all N` and `discard all N` for every change listed that can be, the undo of the last keep or discard, and `to do N`; a row for each change (`ChangeRow`), then one for each agent's copy, whose link opens it on its own page in Review, where it is taken in and applied; with to do, the open annotations from others, a row each. Says once what it watches and what it leaves to the person.
	import { said } from '$lib/library/said';
	import { shortDate } from '$lib/badges';
	import { dotVars, itemLabel } from '$lib/fragments/gutter';
	import { store } from '$lib/manifest/client.svelte';
	import { route } from '$lib/paths';
	import { acted } from '$lib/review/acted.svelte';
	import { ready } from '$lib/review/changes';
	import { itemsOf, tally } from '$lib/review/contribution';
	import { discardChanges, history, keepChanges, nextUndo, undo } from '$lib/review/history.svelte';
	import { copySays } from '$lib/review/proposed';
	import SaidOnce from '$lib/review/SaidOnce.svelte';
	import { todoOf } from '$lib/review/yourChanges';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { can } from '$lib/write';
	import { changeSaid } from './answers';
	import ChangeRow from './rows/ChangeRow.svelte';
	import SeeItLink from './SeeItLink.svelte';
	import { rv } from './state.svelte';
	import { changeList, copiesOf } from './yours';

	const m = $derived(store.manifest!);
	const items = $derived(changeList(m, acted.map, rv.doc));
	const copies = $derived(copiesOf(m, rv.doc));
	const ids = $derived(items.filter((i) => ready(i.c)).map((i) => i.c.id));
	const todo = $derived(todoOf(m).filter((t) => !rv.doc || t.path === rv.doc));
	const todoCount = $derived(todo.reduce((n, t) => n + t.annotations.length, 0));
	const undoes = $derived(nextUndo().startsWith('keep') || nextUndo().startsWith('discard'));
	let todoOn = $state(false);
	let busy = $state(false);
	let writes = $state({ keep: false, discard: false });
	$effect(() => {
		void can('change-keep').then((yes) => (writes.keep = yes));
		void can('change-discard').then((yes) => (writes.discard = yes));
	});

	/** Keep or discard every change listed that can be; the column's message says how many, and why any was not, in the viewer's words (`changeSaid`). */
	async function every(how: 'keep' | 'discard'): Promise<void> {
		busy = true;
		const res = how === 'keep' ? await keepChanges({ changes: ids }) : await discardChanges({ changes: ids });
		busy = false;
		if (!res.ok) return message.post(said({ code: res.error?.code ?? 'failed', message: res.error?.message ?? '' }));
		const refused = res.refused ?? [];
		message.post(changeSaid(how, res.done?.length ?? ids.length - refused.length, refused));
	}

	async function back(): Promise<void> {
		// a refusal is loom's sentence, so the viewer says its own
		if (await undo()) message.post(words.edits.notUndone);
	}
	const name = (path: string) => (path.split('/').pop() ?? path).replace(/\.tex$/, '');
</script>

<div class="yours" data-testid="review-edit-list">
	{#if m.changes_since}<SaidOnce text={words.once.watched(m.changes_since.when.slice(0, 16).replace('T', ' '), m.changes_since.carried ?? '', m.changes_since.unwatched ?? [], m.changes_since.holds ?? '')} testid="review-watched" />{/if}
	{#if items.length || undoes || todoCount}
		<div class="rg head acts" data-testid="review-edit-acts">
			{#if items.length}
				<button type="button" class="btn" disabled={!ids.length || !writes.keep || busy} data-testid="group-keep-all" onclick={() => void every('keep')}>{words.edits.keepAll(ids.length)}</button>
				<button type="button" class="btn" disabled={!ids.length || !writes.discard || busy} data-testid="group-discard-all" onclick={() => void every('discard')}>{words.edits.discardAll(ids.length)}</button>
			{/if}
			{#if undoes}<button type="button" class="btn" disabled={history.busy} data-testid="review-undo" onclick={() => void back()}>{words.edits.undoLast(nextUndo())}</button>{/if}
			<button type="button" class="btn" class:on={todoOn} aria-pressed={todoOn} title={words.edits.todoHover} data-testid="your-todo" onclick={() => (todoOn = !todoOn)}>{words.edits.todo(todoCount)}</button>
		</div>
	{/if}
	{#each items as item (item.c.id)}<ChangeRow {item} />{/each}
	{#each copies as c (c.copy)}
		<div class="rr" data-testid="review-row" data-kind="edits" data-copy={c.copy}>
			<div class="rr-h">
				<span class="slot"></span><span class="slot"></span>
				<span class="tx">{words.at(words.file(c.source), name(c.copy))}</span>
				<span class="meta" data-testid="proposed-tally">{words.quiet([words.edits.copy, copySays(tally(c, itemsOf(m, c)))])}</span>
				<a class="linkish meta" href="{route('/review/proposed')}?copy={encodeURIComponent(c.copy)}" data-testid="proposed-open">{words.edits.openCopy}</a>
				<span class="chev"></span>
			</div>
		</div>
	{/each}
	{#if todoOn}
		{#each todo as t (t.path)}
			{#each t.annotations as a (a.id)}
				<div class="rr todo" data-testid="todo-row" data-annotation={a.id}>
					<div class="rr-h">
						<span class="slot"><span class="dot" style={dotVars(a)}></span></span><span class="slot"></span>
						<span class="tx">{words.at(t.label, itemLabel(m, a))}</span>
						<span class="meta">{shortDate(a.created)}</span>
						<span class="meta"><SeeItLink doc={t.path} key={a.target.key} name={itemLabel(m, a)} /></span>
						<span class="chev"></span>
					</div>
				</div>
			{/each}
		{:else}
			<p class="note" data-testid="todo-none">{words.edits.todoNone}</p>
		{/each}
	{/if}
</div>

<style>
	.dot {
		width: 10px;
		height: 10px;
		box-sizing: border-box;
		background: var(--fill);
		border: 1.5px solid var(--edge);
		border-radius: 50%;
	}
	.btn.on {
		border-color: var(--accent);
	}
</style>
