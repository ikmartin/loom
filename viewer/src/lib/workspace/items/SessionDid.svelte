<script lang="ts">
	// What it did: a session's command log read as its record. The steps list every command once, said in words by what it did (`stepOf`), with how many times and when last, and link what it names, a moved document under where it is now. The record at the foot keeps the log as loom wrote it, every command, newest at the bottom, folded, so nothing in it is hidden (V3). Annotations belong to no session, so none is listed here.
	import { store } from '$lib/manifest/client.svelte';
	import { didOf, stepOf, type Named } from '$lib/sessions/did';
	import { when } from '$lib/sessions/when';
	import { keyName } from '$lib/workspace/names';
	import { review } from '$lib/words/review';
	import type { Item } from '../item';
	import { recordOf } from './session';

	let { item }: { item: Item } = $props();

	const words = review.session;
	const m = $derived(store.manifest!);
	const log = $derived(recordOf(m, item.id).log ?? []);
	const did = $derived(didOf(log));
	const named = (n: Named) => ('key' in n ? { href: `quilt:${n.key}`, text: keyName(m, n.key), title: n.key } : { href: `quilt:${n.path}`, text: n.path.split('/').pop() ?? n.path, title: n.path });

	function clock(stamp: string): string {
		const d = new Date(stamp);
		return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
	}
</script>

<div class="did" data-testid="session-did">
	{#if log.length}
		<p class="about" data-testid="did-about">{words.did}</p>
		{#if did.ran.length}
			<section data-testid="did-ran">
				<h3>{words.heading} <span class="n">{did.ran.length}</span></h3>
				<ul class="ran">
					{#each did.ran as r (r.command)}
						<li class="cmd" data-testid="did-command">
							<span class="step" data-testid="did-step">{stepOf(r.command)}</span>
							<span class="times" data-testid="did-times">{r.count > 1 ? `×${r.count} · ` : ''}{when(r.last)} {clock(r.last)}</span>
							{#if r.names.length}
								<span class="names">{#each r.names as n, i (i)}{@const l = named(n)}<a href={l.href} title={l.title} data-testid="did-named">{l.text}</a>{/each}</span>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}
		<details class="every" data-testid="did-every">
			<summary title={words.recordHover}>{words.record} <span class="n">{log.length}</span></summary>
			<ol class="rows">
				{#each log as e, i (i)}
					<li class="row" data-testid="did-row">
						<span class="when" title={e.time}>{when(e.time)} {clock(e.time)}</span>
						<code class="command">{e.command}</code>
					</li>
				{/each}
			</ol>
		</details>
	{:else}
		<p class="empty muted">{words.none}</p>
	{/if}
</div>

<style>
	.did {
		height: 100%;
		min-height: 0;
		overflow: auto;
		padding: var(--gap) var(--gap-wide);
		font-family: var(--sans);
		font-size: 12.5px;
	}
	h3 {
		font-size: 13px;
		font-weight: 500;
		margin: var(--gap) 0 6px;
	}
	.n,
	.times {
		color: var(--ink-faint);
		font-size: 11.5px;
		font-weight: 400;
	}
	ul,
	ol {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.cmd {
		display: flex;
		flex-wrap: wrap;
		gap: 2px 10px;
		align-items: baseline;
		padding: 4px 0;
		border-bottom: 1px solid var(--rule);
	}
	.command {
		background: none;
		padding: 0;
		font-family: var(--mono, ui-monospace, monospace);
		font-size: 11.5px;
		color: var(--ink-soft);
		overflow-wrap: anywhere;
	}
	.names {
		display: inline-flex;
		gap: 8px;
	}
	.every {
		margin-top: var(--gap);
	}
	.every summary {
		cursor: pointer;
		font-size: 13px;
	}
	.row {
		display: grid;
		grid-template-columns: 8.5rem minmax(0, 1fr);
		column-gap: var(--gap);
		padding: 3px 0;
		border-bottom: 1px solid var(--rule-faint, var(--rule));
	}
	.when {
		color: var(--ink-faint);
		font-size: 11px;
		padding-top: 1px;
	}
	.empty,
	.about {
		margin: 0;
	}
	.about {
		max-width: var(--measure);
		color: var(--ink-soft);
		line-height: 1.5;
	}
</style>
