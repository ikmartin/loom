<script lang="ts">
	// The frame while the publisher waits on a quilt an earlier loom made: only the column's head, then one sentence and one button, which brings the quilt forward with `library-upgrade`. While it runs, and if it fails, a sentence says so; an upgrade that could not carry everything says how much, and the button then opens the quilt. Once upgraded, the page is loaded again, the publisher building the quilt as it does on any.
	import { write } from '$lib/write';
	import { prefs } from '$lib/prefs.svelte';
	import { frame } from '$lib/words/frame';

	type Said = { at: 'asking' } | { at: 'running' } | { at: 'failed'; code: string } | { at: 'problems'; n: number };
	let said = $state<Said>({ at: 'asking' });

	async function upgrade(): Promise<void> {
		if (said.at === 'problems') return location.reload();
		said = { at: 'running' };
		const done = (await write('library-upgrade', {})) as { ok: boolean; error?: { code: string }; carried?: { problems?: unknown[] } };
		if (!done.ok) {
			said = { at: 'failed', code: done.error?.code ?? 'failed' };
			return;
		}
		const n = done.carried?.problems?.length ?? 0;
		if (n) said = { at: 'problems', n };
		else location.reload();
	}

	const sentence = $derived(said.at === 'running' ? frame.upgrade.running : said.at === 'failed' ? frame.upgrade.failed(said.code) : said.at === 'problems' ? frame.upgrade.problems(said.n) : frame.upgrade.said);
</script>

<div class="old" style:--column-width="{prefs.column}px">
	<div class="panel" data-testid="column">
		<div class="head"><span class="name" data-testid="quilt-name">{frame.column.unnamed}</span></div>
	</div>
	<main class="page" data-testid="format-old">
		<p class="said" role="status" data-testid="format-old-said">{sentence}</p>
		<button type="button" class="btn primary" disabled={said.at === 'running'} onclick={() => void upgrade()} data-testid="format-old-upgrade">{said.at === 'problems' ? frame.upgrade.open : frame.upgrade.button}</button>
	</main>
</div>

<style>
	.old {
		display: grid;
		grid-template-columns: var(--column-width) 1fr;
		min-height: 100vh;
	}
	.panel {
		background: var(--leaf);
		border-right: 1px solid var(--rule);
		padding: var(--gap) 14px;
	}
	.head .name {
		font-size: 13px;
		color: var(--ink);
		font-weight: 500;
	}
	.said {
		max-width: 36em;
	}
</style>
