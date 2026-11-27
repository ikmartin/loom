<script lang="ts">
	// A node's context (plan 0.13.3 C1–C2, phase 4): what it is in, where its text came from, what it depends on and rests on, what uses it, which discussions touched it, its detached annotations, and the local graph, in one column opened beside the node by its `context` control. Everything about the node that is not the node: the node's own pane draws its statement and proofs alone.
	//
	// **Laid out as its design is** (phase 5): the lists first — where the node is, where it came from, what it depends on and what uses it — each result named as a reader names it (`Theorem 3.1`, a proof as the proof of its result), its key in no title; the local graph last and small, one expand away.
	//
	// **Absences are omitted, not reported.** A node no document reaches shows no `in` heading, and one nothing depends on shows no `depends on`: nobody asks whether a thing is in nothing, and a heading over "nothing" is the system answering a question the reader has not got.
	import { store } from '$lib/manifest/client.svelte';
	import Diagnostics from '$lib/components/Diagnostics.svelte';
	import { forPerson } from '$lib/diagnostics';
	import RailList from '$lib/components/RailList.svelte';
	import LocalGraphPanel from '$lib/graph/LocalGraphPanel.svelte';
	import { keyUrl, nodeUrl, readUrl, tagUrl, threadUrl } from '$lib/nav';
	import { nodeName } from '../names';
	import { onAny } from '$lib/annotations';
	import type { Annotation } from '$lib/manifest/types';
	import ClosurePanel from '$lib/review/ClosurePanel.svelte';
	import { lookVars, typeName } from '$lib/review/annotationTypes';
	import { versionLabel } from '$lib/badges';
	import type { Item } from '../item';
	import { docs } from '$lib/words/docs';

	const words = docs.context;

	let { item }: { item: Item } = $props();

	const m = $derived(store.manifest!);
	const key = $derived(item.id);
	const node = $derived(m.nodes[key]);
	const stmt = $derived(m.keys[key]);

	function chain(masterPath: string): string[] {
		const out: string[] = [];
		let cur = node?.parent[masterPath];
		let guard = 0;
		while (cur && guard++ < 20) {
			out.unshift(cur);
			cur = m.nodes[cur]?.parent[masterPath];
		}
		return out;
	}

	// One line per result, not one per edge or per key: a statement and its two proofs all using the same lemma is one dependency, and a use from a proof is a use by the result the proof belongs to, so listing each said nothing several times.
	function collapse(edges: { from: string; to: string; kind: string }[], side: 'to' | 'from') {
		const out = new Map<string, Set<string>>();
		for (const e of edges) {
			const at = e[side];
			// a use by an unlabelled proof is a use by its result; one *of* a proof names the proof, which is what it rests on
			const other = side === 'from' ? (m.keys[at]?.node ?? at) : at;
			if (other === key) continue;
			(out.get(other) ?? out.set(other, new Set()).get(other)!).add(e.kind);
		}
		return [...out.entries()].map(([k, kinds]) => ({ key: k, kinds: [...kinds].sort() }));
	}
	const acceptances = $derived([key, ...(node?.proofs ?? [])].flatMap((k, index) =>
		(m.keys[k]?.acceptances ?? []).map((acceptance) => ({ ...acceptance, key: k, label: index === 0 ? words.statement : words.proof(index, node?.proofs.length ?? 0) }))));
	const deps = $derived(collapse(m.edges.filter((e) => e.from === key || node?.proofs.includes(e.from)), 'to'));
	const usedBy = $derived(collapse(m.edges.filter((e) => e.to === key || (node?.proofs ?? []).includes(e.to)), 'from'));
	// what a person is shown of the node's diagnostics, the problems in its LaTeX; `unreachable`, "in no document" in the system's words, is loom's model's, and an absence here (C2)
	const diagnostics = $derived(forPerson(m.diagnostics).filter((d) => d.keys.includes(key)));
	const detached = $derived(onAny(m, [key, ...(node?.proofs ?? [])]).filter((a) => a.detached));
	const threads = $derived(Object.values(m.threads).filter((t) => t.targets.includes(key) && !t.discarded));
	const closure = $derived(stmt?.closure.filter((k) => k !== key) ?? []);
	let restsOpen = $state(false);
	// Where the text came from: the landmark each of the node's keys was recorded at, said once per key that has one.
	const versions = $derived(
		[key, ...(node?.proofs ?? [])].map((k, index) => ({ key: k, part: index === 0 ? words.statement : words.proof(index, node?.proofs.length ?? 0), label: versionLabel(m.keys[k]) })).filter((v) => v.label)
	);
	/** A row's link text: a short preview of what the annotation says, the words it quoted when it says nothing, else that it is an annotation. The row links rather than restates (A2); the box holds the rest. */
	function preview(a: Annotation): string {
		const text = a.body_html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() || (a.quote ? `“${a.quote.trim()}”` : words.untitled);
		return text.length > 90 ? text.slice(0, 89).trimEnd() + '…' : text;
	}
	// Both directions of every declared relation, grouped by kind; an unknown kind renders as a labelled link list like any other.
	const relations = $derived.by(() => {
		const out = new Map<string, string[]>();
		for (const r of m.relations ?? []) {
			const other = r.from === key ? r.to : r.to === key ? r.from : '';
			if (!other) continue;
			const list = out.get(r.kind) ?? [];
			if (!list.includes(other)) list.push(other);
			out.set(r.kind, list);
		}
		return [...out.entries()];
	});
	/** A result in a list, as a reader names it; a key that is no node's is named for the node that owns it. */
	const label = (k: string) => {
		if (m.nodes[k]) return nodeName(m, k);
		const owner = m.keys[k]?.node;
		return owner && m.nodes[owner] ? words.proofOf(nodeName(m, owner)) : words.untitledResult;
	};
	const file = (path: string) => path.split('/').pop() ?? path;
