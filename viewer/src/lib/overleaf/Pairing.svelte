<script lang="ts">
	// The pairing card, while the quilt mirrors no project: the project's link, then, once loom reaches it, the new folder it goes in, its main file where it has several, and which of its history's authors is the person; Copy the project pairs. Where Overleaf asks for a git token, the token field (`TokenField`) stands under the link and the same request is made again once the token is kept. Every refusal is said in the words file's words by its code (`problemSaid`).
	import { landed } from '$lib/manifest/updating.svelte';
	import { overleaf as words } from '$lib/words/overleaf';
	import { write, type WriteResult } from '$lib/write';
	import { ASKS_TOKEN, mirror } from './act.svelte';
	import { problemSaid } from './said';
	import TokenField from './TokenField.svelte';

	/** What `overleaf-pair` answers with the link alone. */
	interface Choose {
		folder: string;
		mains: string[];
		main: string;
		authors: { name: string; email: string }[];
		me: string[];
	}

	let link = $state('');
	let busy = $state(false);
	let refused = $state('');
	let asks = $state('');
	let choose = $state<Choose | null>(null);
	let folder = $state('');
	let main = $state('');
	let me = $state<string[]>([]);
	/** Which request the token was asked for, made again once it is kept. */
	let again: (() => Promise<void>) | null = null;

	function refusal(res: WriteResult, retry: () => Promise<void>): void {
		const code = res.error?.code ?? '';
		if (ASKS_TOKEN.has(code)) {
			asks = code;
			again = retry;
		} else refused = problemSaid(code);
	}

	async function connect(): Promise<void> {
		busy = true;
		refused = asks = '';
		const res = await write('overleaf-pair', { link: link.trim() });
		busy = false;
		if (!res.ok) return refusal(res, connect);
		const c = (res.result as unknown as { choose: Choose }).choose;
		choose = c;
		folder = c.folder;
		main = c.main;
		me = c.me.filter((a) => c.authors.some((x) => x.email === a));
	}

	async function pair(): Promise<void> {
		busy = true;
		refused = asks = '';
		const res = await write('overleaf-pair', { link: link.trim(), folder: folder.trim(), main, me });
		busy = false;
		if (!res.ok) return refusal(res, pair);
		const done = (res.result as unknown as { paired: { folder: string } }).paired;
		Object.assign(mirror, { said: words.pair.paired(done.folder), refused: false, asks: '' });
		await landed();
	}

	function tick(email: string, on: boolean): void {
		me = on ? [...new Set([...me, email])] : me.filter((a) => a !== email);
	}
</script>

<div class="pairing" data-testid="overleaf-pairing">
	{#if mirror.said && !mirror.refused}<p class="said" role="status" data-testid="overleaf-said">{mirror.said}</p>{/if}
	<p class="lede">{words.pair.lede}</p>
	<form
		class="line"
		onsubmit={(e) => {
			e.preventDefault();
			void connect();
		}}
	>
		<input class="text" bind:value={link} disabled={!!choose} spellcheck="false" autocomplete="off" placeholder={words.pair.linkPlaceholder} aria-label={words.pair.link} data-testid="overleaf-link" />
		{#if !choose}<button class="btn primary" type="submit" disabled={busy || !link.trim()} data-testid="overleaf-connect">{busy ? words.pair.connecting : words.pair.connect}</button>{/if}
	</form>
	{#if asks}<TokenField {asks} link={link.trim()} onstored={() => void again?.()} />{/if}
	{#if choose}
		{@const c = choose}
		<div class="choose" data-testid="overleaf-choose">
			<label class="field">
				<span class="name">{words.pair.folder}</span>
				<span class="what">{words.pair.folderWhat}</span>
				<input class="text mono" bind:value={folder} spellcheck="false" autocomplete="off" data-testid="overleaf-folder" />
			</label>
			{#if c.mains.length > 1}
				<label class="field">
					<span class="name">{words.pair.main}</span>
					<span class="what">{words.pair.mainWhat}</span>
					<select bind:value={main} data-testid="overleaf-main">
						{#if !c.main}<option value="" disabled></option>{/if}
						{#each c.mains as f (f)}<option value={f}>{f}</option>{/each}
					</select>
				</label>
			{/if}
			<fieldset class="field">
				<legend class="name">{words.pair.me}</legend>
				<span class="what">{words.pair.meWhat}</span>
				{#each c.authors as a (a.email)}
					<label class="tick"><input type="checkbox" checked={me.includes(a.email)} onchange={(e) => tick(a.email, e.currentTarget.checked)} data-testid="overleaf-me" data-email={a.email} />{a.name} <span class="email">{a.email}</span></label>
				{:else}
					<span class="what">{words.pair.nobody}</span>
				{/each}
				{#if c.authors.length}<label class="tick"><input type="checkbox" checked={!me.length} onchange={(e) => e.currentTarget.checked && (me = [])} data-testid="overleaf-me-none" />{words.pair.noneYet}</label>{/if}
			</fieldset>
			<div class="acts">
				<button class="btn primary" disabled={busy || !folder.trim() || !main} data-testid="overleaf-pair" onclick={() => void pair()}>{busy ? words.pair.copying : words.pair.go}</button>
				<button class="btn" disabled={busy} data-testid="overleaf-cancel" onclick={() => ((choose = null), (refused = ''))}>{words.pair.cancel}</button>
			</div>
		</div>
	{/if}
	{#if refused}<p class="refused" role="alert" data-testid="overleaf-refused">{refused}</p>{/if}
</div>

<style>
	.pairing {
		display: grid;
		gap: 10px;
		margin-top: 10px;
	}
	.lede,
	.said {
		margin: 0;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--ink-soft);
	}
	.said {
		color: var(--ink);
	}
	.line {
		display: flex;
		gap: 8px;
	}
	.line input {
		flex: 1 1 auto;
		width: auto;
	}
	.choose {
		display: grid;
		gap: 12px;
		padding-top: 4px;
	}
	.field {
		display: grid;
		gap: 4px;
		margin: 0;
		padding: 0;
		border: 0;
	}
	.name {
		padding: 0;
		font-size: 13px;
		font-weight: 500;
		color: var(--ink);
	}
	.what {
		font-size: 12px;
		color: var(--ink-faint);
	}
	.field input.text,
	.field select {
		max-width: 320px;
	}
	.tick {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 13px;
	}
	.email {
		color: var(--ink-faint);
	}
	.acts {
		display: flex;
		gap: 8px;
	}
	.refused {
		margin: 0;
		font-size: 12.5px;
		color: var(--state-conflicted);
	}
</style>
