<script lang="ts">
	// The graph (7b): four columns, two steps back, what the focus uses, the focus, and what uses it; a solid line for a use by a statement and a dashed one for a use by a proof; a column holding more than it draws ends in "and 3 more · in the list". Laid out in columns here, with no simulation; a box puts its result in focus.
	import type { Row, WebGraph } from '$lib/library/types';
	import Mark from '$lib/marks/Mark.svelte';
	import { leanMark, paperMark } from '$lib/marks/marks';
	import { web as words } from '$lib/words/web';
	import { wb } from './state.svelte';

	let { graph }: { graph: WebGraph } = $props();
	let width = $state(0);

	type Box = { row: Row | null; more: number; x: number; y: number; w: number; h: number; col: number };
	const TOP = 26;
	const layout = $derived.by(() => {
		const W = Math.max(width, 600);
		const cw = (W - 60) / 4;
		const cols: { rows: Row[]; more: number; x: number; w: number }[] = [
			{ rows: graph.columns.back, more: graph.more.back, x: 0, w: cw - 10 },
			{ rows: graph.columns.uses, more: graph.more.uses, x: cw + 20, w: cw },
			{ rows: [graph.focus], more: 0, x: 2 * cw + 40, w: cw + 10 },
			{ rows: graph.columns.used_by, more: graph.more.used_by, x: 3 * cw + 70, w: cw - 20 }
		];
		const most = Math.max(...cols.map((c) => c.rows.length + (c.more ? 1 : 0)));
		const H = Math.max(380, TOP + most * 54);
		const boxes: Box[] = [];
		cols.forEach((c, col) => {
			const k = c.rows.length + (c.more ? 1 : 0);
			const at = (i: number, h: number) => TOP + ((i + 0.5) * (H - TOP)) / Math.max(k, 1) - h / 2;
			c.rows.forEach((row, i) => boxes.push({ row, more: 0, x: c.x, y: at(i, col === 2 ? 84 : 46), w: c.w, h: col === 2 ? 84 : 46, col }));
			if (c.more) boxes.push({ row: null, more: c.more, x: c.x, y: at(c.rows.length, 46), w: c.w, h: 46, col });
		});
		const by = new Map(boxes.filter((b) => b.row).map((b) => [b.row!.result, b]));
		const edges = graph.edges.flatMap((e) => {
			const a = by.get(e.from);
			const b = by.get(e.to);
			if (!a || !b) return [];
			if (b.col < a.col) {
				const [x1, y1, x2, y2] = [b.x + b.w, b.y + b.h / 2, a.x, a.y + a.h / 2];
				const mx = (x1 + x2) / 2;
				return [{ d: `M${x1} ${y1}C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`, proof: e.proof }];
			}
			if (b.col === a.col) {
				const [x, y1, y2] = [a.x, b.y + b.h / 2, a.y + a.h / 2];
				return [{ d: `M${x} ${y1}C${x - 34} ${y1} ${x - 34} ${y2} ${x} ${y2}`, proof: e.proof }];
			}
			return [];
		});
		return { W, H, cw, boxes, edges };
	});
	const cut = (s: string, w: number, per: number) => {
		const n = Math.floor(w / per);
		return s.length > n ? s.slice(0, n - 1) + '…' : s;
	};
	const sub = (r: Row) => [r.title, !r.source ? '' : 'doc' in r.source ? words.file(r.source.doc) : r.source.short].filter(Boolean).join(' · ');
	const go = (e: KeyboardEvent, r: Row) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), wb.follow(r));
</script>

<div class="graph" bind:clientWidth={width} data-testid="web-graph">
	{#if width}
		{@const g = layout}
		<svg width={g.W} height={g.H + 6} viewBox="0 0 {g.W} {g.H + 6}" role="group" aria-label={words.graph.label(graph.focus.name)}>
			<text class="head" x="0" y="12">{words.graph.back}</text>
			<text class="head" x={g.cw + 20} y="12">{words.graph.uses}</text>
			<text class="head" x={3 * g.cw + 70} y="12">{words.graph.usedBy}</text>
			{#each g.edges as e, i (i)}<path class="edge" class:proof={e.proof} d={e.d} />{/each}
			{#each g.boxes as b, i (i)}
				{#if b.row}
					{@const r = b.row}
					{@const focus = b.col === 2}
					<g class="n" role="button" tabindex="0" aria-label={r.name} data-testid="web-node" onclick={() => wb.follow(r)} onkeydown={(e) => go(e, r)}>
						<rect class="box" class:focus x={b.x} y={b.y} width={b.w} height={b.h} rx="8" />
						{#if r.paper}<g transform="translate({b.x + 9} {b.y + 11})"><Mark kind={paperMark(r.paper)} /></g>{/if}
						{#if r.lean}<g transform="translate({b.x + 24} {b.y + 11})"><Mark kind={leanMark(r.lean)} /></g>{/if}
						<text x={b.x + 42} y={b.y + 21} class:bold={focus}>{cut(r.name, b.w - 46, 6.2)}</text>
						<text class="sub" x={b.x + 42} y={b.y + 36}>{cut(sub(r), b.w - 50, 6.1)}</text>
						{#if focus && graph.excerpt}<text class="sub" x={b.x + 12} y={b.y + 64}>{cut(graph.excerpt, b.w - 24, 6.3)}</text>{/if}
					</g>
				{:else}
					<g><rect class="box more" x={b.x} y={b.y} width={b.w} height={b.h} rx="8" /><text class="sub" x={b.x + 12} y={b.y + 28}>{words.graph.more(b.more)}</text></g>
				{/if}
			{/each}
		</svg>
		<div class="legend"><span>── {words.graph.statement}</span><span>- - - {words.graph.proof}</span></div>
	{/if}
</div>
