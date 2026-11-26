// Review on round six's fixture (`?fixture=round6`, `src/lib/library/fixtures/review6.ts`), as the author settled it (`docs/design/mockups/library-round-6/`, screens 4 to 12): the column's kinds, counts and drafts; the list by who is waiting; answering a question, keeping an edit, withdrawing a task; and the rules that hold everywhere: no control but the four view names changes view, and no id is drawn. Where Review's reads are not served, today's Review stands, which its own specs hold.
import { expect, test, type Page } from '@playwright/test';
import { serve } from '../manifest';
import { wideFont } from '../fonts';

async function open(page: Page): Promise<void> {
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/review?fixture=round6');
	await expect(page.getByTestId('review-view')).toBeVisible();
	await expect(page.getByTestId('review-row').first()).toBeVisible();
}

const count = (page: Page, testid: string) => page.getByTestId(testid).locator('.n');
// every row Review draws, loom's and the two kinds drawn from the manifest alike
const rows = (page: Page) => page.locator('[data-testid="review-row"][data-kind]');
/** The rows of a kind drawn from the manifest: Results to accept's blocks, Proposed edits' files, suggested edits and copies. */
const kindRows = (page: Page, kind: 'accepted-changed' | 'edits') => page.locator(`[data-testid="review-row"][data-kind="${kind}"]`);
/** Opens a row that is closed, by the button that opens it. */
async function openRow(row: ReturnType<Page['locator']>): Promise<void> {
	const h = row.locator('.rr-h[aria-expanded]');
	if ((await h.getAttribute('aria-expanded')) !== 'true') await h.click();
}

