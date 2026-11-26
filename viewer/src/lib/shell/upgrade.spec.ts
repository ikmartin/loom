import { describe, expect, it } from 'vitest';
import { judgeFormat, upgrade } from './upgrade.svelte';

describe('a quilt an earlier loom made', () => {
	it('is waited on while the layout found is below the one this loom reads', () => {
		judgeFormat({ write_api: 1, capabilities: ['library-upgrade'], format: { found: 1, reads: 2 } });
		expect(upgrade.waiting).toBe(true);
	});
	it('is not, once the layouts agree, where no format is said, or where no loom serves the quilt', () => {
		judgeFormat({ write_api: 1, capabilities: [], format: { found: 2, reads: 2 } });
		expect(upgrade.waiting).toBe(false);
		judgeFormat({ write_api: 1, capabilities: [] });
		expect(upgrade.waiting).toBe(false);
		judgeFormat(null);
		expect(upgrade.waiting).toBe(false);
	});
});
