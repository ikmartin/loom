<script lang="ts">
	// Review › Proposed edits, where loom serves no lists of Review: everything someone proposes that the person decides in a pass of its own, one card each: an agent's copy, which the card opens here at its own address (`?copy=`). A suggested edit is a pending change, kept or discarded in its document and in Your Changes; one on an agent's copy is listed on the copy's card, with what it says and the annotation it answers, and comes in with the copy.
	import { barShown } from '$lib/shell/scrollbars';
	import '$lib/review/review.css';
	import { page } from '$app/state';
	import DiffView from '$lib/components/DiffView.svelte';
	import { changeById, refusal } from '$lib/review/changes';
	import { store } from '$lib/manifest/client.svelte';
	import type { SuggestedEdit } from '$lib/manifest/types';
	import Prose from '$lib/math/Prose.svelte';
	import TexProse from '$lib/math/TexProse.svelte';
	import { placeUrl } from '$lib/nav';
	import { noteUrl } from '$lib/review/annotating.svelte';
	import { route } from '$lib/paths';
	import ContributionReview from '$lib/review/ContributionReview.svelte';
	import Empty from '$lib/review/Empty.svelte';
	import ReviewHeading from '$lib/review/ReviewHeading.svelte';
	import Said from '$lib/review/Said.svelte';
	import AppliedUndo from '$lib/review/AppliedUndo.svelte';
	import type { Answer } from '$lib/review/applied';
	import { itemsOf, tally } from '$lib/review/contribution';
	import { adoptionsOf, cardsOf, copySays } from '$lib/review/proposed';
	import { documentOf, writerOf } from '$lib/review/suggestions';
	import { keyName, linkName } from '$lib/workspace/names';
	import { rv } from '$lib/views/review/state.svelte';
	import { review as reviewWords } from '$lib/words/review';

	const here = route('/review/proposed');
	/** How many of a card's changes it names before saying how many more. */
	const CHIPS = 12;

	const m = $derived(store.manifest!);
	const cards = $derived(cardsOf(m));
	const asked = $derived(page.url.searchParams);
	// what the address opens; one gone by the time it is asked for, as a copy taken in whole, leaves the list
	const adoption = $derived(adoptionsOf(m).find((x) => x.copy === asked.get('copy')));
	const opened = $derived(!!adoption);
	const showing = $derived(adoption?.copy ?? '');

	// the last answer from a copy: said by its bar while it is open, and by the list once it is not, with the undo of an Apply beside it; what that undo says is said here even once the copy it brought back is open again
	let answer = $state<(Answer & { from: string }) | null>(null);

	const name = (e: SuggestedEdit) => keyName(m, e.target.key);
	const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
	const file = (p: string) => p.split('/').pop()?.replace(/\.tex$/, '') ?? p;
</script>

