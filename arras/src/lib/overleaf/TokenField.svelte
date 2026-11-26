<script lang="ts">
	// The git token Overleaf asked for: why it asks (none kept, or the one kept refused), a field that hides what is pasted, and Use this token, which gives it to loom's credential helper and then calls `onstored`, so what asked for it is done again. The token goes to `overleaf-token` and nowhere else; the field is emptied once it is sent.
	import { overleaf as words } from '$lib/words/overleaf';
	import { giveToken } from './act.svelte';

	let { asks, link = '', onstored }: { asks: string; link?: string; onstored: () => void } = $props();
	let token = $state('');
	let busy = $state(false);
	let refused = $state('');

	async function use(): Promise<void> {
		busy = true;
		refused = await giveToken(token, link || undefined);
		token = '';
		busy = false;
		if (!refused) onstored();
	}
</script>

<form
	class="token"
	data-testid="overleaf-token"
	onsubmit={(e) => {
		e.preventDefault();
		void use();
	}}
>
	<p class="ask">{asks === 'token-refused' ? words.pair.tokenRefused : words.pair.token}</p>
	<div class="line">
		<input class="text mono" type="password" bind:value={token} autocomplete="off" spellcheck="false" aria-label={words.pair.tokenField} data-testid="overleaf-token-field" />
		<button class="btn primary" type="submit" disabled={busy || !token.trim()} data-testid="overleaf-token-use">{words.pair.useToken}</button>
	</div>
	{#if refused}<p class="refused" role="alert">{refused}</p>{/if}
</form>

<style>
	.token {
		display: grid;
		gap: 8px;
		margin-top: 10px;
	}
	.ask {
		margin: 0;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--ink-soft);
	}
	.line {
		display: flex;
		gap: 8px;
	}
	.line input {
		flex: 1 1 auto;
		width: auto;
	}
	.refused {
		margin: 0;
		font-size: 12.5px;
		color: var(--state-conflicted);
	}
</style>
