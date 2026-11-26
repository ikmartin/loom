import { relationships } from './relationships';
import { displayNode } from '$lib/nodes/display';
// The dependency graph as a layered drawing: ELK lays the results out in layers, what a result rests on above it. Edges keep their kind so the drawing can dash proof-edges and dot prose-edges.
import { taxonTone } from "$lib/taxonomy";
import type { Manifest, Node } from "$lib/manifest/types";

export interface GNode {
  id: string;
  label: string;
  taxon: string;
  state: string;
  color: string;
  /** The taxon's colour from the shared palette, as a `var(...)` reference. */
  tone: string;
  style: string;
  external: boolean;
  section: boolean;
  x: number;
  y: number;
  w: number;
  h: number;
  /** A second line in the box: the section a result sits in. */
  note?: string;
}

export interface GEdge {
  from: string;
  to: string;
  kind: string;
  points: { x: number; y: number }[];
}

export interface Layout {
  nodes: GNode[];
  edges: GEdge[];
  width: number;
  height: number;
}

export interface Filters {
  /** Keep every node, including sections and external nodes outside the default document. */
  allNodes?: boolean;
  master?: string;
  taxon?: string;
  tag?: string;
}

export function graphInput(m: Manifest, f: Filters): { nodes: Node[]; edges: { from: string; to: string; kind: string }[] } {
  const passes = (n: Node) => {
    // an agent document's nodes are drawn only when its own document is the scope: the whole quilt shows each of the person's nodes once
    if (!f.master && n.derived_of) return false;
    if (f.master && !n.reached_by.includes(f.master) && (!n.external || f.allNodes))
      return false;
    if (f.taxon && n.taxon !== f.taxon) return false;
    if (f.tag && !n.tags.includes(f.tag)) return false;
    return true;
  };
  const stmtOf = (key: string) => m.keys[key]?.node ?? key;
  // A section is a container, not a result, so it is not drawn — unless something depends on it by name, in which case dropping it would silently delete the edge as well. Sections that are an endpoint are kept and drawn as containers.
  const endpoints = new Set<string>();
  for (const e of m.edges) {
    endpoints.add(stmtOf(e.from));
    endpoints.add(stmtOf(e.to));
  }
  const nodes = Object.values(m.nodes).filter((n) => {
    if (!f.allNodes && n.kind === "section" && !endpoints.has(n.id)) return false;
    return passes(n);
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = m.edges
    .map((e) => ({ from: stmtOf(e.from), to: stmtOf(e.to), kind: e.kind }))
    .filter((e) => ids.has(e.from) && ids.has(e.to) && e.from !== e.to);
  const seen = new Set<string>();
  const unique = edges.filter((e) => {
    const k = `${e.from}>${e.to}>${e.kind}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return { nodes, edges: unique };
}

export function colorOf(m: Manifest, state: string): string {
  return m.states.labels[state]?.color ?? "neutral";
}

export function downstream(m: Manifest, id: string): Set<string> {
  const stmtOf = (key: string) => m.keys[key]?.node ?? key;
  return relationships(m.edges.map((e) => ({ ...e, from: stmtOf(e.from), to: stmtOf(e.to) })), id, 'downstream').reached;
}

type ElkNode = {
  id: string;
  width?: number;
  height?: number;
  children?: ElkNode[];
  labels?: { text: string }[];
  x?: number;
  y?: number;
  layoutOptions?: Record<string, string>;
  edges?: ElkEdge[];
};
type ElkEdge = {
  id: string;
  sources: string[];
  targets: string[];
  sections?: {
    id: string;
    startPoint: { x: number; y: number };
    endPoint: { x: number; y: number };
    bendPoints?: { x: number; y: number }[];
  }[];
};

/**
 * Lay the filtered graph out in layers with ELK, dependencies above what uses them.
 *
 * `allNodes` includes sections as ordinary boxes and preserves their connections. Without it, the drawing keeps results only. Section membership is written in each box rather than nesting layout groups.
 */
export async function layout(m: Manifest, f: Filters): Promise<Layout> {
  const { nodes, edges } = graphInput(m, f);
  const master = f.master ?? "";
  const W = 220;
  const H = 72;
  const drawn = nodes.filter((n) => f.allNodes || n.kind !== "section");
  const ids = new Set(drawn.map((n) => n.id));
  const routed = edges.filter((e) => ids.has(e.from) && ids.has(e.to));
  const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
  const laid = (await new ELK().layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.edgeRouting": "POLYLINE",
      "elk.layered.spacing.nodeNodeBetweenLayers": "34",
      "elk.spacing.nodeNode": "14",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
    },
    // ELK puts a source above its target, and upstream belongs above, so each edge is laid out from the dependency to what uses it
    children: drawn.map((n) => ({ id: n.id, width: W, height: H })),
    edges: routed.map((e, i) => ({ id: "e" + i, sources: [e.to], targets: [e.from] })),
  })) as ElkNode & { edges?: ElkEdge[]; width?: number; height?: number };
  const box = new Map((laid.children ?? []).map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0, w: c.width ?? W, h: c.height ?? H }]));
  const out: Layout = { nodes: [], edges: [], width: laid.width ?? 800, height: laid.height ?? 600 };
  for (const n of drawn) {
    const b = box.get(n.id);
    if (!b) continue;
    out.nodes.push({
      id: n.id,
      label: displayNode(m, n.id, master).name,
      taxon: n.taxon,
      state: n.state,
      color: colorOf(m, n.state),
      tone: taxonTone(m, n.taxon),
      style: n.style ?? "plain",
      external: n.external,
      section: false,
      note: displayNode(m, n.id, master).context,
      ...b,
    });
  }
  for (const e of laid.edges ?? []) {
    const src = routed[Number(e.id.slice(1))];
    if (!src) continue;
    const pts: { x: number; y: number }[] = [];
    for (const s of e.sections ?? []) for (const p of [s.startPoint, ...(s.bendPoints ?? []), s.endPoint]) pts.push({ x: p.x, y: p.y });
    if (!pts.length) {
      const a = box.get(src.to);
      const b = box.get(src.from);
      if (a && b) pts.push({ x: a.x + a.w / 2, y: a.y + a.h }, { x: b.x + b.w / 2, y: b.y });
    }
    out.edges.push({ from: src.from, to: src.to, kind: src.kind, points: pts.reverse() });
  }
  return out;
}

/** The nearest section above a node in the master's tree. */
export function sectionOf(m: Manifest, id: string, master: string): string {
  let p = m.nodes[id]?.parent[master];
  while (p && m.nodes[p] && m.nodes[p].kind !== "section") p = m.nodes[p].parent[master];
  return p && m.nodes[p]?.kind === "section" ? p : "";
}


/** A document's color depends only on its path, never on its source files or list position. */
export function documentColor(path: string): string {
	let hash = 0;
	for (const char of path) hash = (Math.imul(hash, 31) + char.charCodeAt(0)) >>> 0;
	const palette = ['#3478b8', '#b38418', '#8f62b5', '#34866b', '#be6255', '#3c8290', '#a65583', '#72783a'];
	return palette[hash % palette.length];
}

/** Shared nodes keep every live document that reaches them. */
export function memberships(m: Manifest, id: string): string[] {
	const live = new Set(m.masters.filter(d => !d.closed && !d.context_only).map((master) => master.path));
	return (m.nodes[id]?.reached_by ?? []).filter((path) => live.has(path)).sort();
}
