<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { store } from '$lib/manifest/client.svelte';
	import { canonUrl, keyUrl, masterUrl, threadUrl } from '$lib/nav';
	import { landmarkName } from '$lib/workspace/history';
	import { frame } from '$lib/words/frame';
	import { upgrade } from '$lib/shell/upgrade.svelte';

	let el: HTMLElement | undefined = $state();

	// ⌘K is ninja-keys' own hotkey, and the one way in: search is not offered as a control until it does more than find by id and title
	onMount(() => {
		void import('ninja-keys');
	});

	type Item = { id: string; title: string; section: string; keywords?: string; handler: () => void };

	const data = $derived.by((): Item[] => {
		const m = store.manifest;
		if (!m) return [];
		return m.search.map((s) => {
			const url =
				s.kind === 'master'
					? masterUrl(s.key)
					: s.kind === 'canon'
						? canonUrl(s.key)
						: s.kind === 'thread'
							? threadUrl(s.key)
							: keyUrl(m, s.key);
			// a landmark by the name its tab carries, `main.tex · widgets-v2`: its path and its paper's title say the same thing for every version
			const landmark = s.kind === 'canon' ? m.canon?.find((c) => c.path === s.key) : undefined;
			return {
				id: s.key,
				title: landmark ? landmarkName(m, landmark) : `${s.key} ${s.title && s.title !== s.key ? '· ' + s.title : ''}`,
				// the palette is a person naming where to go, as the four views' names are; each result says the view it opens in, all of them Docs' pages today
				section: `${frame.views.docs.name} · ${s.taxon || s.kind || 'node'}`,
				keywords: [...(s.aliases ?? []), ...(s.tags ?? []), s.excerpt ?? ''].join(' '),
				handler: () => void goto(url)
			};
		});
	});

	$effect(() => {
		if (el) (el as unknown as { data: Item[] }).data = data;
	});
</script>

<!-- drawn once the publisher has said the quilt is in this loom's layout and there is a manifest to search: the frame drawn before a quilt an earlier loom made is known is taken away before ninja-keys' header gives its field the keyboard, a frame after it is first drawn -->
{#if upgrade.judged && store.manifest}<ninja-keys bind:this={el} placeholder="Search ids, titles, aliases, tags… (⌘K)"></ninja-keys>{/if}