<!-- An answer the open copy's bar does not say: a copy's once it has left, and an undo's, whose copy may be back -->
{#snippet answered(a: Answer)}
	<div class="answer"><Said text={a.text} refused={a.refused} testid="proposed-answer" />{#if a.undo}<AppliedUndo undo={a.undo} onanswer={(x) => (answer = { ...x, from: '' })} />{/if}</div>
{/snippet}

{#snippet chips(names: { name: string; bad: boolean }[])}
	<div class="chips" data-testid="proposed-chips">
		{#each names.slice(0, CHIPS) as c, i (i)}<span class="chip" class:bad={c.bad}>{c.name}</span>{/each}
		{#if names.length > CHIPS}<span class="more">and {names.length - CHIPS} more</span>{/if}
	</div>
{/snippet}

{#snippet editHead(e: SuggestedEdit)}
	{@const where = documentOf(m, e)}
	{@const placed = changeById(m, e.id)}
	<!-- an edit on no block links to none, never to the block that took the key it was suggested on -->
	<a class="name" href={placed && !placed.key ? undefined : placeUrl(m, e.target.key)} data-testid="suggestion-open">{name(e)}</a>
	{#if where?.words}<span class="of" data-testid="suggestion-document">{where.words}</span>{/if}
	<span class="of" data-testid="suggestion-writer">· {writerOf(m, e)}</span>
{/snippet}

<!-- A suggested edit on an agent's copy, folded on the copy's card: it comes in with the copy, so here it is only read. -->
{#snippet suggestedEdit(e: SuggestedEdit)}
	{@const answers = e.answers ? m.annotations[e.answers] : undefined}
	{@const change = changeById(m, e.id)}
	<div class="line">
		<span class="tag">a suggested edit</span>
		{@render editHead(e)}
	</div>
	{#if answers}<p class="why" data-testid="edit-answers">It answers <a href={noteUrl(m, answers)}>{linkName(m, `quilt:${answers.id}`)}</a>.</p>{/if}
	{#if e.quote}<q class="quoted" data-testid="suggestion-quote"><TexProse text={e.quote} /></q>{/if}
	{#if e.comment_html}<Prose html={e.comment_html} />{/if}
	{#if change?.diff}<DiffView path={change.diff} />{/if}
	{#if change && change.state !== 'ready' && change.state !== 'on-a-copy'}<p class="why" data-testid="suggestion-unplaced">{refusal(change)}</p>{/if}
	<p class="why" data-testid="suggestion-on-copy">It is on the agent's copy, and comes in with the copy.</p>
{/snippet}

<main class="page" use:barShown class:review-page={!opened} data-testid="proposed">
	<ReviewHeading title={rv.served ? reviewWords.kinds.edits.name : 'Proposed edits'} />
	<!-- where Review's reads are served, a copy is opened from Proposed edits, and goes back there -->
	{#if opened}<p class="back">{#if rv.served}<a href={route('/review')} onclick={() => rv.choose('edits')} data-testid="proposed-back">{reviewWords.yours.back}</a>{:else}<a href={here} data-testid="proposed-back">‹ Everything proposed</a>{/if}</p>{/if}
	{#if adoption}
		{@const copy = adoption.copy}
		{#if answer?.from === ''}{@render answered(answer)}{/if}
		{#key copy}<ContributionReview contribution={adoption} onanswer={(a) => (answer = a && { ...a, from: copy })} />{/key}
	{:else}
		{#if answer && answer.from !== showing}{@render answered(answer)}{/if}
		{#if !cards.length}
			<Empty text="Nobody has proposed anything." testid="proposed-none" />
		{:else}
			<p class="lead" data-testid="proposed-summary">{cards.length} to decide. What agents and collaborators propose in a pass of its own: a copy is reviewed whole. A suggested edit is kept or discarded where it stands, in its document or in Review.</p>
			<ul class="plain cards" data-testid="proposed-cards">
				{#each cards as c (c.kind + c.id)}
					<li class="card" data-testid="proposed-card" data-kind={c.kind} data-id={c.id}>
						{#if c.kind === 'copy'}
							{@const items = itemsOf(m, c.copy)}
							<div class="line">
								<span class="tag">an agent's copy</span>
								<span class="name">{file(c.copy.copy)}</span>
								<span class="of">into {file(c.copy.source)}</span>
								<span class="acts"><a class="btn small primary" href="{here}?copy={encodeURIComponent(c.copy.copy)}" data-testid="proposed-open">Review the copy</a></span>
							</div>
							<p class="why" data-testid="proposed-tally">{copySays(tally(c.copy, items))}.</p>
							{#if c.copy.issues.length}<p class="why" data-testid="proposed-issue">{c.copy.issues[0]}</p>{/if}
							{@render chips(items.map((i) => ({ name: i.name, bad: !i.can })))}
							{#if c.edits.length}
								<details class="on-copy" data-testid="proposed-on-copy">
									<summary>{count(c.edits.length, 'suggested edit', 'suggested edits')} on it, which come in with the copy</summary>
									<ul class="plain">
										{#each c.edits as e (e.id)}<li class="folded" id={e.id} data-testid="suggestion" data-id={e.id}>{@render suggestedEdit(e)}</li>{/each}
									</ul>
								</details>
							{/if}
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</main>

<style>
	.back {
		margin: -8px 2px var(--gap);
		font-size: 13px;
	}
	.answer {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--gap-tight) var(--gap);
		margin-bottom: var(--gap);
	}
	.lead {
		margin: 0 0 var(--gap);
		font-size: 13px;
		color: var(--ink-soft);
	}
	.card {
		margin: 0 0 var(--gap-tight);
		padding: 12px 14px;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--review-paper);
	}
	.line {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 8px;
	}
	.name {
		font-size: 14px;
		overflow-wrap: anywhere;
	}
	.of {
		color: var(--ink-soft);
		font-size: 12.5px;
		font-weight: 400;
	}
	.tag {
		padding: 1px 8px;
		border-radius: 999px;
		background: var(--leaf);
		color: var(--ink-soft);
		font-size: 11.5px;
	}
	.acts {
		margin-left: auto;
		display: flex;
		gap: 6px;
	}
	.quoted {
		display: block;
		margin: 6px 0 2px;
		color: var(--ink-soft);
	}
	.why {
		margin: 4px 0 0;
		font-size: 12.5px;
		color: var(--ink-soft);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px;
		margin-top: 8px;
		font-size: 12px;
	}
	.chip {
		padding: 1px 9px;
		border: 1px solid var(--rule);
		border-radius: 999px;
		color: var(--ink-soft);
		overflow-wrap: anywhere;
	}
	.chip.bad {
		border-color: var(--state-stale);
		color: var(--state-stale);
	}
	.more {
		color: var(--ink-faint);
	}
	.on-copy {
		margin-top: 8px;
		font-size: 13px;
	}
	.folded {
		margin: 10px 0 0;
		padding-top: 10px;
		border-top: 1px solid var(--rule);
		font-size: 14px;
	}
</style>
