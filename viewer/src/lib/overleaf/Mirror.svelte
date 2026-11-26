<script lang="ts">
	// The mirror's card, while the quilt mirrors a project: the folder and main document with a link to the project's page in Overleaf; Update from Overleaf, "Overleaf has changes." beside it when the last fetch found text not taken in, and its line (the last press's answer, else the manifest's last update and what reaching Overleaf could not do, `standing`); the token field where Overleaf asks for one; who the person is on Overleaf, asked again when the history names someone they were not shown (`ask_me`); and End the pairing, asked once in place.
	import type { OverleafState } from '$lib/manifest/types';
	import { landed } from '$lib/manifest/updating.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { overleaf as words } from '$lib/words/overleaf';
	import { write } from '$lib/write';
	import { ASKS_TOKEN, mirror, updateNow } from './act.svelte';
	import { problemSaid, standing } from './said';
	import TokenField from './TokenField.svelte';

	let { o }: { o: Extract<OverleafState, { paired: true }> } = $props();

	const line = $derived(mirror.said || standing(o));
	const refused = $derived(mirror.said ? mirror.refused : !!o.problem);
	// the token is asked for after a press Overleaf refused, or when the fetch at the server's start was
	const asks = $derived(mirror.asks || (o.problem && ASKS_TOKEN.has(o.problem) ? o.problem : ''));

	let authors = $state<{ name: string; email: string }[] | null>(null);
	let me = $state<string[]>([]);
	let asking = $state(false);
	let busy = $state(false);
	let said = $state('');

	async function who(): Promise<void> {
		const res = await write('overleaf-me', {});
		if (!res.ok) return void (said = problemSaid(res.error?.code));
		authors = (res.result as unknown as { authors: { name: string; email: string }[] }).authors;
		me = [];
	}
	async function saveMe(): Promise<void> {
		busy = true;
		const res = await write('overleaf-me', { me });
		busy = false;
		if (!res.ok) return void (said = problemSaid(res.error?.code));
		authors = null;
		await landed();
	}
	async function unpair(): Promise<void> {
		busy = true;
		const res = await write('overleaf-unpair', {});
		busy = false;
		asking = false;
		if (!res.ok) return void (said = problemSaid(res.error?.code));
		Object.assign(mirror, { said: words.paired.unpaired, refused: false, asks: '' });
		await landed();
	}
</script>

<div class="mirror" data-testid="overleaf-mirror">
	<p class="lede">{words.paired.mirrors(o.folder)} <a href={o.link} target="_blank" rel="noopener noreferrer" data-testid="overleaf-open">{words.paired.open}</a></p>
	<dl>
		<dt>{words.paired.folder}</dt><dd class="mono">{o.folder}/</dd>
		<dt>{words.paired.main}</dt><dd class="mono">{o.main}</dd>
	</dl>
	<div class="update">
		<button class="btn primary" disabled={mirror.busy} data-testid="overleaf-update" onclick={() => void updateNow()}><Icon name="update" size={14} />{mirror.busy ? words.update.busy : words.update.label}</button>
		{#if o.waiting}<span class="waiting" data-testid="overleaf-waiting">{words.update.waiting}</span>{/if}
	</div>
	<p class="line" class:refused role={refused ? 'alert' : 'status'} data-testid="overleaf-said">{line}</p>
	{#if asks}<TokenField {asks} onstored={() => void updateNow()} />{/if}
	{#if authors}
		<fieldset class="who" data-testid="overleaf-who">
			<legend>{words.pair.me}</legend>
			{#each authors as a (a.email)}<label class="tick"><input type="checkbox" checked={me.includes(a.email)} onchange={(e) => (me = e.currentTarget.checked ? [...me, a.email] : me.filter((x) => x !== a.email))} data-testid="overleaf-me" data-email={a.email} />{a.name} <span class="email">{a.email}</span></label>{/each}
			<div class="acts"><button class="btn" disabled={busy} data-testid="overleaf-me-save" onclick={() => void saveMe()}>{words.paired.saveMe}</button></div>
		</fieldset>
	{/if}
	<div class="acts">
		{#if !authors}<button class="btn" class:primary={o.ask_me} data-testid="overleaf-who-again" onclick={() => void who()}>{words.paired.whoAgain}</button>{/if}
		{#if asking}
			<span class="ask">{words.paired.unpairAsk}</span>
			<button class="btn" disabled={busy} data-testid="overleaf-unpair-yes" onclick={() => void unpair()}>{words.paired.unpairYes}</button>
			<button class="btn" disabled={busy} onclick={() => (asking = false)}>{words.paired.unpairNo}</button>
		{:else}
			<button class="btn" data-testid="overleaf-unpair" onclick={() => (asking = true)}>{words.paired.unpair}</button>
		{/if}
	</div>
	{#if said}<p class="line refused" role="alert">{said}</p>{/if}
</div>

<style>
	.mirror {
		display: grid;
		gap: 10px;
		margin-top: 10px;
	}
	.lede,
	.line {
		margin: 0;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--ink-soft);
	}
	.line.refused {
		color: var(--state-conflicted);
	}
	dl {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 6px 14px;
		margin: 0;
		font-size: 13px;
	}
	dt {
		color: var(--ink-faint);
	}
	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}
	.mono {
		font-family: var(--mono);
		font-size: 12.5px;
	}
	.update,
	.acts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}
	.update .btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.waiting {
		font-size: 12.5px;
		font-weight: 500;
		color: var(--change);
	}
	.who {
		display: grid;
		gap: 4px;
		margin: 0;
		padding: 0;
		border: 0;
		font-size: 13px;
	}
	.who legend {
		padding: 0;
		margin-bottom: 4px;
		font-weight: 500;
	}
	.tick {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.email {
		color: var(--ink-faint);
	}
	.ask {
		font-size: 12.5px;
		color: var(--ink-soft);
	}
</style>
