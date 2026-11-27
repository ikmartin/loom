<script lang="ts">
	// Settings › Notes: the folder new notes go in, picked from the quilt's folders and saved in config.toml with the other quilt settings (a draft until Save); and the new-note command, the person's own, read and saved at once through `notes-settings`, never through config.toml or the manifest, and set by no agent.
	import { refusalOf } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import { notes as words } from '$lib/words/notes';
	import { can, write, type WriteResult } from '$lib/write';
	import { draft } from './draft.svelte';
	import Row from './Row.svelte';

	let { editable }: { editable: boolean } = $props();

	const fallback = $derived(store.manifest?.config?.notes?.default ?? 'notes');
	const chosen = $derived(String(draft.value('notes.dir') ?? ''));
	// every folder of the quilt the Files tree shows, from its files' paths
	const folders = $derived.by(() => {
		const out = new Set<string>();
		for (const f of store.manifest?.files ?? []) {
			const parts = f.path.split('/').slice(0, -1);
			for (let i = 1; i <= parts.length; i++) out.add(parts.slice(0, i).join('/'));
		}
		if (chosen) out.add(chosen);
		out.delete(fallback);
		return [...out].sort();
	});

	let served = $state(false);
	let command = $state('');
	let kept = $state('');
	let saved = $state('');
	let busy = $state(false);
	let refused = $state('');
	$effect(() => {
		void can('notes-settings').then(async (ok) => {
			served = ok;
			if (!ok) return;
			const res: WriteResult & { command?: string; kept?: string } = await write('notes-settings', {});
			if (res.ok) {
				command = saved = res.command ?? '';
				kept = res.kept ?? '';
			} else refused = refusalOf(res.error);
		});
	});

	async function save(): Promise<void> {
		busy = true;
		refused = '';
		const res: WriteResult & { command?: string; kept?: string } = await write('notes-settings', { command });
		if (res.ok) {
			command = saved = res.command ?? '';
			kept = res.kept ?? kept;
		} else refused = refusalOf(res.error);
		busy = false;
	}
</script>

<div class="card">
	<Row id="notes.dir" refused={draft.refused['notes.dir']}>
		<select value={chosen} disabled={!editable} aria-label={words.settings.dirPick} onchange={(e) => draft.set('notes.dir', e.currentTarget.value)} data-testid="config-notes.dir">
			<option value="">{words.settings.dirDefault(fallback)}</option>
			{#each folders as path (path)}<option value={path}>{path}/</option>{/each}
		</select>
	</Row>
	<Row id="notes.command" stack refused={refused}>
		{#if served}
			<form
				class="command"
				onsubmit={(event) => {
					event.preventDefault();
					void save();
				}}
			>
				<input class="text mono" bind:value={command} spellcheck="false" autocomplete="off" placeholder={words.settings.commandPlaceholder} aria-label={words.settings.command} data-testid="notes-command" />
				<button class="btn" type="submit" disabled={busy || command.trim() === saved} data-testid="notes-command-save">{busy ? words.settings.saving : words.settings.save}</button>
			</form>
			{#if kept}<p class="kept" data-testid="notes-command-kept">{words.settings.kept(kept)}</p>{/if}
		{:else}
			<p class="kept">{words.settings.cannot}</p>
		{/if}
	</Row>
</div>

<style>
	.command {
		display: flex;
		gap: 8px;
		margin-top: 10px;
	}
	.command input {
		flex: 1 1 auto;
		width: auto;
	}
	.kept {
		font-size: 12px;
		color: var(--ink-faint);
		margin: 6px 0 0;
		overflow-wrap: anywhere;
	}
</style>
