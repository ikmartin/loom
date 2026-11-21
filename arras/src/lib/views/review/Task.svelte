<script lang="ts">
	// A task waiting for an agent: what was asked, in words, whether an agent is working on it, and `delete` on hover, which withdraws it.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import type { TaskRow } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { task } from './rows';

	let { row }: { row: TaskRow } = $props();

	/** Withdraws the task; its `undo` asks for the same again. */
	async function withdraw(): Promise<void> {
		const done = await api.withdraw(row.task);
		if (!done.ok) return message.post(said(done.error));
		const again = row;
		message.post(words.agents.deleted, () => api.ask(again.what, again.on, again.text ? { text: again.text } : {}, again.docs, again.text ?? ''));
	}
</script>

<div class="rr" data-testid="review-task">
	<div class="rr-h">
		<span class="slot" aria-hidden="true">{row.working ? '▸' : '·'}</span>
		<span class="slot"></span>
		<span class="tx">{task(row)}</span>
		<span class="meta">{#if row.working}<span class="who">{row.working.by}</span> {words.agents.working}{:else}{words.agents.waiting}{/if}</span>
		<button type="button" class="del" onclick={withdraw}>{words.agents.delete}</button>
		<span class="chev"></span>
	</div>
</div>

<style>
	/* withdrawing a task: a 28 pixel target, shown on the row under the pointer or holding the keyboard */
	.del {
		min-height: 28px;
		margin-left: 6px;
		padding: 0 8px;
		font: inherit;
		font-size: 12px;
		color: var(--ink-faint);
		background: none;
		border: 0;
		border-radius: 6px;
		cursor: pointer;
		opacity: 0;
	}
	:global(.rvw .rr:hover) .del,
	.del:focus-visible {
		opacity: 1;
	}
	.del:hover {
		color: var(--ink);
		background: var(--ann-neutral-wash);
	}
</style>
