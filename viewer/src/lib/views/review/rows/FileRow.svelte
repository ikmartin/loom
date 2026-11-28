<script lang="ts">
	// A file with edits made in place since the look, as one row of Proposed edits: "main.tex · proof of Theorem 3.1" where every change in it is in one block, else the file; how many edits, and for a document holding those of the files it loads beside its text (a preamble or another LaTeX file it inputs, the only kind watched for edits), how many such files; a chevron. Open: with more than one, `keep all N` and `discard all N` for the file; then each change as its card draws it bare (`ChangeCard`), named by its block where the file's changes are in several and by its file where it is in one the document loads, with Keep and Discard and `see it in main.tex`. The column's message says what an act did in the viewer's words (`changeSaid`).
	import Icon from '$lib/components/Icon.svelte';
	import { said } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import type { PendingChange } from '$lib/manifest/types';
	import { mirrors } from '$lib/overleaf/said';
	import ChangeCard from '$lib/review/ChangeCard.svelte';
	import { ready } from '$lib/review/changes';
	import type { ChangeAnswer } from '$lib/review/history.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { keyName } from '$lib/workspace/names';
	import { review as words } from '$lib/words/review';
	import { can } from '$lib/write';
	import { changeSaid } from '../answers';
	import { every } from '../every';
	import SeeItLink from '../SeeItLink.svelte';
	import { rv } from '../state.svelte';
	import type { EditRow } from '../yours';

	let { row }: { row: Extract<EditRow, { type: 'file' }> } = $props();
	const m = $derived(store.manifest!);
	const id = $derived(`file:${row.doc ?? ''}:${row.path}`);
	const open = $derived(rv.open.has(id));
	/** The block every change in the file is in, or the one whose own file it is; null where they are in several or outside any. */
	const block = $derived.by((): string | null => {
		if (row.also.length) return null;
		const keys = [...new Set(row.changes.map((c) => c.key))];
		if (keys.length === 1 && keys[0]) return keys[0];
		const nodes = new Set(row.changes.map((c) => (c.key ? (m.keys?.[c.key]?.node ?? c.key) : null)));
		const [only] = nodes;
		return nodes.size === 1 && only ? only : null;
	});
	const what = $derived(block ? keyName(m, block) : words.file(row.path));
	// where it is: the draft, or the file in no draft's text; then the block, or a file of the draft's that is not the draft itself
	const where = $derived(row.doc ? words.file(row.doc) : row.label);
	const line = $derived(block || (where !== row.path && where !== what) ? words.at(where, what) : where);
	const hover = $derived(row.also.length ? words.edits.loadsFileHover : words.edits.fileHover);
	const ids = $derived(row.changes.filter((c) => ready(c)).map((c) => c.id));
	// a change to a document that mirrors Overleaf is made there, and kept by its own Done in Overleaf
	const keeps = $derived(row.changes.filter((c) => ready(c) && !mirrors(m.overleaf, c.path)).map((c) => c.id));
	/** A change's block, said over its card where the file's changes are in several. */
	const named = (c: PendingChange) => (c.path !== row.path ? words.file(c.path) : !block && c.key ? keyName(m, c.key) : '');
	/** A block the card names (the note it answers) is laid over Review in the draft that holds the change, else named in words. */
	const see = $derived(row.doc ? (key: string, name: string) => (rv.over = { doc: row.doc!, key, name }) : null);
	/** What Keep or Discard did, said in the column's message in the viewer's words. */
	const answered = (how: 'keep' | 'discard', res: ChangeAnswer) => message.post(res.ok ? (res.refused?.length ? changeSaid(how, res.done?.length ?? 0, res.refused) : how === 'keep' ? words.edits.kept : words.edits.discarded) : said({ code: res.error?.code ?? 'failed', message: '' }));
	let busy = $state(false);
	let writes = $state({ keep: false, discard: false });
	$effect(() => {
		void can('change-keep').then((yes) => (writes.keep = yes));
		void can('change-discard').then((yes) => (writes.discard = yes));
	});
	async function all(how: 'keep' | 'discard'): Promise<void> {
		busy = true;
		await every(how, how === 'keep' ? keeps : ids);
		busy = false;
	}
</script>

<div class="rr" class:open data-testid="review-row" data-kind="edits" data-file={row.path} data-loads={row.also.length || null}>
	<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(id)}>
		<span class="slot"></span><span class="slot"></span>
		<span class="tx">{line}</span>
		<span class="meta" title={row.also.length ? words.edits.loadsHover(row.also.map(words.file)) : null}>{words.quiet([words.edits.sinceLook(row.changes.length), row.also.length ? words.edits.loads(row.also.length) : ''])}</span>
		<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
	</button>
	{#if open}
		<div class="rr-b">
			{#if row.changes.length > 1}
				<div class="answers file-acts">
					<button type="button" class="btn" disabled={!keeps.length || !writes.keep || busy} title={hover.keep} data-testid="file-keep-all" onclick={() => void all('keep')}>{words.edits.keepAll(keeps.length)}</button>
					<button type="button" class="btn" disabled={!ids.length || !writes.discard || busy} title={hover.discard} data-testid="file-discard-all" onclick={() => void all('discard')}>{words.edits.discardAll(ids.length)}</button>
				</div>
			{/if}
			{#each row.changes as c (c.id)}
				<div class="fc" data-testid="file-change">
					{#if named(c)}<p class="note">{named(c)}</p>{/if}
					<ChangeCard {c} {see} bare onanswer={answered} />
					{#if row.doc && c.key}<SeeItLink doc={row.doc} key={c.key} name={keyName(m, c.key)} />{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.file-acts {
		margin-bottom: 12px;
	}
	.fc + .fc {
		margin-top: 14px;
		padding-top: 12px;
		border-top: 1px solid var(--rule);
	}
</style>
