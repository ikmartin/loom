// "Settle as it stands" under a running `loom serve`: a Keep cut short after it wrote its file, and the person's own line added since, leaves a write recovery can neither finish nor undo; its notice in Problems settles it from the preview, with no command, none of the person's files written, and the suggestion recorded kept as the file shows it.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { VIEWER, expect, reviewerEnv, suiteOf, test, type Served } from '../served';

const NODE = 'drafting/nodes/sy-0002.tex';
// the agent's suggestion on sy-0002: "the fixed points are those of" in place of "compare"
const SUGGESTED = 'e-2026-09-17-zwvx4m';

/** Keep `edit` in-process with the history's line made to fail, as a Keep dies after writing its file; then a line of the person's own at the end of `rel`, so recovery can neither finish the act nor put it back. */
const LEAVE = `
import sys
from pathlib import Path
from loom import writes
from loom.cli import main

root, edit, rel = Path(sys.argv[1]), sys.argv[2], sys.argv[3]


class Died(BaseException):
    pass


def died(*args, **kwargs):
    raise Died


writes._append_guarded = died
try:
    main(["changes", "--keep", edit, "--quilt", str(root)], standalone_mode=False)
except Died:
    pass
else:
    sys.exit("the Keep was not cut short")
f = root / rel
f.write_bytes(f.read_bytes() + b"% the person's own line\\n")
if len(writes.left_acts(root, root / ".loom/records/history")) != 1:
    sys.exit("no write was left")
`;

test.use({
	prepareQuilt: async ({}, use, info) => {
		await use(({ root }) => {
			execFileSync(join(VIEWER, '../loom/.venv/bin/python'), ['-I', '-c', LEAVE, root, SUGGESTED, NODE], { cwd: VIEWER, env: reviewerEnv(suiteOf(info), `${root}.config`), stdio: 'pipe' });
		});
	}
});

/** The manifest as the publisher last built it. */
const built = (served: Served) => JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));
const leftNotices = (served: Served) => (built(served).diagnostics as { code: string }[]).filter((d) => d.code === 'loom:write-left').length;

test('a person settles a left Keep from its notice with no command: the preview first, then their file as it stands and the suggestion recorded kept', async ({ page, served }) => {
	await expect.poll(() => leftNotices(served), { timeout: 60_000 }).toBe(1);
	const before = readFileSync(join(served.root, NODE));
	expect(before.toString()).toContain('the fixed points are those of');
	expect(built(served).suggested_edits[SUGGESTED].status).toBe('open');

	await page.goto('/review/problems');
	const notice = page.locator('[data-testid="problems-yours"] [data-testid="problem-group"][data-codes="loom:write-left"]');
	await notice.getByTestId('settle-open').click();
	const preview = notice.getByTestId('settle-preview');
	await expect(preview.getByTestId('settle-lead')).toHaveText('Settling a Keep as it stands writes none of your files.');
	await expect(preview.getByTestId('settle-files').locator('li')).toHaveText([NODE]);
	await expect(preview.getByTestId('settle-edits').locator('li')).toHaveCount(1);
	await expect(preview.getByTestId('settle-edits').locator('li')).toContainText(': kept, since its words stand where it was written.');
	// looking settles nothing
	expect(leftNotices(served)).toBe(1);
	expect(built(served).suggested_edits[SUGGESTED].status).toBe('open');

	await preview.getByTestId('settle-confirm').click();
	await expect(page.getByTestId('settle-said')).toHaveText('Settled as it stands: none of your files was written. Suggested edits: 1 kept.');
	// the notice goes with the act, and nothing of loom's own is said
	await expect.poll(() => leftNotices(served), { timeout: 60_000 }).toBe(0);
	await expect(notice).toHaveCount(0);
	await expect(page.locator('main')).not.toContainText('loom doctor');
	expect(readFileSync(join(served.root, NODE)).equals(before)).toBe(true);
	expect(built(served).suggested_edits[SUGGESTED].status).toBe('kept');
});
