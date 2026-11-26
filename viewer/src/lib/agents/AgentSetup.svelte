<script lang="ts">
	// The setup card: Use with Claude and Use with Codex, nothing written until one is pressed, which asks the publisher's `agents-setup`. For an app set up, the steps that connect it, then it waits for the app's first conversation to start loom here, says when one has, and after a minute with none says what to check. The trust step is there because Claude Code applies none of loom's permissions until the folder is trusted. A quilt whose agents reach loom in a shell is told that no app shows as connected there.
	import { onMount } from 'svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { copyText } from '$lib/clipboard';
	import { can, quiltRoot, write } from '$lib/write';
	import { agents as words } from '$lib/words/agents';
	import { presence } from './presence.svelte';
	import { OFFERED, setup, wroteWords, type Offered } from './setup.svelte';
	import { clock, ofApp } from './connected';

	let { compact = false }: { compact?: boolean } = $props();

	const m = $derived(store.manifest);
	const apps = $derived(m?.agents?.apps ?? []);
	const shell = $derived(m?.config?.agents.variant === 'shell');
	const isSetUp = (o: Offered) => !!apps.find((a) => a.key === o.key)?.set_up;
	const setUp = $derived(OFFERED.filter(isSetUp));
	const offered = $derived(OFFERED.filter((o) => apps.some((a) => a.key === o.key)));

	let writes = $state(false);
	let opens = $state(false);
	let root = $state('');
	let copied = $state('');
	let refused = $state('');
	onMount(() => {
		void can('agents-setup').then((ok) => (writes = ok));
		void can('open').then((ok) => (opens = ok));
		void quiltRoot().then((r) => (root = r));
		const t = setInterval(() => presence.tick(), 5000);
		return () => clearInterval(t);
	});

	async function open(o: Offered): Promise<void> {
		refused = '';
		setup.waitFor(o.key);
		const done = await write('open', { app: o.open });
		if (!done.ok) refused = done.error?.message ?? words.setup.openFailed(o.open);
	}

	async function copy(): Promise<void> {
		copied = (await copyText(root)) ? words.setup.copied : words.setup.refused;
		setTimeout(() => (copied = ''), 2500);
	}

	/** The first conversation of `o` that started loom here, if any. */
	const first = (o: Offered) => ofApp(presence.records, o.clients)[0];
	/** Waiting for over a minute since set up or opened from here, with none come. */
	const late = (o: Offered) => !first(o) && !!setup.since[o.key] && presence.now - setup.since[o.key] > 60_000;
</script>

{#snippet path()}
	{#if root}<span class="path"><code data-testid="setup-root">{root}</code><button type="button" class="btn small quiet" onclick={() => void copy()} data-testid="copy-root">{copied || words.setup.copy}</button></span>{/if}
{/snippet}

<div class="setup" data-testid="agent-setup">
	{#if !setUp.length}
		<p class="lead">{words.setup.lead}</p>
		{#if writes}
			<div class="uses">
				{#each offered as o (o.key)}
					<button type="button" class="btn" class:primary={o.key === 'claude-code'} disabled={!!setup.busy} onclick={() => void setup.run(o.key)} data-testid="use-{o.key}">{setup.busy === o.key ? words.setup.busy : words.setup.use(o.short)}</button>
				{/each}
			</div>
		{:else}
			<p class="aside">{words.setup.unserved}</p>
		{/if}
		{#each offered as o (o.key)}
			{#if setup.error[o.key]}<p class="warn" role="alert">{setup.error[o.key]}</p>{/if}
		{/each}
	{/if}

	{#each setUp as o (o.key)}
		<section class="app" data-testid="setup-{o.key}">
			<h5><span class="tick" aria-hidden="true"></span>{words.setup.done(o.app)}</h5>
			{#if setup.said[o.key]}<p class="aside" data-testid="setup-wrote">{wroteWords(setup.said[o.key])}</p>{/if}
			{#if shell}
				<p class="aside">{words.setup.shell}</p>
			{:else if first(o)}
				<p class="connected" data-testid="setup-connected">{words.setup.connected(o.app, clock(first(o)?.started ?? ''))}</p>
			{:else}
				<ol class="steps">
					{#if o.key === 'claude-code'}
						<li>
							{#if opens}<button type="button" class="btn small" onclick={() => void open(o)} data-testid="open-claude">{words.setup.openClaude}</button>{:else}{words.setup.openClaudeWords}{/if}
						</li>
						<li>{words.setup.chooseFolder}{#if root}:{/if}{@render path()}</li>
						<li>{words.setup.trust}</li>
						<li>{words.setup.approve}<em>{words.setup.server}</em>{words.setup.approveThen}</li>
					{:else}
						<li>{words.setup.codexOpen}{#if root}:{/if}{@render path()}</li>
						<li>{words.setup.codexTrust}</li>
					{/if}
				</ol>
				<p class="waiting" data-testid="setup-waiting">{words.setup.waiting(o.app)}</p>
				{#if late(o)}
					<p class="aside" data-testid="setup-late">{words.setup.late}<em>{words.setup.server}</em>{words.setup.lateThen(o.short)}</p>
				{/if}
			{/if}
		</section>
	{/each}
	{#if refused}<p class="warn" role="alert">{refused}</p>{/if}

	{#if setUp.length && writes && !compact}
		{@const more = offered.filter((o) => !isSetUp(o))}
		{#if more.length}
			<div class="uses">
				{#each more as o (o.key)}
					<button type="button" class="btn small" disabled={!!setup.busy} onclick={() => void setup.run(o.key)} data-testid="use-{o.key}">{setup.busy === o.key ? words.setup.busy : words.setup.also(o.short)}</button>
				{/each}
			</div>
			{#each more as o (o.key)}
				{#if setup.error[o.key]}<p class="warn" role="alert">{setup.error[o.key]}</p>{/if}
			{/each}
		{/if}
	{/if}
</div>

<style>
	.setup {
		display: grid;
		gap: 10px;
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink);
	}
	.lead {
		margin: 0;
	}
	.uses {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.app {
		display: grid;
		gap: 6px;
	}
	h5 {
		margin: 0;
		font-size: 13px;
		font-weight: 600;
		display: flex;
		align-items: center;
		gap: 7px;
	}
	.tick {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--state-accepted);
	}
	.steps {
		margin: 0;
		padding-left: 20px;
		display: grid;
		gap: 6px;
	}
	.path {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 3px;
		min-width: 0;
	}
	.path code {
		font-family: var(--mono);
		font-size: 11.5px;
		background: var(--leaf);
		padding: 2px 6px;
		border-radius: 4px;
		overflow-wrap: anywhere;
		min-width: 0;
	}
	.waiting {
		margin: 0;
		color: var(--ink-soft);
	}
	.connected {
		margin: 0;
		color: var(--state-accepted);
	}
	.aside {
		margin: 0;
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.warn {
		margin: 0;
		color: var(--state-stale);
		font-size: 12.5px;
	}
</style>
