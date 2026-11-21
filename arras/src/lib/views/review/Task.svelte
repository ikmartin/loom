<script lang="ts">
	// A task waiting for an agent: what was asked, in words, whether an agent is working on it, and `delete` on hover, which withdraws it.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import type { TaskRow } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import { task } from './rows';

	let { row }: { row: TaskRow } = $props();

	async function withdraw(): Promise<void> {
		const done = await api.withdraw(row.task);
		message.post(done.ok ? words.agents.deleted : said(done.error));
	}
</script>

<div class="rr" data-testid="review-task">
	<div class="rr-h">
		<span class="slot" aria-hidden="true">{row.working ? '▸' : '·'}</span>
		<span class="slot"></span>
		<span class="tx">{task(row)}</span>
		<span class="meta">{#if row.working}<span class="who">{row.working.by}</span> {words.agents.working}{:else}{words.agents.waiting}{/if}</span>
		<button type="button" class="linkish hov" onclick={withdraw}>{words.agents.delete}</button>
		<span class="chev"></span>
	</div>
</div>
