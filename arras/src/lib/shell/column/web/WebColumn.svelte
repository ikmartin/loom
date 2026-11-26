<script lang="ts">
	// The Web's column (7a, 7b): its scope, the library, a draft, a draft and what it rests on, or everything, with the choice of draft under the two that need one; its form, list or graph; and in graph form the scope's results to choose from (`WebResults`). While it stands it tells the Web it is open, so the graph's place can say where to choose a result.
	import { store } from '$lib/manifest/client.svelte';
	import type { WebScope } from '$lib/library/types';
	import { isAgentDocument } from '$lib/manifest/documents';
	import { wb } from '$lib/views/web/state.svelte';
	import { web as words } from '$lib/words/web';
	import WebResults from './WebResults.svelte';

	$effect(() => {
		wb.columnOpen = true;
		return () => (wb.columnOpen = false);
	});

	const SCOPES: WebScope[] = ['library', 'draft', 'deps', 'all'];
	// the person's drafts; the one shown is the quilt's main draft until another is chosen
	const drafts = $derived((store.manifest?.masters ?? []).filter((m) => !isAgentDocument(m)).map((m) => m.path));
</script>

<div class="wb-col" data-testid="web-column">
	<p class="rl">{words.column.scope}</p>
	<div class="scope" role="radiogroup" aria-label={words.column.scope}>
		{#each SCOPES as s (s)}
			<label class:on={wb.scope === s} title={words.column.scopes[s]}><input type="radio" name="web-scope" checked={wb.scope === s} onchange={() => wb.choose(s)} data-testid="web-scope-{s}" /><span class="t">{words.column.scopes[s]}</span></label>
			{#if wb.scope === s && (s === 'draft' || s === 'deps')}
				<select class="draft" aria-label={words.column.draft} value={wb.doc ?? ''} onchange={(e) => (wb.doc = e.currentTarget.value || null)} data-testid="web-draft">
					{#if !wb.doc}<option value="" disabled>{words.column.choose}</option>{/if}
					{#each drafts as d (d)}<option value={d}>{words.file(d)}</option>{/each}
				</select>
			{/if}
		{/each}
	</div>
	<p class="rl">{words.column.form}</p>
	<span class="seg">
		<button type="button" class:on={wb.form === 'list'} aria-pressed={wb.form === 'list'} data-testid="web-form-list" onclick={() => (wb.form = 'list')}>{words.column.list}</button>
		<button type="button" class:on={wb.form === 'graph'} aria-pressed={wb.form === 'graph'} data-testid="web-form-graph" onclick={() => (wb.form = 'graph')}>{words.column.graph}</button>
	</span>
	{#if wb.form === 'graph'}<WebResults />{/if}
</div>

<style>
	.wb-col {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		overflow: auto;
		margin: 0 -8px;
		padding: 0 8px 10px;
		font-size: 13px;
	}
	.rl {
		margin: 4px 0 6px;
		padding: 0 2px;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.scope {
		display: flex;
		flex-direction: column;
		gap: 1px;
		margin-bottom: 16px;
	}
	label {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px;
		border-radius: 6px;
		cursor: pointer;
	}
	/* a scope is one line whatever the font and the column's width, its words ending in an ellipsis before they wrap, its hover saying them in full */
	label {
		min-width: 0;
	}
	label input {
		flex: none;
	}
	.t {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	label:hover,
	label.on {
		background: var(--ann-neutral-wash);
	}
	.draft {
		margin: 2px 0 6px 28px;
		align-self: flex-start;
		font: inherit;
	}
	.seg {
		align-self: flex-start;
		flex: none;
		display: inline-flex;
		border: 1px solid var(--rule);
		border-radius: 7px;
		overflow: hidden;
		background: var(--sheet);
	}
	.seg button {
		font: inherit;
		border: 0;
		background: none;
		padding: 2px 10px;
		font-size: 11.5px;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.seg button + button {
		border-left: 1px solid var(--rule);
	}
	.seg button.on {
		background: var(--leaf);
		color: var(--ink);
		font-weight: 500;
	}
</style>
