// Review on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/review6.ts`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 4 to 12): the column's kinds, counts and drafts; the list by who is waiting; answering a question, keeping an edit, withdrawing a task; and the rules that hold everywhere: no control but the four view names changes view, and no id is drawn. Where Review's reads are not served, today's Review stands, which its own specs hold.
import { expect, test, type Page } from '@playwright/test';
import { serve } from '../manifest';

async function open(page: Page): Promise<void> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/review?fixture=round6');
	await expect(page.getByTestId('review-view')).toBeVisible();
	await expect(page.getByTestId('review-row').first()).toBeVisible();
}

const count = (page: Page, testid: string) => page.getByTestId(testid).locator('.n');

test('Everything lists 29 rows by who is waiting, and the column counts each kind alphabetically, the agents apart', async ({ page }) => {
	await open(page);
	await expect(count(page, 'review-kind-all')).toHaveText('29');
	const kinds = await page.getByTestId('review-column').locator('[data-testid^="review-kind-"]').evaluateAll((bs) => bs.map((b) => b.getAttribute('data-testid')!.slice(12) + ' ' + b.querySelector('.n')?.textContent));
	expect(kinds).toEqual(['all 29', 'accepted-changed 6', 'questions 2', 'attested-changed 2', 'cited 4', 'check 5', 'attest 2', 'fetch 3', 'edits 5', 'agents 6']);
	const groups = await page.getByTestId('review-group').evaluateAll((gs) => gs.map((g) => g.getAttribute('data-kind')));
	expect(groups).toEqual(['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'attested-changed', 'edits', 'agents']);
	await expect(page.getByTestId('review-row')).toHaveCount(29);
	// the agents' group starts folded
	await expect(page.getByTestId('review-task')).toHaveCount(0);
	await page.getByTestId('review-group').filter({ hasText: 'Waiting for an agent' }).getByRole('button').click();
	await expect(page.getByTestId('review-task')).toHaveCount(6);
	await expect(page.getByTestId('review-draft')).toHaveText(['main.tex20', 'bounds.tex9']);
});

test('the column shows a kind alone, and a draft narrows the list and the counts', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	await expect(page.getByTestId('review-row')).toHaveCount(5);
	await expect(page.getByTestId('review-row').first()).toContainText('Smith 2024 · 9 results');
	await expect(page.getByTestId('review-row').first()).toContainText('bounds.tex rests on one');
	await page.getByTestId('review-draft').filter({ hasText: 'bounds.tex' }).click();
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await expect(count(page, 'review-kind-all')).toHaveText('9');
	await page.getByTestId('review-kind-all').click();
	await expect(count(page, 'review-kind-all')).toHaveText('29');
	await expect(page).toHaveURL(/\/review/);
});

test("an agent's question is answered by a choice or in the person's words, and leaves", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-questions').click();
	const first = page.getByTestId('review-row').first();
	await expect(first).toContainText('Claude Code asks, digesting Okafor 2022: your mark on page 7');
	await first.getByRole('button', { expanded: false }).click();
	await first.getByRole('button', { name: 'only the proposition', exact: true }).click();
	await expect(page.getByTestId('column-message')).toContainText('Answered. Claude Code is told.');
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await page.getByTestId('review-row').first().getByRole('button', { expanded: false }).click();
	await page.getByPlaceholder('or answer in your own words').fill('Only for quivers with a cycle.');
	await page.getByRole('button', { name: 'send' }).click();
	await expect(page.getByTestId('review-empty')).toHaveText('Nothing waits here.');
	await expect(count(page, 'review-kind-questions')).toHaveText('0');
});

