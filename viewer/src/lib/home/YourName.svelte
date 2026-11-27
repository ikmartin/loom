<script lang="ts">
	// The person's name on the home page: asked once, in a card under the heading, while no source gives one; otherwise in the footer, with "from git" where git gives it, and Change, which edits it there. Saved by `quilt-name`, as Settings › Profile saves it, for every quilt on this machine.
	import { call } from './api';
	import { homePage, nameOf } from './listing.svelte';
	import { home as words } from '$lib/words/home';

	let { place }: { place: 'card' | 'foot' } = $props();

	const shown = $derived(nameOf(homePage.listing));
	let editing = $state(false);
	let draft = $state('');
	let refused = $state('');
	let busy = $state(false);

	async function save(): Promise<void> {
		if (!draft.trim()) return document.getElementById(editing ? 'home-name-edit' : 'home-name-field')?.focus();
		if (busy) return;
		busy = true;
		const r = await call('quilt-name', { name: draft.trim() });
		busy = false;
		if (!r.ok) {
			refused = r.code === 'author-only' ? words.name.agent : words.name.refused;
			return;
		}
		refused = '';
		editing = false;
		await homePage.refresh();
	}

	function change(): void {
		draft = shown && !shown.asked ? shown.name : '';
		refused = '';
		editing = true;
	}

	function focus(el: HTMLInputElement): void {
		el.focus();
		el.select();
	}
</script>

{#if place === 'card' && shown?.asked}
	<div class="namecard" data-testid="home-name-asked">
		<label for="home-name-field">{words.name.ask}</label>
		<div class="r">
			<input id="home-name-field" class="field" placeholder={words.name.placeholder} bind:value={draft} onkeydown={(e) => e.key === 'Enter' && void save()} data-testid="home-name-field" />
			<button type="button" class="btn primary" disabled={busy} onclick={() => void save()} data-testid="home-name-save">{words.name.save}</button>
		</div>
		{#if refused}<div class="refused">{refused}</div>{/if}
	</div>
{:else if place === 'foot' && shown && !shown.asked}
	<footer class="hfoot" data-testid="home-name">
		{#if editing}
			<label for="home-name-edit">{words.name.label}</label>
			<input id="home-name-edit" class="field" bind:value={draft} use:focus onkeydown={(e) => (e.key === 'Enter' ? void save() : e.key === 'Escape' && (editing = false))} data-testid="home-name-field" />
			<button type="button" class="btn primary" disabled={busy} onclick={() => void save()} data-testid="home-name-save">{words.name.save}</button>
			<button type="button" class="btn quiet" onclick={() => (editing = false)}>{words.name.cancel}</button>
			{#if refused}<span class="refused">{refused}</span>{/if}
		{:else}
			<span>{words.name.shown}<span class="who" data-testid="home-name-shown">{shown.name}</span>{#if shown.fromGit}{words.name.fromGit}{/if}</span>
			<span aria-hidden="true">·</span>
			<button type="button" class="linkbtn" onclick={change} data-testid="home-name-change">{words.name.change}</button>
		{/if}
	</footer>
{/if}

<style>
	.namecard {
		border: 1px solid var(--rule);
		border-radius: 10px;
		background: var(--sheet);
		padding: 14px 16px;
		margin: 0 0 18px;
	}
	.namecard label {
		display: block;
		margin: 0 0 8px;
	}
	.r {
		display: flex;
		gap: 8px;
	}
	.r .btn {
		padding: 4px 11px;
		border-radius: 7px;
	}
	.field {
		border: 1px solid var(--rule);
		border-radius: 7px;
		padding: 4px 9px;
		background: var(--sheet);
		color: var(--ink);
		font: inherit;
		width: 320px;
		max-width: 100%;
		height: 28px;
	}
	.field:focus {
		outline: 2px solid var(--link-wash);
		border-color: color-mix(in srgb, var(--link) 45%, var(--rule));
	}
	.refused {
		color: var(--state-incomplete);
		margin-top: 6px;
	}
	.hfoot {
		flex: none;
		height: 36px;
		border-top: 1px solid var(--rule);
		background: var(--leaf);
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 16px;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.hfoot .who {
		color: var(--ink);
	}
	.hfoot .field {
		width: 220px;
		height: 24px;
		padding: 2px 8px;
		font-size: 11px;
	}
	.hfoot .btn {
		font-size: 11px;
		padding: 2px 9px;
	}
	.hfoot .refused {
		margin: 0;
	}
	.linkbtn {
		all: unset;
		color: var(--link);
		cursor: pointer;
	}
	.linkbtn:hover {
		text-decoration: underline;
	}
</style>