test('Everything lists what waits by who is waiting, a row for each thing counted, and the column counts each kind alphabetically, the agents below the drafts', async ({ page }) => {
	await open(page);
	await expect(count(page, 'review-kind-all')).toHaveText('28');
	const kinds = await page.getByTestId('review-column').locator('[data-testid^="review-kind-"]').evaluateAll((bs) => bs.map((b) => b.getAttribute('data-testid')!.slice(12) + ' ' + b.querySelector('.n')?.textContent));
	// Results to accept and Proposed edits count their rows drawn from the manifest, not the fixture's rows; Lean statements to attest counts the attested results that changed too
	expect(kinds).toEqual(['all 28', 'questions 2', 'cited 4', 'attest 4', 'fetch 3', 'edits 5', 'accepted-changed 5', 'check 5', 'agents 6']);
	await expect(page.getByTestId('review-column').locator('[data-testid^="review-kind-"] .t')).toHaveText(['Everything', 'Agent questions', "Cited results loom can't read", 'Lean statements to attest', 'Papers to add', 'Proposed edits', 'Results to accept', 'Results to check', 'Agents still working']);
	// Problems stands among the kinds by its name
	await expect(page.getByTestId('review-column').locator('nav').first().locator('.t')).toHaveText(['Everything', 'Agent questions', "Cited results loom can't read", 'Lean statements to attest', 'Papers to add', 'Problems', 'Proposed edits', 'Results to accept', 'Results to check']);
	// the tasks agents are still working on need nothing of the person, so they stand below the drafts, not under Waiting for you
	expect(await page.getByTestId('review-kind-agents').evaluate((a) => !!(document.querySelector('[data-testid="review-draft"]')!.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true);
	await expect(page.getByTestId('review-record')).toHaveText('History');
	const groups = await page.locator('[data-testid="review-group"][data-kind]').evaluateAll((gs) => gs.map((g) => g.getAttribute('data-kind')));
	expect(groups).toEqual(['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'edits', 'agents']);
	// a row for each thing Everything counts, the never accepted and the accepted folded beneath Results to accept and counting nothing
	await expect(rows(page)).toHaveCount(28);
	await expect(kindRows(page, 'accepted-changed')).toHaveCount(5);
	await expect(kindRows(page, 'edits')).toHaveCount(5);
	// under Lean statements to attest, the attested results that changed first, then those never attested
	const order = await page.locator('[data-testid="review-group"][data-kind="attest"] ~ [data-testid="review-row"]').evaluateAll((rs) => rs.map((r) => r.getAttribute('data-kind')));
	expect(order.slice(0, 4)).toEqual(['attested-changed', 'attested-changed', 'attest', 'attest']);
	await expect(page.getByTestId('your-changes')).toHaveCount(0);
	// the agents' group starts folded
	await expect(page.getByTestId('review-task')).toHaveCount(0);
	await page.getByTestId('review-group').filter({ hasText: 'Agents still working' }).getByRole('button').click();
	await expect(page.getByTestId('review-task')).toHaveCount(6);
	await expect(page.getByTestId('review-draft')).toHaveText(['main.tex22', 'bounds.tex5']);
});

test('the column shows a kind alone, and a draft narrows the list and the counts', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	await expect(page.getByTestId('review-row')).toHaveCount(5);
	await expect(page.getByTestId('review-row').first()).toContainText('Smith 2024 · 9 results');
	await expect(page.getByTestId('review-row').first()).toContainText('bounds.tex rests on one');
	await page.getByTestId('review-draft').filter({ hasText: 'bounds.tex' }).click();
	await expect(page.getByTestId('review-row')).toHaveCount(1);
	await expect(count(page, 'review-kind-all')).toHaveText('5');
	// the kinds are counted for every draft only, so under a draft they show none
	await expect(count(page, 'review-kind-check')).toHaveText('');
	await page.getByTestId('review-kind-all').click();
	await expect(count(page, 'review-kind-all')).toHaveText('28');
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

test('under Proposed edits each file edited in place and each suggested edit is a row that opens to its words out and in, an edit made in place said so, Keep and Discard on each', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const edit = page.locator('[data-testid="review-row"][data-file="drafting/main.tex"]');
	await expect(edit.locator('.meta')).toHaveText('edited since your look');
	await expect(page.locator('[data-testid="review-row"][data-change="e-2026-09-16-r2hw0m"] .meta')).toHaveText('proposed by agent');
	await expect(page.getByTestId('change-card')).toHaveCount(0);
	for (const row of await page.locator('[data-testid="review-row"]:is([data-change], [data-file])').all()) {
		await openRow(row);
		await expect(row.getByTestId('card-keep')).toBeVisible();
		await expect(row.getByTestId('card-discard')).toBeVisible();
	}
	await expect(edit.getByTestId('change-words').locator('.del, .ins').first()).toBeVisible();
	await expect(edit.getByTestId('change-card')).toContainText('since your look');
	// an agent's copy is a row whose link opens it on its own page in Review
	const copy = page.locator('[data-testid="review-row"][data-copy]');
	await expect(copy).toHaveCount(1);
	await expect(copy.getByTestId('proposed-open')).toHaveAttribute('href', /\/review\/proposed\?copy=/);
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

test("a transcription is judged against the page itself: the paper's page at the result's place, washed there, beside loom's copy, with the copy's words the page lacks named, and the page's text layer never shown", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-check').click();
	const arden = page.getByTestId('review-row').filter({ hasText: 'Arden 2025 · Theorem 5.1' });
	await arden.getByRole('button', { expanded: false }).first().click();
	await expect(arden).toContainText('so read it closely');
	// the page itself, drawn, with the place washed as a found passage is
	const crop = arden.getByTestId('review-crop');
	await expect(crop.locator('canvas')).toBeVisible();
	await expect(crop.locator('.mark.on')).toHaveCount(1);
	// beside loom's copy, not under it
	const copy = (await arden.locator('.stmt').boundingBox())!;
	const paper = (await crop.boundingBox())!;
	expect(paper.x).toBeGreaterThanOrEqual(copy.x + copy.width - 1);
	expect(paper.y).toBeLessThan(copy.y + copy.height);
	// the words of the copy the page does not have are named
	await expect(arden.getByTestId('check-lacks')).toHaveText("Loom's copy has words the page does not: “sums”, “adjacent”.");
	// the text layer is there to select from and never shown as text
	for (const span of (await crop.locator('.text span').all()).slice(0, 5)) expect(await span.evaluate((s) => getComputedStyle(s).color)).toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
	// a result whose every word is on the page names none
	const smith = page.getByTestId('review-row').filter({ hasText: 'Smith 2024 · ' });
	await smith.getByRole('button', { expanded: false }).first().click();
	await expect(smith.getByTestId('review-sub').first().getByTestId('review-crop')).toBeVisible();
	await expect(smith.getByTestId('check-lacks')).toHaveCount(0);
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
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to read it. It comes back under Results to check.');
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

test("a Lean statement to attest shows the statement beside loom's Lean, each definition beside what it stands for, the agent's reading part by part, and the yes attests it", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-attest').click();
	const lemma = page.getByTestId('review-row').filter({ hasText: 'main.tex · Lemma 3.3' });
	await expect(lemma).toContainText('statement and proof');
	await lemma.getByRole('button', { expanded: false }).first().click();
	// the statement as written beside the Lean as loom's check printed it, both theorems that state it
	const beside = lemma.getByTestId('attest-beside');
	await expect(beside).toContainText('main.tex, as you wrote it');
	await expect(beside).toContainText('the Lean that states it, as Lean printed it when loom checked it');
	await expect(beside.locator('pre.lean')).toHaveCount(2);
	await expect(beside.locator('pre.lean').first()).toContainText('theorem Weighting.IsBalanced.eq_zero_of_isForest');
	// each definition the Lean's statement names, beside the result it stands for, or the Lean's alone, or by its name where loom kept no print
	const defs = lemma.getByTestId('attest-definitions');
	await expect(defs.locator('tbody tr')).toHaveCount(3);
	const balanced = defs.locator('tr[data-lean="Weighting.IsBalanced"]');
	await expect(balanced).toContainText('Definition 2.3');
	await expect(balanced).toContainText('You attested its Lean on 12 Nov.');
	await expect(defs.locator(`tr[data-lean="Quiver'.cycleSign"]`)).toContainText('Defined in the Lean only, standing for no result, so your yes covers it.');
	await expect(defs.locator(`tr[data-lean="Quiver'.sameWay"] pre.lean`)).toHaveText("def Quiver'.sameWay");
	// the agent's reading, part by part, drawn as that agent's: each part names the declaration of loom's record it reads and carries no Lean of its own
	await expect(lemma.getByTestId('attest-reading')).toHaveText('Claude Code Agent read the Lean on 21 Nov. Nothing checks a reading against the Lean: your yes is to the Lean above.');
	const parts = lemma.getByTestId('attest-parts');
	await expect(parts.locator('th')).toHaveText(['', 'your draft', 'the Lean it reads', 'Claude Code Agent’s reading']);
	await expect(parts.locator('tbody tr')).toHaveCount(4);
	await expect(parts.locator('tr[data-lean="Weighting.IsBalanced.eq_cycleSign_mul"]')).toContainText('(ii)');
	await expect(parts).toContainText('notation from your macros, defined by no result');
	await expect(parts.locator('pre.lean')).toHaveCount(0);
	await lemma.getByRole('button', { name: /It uses Definitions 2.1 and 2.3, which you attested on 12 Nov./ }).click();
	await expect(lemma).toContainText('Definition 2.3, Balanced');
	await expect(lemma).toContainText('Claude Code Agent found');
	await expect(lemma).toContainText("Yes covers parts (i), (ii) and ε, supp. Lemma 3.3 then reads formalized. It covers Quiver'.cycleSign and Quiver'.sameWay too, which the Lean defines alone.");
	await lemma.getByRole('button', { name: 'no, it differs…' }).click();
	await lemma.getByPlaceholder('what the Lean gets wrong').fill('(ii) should fix a₀ first');
	await lemma.getByRole('button', { name: 'ask an agent to restate' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Asked an agent to restate it in Lean.');
	await lemma.getByRole('button', { name: 'yes, I attest it' }).click();
	await expect(page.getByTestId('column-message')).toContainText('Lemma 3.3 attested.');
	await expect(lemma).toHaveCount(0);
	await expect(count(page, 'review-kind-attest')).toHaveText('3');
});

test('an attested definition that changed is asked about in three steps, and each result resting on it again', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-attest').click();
	// the attested results that changed come first, each saying so, then those never attested
	const kinds = await rows(page).evaluateAll((rs) => rs.map((r) => r.getAttribute('data-kind')));
	expect(kinds).toEqual(['attested-changed', 'attested-changed', 'attest', 'attest']);
	for (const r of await page.locator('[data-testid="review-row"][data-kind="attested-changed"]').all()) await expect(r).toContainText('changed since you attested');
	const def = page.getByTestId('review-row').filter({ hasText: 'main.tex · Definition 3.7' });
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

test('see it lays the document over Review, read only, lands at the place, and closes back to the list', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-cited').click();
	const cite = rows(page).filter({ hasText: 'main.tex · the proof of Theorem 3.4 cites Okafor 2022 without naming a result' });
	await cite.getByRole('button', { expanded: false }).click();
	await cite.getByTestId('see-it').click();
	const over = page.getByTestId('review-over');
	await expect(over).toContainText('main.tex');
	await expect(over).toContainText('at the proof of Theorem 3.4 · read only here; edit it in Docs');
	await expect(over.locator('.fragment').first()).toBeVisible();
	await expect(over.locator('#sy-0002-proof')).toBeInViewport();
	await expect(page).toHaveURL(/\/review/);
	await over.getByRole('button', { name: 'Close the document' }).click();
	await expect(over).toHaveCount(0);
	await expect(cite.getByTestId('see-it')).toBeVisible();
});

test("a proposed edit's see it lays its draft over Review and lands at the result, and a change in no draft's text offers none", async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const nowhere = page.locator('[data-testid="review-row"][data-file="notes/intro.md"]');
	await openRow(nowhere);
	await expect(nowhere.getByTestId('see-it')).toHaveCount(0);
	const suggested = page.locator('[data-testid="review-row"][data-change="e-2026-09-16-r2hw0m"]');
	await openRow(suggested);
	const name = (await suggested.locator('.tx').innerText()).split(' · ')[1].trim();
	await suggested.getByTestId('see-it').click();
	const over = page.getByTestId('review-over');
	await expect(over).toContainText(`at ${name} · read only here; edit it in Docs`);
	await expect(over.locator('#sy-0004')).toBeInViewport();
	await expect(page).toHaveURL(/\/review(\?|$)/);
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

test("Problems has its own entry in Review's column, with its count, and opens Review's Problems page inside Review", async ({ page }) => {
	// a document of the person's that did not compile, so that something is counted
	await serve(page, (m) => void m.diagnostics.push({ severity: 'error', code: 'loom:compile-failed', class: 'latex', message: 'drafting/main.tex did not compile', locations: [{ file: 'drafting/main.tex', line: 31 }], keys: ['drafting/main.tex'], owner: 'person' } as never));
	await open(page);
	const entry = page.getByTestId('review-problems');
	await expect(entry.locator('.t')).toHaveText('Problems');
	await expect(count(page, 'review-problems')).toHaveText(/^[1-9]\d*$/);
	const n = (await count(page, 'review-problems').textContent())!;
	await entry.click();
	await expect(page).toHaveURL(/\/review\/problems/);
	// still Review, its column standing, the entry marked as the page shown, and its count the page's
	await expect(page.getByTestId('review-column')).toBeVisible();
	await expect(entry).toHaveAttribute('aria-current', 'page');
	await expect(page.getByTestId('problems-yours-count')).toHaveText(n);
	// under a draft, it counts nothing, as the kinds do
	await page.getByTestId('review-draft').first().click();
	await expect(page).toHaveURL(/\/review(\?|$)/);
	await expect(count(page, 'review-problems')).toHaveText('');
	// every link in the column keeps the person in Review
	const links = await page.getByTestId('review-column').locator('a').evaluateAll((as) => as.map((a) => new URL((a as HTMLAnchorElement).href).pathname));
	expect(links.length).toBeGreaterThan(1);
	for (const l of links) expect(l).toMatch(/^\/review(\/|$)/);
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
	await expect(prop.getByTestId('attest-parts').locator('th').nth(1)).toHaveText('the paper');
	// a reading of an earlier Lean says so
	await expect(prop.getByTestId('attest-reading')).toHaveText('Claude Code Agent read an earlier Lean, on 20 Nov; loom has checked the Lean again since, so this reading may not say what the Lean above says.');
	await expect(prop.getByTestId('attest-definitions').locator('th').nth(1)).toHaveText('in the paper');
	await expect(prop).toContainText('Does the Lean say what the paper says?');
	await expect(prop).not.toContainText('as you wrote it');
});

test("the review's round: a task deleted comes back on undo, results are named in the paper's order, and the column fits", async ({ page }) => {
	await open(page);
	const label = page.getByTestId('review-kind-accepted-changed');
	expect((await label.boundingBox())!.height).toBeLessThanOrEqual(30);
	// and in a wider font than this Mac's, as on a runner with other fonts: every label of the column on one line, its count in view
	await wideFont(page);
	for (const b of await page.getByTestId('review-column').locator('nav button').all()) {
		const box = (await b.boundingBox())!;
		expect(box.height, await b.innerText()).toBeLessThanOrEqual(30);
		const n = b.locator('.n');
		if (await n.count()) {
			const nb = (await n.boundingBox())!;
			expect(nb.x + nb.width, await b.innerText()).toBeLessThanOrEqual(box.x + box.width + 0.5);
		}
	}
	await page.getByTestId('review-kind-check').click();
	await expect(page.getByTestId('review-row').filter({ hasText: 'Arden 2024 · Lemmas' })).toContainText('Arden 2024 · Lemmas 5.7 and 5.9');
	await page.getByTestId('review-kind-agents').click();
	const tasks = page.getByTestId('review-task');
	// the undo puts back the same task, in its place and as it stood, not a new ask at the end
	const before = await tasks.allInnerTexts();
	const working = before.findIndex((t) => t.includes('working'));
	expect(working).toBeGreaterThanOrEqual(0);
	await tasks.nth(working).hover();
	const del = tasks.nth(working).getByRole('button', { name: 'delete' });
	const box = (await del.boundingBox())!;
	expect(box.height).toBeGreaterThanOrEqual(28);
	await del.click();
	await expect(tasks).toHaveCount(5);
	await page.getByTestId('column-message-undo').click();
	await expect(tasks).toHaveCount(6);
	expect(await tasks.allInnerTexts()).toEqual(before);
});

test('a link to one block\'s row opens it in view, at the top of the list as further down and in a fold', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-accepted-changed').click();
	const waiting = await kindRows(page, 'accepted-changed').evaluateAll((rows) => rows.map((r) => r.id));
	expect(waiting.length).toBeGreaterThan(3);
	await page.getByTestId('review-fold').filter({ hasText: 'Never accepted' }).getByRole('button').click();
	const never = await page.locator('[data-testid="review-fold"][data-fold="accept:never"] ~ [data-kind="accepted-changed"]').evaluateAll((rows) => rows.map((r) => r.id));
	for (const id of [waiting[0], waiting[waiting.length - 1], never[never.length - 1]]) {
		await page.goto(`/review?fixture=round6#${id}`);
		const row = page.locator(`#${id}`);
		await expect(row).toBeInViewport();
		await expect(row.locator('.rr-h')).toHaveAttribute('aria-expanded', 'true');
	}
});

test('nothing in Results to accept or Proposed edits leaves Review, and see it on a block changed since accepted draws that change over its draft', async ({ page }) => {
	await open(page);
	// a link leaves Review unless it is one of Review's pages or an anchor in the page
	const leaving = () => page.getByTestId('review-view').locator('a[href]').evaluateAll((as) => as.filter((a) => !/^(\/review|#)/.test(a.getAttribute('href')!)).map((a) => `${a.textContent!.trim()} ${a.getAttribute('href')}`));
	await page.getByTestId('review-kind-accepted-changed').click();
	for (const f of await page.getByTestId('review-fold').getByRole('button').all()) await f.click();
	for (const row of await kindRows(page, 'accepted-changed').all()) await openRow(row);
	expect(await leaving()).toEqual([]);
	await page.getByTestId('review-kind-edits').click();
	await page.getByTestId('your-todo').click();
	for (const row of await page.locator('[data-testid="review-row"]:is([data-change], [data-file])').all()) await openRow(row);
	await expect(page.getByTestId('todo-row').first()).toBeVisible();
	expect(await leaving()).toEqual([]);
	// a To do item lays its draft over Review
	await page.getByTestId('todo-row').first().getByTestId('see-it').click();
	const over = page.getByTestId('review-over');
	await expect(over).toBeVisible();
	await over.getByRole('button', { name: 'Close the document' }).click();
	// the block's own text edited: what was accepted is drawn over the draft, at the block
	await page.getByTestId('review-kind-accepted-changed').click();
	const widget = page.locator('[data-testid="review-row"][data-key="sy-0001"]');
	await expect(widget.getByTestId('review-row-why')).toHaveText('changed since you accepted');
	await openRow(widget);
	await expect(widget.getByTestId('review-comparison')).toContainText('Last accepted · Widget');
	await widget.getByTestId('see-it').click();
	await expect(over.getByTestId('review-over-since').getByTestId('review-comparison')).toContainText('Last accepted · Widget');
	await expect(over.locator('#sy-0001')).toBeInViewport();
	await expect(page).toHaveURL(/\/review(\?|$)/);
	// the document's references, and the strip's, stay in-page anchors
	expect(await leaving()).toEqual([]);
	await over.getByRole('button', { name: 'Close the document' }).click();
	// a block changed by what it rests on: that result as it is now, or the change's diff
	const proof = page.locator('[data-testid="review-row"][data-key="sy-0002/proof"]');
	await expect(proof.getByTestId('review-row-why')).toHaveText('This block uses Orbits, which uses the changed Widget.');
	await openRow(proof);
	await proof.getByTestId('see-it').click();
	await expect(over.getByTestId('review-over-since')).toContainText('This block uses Orbits, which uses the changed Widget.');
	// see it from a row that did not change since it was accepted draws no strip
	await over.getByRole('button', { name: 'Close the document' }).click();
	const never = page.locator('[data-testid="review-fold"][data-fold="accept:never"] ~ [data-kind="accepted-changed"]').first();
	await openRow(never);
	await never.getByTestId('see-it').click();
	await expect(over).toBeVisible();
	await expect(over.getByTestId('review-over-since')).toHaveCount(0);
});

test('see it keeps the block in view while the document above it settles, as a draft drawn as its source does, until the reader scrolls', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const suggested = page.locator('[data-testid="review-row"][data-change="e-2026-09-16-r2hw0m"]');
	await openRow(suggested);
	await suggested.getByTestId('see-it').click();
	const doc = page.getByTestId('review-over-doc');
	const at = doc.locator('#sy-0004');
	const offset = () => at.evaluate((e) => Math.round(e.getBoundingClientRect().top - e.closest('[data-testid="review-over-doc"]')!.getBoundingClientRect().top) + 0); // + 0: a top a hair above the pane rounds to -0, which toBe(0) tells from 0
	await expect.poll(offset).toBe(0);
	// what is drawn above the block grows after it mounted, as source blocks and mathematics settle: the block stays where it landed, the browser's own scroll anchoring off so the pane's landing is what is tested
	await doc.evaluate((d) => ((d as HTMLElement).style.overflowAnchor = 'none'));
	await doc.evaluate((d) => d.querySelector('.fragment')!.prepend(Object.assign(document.createElement('div'), { style: 'height: 1500px' })));
	await expect.poll(offset).toBe(0);
	// once the reader scrolls by their own hand, it is theirs
	await doc.hover();
	await page.mouse.wheel(0, -300);
	await doc.evaluate((d) => d.querySelector('.fragment')!.prepend(Object.assign(document.createElement('div'), { style: 'height: 800px' })));
	await expect.poll(offset).toBeGreaterThan(700);
});

test("Proposed edits says once what it watches and what it leaves to the person, and the accepted results say once that git gave the reviewer's name", async ({ page }) => {
	let unwatched = ['config.toml', '/drafting/'];
	await serve(page, (m) => {
		m.changes_since = { ...m.changes_since, unwatched, holds: 'Claude Code is refused an edit there; any other app is only asked not to.' };
		m.reviewer = { name: 'Rae Reviewer', source: 'git config user.name' };
	});
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	const watched = page.getByTestId('review-watched');
	await expect(watched).toHaveText("Here wait agents' suggestions, and every edit made in the places agents may edit since your look of 2026-09-16 11:30. Your own places are not watched, so an edit there is never listed: config.toml, /drafting/. Claude Code is refused an edit there; any other app is only asked not to.");
	await page.getByTestId('review-kind-accepted-changed').click();
	const name = page.getByTestId('review-name-from-git');
	await expect(name).toHaveText('You review as Rae Reviewer, the name git gives, and your look and acceptances are kept under it. Set your own name in Settings › Profile.');
	// closed, it stays closed; on the next visit neither is said again
	await name.getByRole('button', { name: 'Close this note' }).click();
	await expect(name).toHaveCount(0);
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	await expect(page.getByTestId('review-edit-list')).toBeVisible();
	await expect(watched).toHaveCount(0);
	await page.getByTestId('review-kind-accepted-changed').click();
	await expect(name).toHaveCount(0);
	// what it says changing, it is said again
	unwatched = ['config.toml', '/drafting/', '/notes/'];
	await open(page);
	await page.getByTestId('review-kind-edits').click();
	await expect(watched).toContainText('config.toml, /drafting/, /notes/.');
});

test('before any draft has compiled, no block in Review is named by its id: an unnumbered one by its title, else its kind and section', async ({ page }) => {
	// no compile yet: the manifest numbers nothing
	await serve(page, (m) => {
		for (const n of Object.values(m.nodes) as { numbers: Record<string, unknown> }[]) n.numbers = {};
	});
	await open(page);
	await expect(page.getByTestId('review-kind-accepted-changed')).toHaveText(/^Results to accept/);
	await page.getByTestId('review-kind-accepted-changed').click();
	for (const f of await page.getByTestId('review-fold').getByRole('button').all()) await f.click();
	const names = (await kindRows(page, 'accepted-changed').locator('.tx').allInnerTexts()).map((t) => t.split(' · ').slice(1).join(' · '));
	expect(names.length).toBeGreaterThan(10);
	for (const name of names) expect(name).not.toMatch(/\b[a-z]{1,4}-[0-9A-Z]{4}\b/);
	expect(names).toContain('Main Theorem in Appendix: an incomplete argument');
	await page.getByTestId('review-kind-edits').click();
	for (const place of await kindRows(page, 'edits').locator('.tx').allInnerTexts()) expect(place).not.toMatch(/\b[a-z]{1,4}-[0-9A-Z]{4}\b/);
});

test('Results to accept and Proposed edits draw a row for each thing they count, and a draft narrows each', async ({ page }) => {
	await open(page);
	await page.getByTestId('review-kind-accepted-changed').click();
	// every draft's blocks waiting, each once, as many as the column counts
	await expect(kindRows(page, 'accepted-changed')).toHaveCount(5);
	await expect(count(page, 'review-kind-accepted-changed')).toHaveText('5');
	await expect(kindRows(page, 'accepted-changed').first().locator('.tx')).toHaveText('main.tex · Widget');
	// the blocks never accepted and those accepted are folded beneath, and count nothing
	await expect(page.getByTestId('review-fold')).toHaveText(['Never accepted22', 'Accepted1']);
	await page.getByTestId('review-fold').filter({ hasText: 'Never accepted' }).getByRole('button').click();
	await expect(kindRows(page, 'accepted-changed')).toHaveCount(27);
	const keys = await kindRows(page, 'accepted-changed').evaluateAll((rows) => rows.map((r) => r.getAttribute('data-key')));
	expect(new Set(keys).size).toBe(keys.length);
	await expect(count(page, 'review-kind-accepted-changed')).toHaveText('5');
	await page.getByTestId('review-draft').filter({ hasText: 'bounds.tex' }).click();
	await expect(page.getByTestId('review-empty')).toHaveText('Nothing waits here.');
	await page.getByTestId('review-kind-edits').click();
	await expect(kindRows(page, 'edits')).toHaveCount(0);
	await page.getByTestId('review-draft').filter({ hasText: 'main.tex' }).click();
	// the suggested edits in main.tex's text, the file edited in place, and the agent's copy into it: four rows, as the column counts
	await expect(page.locator('[data-testid="review-row"][data-change]')).toHaveCount(2);
	await expect(page.locator('[data-testid="review-row"][data-file]')).toHaveCount(1);
	await expect(page.locator('[data-testid="review-row"][data-copy]')).toHaveCount(1);
	// widened again, the file in no document's text is listed too
	await page.getByTestId('review-kind-all').click();
	await expect(page.locator('[data-testid="review-row"][data-file]')).toHaveCount(2);
	await expect(count(page, 'review-kind-edits')).toHaveText('5');
});

test("edits made in place are one row a file, opening to each with Keep and Discard and the file's own keep all and discard all, and the column counts the rows drawn", async ({ page }) => {
	await serve(page, (m) => {
		const at = (id: string) => m.changes.find((c: { id: string }) => c.id === id);
		// two more edits in main.tex, one in the block already edited and one outside any, and one more in notes/intro.md
		m.changes.push({ ...at('c-0f621ccf'), id: 'c-00000001', old: 'one', new: 'two' }, { ...at('c-0f621ccf'), id: 'c-00000002', key: null, block: null, old: 'left', new: 'right' }, { ...at('c-5a59b9ba'), id: 'c-00000003', old: 'up', new: 'down' });
	});
	const sent: Record<string, unknown>[] = [];
	await page.route('**/_api', (r) => r.fulfill({ json: { write_api: 1, capabilities: ['change-keep', 'change-discard'], token: 't', quilt: 'q-test' } }));
	await page.route('**/_api/change-*', (r) => {
		const body = r.request().postDataJSON();
		sent.push(body);
		return r.fulfill({ json: { ok: true, result: 'done', done: body.changes, refused: [] } });
	});
	await open(page);
	// seven changes and a copy, drawn as five rows: two files, two suggested edits and the copy
	await expect(count(page, 'review-kind-edits')).toHaveText('5');
	await expect(count(page, 'review-kind-all')).toHaveText('28');
	await page.getByTestId('review-kind-edits').click();
	await expect(kindRows(page, 'edits')).toHaveCount(5);
	const main = page.locator('[data-testid="review-row"][data-file="drafting/main.tex"]');
	await expect(main.locator('.tx')).toHaveText('main.tex');
	await expect(main.locator('.meta')).toHaveText('3 edits since your look');
	await openRow(main);
	await expect(main.getByTestId('change-card')).toHaveCount(3);
	await expect(main.getByTestId('card-keep')).toHaveCount(3);
	await expect(main.getByTestId('card-discard')).toHaveCount(3);
	// over them the file's own acts, which keep exactly its changes
	await expect(main.getByTestId('file-keep-all')).toHaveText('keep all 3');
	await expect(main.getByTestId('file-discard-all')).toHaveText('discard all 3');
	await main.getByTestId('file-keep-all').click();
	await expect.poll(() => sent).toEqual([{ changes: ['c-0f621ccf', 'c-00000001', 'c-00000002'] }]);
	await expect(page.getByTestId('column-message')).toHaveText('Kept 3 changes.');
	await expect(main).toHaveCount(0);
	await expect(count(page, 'review-kind-edits')).toHaveText('4');
	// the other file still holds both its edits
	const intro = page.locator('[data-testid="review-row"][data-file="notes/intro.md"]');
	await expect(intro.locator('.meta')).toHaveText('2 edits since your look');
});
