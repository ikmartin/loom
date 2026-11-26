<script lang="ts">
	// A suggested edit waiting in the person's text, as round six draws a row of Proposed edits: "main.tex · proof of Theorem 3.1", who proposed it, a chevron; edits made in place are a row a file (`FileRow`). Open: the change as a card drawn bare (`ChangeCard`), its words out and in, what it answers, why it cannot be kept or discarded where it cannot, and Keep and Discard, the history offering their undo and the column's message saying what they did in the viewer's words (`changeSaid`); then `see it in main.tex`. A change in no draft's text names no draft and offers no see it.
	import Icon from '$lib/components/Icon.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import ChangeCard from '$lib/review/ChangeCard.svelte';
	import { whoMade } from '$lib/review/changes';
	import { keyName } from '$lib/workspace/names';
	import { review as words } from '$lib/words/review';
	import { said } from '$lib/library/said';
	import { message } from '$lib/shell/message.svelte';
	import type { ChangeAnswer } from '$lib/review/history.svelte';
	import { changeSaid } from '../answers';
	import SeeItLink from '../SeeItLink.svelte';
	import { rv } from '../state.svelte';
	import type { ChangeItem } from '../yours';

	let { item }: { item: ChangeItem } = $props();
	const m = $derived(store.manifest!);
	const c = $derived(item.c);
	const id = $derived(`edit:${c.id}`);
	const open = $derived(rv.open.has(id));
	const what = $derived(c.key ? keyName(m, c.key) : words.file(c.path));
	// where it is: the draft, or the file in no draft's text; then the block, or a file of the draft's that is not the draft itself
	const where = $derived(item.doc ? words.file(item.doc) : item.label);
	const line = $derived(c.key || (where !== c.path && where !== what) ? words.at(where, what) : where);
	const who = $derived(whoMade(m, c));
	const meta = $derived(who ? words.edits.by(who) : '');
	/** A block the card names (the note it answers) is laid over Review in the draft that holds the change, else named in words. */
	const see = $derived(item.doc ? (key: string, named: string) => (rv.over = { doc: item.doc!, key, name: named }) : null);
	/** What Keep or Discard did, said in the column's message in the viewer's words. */
	const answered = (how: 'keep' | 'discard', res: ChangeAnswer) => message.post(res.ok ? (res.refused?.length ? changeSaid(how, res.done?.length ?? 0, res.refused) : how === 'keep' ? words.edits.kept : words.edits.discarded) : said({ code: res.error?.code ?? 'failed', message: '' }));
</script>

<div class="rr" class:open data-testid="review-row" data-kind="edits" data-change={c.id}>
	<button type="button" class="rr-h" aria-expanded={open} onclick={() => rv.toggle(id)}>
		<span class="slot"></span><span class="slot"></span>
		<span class="tx">{line}</span>
		{#if meta}<span class="meta">{meta}</span>{/if}
		<span class="chev"><Icon name={open ? 'caret' : 'right'} size={16} /></span>
	</button>
	{#if open}
		<div class="rr-b">
			<ChangeCard {c} {see} bare onanswer={answered} />
			{#if item.doc && c.key}<SeeItLink doc={item.doc} key={c.key} name={what} />{/if}
		</div>
	{/if}
</div>
