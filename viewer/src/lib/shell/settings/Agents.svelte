<script lang="ts">
	// The setup card, to use an agent's app here; where agents may not write, a draft until Save, with how far that holds for the apps set up here (which cannot edit there, which are only asked); what is always protected; whether their edits in place wait in Your Changes; the apps that start loom here, each not set up with Set up beside it; and what any agent here is told, sees and never does. A saved list the permission file Claude Code reads has not caught up with is said at the top, with the act that rewrites it.
	import { landed } from '$lib/manifest/updating.svelte';
	import type { QuiltSettings } from '$lib/manifest/types';
	import { can, write } from '$lib/write';
	import AgentPanel from '$lib/agents/AgentPanel.svelte';
	import AgentSetup from '$lib/agents/AgentSetup.svelte';
	import { setup } from '$lib/agents/setup.svelte';
	import { agents as words } from '$lib/words/agents';
	import { draft } from './draft.svelte';
	import Chips from './Chips.svelte';
	import Row from './Row.svelte';

	let { config, editable, canUpdate }: { config: QuiltSettings; editable: boolean; canUpdate: boolean } = $props();
	const deny = $derived((draft.value('agents.deny') as string[] | undefined) ?? []);
	const agents = $derived(config.agents);
	const stale = $derived(`Claude Code's permission file is behind this list, so Claude Code holds agents to an older boundary; loom already refuses them by this one.${'agents.deny' in draft.changes ? ' Save the list first.' : ''}`);
	let pattern = $state('');
	let busy = $state(false);
	let error = $state('');
	let canSetUp = $state(false);
	$effect(() => {
		void can('agents-setup').then((ok) => (canSetUp = ok));
	});

	function add(): void {
		const p = pattern.trim();
		if (!p) return;
		if (!deny.includes(p)) draft.set('agents.deny', [...deny, p]);
		pattern = '';
	}

	async function update(): Promise<void> {
		busy = true;
		error = '';
		const answer = await write('agents-update', {});
		if (answer.ok) await landed();
		else error = answer.error?.message ?? 'Could not rewrite the permission files';
		busy = false;
	}
</script>

{#if agents.stale}
	<div class="note warn" data-testid="agents-stale">
		<span>{stale}</span>
		{#if canUpdate}<button class="btn" disabled={busy || 'agents.deny' in draft.changes} onclick={update} data-testid="agents-update">{busy ? 'Updating…' : 'Update Claude Code'}</button>{/if}
	</div>
{/if}
{#if error}<p class="note warn" role="alert">{error}</p>{/if}
<div class="card">
	<Row id="agents.setup" stack>
		<div class="in-row"><AgentSetup /></div>
	</Row>
</div>
<div class="card">
	<Row id="agents.deny" stack refused={draft.refused['agents.deny']}>
		<Chips test="config-agents.deny" items={deny} remove={editable ? (p) => draft.set('agents.deny', deny.filter((x) => x !== p)) : undefined} />
		{#if editable}
			<form
				class="add"
				onsubmit={(e) => {
					e.preventDefault();
					add();
				}}
			>
				<input class="text mono" bind:value={pattern} placeholder="paper/  or  *.bib" aria-label="A path agents may not write" data-testid="deny-pattern" />
				<button class="btn" type="submit" disabled={!pattern.trim()} data-testid="deny-add">Add</button>
			</form>
		{:else if !deny.length}
			<p class="aside">Nothing beyond what is always protected.</p>
		{/if}
		{#if agents.holds}<p class="aside" data-testid="agents-holds">{agents.holds}</p>{/if}
	</Row>
	<Row id="agents.protected" stack>
		<Chips test="agents-protected" fixed items={agents.protected} />
	</Row>
</div>
{#if agents.layer}
	<div class="card">
		<Row id="agents.apps" stack>
			<ul class="apps" data-testid="agents-apps">
				{#each agents.clients as c (c.key)}
					<li>
						<span class="app">{c.label}</span>
						<span class="file">{c.file}</span>
						{#if c.set_up}<span class="ok">Set up</span>{:else if canSetUp}<button type="button" class="btn small" disabled={!!setup.busy} onclick={() => void setup.run(c.key)} data-testid="set-up-{c.key}">{setup.busy === c.key ? words.setup.busy : words.apps.setUp}</button>{:else}<span class="off">{words.apps.notSetUp}</span>{/if}
					</li>
				{/each}
			</ul>
			{#if agents.variant === 'shell'}<p class="aside">Agents here run loom in a shell, so no app starts loom's server.</p>{/if}
			{#each agents.clients as c (c.key)}
				{#if setup.error[c.key]}<p class="aside warn-ink" role="alert">{setup.error[c.key]}</p>{/if}
			{/each}
		</Row>
	</div>
{/if}
<div class="card">
	<Row id="agents.told" stack>
		<div class="in-row"><AgentPanel parts={['told', 'sees', 'never']} /></div>
	</Row>
</div>

<style>
	.apps {
		list-style: none;
		margin: 10px 0 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.apps li {
		display: grid;
		grid-template-columns: 8rem minmax(0, 1fr) auto;
		gap: 10px;
		align-items: baseline;
		font-size: 13px;
	}
	.app {
		color: var(--ink);
	}
	.file {
		font-family: var(--mono);
		font-size: 11.5px;
		color: var(--ink-faint);
		overflow-wrap: anywhere;
	}
	.ok {
		color: var(--state-accepted);
		font-size: 12.5px;
	}
	.off {
		color: var(--ink-faint);
		font-size: 12.5px;
	}
	.warn-ink {
		color: var(--state-stale);
	}
	.in-row {
		margin-top: 10px;
	}
	@media (max-width: 560px) {
		.apps li {
			grid-template-columns: minmax(0, 1fr);
			gap: 2px;
		}
	}
</style>
