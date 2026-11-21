<script lang="ts">
	// An agent's question, open: its choices as buttons, and a field for an answer in the person's own words. Either answers it, and the agent is told.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import type { QuestionRow } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';

	let { row }: { row: QuestionRow } = $props();
	let own = $state('');
	let busy = $state(false);

	async function answer(choice: number | null): Promise<void> {
		busy = true;
		const done = await api.answer(row.task, choice, choice === null ? own.trim() : '');
		busy = false;
		message.post(done.ok ? words.questions.answered(row.by) : said(done.error));
	}
</script>

{#if row.choices.length}
	<div class="answers">
		{#each row.choices as c, i (c)}<button type="button" class="btn" disabled={busy} onclick={() => answer(i)}>{c}</button>{/each}
	</div>
{/if}
<form class="answers" onsubmit={(e) => (e.preventDefault(), own.trim() && answer(null))}>
	<input class="field" bind:value={own} placeholder={words.questions.own} aria-label={words.questions.own} />
	<button type="submit" class="btn" disabled={busy || !own.trim()}>{words.questions.send}</button>
</form>
