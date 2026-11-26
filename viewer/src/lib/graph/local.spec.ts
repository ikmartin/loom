import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { neighbourhood } from './local';
import { documentColor, memberships, graphInput } from './layout';
import type { Manifest } from '$lib/manifest/types';

const m = JSON.parse(readFileSync('tests/fixture/manifest.json', 'utf8')) as Manifest;

describe('the local graph', () => {
	it('holds the centre and exactly its direct neighbours at depth 1', () => {
		const id = Object.keys(m.nodes).find((k) => m.edges.some((e) => e.from === k || e.to === k))!;
		const n = neighbourhood(m, id, 1);
		expect(n.nodes[0]).toBe(id);
		expect(n.distance.get(id)).toBe(0);
		const rest = n.nodes.slice(1);
		expect(rest.filter((other) => n.distance.get(other) !== 1)).toEqual([]);
		expect(rest.filter((other) => !n.links.some((l) => (l.from === id && l.to === other) || (l.to === id && l.from === other)))).toEqual([]);
	});

	it('grows with depth and never loses a node', () => {
		const id = Object.keys(m.nodes).find((k) => m.edges.some((e) => e.from === k || e.to === k))!;
		const one = new Set(neighbourhood(m, id, 1).nodes);
		const two = new Set(neighbourhood(m, id, 2).nodes);
		expect([...one].filter((x) => !two.has(x))).toEqual([]);
		expect(neighbourhood(m, id, 0).nodes).toEqual([id]);
	});

	it('draws a proof as its statement', () => {
		const proof = Object.values(m.keys).find((k) => k.key !== k.node && m.nodes[k.node])!;
		expect(neighbourhood(m, proof.key, 1).nodes[0]).toBe(proof.node);
	});

	it('draws nothing for a key the manifest does not know', () => {
		expect(neighbourhood(m, 'no-such-node', 2).nodes).toEqual([]);
	});
});


it("whole quilt retains all the person's nodes; document scope uses reachability across source files", () => {
	const changed = structuredClone(m);
	const node = changed.nodes['sy-0003'];
	const primary = changed.masters[0].path;
	const secondary = 'drafting/toy.tex';
	changed.masters.push({ ...changed.masters[0], path: secondary });
	node.reached_by = [primary, secondary];
	const options = { allNodes: true };
	// every node but an agent document's derived ones, which only their own document's scope draws
	expect(graphInput(changed, options).nodes).toHaveLength(Object.values(changed.nodes).filter((n) => !n.derived_of).length);
	const before = graphInput(changed, { ...options, master: secondary });
	expect(before.nodes.map((n) => n.id)).toContain(node.id);
	expect(before.nodes.every((n) => n.reached_by.includes(secondary))).toBe(true);
	expect(memberships(changed, node.id)).toEqual([primary, secondary].sort());
	node.file = 'sections/local-theory.tex';
	expect(graphInput(changed, { ...options, master: secondary }).nodes.map((n) => n.id)).toEqual(before.nodes.map((n) => n.id));
	expect(memberships(changed, node.id)).toEqual([primary, secondary].sort());
	const color = documentColor(primary);
	changed.masters.reverse();
	expect(documentColor(primary)).toBe(color);
	expect(documentColor(secondary)).not.toBe(color);
});
