<script lang="ts">
	// The box Ask your agent opens: what the request is about where there is a choice, the mode from the quilt's own, the person's words, and the request as it will be pasted; Copy, and Copy and open Claude where the quilt is set up for Claude Code and loom can open an app. It writes nothing and starts no agent.
	import { refusalOf } from '$lib/library/said';
	import Popover from '$lib/components/Popover.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { copyText } from '$lib/clipboard';
	import { say } from '$lib/review/toasts.svelte';
	import { can, write } from '$lib/write';
	import { agents as words } from '$lib/words/agents';
	import { prefs } from '$lib/prefs.svelte';
	import { request, type Place } from './ask';

	let { open = $bindable(false), places }: { open?: boolean; places: Place[] } = $props();

	const m = $derived(store.manifest);
	const modes = $derived(m?.agents?.modes ?? []);
	const claude = $derived(!!m?.agents?.apps.find((a) => a.key === 'claude-code')?.set_up);

	let which = $state(0);
	let mode = $state('');
	let said = $state('');
	let opens = $state(false);
	$effect(() => {
		if (!open) return;
		which = 0;
		void can('open').then((ok) => (opens = ok));
	});

	const place = $derived(places[Math.min(which, places.length - 1)]);
	const text = $derived(place ? request(place, mode, said, prefs.ids) : '');
	const fits = $derived(modes.find((x) => x.name === mode)?.fits ?? '');

	async function copy(andOpen: boolean): Promise<void> {
		const ok = await copyText(text);
		let refused = '';
		if (ok && andOpen) {
			const done = await write('open', { app: 'Claude' });
			if (!done.ok) refused = refusalOf(done.error, words.ask.openFailed);
		}
		open = false;
		said = '';
		say({ title: words.ask.toast(ok), lines: [words.ask.toastLine(ok, andOpen && !refused), ...(refused ? [refused] : [])] });
	}
</script>

<Popover modal bind:open label={words.ask.title} testid="ask-agent">
	<form
		class="ask"
		onsubmit={(e) => {
			e.preventDefault();
			void copy(false);
		}}
	>
		<h3>{words.ask.title}</h3>
		<p class="lead">{words.ask.lead}</p>
		{#if places.length > 1}
			<fieldset>
				<legend>{words.ask.about}</legend>
				{#each places as p, i (p.href + i)}
					<label><input type="radio" name="ask-about" value={i} bind:group={which} data-testid="ask-about-{i}" />{p.label ?? p.name}</label>
				{/each}
			</fieldset>
		{/if}
		<label class="field">
			<span>{words.ask.mode}</span>
			<select bind:value={mode} data-testid="ask-mode">
				<option value="">{words.ask.noMode}</option>
				{#each modes as x (x.name)}<option value={x.name}>{x.name}</option>{/each}
			</select>
		</label>
		{#if fits}<p class="fits" data-testid="ask-fits">{fits}</p>{/if}
		<label class="field">
			<span>{words.ask.words}</span>
			<textarea rows="3" bind:value={said} placeholder={words.ask.wordsHint} data-testid="ask-words"></textarea>
		</label>
		<div class="field">
			<span>{words.ask.copied}</span>
			<pre class="request" data-testid="ask-request">{text}</pre>
		</div>
		<div class="acts">
			<button type="button" class="btn quiet" onclick={() => (open = false)}>{words.ask.cancel}</button>
			{#if claude && opens}<button type="button" class="btn" onclick={() => void copy(true)} data-testid="ask-copy-open">{words.ask.copyOpen}</button>{/if}
			<button type="submit" class="btn primary" data-testid="ask-copy">{words.ask.copy}</button>
		</div>
	</form>
</Popover>

<style>
	.ask {
		box-sizing: border-box;
		width: min(520px, calc(100vw - 48px));
		padding: 16px 18px;
		overflow-y: auto;
		display: grid;
		gap: 10px;
		font-size: 13px;
		color: var(--ink);
	}
	h3 {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
	}
	.lead,
	.fits {
		margin: 0;
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.fits {
		margin-top: -4px;
	}
	fieldset {
		border: 0;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 4px;
	}
	legend,
	.field > span {
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink-soft);
		margin-bottom: 4px;
		padding: 0;
	}
	fieldset label {
		display: flex;
		align-items: center;
		gap: 7px;
	}
	.field {
		display: grid;
		gap: 2px;
	}
	select,
	textarea {
		font: inherit;
		font-size: 13px;
		color: var(--ink);
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 6px;
		padding: 5px 8px;
	}
	select {
		justify-self: start;
	}
	textarea {
		resize: vertical;
	}
	.request {
		margin: 0;
		padding: 8px 10px;
		background: var(--leaf);
		border-radius: 6px;
		font-family: var(--mono);
		font-size: 11.5px;
		line-height: 1.5;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		max-height: 12rem;
		overflow: auto;
	}
	.acts {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
</style>
