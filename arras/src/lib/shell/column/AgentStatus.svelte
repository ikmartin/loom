<script lang="ts">
	// The foot of the column, in both of its views and folded: the connection chip, whether an agent is connected, which opens what it is and did, is told, sees and may change (`AgentPanel`). It stands only where a publisher says who is connected, and says it does not know while the stream to it is down. Folded, it is its dot alone.
	import Popover from '$lib/components/Popover.svelte';
	import AgentPanel from '$lib/agents/AgentPanel.svelte';
	import { presence } from '$lib/agents/presence.svelte';
	import { chipWords } from '$lib/agents/connected';
	import { agents } from '$lib/words/agents';

	let { folded = false }: { folded?: boolean } = $props();

	const said = $derived(chipWords(presence.records, presence.now));
	const label = $derived(agents.chip.label(said.lead, said.sub));
	let open = $state(false);

	// "active" and "3 min ago" age while nothing is said
	$effect(() => {
		if (!presence.served) return;
		const t = setInterval(() => presence.tick(), 15_000);
		return () => clearInterval(t);
	});
</script>

{#if presence.served}
	<div class="agents" class:folded>
		<Popover bind:open placement={folded ? 'right' : 'above'} width={420} block label={agents.chip.panel} testid="agent-popover">
			{#snippet trigger({ open, toggle })}
				<button type="button" class="chip tone-{said.tone}" aria-haspopup="dialog" aria-expanded={open} aria-label={label} title={folded ? label : undefined} data-testid="agent-chip" data-tone={said.tone} onclick={toggle}>
					<span class="dot" aria-hidden="true"></span>
					{#if !folded}
						<span class="said">
							<span class="lead" data-testid="agent-chip-lead">{said.lead}</span>
							{#if said.sub}<span class="sub" data-testid="agent-chip-sub">{said.sub}</span>{/if}
						</span>
						<span class="chev" aria-hidden="true"></span>
					{/if}
				</button>
			{/snippet}
			<div class="in-box"><AgentPanel onleave={() => (open = false)} /></div>
		</Popover>
	</div>
{/if}

<style>
	.agents {
		flex: none;
		margin: 0 -14px calc(-1 * var(--gap));
		border-top: 1px solid var(--rule);
	}
	/* the strip has no padding at its sides or foot, so the folded chip takes none of the margins that pull it to the open column's edges: it stands inside the strip, its dot whole in the window */
	.agents.folded {
		margin: auto 0 0;
		align-self: stretch;
	}
	.chip {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		font-family: var(--sans);
		font-size: 12px;
		color: var(--ink);
		background: none;
		border: 0;
		padding: 8px 14px;
		text-align: left;
		cursor: pointer;
	}
	.folded .chip {
		justify-content: center;
		padding: 10px 0;
	}
	.chip:hover {
		background: var(--sheet);
	}
	.dot {
		flex: none;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: none;
		box-shadow: inset 0 0 0 1.5px var(--ink-faint);
	}
	.tone-connected .dot {
		box-shadow: inset 0 0 0 1.5px var(--state-accepted);
	}
	.tone-active .dot {
		background: var(--state-accepted);
		box-shadow: none;
	}
	.tone-unknown .dot {
		box-shadow: inset 0 0 0 1.5px var(--rule);
	}
	.said {
		flex: 1 1 auto;
		min-width: 0;
		display: grid;
	}
	.lead,
	.sub {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.tone-none .lead,
	.tone-unknown .lead {
		color: var(--ink-soft);
	}
	.sub {
		font-size: 11px;
		color: var(--ink-faint);
	}
	.in-box {
		padding: 12px 14px 14px;
	}
	.chev {
		flex: none;
		width: 5px;
		height: 5px;
		border-right: 1.5px solid var(--ink-faint);
		border-bottom: 1.5px solid var(--ink-faint);
		transform: rotate(-135deg);
	}
</style>
