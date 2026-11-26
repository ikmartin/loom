<script lang="ts">
	// Review › History › Sessions: every session, open and closed, with when it was last active, each opening its transcript, the report of an agent's conversation; annotations belong to no session, so none is counted here. Renaming, closing, reopening and deleting are `sessions/actions.ts`.
	import { onMount } from 'svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { threadUrl } from '$lib/nav';
	import { can } from '$lib/write';
	import Empty from '$lib/review/Empty.svelte';
	import DeleteSession from '$lib/sessions/DeleteSession.svelte';
	import { closeSession, deleteSession, renameSession, reopenSession } from '$lib/sessions/actions';
	import { grouped, sessionView, titleOf } from '$lib/sessions/sessions.svelte';
	import { when } from '$lib/sessions/when';
	import type { SessionRow } from '$lib/manifest/types';

	const m = $derived(store.manifest!);
	const rows = $derived([...grouped(m).open, ...grouped(m).closed]);
	let writable = $state(false);
	onMount(() => {
		void can('session-close').then((ok) => (writable = ok));
	});
	let busy = $state('');
	let renaming = $state('');
	let title = $state('');
	let doomed = $state<SessionRow | null>(null);

	// A pending rename is dropped once the manifest carries it.
	$effect(() => {
		for (const [id, t] of Object.entries(sessionView.renamed)) {
			if ((m?.sessions ?? []).find((s) => s.id === id)?.title === t) delete sessionView.renamed[id];
		}
	});

	async function act(id: string, verb: () => Promise<boolean>): Promise<void> {
		busy = id;
		await verb();
		busy = '';
	}
	async function rename(s: SessionRow): Promise<void> {
		const want = title.trim();
		renaming = '';
		if (want && want !== titleOf(s)) await act(s.id, () => renameSession(s, want));
	}
</script>

	{#if !rows.length}
		<Empty text="No sessions yet. An agent opens its own." testid="sessions-none" />
	{:else}
		<table class="list" data-testid="sessions-table">
			<thead><tr><th>Session</th><th>State</th><th title="The newest command, note or message in it">Last active</th><th></th></tr></thead>
			<tbody>
				{#each rows as s (s.id)}
					<tr data-testid="session-row-{s.id}">
						<td>
							{#if renaming === s.id}
								<!-- svelte-ignore a11y_autofocus -->
								<input bind:value={title} aria-label="Rename {titleOf(s)}" autofocus onkeydown={(e) => (e.key === 'Enter' ? rename(s) : e.key === 'Escape' ? (renaming = '') : undefined)} onblur={() => rename(s)} />
							{:else}
								<a href={threadUrl(s.id)}>{titleOf(s)}</a>{#if s.purpose}<div class="muted">{s.purpose}</div>{/if}
							{/if}
						</td>
						<td>{s.state}</td>
						<td data-testid="session-last-{s.id}" title={s.last || s.opened || s.created}>{when(s.last || s.opened || s.created)}</td>
						<td class="verbs">
							{#if writable}
								<button type="button" class="btn small quiet" disabled={busy === s.id} onclick={() => ((renaming = s.id), (title = titleOf(s)))} data-testid="sessions-rename-{s.id}">rename</button>
								{#if s.state === 'open'}
									<button type="button" class="btn small quiet" disabled={busy === s.id} onclick={() => act(s.id, () => closeSession(s.id))} data-testid="sessions-close-{s.id}">close</button>
								{:else}
									<button type="button" class="btn small quiet" disabled={busy === s.id} onclick={() => act(s.id, () => reopenSession(s.id))} data-testid="sessions-reopen-{s.id}">reopen</button>
								{/if}
								<button type="button" class="btn small quiet" disabled={busy === s.id} onclick={() => (doomed = s)} data-testid="sessions-delete-{s.id}">delete</button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	{/if}

{#if doomed}
	<DeleteSession
		title={titleOf(doomed)}
		onCancel={() => (doomed = null)}
		onDelete={() => {
			const id = doomed!.id;
			doomed = null;
			void act(id, () => deleteSession(id));
		}}
	/>
{/if}

<style>
	.verbs {
		white-space: nowrap;
		text-align: right;
	}
</style>