</script>

<div class="page item context" data-testid="context">
	{#if !node}
		<p class="muted">{docs.node.gone}</p>
	{:else}
		{#if acceptances.length}
			<details class="acceptances">
				<summary>{words.accepted}</summary>
				{#each acceptances as acceptance (`${acceptance.key}:${acceptance.author}`)}
					<p>{acceptance.label} · {acceptance.author} · {acceptance.date.slice(0, 10)} · {acceptance.fresh ? words.current : words.stale}</p>
				{/each}
			</details>
		{/if}
		{#if node.reached_by.length}
			<RailList label={words.in}>
				{#each node.reached_by as mp (mp)}
					<p class="crumb">
						<a href={readUrl(mp, key)} title={mp}>{file(mp)}</a>
						{#each chain(mp) as ck (ck)}
							<span class="sep">›</span><a href={nodeUrl(ck)}>{nodeName(m, ck)}</a>
						{/each}
					</p>
				{/each}
			</RailList>
		{/if}

		{#if versions.length || node.tags.length}
			<RailList label={words.from}>
				{#each versions as v (v.key)}<p class="line" data-testid="version">{v.part} · {v.label}</p>{/each}
				{#if node.tags.length}<p class="line">{#each node.tags as t (t)}<a class="tag" href={tagUrl(t)}>#{t}</a> {/each}</p>{/if}
			</RailList>
		{/if}

		{#if deps.length}
			<RailList label={words.dependsOn}>
				<ul class="plain">
					{#each deps as d (d.key)}
						<li><a href={keyUrl(m, d.key)}>{label(d.key)}</a> <span class="faint">{d.kinds.join(', ')}</span></li>
					{/each}
				</ul>
				{#if closure.length}<p class="faint">{words.readFirst(closure.length)}</p>{/if}
			</RailList>
			<!-- The graph answers "what would this disturb"; the stack answers "what does this rest on". Built only once opened: it renders other results in full. -->
			<details class="closure-open" data-testid="closure-open" bind:open={restsOpen}>
				<summary>{words.restsOn}</summary>
				{#if restsOpen}<ClosurePanel center={key} />{/if}
			</details>
		{/if}

		{#if usedBy.length}
			<RailList label={words.usedBy}>
				<ul class="plain">
					{#each usedBy as d (d.key)}
						<li><a href={keyUrl(m, d.key)}>{label(d.key)}</a> <span class="faint">{d.kinds.join(', ')}</span></li>
					{/each}
				</ul>
			</RailList>
		{/if}

		{#each relations as [kind, items] (kind)}
			<RailList label={words.relation(kind)}>
				<ul class="plain" data-testid="relations-{kind}">
					{#each items as k (k)}
						<li>
							<a href={keyUrl(m, k)}>{label(k)}</a>
							<span class="faint">{m.nodes[k]?.reached_by?.length ? m.nodes[k].reached_by.join(', ') : m.publishes.documents ? words.noDocument : ''}</span>
						</li>
					{/each}
				</ul>
			</RailList>
		{/each}

		{#if threads.length}
			<RailList label={words.discussions}>
				<ul class="plain">
					{#each threads as t (t.id)}<li><a href={threadUrl(t.id)}>{t.title}</a></li>{/each}
				</ul>
			</RailList>
		{/if}

		{#if detached.length}
			<RailList label={words.detached}>
				<ul class="plain" data-testid="detached-list">
					{#each detached as a (a.id)}
						<li class="ann-row"><span class="ann-dot" style={lookVars(a.look)} role="img" aria-label={typeName(m, a)} title={typeName(m, a)}></span><a href="quilt:{a.id}">{preview(a)}</a></li>
					{/each}
				</ul>
			</RailList>
		{/if}

		{#if diagnostics.length}
			<RailList label={words.problems}>
				<Diagnostics items={diagnostics} />
			</RailList>
		{/if}

		<!-- Last and small: the lists answer the questions a reader brings, and the graph is the picture of them, one expand away from full size. Under its own title, which names it once; `hrefFor` makes it navigable (plan 0.11 Part D). -->
		<section class="graph"><LocalGraphPanel center={key} height={150} hrefFor={(id) => keyUrl(m, id)} /></section>
	{/if}
</div>

<style>
	.acceptances { margin-block: 12px; overflow-wrap: anywhere; }
	.acceptances summary { cursor: pointer; }
	.item.context {
		max-width: 44rem;
		font-family: var(--sans);
		font-size: 12px;
	}
	.graph {
		margin-top: var(--gap-wide);
	}
	.crumb {
		font-size: 11px;
		margin: 0;
	}
	.line {
		margin: 0 0 2px;
	}
	.tag {
		margin-right: 4px;
	}
	.closure-open {
		margin: var(--gap-tight) 0 var(--gap);
	}
	.closure-open > summary {
		cursor: pointer;
		color: var(--ink-soft);
	}
	.ann-row {
		display: flex;
		gap: 6px;
		align-items: center;
	}
	.crumb .sep {
		color: var(--ink-faint);
		margin: 0 3px;
	}
</style>