test('a proposed edit opens to its change and is kept; one made in place that broke the compile says why', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const broke = page.getByTestId('review-row').filter({ hasText: 'bounds.tex · Lemma 2' });
	await expect(broke).toContainText('bounds.tex has not compiled since this edit (line 14)');
	await broke.getByRole('button', { expanded: false }).click();
	await expect(broke.getByTestId('review-statement').locator('span.change[data-side="new"]').first()).toHaveText('Suppose');
	await expect(broke).toContainText('Claude Code made this edit in place. bounds.tex has not compiled since: the command it adds is not defined (line 14).');
	await expect(broke.getByRole('button', { name: 'undo the edit' })).toBeVisible();
	const first = page.getByTestId('review-row').first();
	await first.getByRole('button', { expanded: false }).click();
	await first.getByRole('button', { name: 'keep' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Kept.');
	await expect(page.getByTestId('review-row')).toHaveCount(4);
});

test("a work's results to check open the first a draft rests on beside its page, and the yes takes it away", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	const smith = page.getByTestId('review-row').filter({ hasText: 'Smith 2024 · ' });
	await expect(smith).toContainText('Smith 2024 · 9 results');
	await smith.getByRole('button', { expanded: false }).first().click();
	const first = smith.getByTestId('review-sub').first();
	await expect(first).toContainText('3.2 Lemma · Test lemma');
	await expect(first).toContainText('bounds.tex rests on it, through Proposition 3.4');
	await expect(first).toContainText('extracted exactly from the TeX source, so compare it at a glance');
	await expect(first.getByTestId('review-crop')).toBeVisible();
	await expect(first.getByTestId('review-crop').locator('canvas')).toBeVisible();
	await first.getByRole('button', { name: 'yes, it matches' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Lemma 3.2 matches the paper.');
	await expect(smith).toContainText('Smith 2024 · 8 results');
	await expect(smith.getByTestId('review-sub').first()).toContainText('3.1 Definition · Radius');
	await expect(smith.getByTestId('review-sub').first().getByRole('button', { name: 'yes, it matches' })).toBeVisible();
	const arden = page.getByTestId('review-row').filter({ hasText: 'Arden 2025 · Theorem 5.1' });
	await arden.getByRole('button', { expanded: false }).first().click();
	await expect(arden).toContainText('transcribed by Claude Code from page 2, so read it closely');
	await arden.getByRole('button', { name: 'yes, it matches' }).click();
	await expect(arden).toHaveCount(0);
	await expect(count(page, 'review-kind-check')).toHaveText('4');
});

test("an agent's correction to a compared result shows what it changes, and is taken or declined", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	const row = page.getByTestId('review-row').filter({ hasText: 'Arden 2024 · a correction to Definition 1.2' });
	await expect(row).toContainText('proposed by Claude Code');
	await row.getByRole('button', { expanded: false }).click();
	await expect(row.getByTestId('review-correction').locator('[data-side="old"]')).toHaveText('of the divergence map');
	await expect(row).toContainText('The text you compared on 18 Nov stands until you take this.');
	await row.getByRole('button', { name: 'take' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Definition 1.2 corrected.');
	await expect(row).toHaveCount(0);
});

test("a cited result is located in its paper, its passage marked to digest, and asked for; or asked for at once, alone or all together", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-cited').click();
	await expect(page.getByText('4 results your drafts cite that loom could not digest by itself')).toBeVisible();
	const okafor = page.getByTestId('review-row').filter({ hasText: 'Okafor 2022 · ' });
	await expect(okafor).toContainText('Okafor 2022 · Theorem 2.3 and Corollary 4.2');
	await expect(okafor).toContainText('PDF only · main.tex rests on both');
	await okafor.getByRole('button', { expanded: false }).first().click();
	const thm = okafor.getByTestId('review-sub').filter({ hasText: 'Theorem 2.3' });
	await thm.getByRole('button', { name: 'locate…' }).click();
	await expect(thm).toContainText('main.tex, Section 1 cites it here');
	await expect(thm.locator('span.cite.hot')).toHaveText('[2, Theorem 2.3]');
	await expect(thm).toContainText('these words are on page 1 · 1 of 2');
	await thm.getByRole('button', { name: 'next ›' }).click();
	await expect(thm).toContainText('these words are on page 2 · 2 of 2');
	await expect(thm).toContainText('Nothing is marked. Select the passage, then mark to digest.');
	// select the words of a line the crop shows, as a reader's drag would, and let go
	const crop = thm.getByTestId('review-crop');
	await expect(crop.locator('.text span').first()).toBeAttached();
	await crop.evaluate((box) => {
		const at = box.getBoundingClientRect();
		const span = [...box.querySelectorAll('.text span')].find((s) => {
			const r = s.getBoundingClientRect();
			return (s.textContent ?? '').trim().length > 8 && r.top > at.top && r.bottom < at.bottom;
		})!;
		const range = document.createRange();
		range.selectNodeContents(span);
		getSelection()!.removeAllRanges();
		getSelection()!.addRange(range);
		span.closest('.text')!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
	await thm.getByRole('button', { name: 'mark to digest' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Marked on page 2. An agent reads it from there.');
	// the row stays open, its other result under it
	await expect(okafor).toContainText('Okafor 2022 · Corollary 4.2');
	await okafor.getByRole('button', { name: 'ask an agent to read it' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to read it. It comes back under Digested results to check.');
	await expect(okafor).toHaveCount(0);
	await page.getByTestId('read-all').click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to read them.');
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await expect(count(page, 'review-kind-agents')).toHaveText('10');
});

test('a citation that names no result says what to add, and is asked about or remembered as a mention', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-cited').click();
	const bare = page.getByTestId('review-row').filter({ hasText: 'main.tex · the proof of Theorem 3.4 cites Okafor 2022 without naming a result' });
	await bare.getByRole('button', { expanded: false }).click();
	await expect(bare.locator('span.cite.hot')).toHaveText('[2]');
	await expect(bare).toContainText('Add the result to this citation in main.tex, for example \\cite[Lemma 2.4]{Oka22}.');
	await bare.getByRole('button', { name: 'only a mention' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Remembered as a mention. It is not asked about again.');
	await expect(bare).toHaveCount(0);
});

test('a Lean statement to attest shows it part by part beside the Lean and the agent\'s reading, and the yes attests it', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-attest').click();
	const lemma = page.getByTestId('review-row').filter({ hasText: 'main.tex · Lemma 3.3' });
	await expect(lemma).toContainText('statement and proof');
	await lemma.getByRole('button', { expanded: false }).first().click();
	await expect(lemma).toContainText('main.tex, as you wrote it');
	await expect(lemma.locator('table.att tbody tr')).toHaveCount(4);
	await expect(lemma.locator('table.att')).toContainText('theorem Weighting.IsBalanced.eq_zero_of_isForest');
	await expect(lemma.locator('table.att')).toContainText('notation from your macros, defined by no result');
	await lemma.getByRole('button', { name: /It uses Definitions 2.1 and 2.3, which you attested on 12 Nov./ }).click();
	await expect(lemma).toContainText('Definition 2.3, Balanced');
	await expect(lemma).toContainText('Claude Code found');
	await expect(lemma).toContainText('Yes covers parts (i) and (ii), ε and supp. Lemma 3.3 then reads formalized.');
	await lemma.getByRole('button', { name: 'no, it differs…' }).click();
	await lemma.getByPlaceholder('what the Lean gets wrong').fill('(ii) should fix a₀ first');
	await lemma.getByRole('button', { name: 'ask an agent to restate' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to restate it in Lean.');
	await lemma.getByRole('button', { name: 'yes, I attest it' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Lemma 3.3 attested.');
	await expect(lemma).toHaveCount(0);
	await expect(count(page, 'review-kind-attest')).toHaveText('1');
});

test('an attested definition that changed is asked about in three steps, and each result resting on it again', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-attested-changed').click();
	const def = page.getByTestId('review-row').filter({ hasText: 'main.tex · Definition 3.7, Connected' });
	await expect(def).toContainText('changed since you attested it · 2 results rest on it');
	await def.getByRole('button', { expanded: false }).first().click();
	await expect(def).toContainText('What you attested, on 12 Nov');
	await expect(def).toContainText("def Quiver'.Connected");
	await expect(def.locator('[data-side="new"]')).toHaveText('after its loops are removed');
	await expect(def).toContainText('Resting on Definition 3.7 · 2 · their words are unchanged, but what they mean has changed, so you attest each again');
	const p38 = def.getByTestId('review-sub').filter({ hasText: 'Proposition 3.8' });
	await expect(p38).toContainText('to attest again');
	await p38.getByRole('button', { expanded: false }).click();
	await expect(p38).toContainText('Does the Lean still say this, with Definition 3.7 as it reads now?');
	await p38.getByRole('button', { name: 'still states it' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Attested again.');
	await expect(p38).toContainText('attested again');
	await def.getByRole('button', { name: 'still states it' }).first().click();
	await expect(def).toHaveCount(0);
	const cor = page.getByTestId('review-row').filter({ hasText: 'main.tex · Corollary 3.5' });
	await expect(cor).toContainText('its statement changed since you attested it, 20 Nov');
	await cor.getByRole('button', { expanded: false }).first().click();
	await expect(cor).toContainText('The Lean above has not changed; only your statement has.');
});

test('see it lays the document over Review, read only, at the result, and closes back to the list', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const bounds = page.getByTestId('review-row').filter({ hasText: 'bounds.tex · Theorem 1' });
	await bounds.getByRole('button', { expanded: false }).click();
	// a draft the quilt does not hold offers nothing to see
	await expect(bounds.getByTestId('see-it')).toHaveCount(0);
	const main = page.getByTestId('review-row').filter({ hasText: 'main.tex · proof of Theorem 3.1' });
	await main.getByRole('button', { expanded: false }).click();
	await main.getByTestId('see-it').click();
	const over = page.getByTestId('review-over');
	await expect(over).toContainText('main.tex');
	await expect(over).toContainText('at proof of Theorem 3.1 · read only here; edit it in Docs');
	await expect(over.locator('.fragment').first()).toBeVisible();
	await expect(page).toHaveURL(/\/review/);
	await over.getByRole('button', { name: 'Close the document' }).click();
	await expect(over).toHaveCount(0);
	await expect(main.getByTestId('see-it')).toBeVisible();
});

test("a collaborator's pull is chosen under the kinds and drawn as today's review of it", async ({ page }) => {
	await serve(page, (m) => {
		m.incoming = { workspace: 'https://git.overleaf.com/0123', branch: 'master', base: 'a'.repeat(40), commit: 'b'.repeat(40), observed: '2026-09-28', files: [{ status: 'M', path: 'drafting/main.tex', diff: '-Old prose\n+New prose' }], changes: [{ key: 'prose:setup', name: 'Introduction', category: 'prose', kind: 'edited', local_changed: false, conflict: false, already_local: false, current: 'Old prose', proposed: 'New prose', affected: [] }] };
	});
	await open(page);
	await page.getByTestId('review-kind-incoming').click();
	await expect(page.getByText('New prose', { exact: true })).toBeVisible();
	await expect(page.getByTestId('contribution-bar')).toContainText('A pull is taken whole.');
	await page.getByTestId('review-kind-all').click();
	await expect(page.getByTestId('review-row')).toHaveCount(29);
});

test('the tasks waiting for an agent say what was asked, who works on one, and delete withdraws one', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	await expect(tasks).toHaveCount(6);
	await expect(tasks.first()).toContainText('Digest the 2 places you marked in Okafor 2022');
	await expect(tasks.first()).toContainText('Claude Code is working on it');
	await expect(tasks.nth(4)).toContainText('Read Theorem 2.3 of Okafor 2022');
	await expect(tasks.nth(4)).toContainText('waiting');
	await tasks.nth(4).hover();
	await tasks.nth(4).getByRole('button', { name: 'delete' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Task deleted.');
	await expect(tasks).toHaveCount(5);
	await expect(count(page, 'review-kind-agents')).toHaveText('5');
});

test('no control in Review changes view, and no id is drawn', async ({ page }) => {
	test.setTimeout(300000);
	await open(page);
	// every control Review draws, in its list and its column, each from where the one before left it
	const n = await page.evaluate(() => {
		const roots = [document.querySelector('[data-testid="review-view"]'), document.querySelector('[data-testid="review-column"]')];
		const buttons = roots.flatMap((r) => [...(r?.querySelectorAll('button') ?? [])]);
		buttons.forEach((b, i) => b.setAttribute('data-crawl', String(i)));
		return buttons.length;
	});
	expect(n).toBeGreaterThan(20);
	for (let i = 0; i < n; i++) {
		const b = page.locator(`[data-crawl="${i}"]`);
		if (!(await b.isVisible().catch(() => false))) continue;
		await b.click({ timeout: 5000 }).catch(() => {});
		expect(page.url()).toMatch(/\/review/);
		await page.keyboard.press('Escape');
	}
	await page.getByTestId('review-kind-all').click();
	const text = await page.locator('body').innerText();
	expect(text).not.toMatch(/\b(tq-[0-9A-Z]{4}|t-2026-|ev-2026-|m-2026-|c-[0-9a-f]{8})/);
});

test("the review's round: locate washes the words found at reading size, a page the PDF lacks says so, and a library result to attest speaks of the paper", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-cited').click();
	const okafor = page.getByTestId('review-row').filter({ hasText: 'Okafor 2022 · ' });
	await okafor.getByRole('button', { expanded: false }).first().click();
	await okafor.getByTestId('review-sub').filter({ hasText: 'Theorem 2.3' }).getByRole('button', { name: 'locate…' }).click();
	const crop = okafor.getByTestId('review-crop');
	await expect(crop.locator('.mark.on')).toHaveCount(1);
	const canvas = (await crop.locator('canvas').boundingBox())!;
	expect(canvas.width).toBeGreaterThan(612);
	// the crops of a work whose PDF is shorter than its places say so, in words
	await page.getByTestId('review-kind-check').click();
	const smith = page.getByTestId('review-row').filter({ hasText: 'Smith 2024 · ' });
	await smith.getByRole('button', { expanded: false }).first().click();
	for (const sub of await smith.getByTestId('review-sub').all()) {
		const head = sub.getByRole('button').first();
		if ((await head.getAttribute('aria-expanded')) !== 'true') await head.click();
		await expect(sub.getByTestId('review-crop').or(sub.getByTestId('review-crop-missing'))).toBeVisible();
	}
	await expect(page.locator('body')).not.toContainText('Invalid page request');
	await page.getByTestId('review-kind-attest').click();
	const prop = page.getByTestId('review-row').filter({ hasText: 'Smith 2024 · Proposition 3.4' });
	await prop.getByRole('button', { expanded: false }).first().click();
	await expect(prop).toContainText('Smith 2024, as the paper has it');
	await expect(prop.locator('table.att th').nth(1)).toHaveText('the paper');
	await expect(prop).toContainText('Does the Lean say what the paper says?');
	await expect(prop).not.toContainText('as you wrote it');
});

test("the review's round: a task deleted comes back on undo, results are named in the paper's order, the column fits, the pull has its card, and see it lands at the result", async ({ page }) => {
	await serve(page, (m) => {
		m.incoming = { workspace: 'https://git.overleaf.com/0123', branch: 'master', base: 'a'.repeat(40), commit: 'b'.repeat(40), observed: '2026-09-28', files: [], changes: [] };
	});
	await open(page);
	const label = page.getByTestId('review-kind-accepted-changed');
	expect((await label.boundingBox())!.height).toBeLessThanOrEqual(30);
	await expect(page.getByTestId('review-kind-incoming')).toHaveAttribute('aria-description', /collaborator's changes/);
	await page.getByTestId('review-kind-check').click();
	await expect(page.getByTestId('review-row').filter({ hasText: 'Arden 2024 · Lemmas' })).toContainText('Arden 2024 · Lemmas 5.7 and 5.9');
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	await tasks.first().hover();
	const del = tasks.first().getByRole('button', { name: 'delete' });
	const box = (await del.boundingBox())!;
	expect(box.height).toBeGreaterThanOrEqual(28);
	await del.click();
	await expect(tasks).toHaveCount(5);
	await page.getByTestId('column-message-undo').click();
	await expect(tasks).toHaveCount(6);
	await page.getByTestId('review-kind-edits').click();
	const first = page.getByTestId('review-row').filter({ hasText: 'main.tex · proof of Theorem 3.1' });
	await first.getByRole('button', { expanded: false }).click();
	await first.getByTestId('see-it').click();
	const over = page.getByTestId('review-over');
	const at = over.locator('#sy-0002-proof');
	await expect(at).toBeInViewport();
});
