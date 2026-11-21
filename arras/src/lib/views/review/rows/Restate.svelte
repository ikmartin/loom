<script lang="ts">
	// "no, it differs…" and "ask an agent to restate": a field for what the Lean gets wrong, then the ask, which names the result.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';

	let { result, docs, label, open = false }: { result: string; docs: string[]; label: string; open?: boolean } = $props();
	let asking = $state(false);
	let differs = $state('');

	async function send(): Promise<void> {
		const target = /^tq-/.test(result) ? { node: result } : { label: result };
		const done = await api.ask('restate', target, { target, differs: differs.trim() }, docs);
		asking = false;
		message.post(done.ok ? words.restate.asked : said(done.error));
	}
</script>

{#if asking || open}
	<form class="answers" onsubmit={(e) => (e.preventDefault(), send())}>
		<input class="field" bind:value={differs} placeholder={words.attest.differs} aria-label={words.attest.differs} />
		<button type="submit" class="btn">{words.restate.ask}</button>
	</form>
{:else}
	<button type="button" class="btn" onclick={() => (asking = true)}>{label}</button>
{/if}
