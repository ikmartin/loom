<script lang="ts">
	// What an agent is and did, and what it is told, sees and may change: opened from the chip, its parts also standing in Settings › Agents (`parts`). Connected lists each conversation the stream says is connected, with its report in Review › History; with none, the setup card. Told is the line loom puts in the app's root file, verbatim. Sees, may change and never are said from the quilt's own settings, with loom's sentence on how far the apps set up here hold an agent to them.
	import { store } from '$lib/manifest/client.svelte';
	import { threadUrl } from '$lib/nav';
	import { agents as words } from '$lib/words/agents';
	import AgentSetup from './AgentSetup.svelte';
	import { presence } from './presence.svelte';
	import { ago, appOf, callOf, clock, isActive, startedIn } from './connected';

	type Part = 'connected' | 'told' | 'sees' | 'changes' | 'never';
	let { parts = ['connected', 'told', 'sees', 'changes', 'never'], onleave }: { parts?: Part[]; onleave?: () => void } = $props();

	const m = $derived(store.manifest);
	const agents = $derived(m?.agents);
	const config = $derived(m?.config?.agents);
	const records = $derived(presence.records);
	const sessionTitle = (id: string) => m?.sessions?.find((s) => s.id === id)?.title ?? '';
	// what follows the first part is read from the manifest, so without one it says nothing rather than something untrue
	const has = (p: Part) => parts.includes(p) && (p === 'connected' || !!m);
	const noLayer = $derived(config?.layer === false);
</script>

<div class="panel" data-testid="agent-panel">
	{#if has('connected')}
		<section>
			<h4>{words.panel.connected}</h4>
			{#if records === null}
				<p class="aside" data-testid="agents-unknown">{words.panel.unknown}</p>
			{:else if !records.length}
				<p class="aside" data-testid="agents-none">{words.panel.none}</p>
				<AgentSetup compact />
			{:else}
				<ul class="records">
					{#each records as r (r.pid)}
						<li data-testid="agent-record">
							<div class="who">
								<span class="dot" class:active={isActive(r, presence.now)} aria-hidden="true"></span>
								<strong>{appOf(r)}</strong>
								{#if r.client?.version}<span class="faint-ink">{r.client.version}</span>{/if}
								{#if startedIn(r)}<span class="faint-ink">{startedIn(r)}</span>{/if}
							</div>
							<div class="line">{words.panel.writesAs} <em>{r.as}</em>{words.panel.since(clock(r.started))}</div>
							<div class="line" data-testid="agent-last">
								{#if r.last}{words.panel.lastCall(isActive(r, presence.now), ago(r.last.when, presence.now))}{#if r.last.kind === 'tool'}<code>{callOf(r.last)}</code>{:else}{callOf(r.last)}{/if}.{:else}{words.panel.noCall}{/if}
							</div>
							{#if r.session}
								<div class="line">{words.panel.session}<a href={threadUrl(r.session)} onclick={() => onleave?.()} data-testid="agent-session">{sessionTitle(r.session) || r.session}</a>{words.panel.sessionAfter}</div>
							{/if}
						</li>
					{/each}
				</ul>
				<p class="aside">{words.panel.meaning}</p>
			{/if}
		</section>
	{/if}

	{#if has('told')}
		<section>
			<h4>{words.panel.told}</h4>
			{#if agents?.line}
				<p>{words.panel.toldFirst}</p>
				<blockquote class="verbatim" data-testid="agents-line">{agents.line}</blockquote>
				<p>{words.panel.toldThen(agents.modes.length)}</p>
			{:else if noLayer}
				<p class="aside">{words.panel.toldNothing}</p>
			{:else}
				<p class="aside">{words.panel.toldUnknown}</p>
			{/if}
		</section>
	{/if}

	{#if has('sees')}
		<section>
			<h4>{words.panel.sees}</h4>
			<ul class="said">
				<li><strong>{words.panel.seesOpen}</strong>{words.panel.seesOpenWhat}</li>
				<li><strong>{words.panel.seesNotes}</strong>{words.panel.seesNotesWhat}</li>
				<li><strong>{words.panel.seesFiles}</strong>{words.panel.seesFilesWhat}</li>
			</ul>
		</section>
	{/if}

	{#if has('changes')}
		<section>
			<h4>{words.panel.changes}</h4>
			<ul class="said">
				<li>
					<strong>{words.panel.changesFiles}</strong>{words.panel.changesFilesWhat}
					<span class="chips">
						{#each config?.deny ?? [] as p (p)}<code>{p}</code>{/each}
						{#each config?.protected ?? [] as p (p)}<code>{p}</code>{/each}
					</span>
				</li>
				<li data-testid="agents-in-place"><strong>{words.panel.changesInPlace}</strong>{words.panel.changesInPlaceWhat}</li>
				{#if config?.holds}<li data-testid="agents-holds-here"><strong>{words.panel.changesWho}</strong> {config.holds}</li>{/if}
				<li><strong>{words.panel.changesSuggested}</strong>{words.panel.changesSuggestedWhat}</li>
			</ul>
		</section>
	{/if}

	{#if has('never')}
		<section>
			<h4>{words.panel.never}</h4>
			<p>{words.panel.neverWhat}</p>
		</section>
	{/if}
</div>

<style>
	.panel {
		display: grid;
		gap: 14px;
		font-size: 13px;
		line-height: 1.45;
		color: var(--ink);
	}
	section {
		display: grid;
		gap: 6px;
	}
	h4 {
		margin: 0;
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--ink-soft);
	}
	p {
		margin: 0;
	}
	.aside {
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.records {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 10px;
	}
	.records li {
		display: grid;
		gap: 2px;
	}
	.who {
		display: flex;
		align-items: baseline;
		gap: 7px;
		flex-wrap: wrap;
	}
	.dot {
		flex: none;
		align-self: center;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: none;
		box-shadow: inset 0 0 0 1.5px var(--state-accepted);
	}
	.dot.active {
		background: var(--state-accepted);
	}
	.faint-ink {
		color: var(--ink-faint);
		font-size: 12px;
	}
	.line code {
		font-family: var(--mono);
		font-size: 11.5px;
	}
	.line {
		color: var(--ink-soft);
		font-size: 12.5px;
		padding-left: 14px;
	}
	.verbatim {
		margin: 0;
		padding: 6px 10px;
		border-left: 2px solid var(--rule);
		background: var(--leaf);
		font-family: var(--mono);
		font-size: 11.5px;
		line-height: 1.5;
		overflow-wrap: anywhere;
		white-space: pre-wrap;
	}
	.said {
		margin: 0;
		padding-left: 18px;
		display: grid;
		gap: 5px;
	}
	.chips {
		display: inline-flex;
		flex-wrap: wrap;
		gap: 4px;
		margin-left: 2px;
	}
	.chips code {
		font-family: var(--mono);
		font-size: 11px;
		background: var(--leaf);
		padding: 0 5px;
		border-radius: 4px;
	}
</style>
