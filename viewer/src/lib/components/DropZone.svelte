<script lang="ts">
	// The window's drop target (1b, 4d): files dragged over any view cover it with one sheet saying they go to the library, and, only while papers wait for their file, that one of them is attached to its paper. A drop anywhere hands the files to the library's intake (`$lib/library/intake`); a drop on a work's row, in the Library's list or among Review's papers to fetch, names that work. The view never changes. The sheet lets the pointer through, so a part of the page that takes a drop for itself (it calls preventDefault) still gets it. Nothing is drawn where the publisher takes no files. Being the intake's on every view, it also asks in the column each question the intake waits on (`askWaiting`).
	import { onMount, untrack } from 'svelte';
	import { call } from '$lib/library/api';
	import { addFiles, askWaiting } from '$lib/library/intake';
	import { store } from '$lib/manifest/client.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { onFixture } from '$lib/library/source';
	import { can } from '$lib/write';
	import { library as words } from '$lib/words/library';

	let served = false;
	let over = $state(false);

	// a question the intake waits on is asked in the column whenever it says nothing else: one a take answered, or one the manifest still lists after a reload
	$effect(() => {
		const arriving = store.manifest?.arriving;
		void message.said;
		untrack(() => askWaiting(arriving));
	});
	let waiting = $state(0);
	let timer: ReturnType<typeof setTimeout> | null = null;
	const carriesFiles = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');

	/** How many papers wait for their file, for the sheet's second line; asked as a drag comes in. */
	async function count(): Promise<void> {
		const r = await call<{ gen: number; kinds?: { fetch?: number } }>('review-counts', {});
		waiting = r.ok ? (r.value.kinds?.fetch ?? 0) : 0;
	}

	onMount(() => {
		void Promise.all([can('library-receive'), can('library-take')]).then(([receive, takes]) => (served = onFixture() || (receive && takes)));
		// a drag shows the sheet while it moves over the window, and the sheet goes when the moves stop: leaving the window, or Escape, ends them
		const move = (e: DragEvent) => {
			if (!(served || onFixture()) || !carriesFiles(e)) return;
			e.preventDefault();
			if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
			if (!over) void count();
			over = true;
			if (timer) clearTimeout(timer);
			timer = setTimeout(() => (over = false), 200);
		};
		const drop = (e: DragEvent) => {
			over = false;
			if (!(served || onFixture()) || !carriesFiles(e) || e.defaultPrevented) return;
			e.preventDefault();
			const onto = (e.target as Element | null)?.closest?.('[data-ref]')?.getAttribute('data-ref') ?? undefined;
			void addFiles(Array.from(e.dataTransfer!.files), onto);
		};
		window.addEventListener('dragover', move);
		window.addEventListener('drop', drop);
		return () => {
			window.removeEventListener('dragover', move);
			window.removeEventListener('drop', drop);
			if (timer) clearTimeout(timer);
		};
	});
</script>

{#if over}
	<div class="sheet" aria-hidden="true" data-testid="drop-sheet">
		<p><strong>{words.drop.cover}</strong>{#if waiting}<span>{words.drop.waiting(waiting)}</span>{/if}</p>
	</div>
{/if}

<style>
	.sheet {
		position: fixed;
		inset: 0;
		z-index: 80;
		pointer-events: none;
		display: grid;
		place-items: center;
		background: color-mix(in srgb, var(--link-wash) 70%, transparent);
		outline: 2px dashed var(--link);
		outline-offset: -10px;
	}
	p {
		display: grid;
		gap: 4px;
		margin: 0;
		padding: 16px 22px;
		max-width: 420px;
		background: var(--sheet);
		color: var(--ink);
		border-radius: var(--rad-card);
		box-shadow: var(--float-shadow);
		font-family: var(--sans);
		font-size: 13px;
		text-align: center;
	}
	strong {
		font-size: 15px;
		font-weight: 500;
	}
	span {
		color: var(--ink-soft);
	}
</style>
