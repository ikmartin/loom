<script lang="ts">
	// One line of a toolbar's *view* menu: the control in full words, then at its right a word on how what it acts on stands and its key, where it has them. A mode is a `menuitemcheckbox` whose words name what a click gives; an action is a `menuitem`, a link where it opens a file, in a new tab. One that cannot act now stays in its place, greyed, with the reason as its title (DR-254-ikmartin).
	let {
		label,
		name,
		key,
		aside,
		about,
		checked,
		href,
		off,
		testid,
		onclick
	}: {
		/** What a click gives, in full words. */
		label: string;
		/** The accessible name: the words and the item they act on. */
		name: string;
		/** The key that does the same from inside the document. */
		key?: string;
		/** A word or two at the line's right on how what it acts on stands (`compiling`), whether or not it can act now. */
		aside?: string;
		/** The title while it can act: more than its words, such as an error. */
		about?: string;
		/** Whether the mode is on; omitted for an action. */
		checked?: boolean;
		/** A file the item opens, in a new tab. */
		href?: string;
		/** Why it cannot act now. */
		off?: string;
		testid?: string;
		onclick?: () => void;
	} = $props();
</script>

{#snippet said()}{#if aside}<span class="aside" data-testid={testid ? `${testid}-said` : undefined}>{aside}</span>{/if}{/snippet}

{#if href && !off}
	<a class="item" role="menuitem" tabindex="-1" {href} target="_blank" rel="noopener" aria-label={name} title={about} data-testid={testid}><span class="lab">{label}</span>{@render said()}</a>
{:else}
	<button
		type="button"
		class="item"
		role={checked === undefined ? 'menuitem' : 'menuitemcheckbox'}
		tabindex="-1"
		aria-checked={checked}
		aria-disabled={off ? 'true' : undefined}
		aria-label={name}
		aria-keyshortcuts={key}
		title={off ?? about}
		data-testid={testid}
		onclick={() => !off && onclick?.()}><span class="lab">{label}</span>{@render said()}{#if key}<kbd aria-hidden="true">{key}</kbd>{/if}</button
	>
{/if}

<style>
	.item {
		display: flex;
		width: 100%;
		box-sizing: border-box;
		justify-content: space-between;
		align-items: center;
		gap: 16px;
		font: inherit;
		color: var(--ink);
		text-decoration: none;
		text-align: left;
		background: none;
		border: 0;
		padding: 5px 12px;
		cursor: pointer;
	}
	.item:hover:not([aria-disabled='true']),
	.item:focus-visible {
		background: var(--leaf);
		outline: none;
	}
	.item[aria-disabled='true'] {
		color: var(--ink-faint);
		opacity: 0.6;
		cursor: default;
	}
	.aside {
		margin-left: auto;
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.item[aria-disabled='true'] .aside {
		color: var(--ink-soft);
	}
	kbd {
		font-family: var(--sans);
		font-size: 11px;
		color: var(--ink-faint);
		border: 1px solid var(--rule);
		border-radius: 4px;
		padding: 0 5px;
	}
</style>
