<script lang="ts">
	// An attested result that changed, open (4i, 4j), in three steps: what the person attested, on its date, beside the Lean they attested; how it reads now, the change marked; and whether the Lean still says it. For a changed definition, the results resting on it below, apart, each asked again one by one.
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { AttestedChangedRow, ReviewBody, Statement as Text } from '$lib/library/types';
	import Icon from '$lib/components/Icon.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { review as words } from '$lib/words/review';
	import Lean from '../Lean.svelte';
	import Statement from '$lib/views/Statement.svelte';
	import Restate from './Restate.svelte';
	import SeeItLink from '../SeeItLink.svelte';

	type Resting = { result: string; name: string; statement: Text; lean: string; attested_again: boolean };
	type Body = ReviewBody & { observation?: string; at?: string; then?: Text; now?: Text; lean?: string; resting?: Resting[] };

	let { row }: { row: AttestedChangedRow } = $props();
	const body = new Read<Body>();
	let busy = $state(false);
	let open = $state<string | null>(null);

	$effect(() => {
		const id = row.row;
		void gen.gen;
		void body.load(id, (s) => api.reviewRow(id, s));
	});

	const b = $derived(body.value);

	async function still(result: string, name: string): Promise<void> {
		if (!b?.observation) return;
		busy = true;
		const done = await api.attest(result, b.observation);
		busy = false;
		message.post(done.ok ? (result === row.result ? words.attest.attested(name) : words.attested.attestedAgain) : done.error.message);
	}
</script>

{#if b?.then && b.now}
	<div class="step">
		<div class="stepn">1</div>
		<div class="stepb">
			<div class="steph">{words.attested.then(words.day(b.at ?? row.attested_at))}</div>
			<div class="cmp">
				<div class="citebox"><Statement fragment={b.then.fragment} /></div>
				<div><div class="crop-cap">{words.attested.leanThen}</div>{#if b.lean}<Lean code={b.lean} />{/if}</div>
			</div>
		</div>
	</div>
	<div class="step">
		<div class="stepn">2</div>
		<div class="stepb">
			<div class="steph">{words.attested.now}</div>
			<div class="citebox"><Statement fragment={b.now.fragment} /></div>
			<SeeItLink doc={row.doc} key={row.result} name={row.name} />
		</div>
	</div>
	<div class="step">
		<div class="stepn">3</div>
		<div class="stepb">
			<div class="steph">{words.attested.ask}</div>
			<div class="answers">
				<button type="button" class="btn" disabled={busy} onclick={() => still(row.result, row.name)}>{words.attested.still}</button>
				<Restate result={row.result} docs={row.docs} label={words.restate.ask} />
			</div>
			<p class="note after">{row.changed === 'statement' ? words.attested.leanSame : words.attested.eachAgain(row.name)}</p>
		</div>
	</div>
	{#if b.resting?.length}
		<div class="crop-cap gap">{words.attested.resting(row.name, b.resting.length)}</div>
		<div class="subtree">
			{#each b.resting as r (r.result)}
				<div class="sr" class:open={open === r.result} data-testid="review-sub">
					<button type="button" class="sr-h" aria-expanded={open === r.result} onclick={() => (open = open === r.result ? null : r.result)}>
						<span class="slot"><Mark kind={r.attested_again ? 'formalized' : 'attest'} /></span>
						<span class="tx">{words.at(words.file(row.doc), r.name)}</span>
						<span class="meta">{r.attested_again ? words.attested.done : words.attested.again}</span>
						<span class="chev"><Icon name={open === r.result ? 'caret' : 'right'} size={16} /></span>
					</button>
					{#if open === r.result}
						<div class="sr-b">
							<div class="cmp">
								<div class="citebox"><Statement fragment={r.statement.fragment} /></div>
								<Lean code={r.lean} />
							</div>
							<p class="ask">{words.attested.askResting(row.name)}</p>
							<div class="answers">
								<button type="button" class="btn" disabled={busy || r.attested_again} onclick={() => still(r.result, r.name)}>{words.attested.still}</button>
								<Restate result={r.result} docs={row.docs} label={words.restate.ask} />
							</div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
{/if}
