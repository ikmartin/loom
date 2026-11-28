<script lang="ts">
	// The viewer's glyphs. Line icons rather than unicode marks, which render at whatever weight and baseline a font decides, so they sit unevenly and read as punctuation. These are drawn on one 24x24 grid at one stroke width, which is what makes them look like a set.
	//
	// Inline rather than an icon package: the viewer ships vendored inside loom's wheel, so a dependency is weight in every install, and six paths are a few hundred bytes.
	let { name, size = 19 }: { name: string; size?: number } = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.75"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
>
	{#if name === 'graph'}
		<circle cx="18" cy="5" r="3" />
		<circle cx="6" cy="12" r="3" />
		<circle cx="18" cy="19" r="3" />
		<path d="m8.59 13.51 6.83 3.98" />
		<path d="m15.41 6.51-6.82 3.98" />
	{:else if name === 'problems'}
		<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
		<path d="M12 9v4" />
		<path d="M12 17h.01" />
	{:else if name === 'search'}
		<circle cx="11" cy="11" r="8" />
		<path d="m21 21-4.3-4.3" />
	{:else if name === 'expand'}
		<path d="M15 3h6v6" />
		<path d="M9 21H3v-6" />
		<path d="m21 3-7 7" />
		<path d="m3 21 7-7" />
	{:else if name === 'fold'}
		<!-- the column's fold: two chevrons pointing the way it goes; the strip turns it round -->
		<path d="m11.5 4.5-7.5 7.5 7.5 7.5" />
		<path d="m20 4.5-7.5 7.5 7.5 7.5" />
	{:else if name === 'home'}
		<!-- Your quilts, loom's home page: a house with its door -->
		<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" />
		<path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
	{:else if name === 'gear'}
		<!-- Settings: a cog, a ring with eight teeth and a hole at its centre -->
		<path data-glyph="cog" d="M10.40 5.08L10.66 2.49L13.34 2.49L13.60 5.08A7.1 7.1 0 0 1 15.76 5.98L17.78 4.33L19.67 6.22L18.02 8.24A7.1 7.1 0 0 1 18.92 10.40L21.51 10.66L21.51 13.34L18.92 13.60A7.1 7.1 0 0 1 18.02 15.76L19.67 17.78L17.78 19.67L15.76 18.02A7.1 7.1 0 0 1 13.60 18.92L13.34 21.51L10.66 21.51L10.40 18.92A7.1 7.1 0 0 1 8.24 18.02L6.22 19.67L4.33 17.78L5.98 15.76A7.1 7.1 0 0 1 5.08 13.60L2.49 13.34L2.49 10.66L5.08 10.40A7.1 7.1 0 0 1 5.98 8.24L4.33 6.22L6.22 4.33L8.24 5.98A7.1 7.1 0 0 1 10.40 5.08Z" />
		<circle cx="12" cy="12" r="3" />
	{:else if name === 'close'}
		<path d="M18 6 6 18" />
		<path d="m6 6 12 12" />
	{:else if name === 'cursor'}
		<!-- the select tool: a pointer, because in this mode the page behaves like any other text -->
		<path d="m4 3 6.5 16 2.4-6.6L19.5 10z" />
	{:else if name === 'marquee'}
		<!-- the box tool: a dashed rectangle being dragged, which is the gesture it names -->
		<path d="M4 8V6a2 2 0 0 1 2-2h2" />
		<path d="M16 4h2a2 2 0 0 1 2 2v2" />
		<path d="M20 16v2a2 2 0 0 1-2 2h-2" />
		<path d="M8 20H6a2 2 0 0 1-2-2v-2" />
		<path d="M11 4h2" />
		<path d="M11 20h2" />
		<path d="M4 11v2" />
		<path d="M20 11v2" />
	{:else if name === 'fit-width'}
		<!-- match width: two edges and the span between them -->
		<path d="M3 5v14" />
		<path d="M21 5v14" />
		<path d="M7 12h10" />
		<path d="m9 9-3 3 3 3" />
		<path d="m15 9 3 3-3 3" />
	{:else if name === 'compare'}
		<!-- two documents side by side: two columns, each with its lines -->
		<rect x="3" y="4" width="7.5" height="16" rx="1.5" />
		<rect x="13.5" y="4" width="7.5" height="16" rx="1.5" />
		<path d="M5.5 8.5h2.5" />
		<path d="M5.5 12h2.5" />
		<path d="M16 8.5h2.5" />
		<path d="M16 12h2.5" />
	{:else if name === 'pen'}
		<!-- the markup bar: what is drawn on a page -->
		<path d="M12 20h9" />
		<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
	{:else if name === 'highlighter'}
		<path d="m9 11-6 6v3h9l3-3" />
		<path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4" />
	{:else if name === 'underline'}
		<path d="M6 4v6a6 6 0 0 0 12 0V4" />
		<path d="M4 20h16" />
	{:else if name === 'strike'}
		<path d="M16 4H9a3 3 0 0 0-2.83 4" />
		<path d="M14 12a4 4 0 0 1 0 8H6" />
		<path d="M4 12h16" />
	{:else if name === 'pin'}
		<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
	{:else if name === 'ink'}
		<path d="M3 17c3-6 5-6 7-2s4 4 6-1 3-5 5-3" />
	{:else if name === 'type'}
		<path d="M4 7V4h16v3" />
		<path d="M9 20h6" />
		<path d="M12 4v16" />
	{:else if name === 'rect'}
		<rect x="4" y="5" width="16" height="14" rx="1" />
	{:else if name === 'oval'}
		<ellipse cx="12" cy="12" rx="9" ry="7" />
	{:else if name === 'arrow'}
		<path d="M5 19 19 5" />
		<path d="M9 5h10v10" />
	{:else if name === 'undo'}
		<path d="M3 7v6h6" />
		<path d="M21 17a9 9 0 0 0-15-6.7L3 13" />
	{:else if name === 'redo'}
		<path d="M21 7v6h-6" />
		<path d="M3 17a9 9 0 0 1 15-6.7L21 13" />
	{:else if name === 'turn-left'}
		<path d="M3 4v6h6" />
		<path d="M3.5 10a9 9 0 1 1 1.2 6" />
	{:else if name === 'turn-right'}
		<path d="M21 4v6h-6" />
		<path d="M20.5 10a9 9 0 1 0-1.2 6" />
	{:else if name === 'quote'}
		<path d="M6 8h4v4c0 2.5-1.5 4-4 4.5" />
		<path d="M14 8h4v4c0 2.5-1.5 4-4 4.5" />
	{:else if name === 'ask'}
		<path d="M4 5h16v11H9l-5 4z" />
		<path d="M9 10.5h.01M12 10.5h.01M15 10.5h.01" />
	{:else if name === 'note'}
		<path d="M5 3h10l4 4v14H5z" />
		<path d="M15 3v4h4" />
		<path d="M9 12h6" />
		<path d="M9 16h4" />
	{:else if name === 'more'}
		<path d="M6 12h.01M12 12h.01M18 12h.01" stroke-width="3" />
	{:else if name === 'caret'}
		<path d="m6 9 6 6 6-6" />
	{:else if name === 'left'}
		<path d="m15 18-6-6 6-6" />
	{:else if name === 'right'}
		<path d="m9 18 6-6-6-6" />
	{:else if name === 'panel'}
		<rect x="3" y="4" width="18" height="16" rx="2" />
		<path d="M15 4v16" />
	{:else if name === 'filter'}
		<path d="M3 5h18l-7 8v6l-4-2v-4z" />
	{:else if name === 'update'}
		<path d="M4 12a8 8 0 0 1 14-5M20 12a8 8 0 0 1-14 5" />
		<path d="M18 3v4h-4M6 21v-4h4" />
	{:else if name === 'copy'}
		<rect x="9" y="9" width="12" height="12" rx="2" />
		<path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
	{:else if name === 'check'}
		<path d="M20 6 9 17l-5-5" />
	{/if}
</svg>

<style>
	svg {
		display: block;
	}
</style>
