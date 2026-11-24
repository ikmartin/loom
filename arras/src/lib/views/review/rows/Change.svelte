<script lang="ts">
	// A proposed edit, or an accepted result that changed, open: the text with its change marked, and keep and discard (or undo the edit, for one an agent made in place), or accept. An edit after which its document stopped compiling says so, with TeX's reason in words.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { AcceptedChangedRow, EditRow, ReviewBody } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Statement from '$lib/views/Statement.svelte';
	import SeeItLink from '../SeeItLink.svelte';

	let { row }: { row: EditRow | AcceptedChangedRow } = $props();
	const body = new Read<ReviewBody>();
	let busy = $state(false);

	$effect(() => {
		const id = row.row;
		void gen.gen;
		void body.load(id, (s) => api.reviewRow(id, s));
	});

	async function act(run: () => ReturnType<typeof api.keep>, saying: string): Promise<void> {
		busy = true;
		const done = await run();
		busy = false;
		message.post(done.ok ? saying : said(done.error));
	}
</script>

{#if body.value?.body.statement}<Statement fragment={body.value.body.statement.fragment} />{/if}
{#if row.kind === 'edits' && row.broke}
	<p class="note">{words.edits.inPlace(row.by, row.doc, words.edits.errors[row.broke.error] ?? row.broke.error, row.broke.line)}</p>
{/if}
<div class="answers">
	{#if row.kind === 'edits'}
		<button type="button" class="btn" disabled={busy} onclick={() => act(() => api.keep(row.change), words.edits.kept)}>{words.edits.keep}</button>
		<button type="button" class="btn" disabled={busy} onclick={() => act(() => api.discard(row.change), words.edits.discarded)}>{row.type === 'edit' ? words.edits.undo : words.edits.discard}</button>
	{:else}
		<button type="button" class="btn" disabled={busy} onclick={() => act(() => api.accept(row.key), words.accepted.accepted)}>{words.accepted.accept}</button>
	{/if}
</div>
<SeeItLink doc={row.doc} key={row.key} name={row.kind === 'edits' ? row.where : row.name} />
