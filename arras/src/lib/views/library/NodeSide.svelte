<script lang="ts">
	// A result beside its page (2): its name, where it stands and how loom has it, its statement rendered or plain, the question "Does loom's copy match the paper?" while it is not compared, its Lean mark, and what it uses, each with its mark; a use in another work opens that work in a Library tab at the use's place. A result of the source not digested yet, and a stub, offer `digest it`.
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import NodeBody from '$lib/node/NodeBody.svelte';
	import { THEOREMS } from '$lib/node/taxa';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { NodeAnswer, Row } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { frame } from '$lib/words/frame';
	import { library as words } from '$lib/words/library';
	import { lib, type Beside } from './state.svelte';

	let { ref, beside }: { ref: string; beside: Beside } = $props();


	const node = new Read<NodeAnswer>();
	$effect(() => {
		const b = beside;
		const r = ref;
		void gen.gen;
		const key = 'node' in b ? b.node : `${r}#${b.item}`;
		void node.load(key, (s) => api.node('node' in b ? { node: b.node } : { ref: r, item: b.item }, s));
	});
	const n = $derived(node.value);
	const how = $derived(!n ? '' : !n.digested ? (n.paper === 'stub' ? words.side.how.stub : words.side.how.none) : words.side.how[n.digested.how]);

	async function yes(): Promise<void> {
		if (!n?.node || !n.hash) return;
		const done = await api.check(n.node, n.hash);
		if (!done.ok) return message.post(done.error.message);
		message.post(words.side.checked(n.name));
	}

	async function digestIt(): Promise<void> {
		const target = 'item' in beside ? beside.item : beside.node;
		const done = await api.digest([ref], 'chosen', [target]);
		if (!done.ok) return message.post(done.error.message);
		message.post(done.value.job ? words.digest.reading : words.digest.made(done.value.made));
	}

	/** A use followed: in this work, beside the page at its place; in another, that work in its own tab, at its place. */
	async function follow(u: Row): Promise<void> {
		const there = u.source && 'ref' in u.source ? u.source.ref : ref;
		const at = await api.places({ node: u.result });
		lib.openWork(there);
		lib.beside = { ...lib.beside, [there]: { node: u.result } };
		if (at.ok && at.value.places[0]) lib.go(there, at.value.places[0].page);
	}
</script>

<aside class="side" data-testid="node-side">
	<button type="button" class="ib x" title={words.side.close} aria-label={words.side.close} onclick={() => (lib.beside = { ...lib.beside, [ref]: null })}><Icon name="close" size={16} /></button>
	{#if node.error && !n}
		<p class="grey small" role="alert">{node.error.message}</p>
	{:else if n}
		<div class="nh">{n.name}{#if n.title}<span class="tl">{n.title}</span>{/if}</div>
		<div class="nsrc">{words.side.where(n.pages ?? '', how)}</div>
		{#if n.body}
			<span class="seg">
				<button type="button" class:on={!lib.plain} onclick={() => (lib.plain = false)}>{words.side.rendered}</button>
				<button type="button" class:on={lib.plain} onclick={() => (lib.plain = true)}>{words.side.plain}</button>
			</span>
			<div class="stmt"><NodeBody body={n.body} macros={n.macros?.body ?? null} points={n.points ?? {}} plain={lib.plain} italic={THEOREMS.has(n.taxon)} drawn={n.hash ? api.drawnUrl(n.hash, n.macros?.hash ?? null) : null} /></div>
		{/if}
		{#if !n.digested}
			<p class="ask grey">{n.paper === 'stub' ? words.side.stub : words.side.notDigested}</p>
			<button type="button" class="btn" onclick={() => void digestIt()} data-testid="digest-it">{words.side.digestIt}</button>
		{:else if n.paper === 'unchecked'}
			<p class="ask">{words.side.ask}</p>
			<div class="answers">
				<button type="button" class="btn" onclick={() => void yes()} data-testid="it-matches">{words.side.yes}</button>
				<button type="button" class="btn" onclick={() => message.post(words.side.noLater)}>{words.side.no}</button>
			</div>
		{:else if n.paper}
			<div class="chip"><Mark kind={paperMark(n.paper)} /> {frame.marks[paperMark(n.paper)]}</div>
		{/if}
		{#if n.lean}<div class="chip"><Mark kind={leanMark(n.lean)} /> {frame.marks[leanMark(n.lean)]}</div>{/if}
		{#if n.uses?.length}
			<dl class="rel">
				<dt>{words.side.uses}</dt>
				<dd>
					{#each n.uses as u (u.result)}
						<div><Mark kind={paperMark(u.paper ?? 'stub')} /> <button type="button" class="linkish" onclick={() => void follow(u)}>{u.name}{u.source && 'short' in u.source ? ` · ${u.source.short}` : ''}</button></div>
					{/each}
				</dd>
			</dl>
		{/if}
	{/if}
</aside>

<style>
	.side {
		width: 370px;
		flex: none;
		border-left: 1px solid var(--rule);
		background: var(--sheet);
		padding: 18px 18px 24px;
		overflow: auto;
		position: relative;
	}
	.x {
		position: absolute;
		top: 10px;
		right: 10px;
	}
	.nh {
		font-family: var(--serif);
		font-size: 17px;
		margin-right: 30px;
	}
	.tl {
		color: var(--ink-faint);
		margin-left: 0.3em;
	}
	.nsrc {
		color: var(--ink-faint);
		font-size: 11px;
		margin: 4px 0 12px;
	}
	.stmt {
		margin: 10px 0 14px;
		padding-left: 12px;
		border-left: 3px solid var(--rule-strong);
	}
	.ask {
		margin: 12px 0 8px;
	}
	.answers {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin: 8px 8px 0 0;
		font-size: 11px;
		color: var(--ink-soft);
	}
	.rel {
		margin: 16px 0 0;
		font-size: 13px;
	}
	.rel dt {
		color: var(--ink-faint);
		font-size: 11px;
		margin-bottom: 4px;
	}
	.rel dd {
		margin: 0;
		display: grid;
		gap: 4px;
	}
</style>
