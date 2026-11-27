// Writing from the viewer, against a publisher that is actually serving the write API.
import { compileFolder, expect, readOnly, test, type Served } from '../served';
import { acceptRow, openRow } from '../review-rows';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/** Select an element's words as a reader would, and let go: the page offers to annotate them. */
/** Hold a type in hand before the page loads, as the format menu would leave it. */
async function holding(page: import('@playwright/test').Page, type: string): Promise<void> {
	await page.addInitScript((t) => localStorage.setItem('viewer.annotate.hand', JSON.stringify({ type: t, over: {} })), type);
}

async function select(at: import('@playwright/test').Locator): Promise<void> {
	await at.evaluate((node) => {
		const range = document.createRange();
		range.selectNodeContents(node);
		const sel = window.getSelection();
		sel?.removeAllRanges();
		sel?.addRange(range);
		node.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
	});
}

test('a comment written from a selection lands in the log as a person, anchored across the formula it crosses', async ({ page, served }) => {
	// The gate of plan 0.11 Part H: not "the button appeared" -- the file changed. Annotate, holding a revision, which asks something, so the popup takes the comment before anything is written.
	await holding(page, 'revision');
	await page.goto('/node/sy-0003');
	const statement = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]').first();
	await statement.locator('mjx-container').first().waitFor();
	await page.getByTestId('tool-annotate').click();
	await select(statement);
	// the popup's head names the place as the tab names it (by its number, from the compile the suite's pages carry), and its type
	const draft = page.getByTestId('ann-popup');
	await expect(draft).toContainText('Theorem 2.1');
	await expect(draft.getByTestId('popup-type')).toContainText('Revision');
	// the selection stays lit while the comment is written
	await expect.poll(() => page.evaluate(() => [...((CSS as unknown as { highlights: Map<string, { values(): Iterable<Range> }> }).highlights.get('note-pending')?.values() ?? [])].map((r) => r.toString()).join(' '))).toContain('widget');
	await draft.getByTestId('popup-comment-field').fill('Does finiteness do any work in the closedness half?');
	await draft.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);

	const mine = served.log().filter((e) => String(e.body ?? '').startsWith('Does finiteness'));
	expect(mine).toHaveLength(1);
	expect(mine[0].kind).toBe('human'); // written by a person, not by the run whose page it was
	expect(mine[0].target).toBe('sy-0003');
	expect(mine[0].type).toBe('revision');
	expect(mine[0]).not.toHaveProperty('severity');
	// anchored to the sentence, not to the node, and recorded as the source has it: the formula's own TeX
	const exact = (mine[0].anchor as { exact: string }).exact;
	expect(exact).toContain('finite widget');
	expect(exact).toMatch(/\$|\\\(/);
});

test("the publisher's refusal is shown rather than swallowed, and nothing is filed as anchored that is not", async ({ page, served }) => {
	// "quote not found" means something different from "no such key", and a reader told only "failed" has to guess.
	await holding(page, 'question');
	await page.goto('/node/sy-0003');
	const statement = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]').first();
	await statement.locator('mjx-container').first().waitFor();
	// words that are nowhere in the source: what a reader would get from a selection loom cannot map back
	await statement.evaluate((p) => p.insertAdjacentText('afterbegin', 'a phrase that appears nowhere in this statement at all '));
	await page.getByTestId('tool-annotate').click();
	await select(statement);
	await page.getByTestId('popup-comment-field').fill('This should be refused.');
	await page.getByTestId('popup-save').click();
	await expect(page.getByTestId('popup-said')).toContainText('quote');
	expect(served.log().filter((e) => e.body === 'This should be refused.')).toHaveLength(0);
});

test('a box drawn round an equation notes the equation itself', async ({ page, served }) => {
	// the quilt's own edit to sy-0001 is kept first: a block with a pending change is drawn merged, as TeX source where no TeX runs, as here
	const built = () => JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));
	const edits = () => (built().changes ?? []).filter((c: { key: string | null; kind: string }) => c.key === 'sy-0001' && c.kind === 'edit').map((c: { id: string }) => c.id);
	if (edits().length) {
		await served.api('change-keep', { changes: edits() });
		await expect.poll(edits).toEqual([]);
	}
	await page.goto('/node/sy-0001');
	const display = page.locator('[data-pane="0"] .fragment .math.display[data-label="eq:fix"]');
	await display.locator('mjx-container').waitFor();
	// Alt-drag draws a box, round what a selection cannot hold
	const b = (await display.boundingBox())!;
	await page.keyboard.down('Alt');
	await page.mouse.move(b.x + 4, b.y + 2);
	await page.mouse.down();
	await page.mouse.move(b.x + b.width - 4, b.y + b.height - 2, { steps: 6 });
	await page.mouse.up();
	await page.keyboard.up('Alt');
	const draft = page.getByTestId('ann-popup');
	await expect(draft).toContainText('equation');
	await draft.getByTestId('popup-comment-field').fill('Name the fixed locus here.');
	await draft.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);
	const mine = served.log().filter((e) => e.body === 'Name the fixed locus here.');
	expect(mine).toHaveLength(1);
	expect(mine[0].target).toBe('sy-0001#eq:fix');
	// and once the publisher has rebuilt, the display is marked, underlined rather than barred
	await expect(display).toHaveClass(/annotation-block/);
	expect(await display.evaluate((d) => getComputedStyle(d).borderLeftWidth)).toBe('0px');
});

test('a document is written on the same way, and what is written there is filed with the document: marked in it, and on no other page', async ({ page, served }) => {
	// decision 9 and 11 of the annotation study: the viewer implies `in` from where the reader is, so a claim made while reading main.tex is about sy-0008 as read there, and talk.tex, which also holds sy-0008, and the node's own page carry no mark for it
	await holding(page, 'question');
	await page.goto('/master/drafting/main');
	const words = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"] > p[data-src]').first();
	await words.scrollIntoViewIfNeeded();
	await noteOn(page, words, 'A gadget wants an example.');
	const mine = served.log().filter((e) => e.body === 'A gadget wants an example.');
	expect(mine).toHaveLength(1);
	expect(mine[0].target).toBe('sy-0008');
	expect(mine[0].in).toBe('drafting/main.tex');
	const id = mine[0].id as string;
	const markOf = () => page.locator(`[data-pane="0"] .fragment mark.annotation[data-annotation~="${id}"]`);
	await expect(markOf()).toHaveCount(1);
	await page.goto('/master/drafting/talk');
	await expect(page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"]')).toBeVisible();
	await expect(markOf()).toHaveCount(0);
	await page.goto('/node/sy-0008');
	await expect(page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"]')).toBeVisible();
	await expect(markOf()).toHaveCount(0);
});

readOnly('the actions stay at the end of the selection as its pane scrolls, and is hidden while those words are scrolled out of the pane', async ({ page }) => {
	await page.goto('/master/drafting/main');
	const body = page.locator('[data-pane="0"] > .body');
	const words = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"] > p[data-src]').first();
	await words.scrollIntoViewIfNeeded();
	await select(words);
	const chip = page.getByTestId('selection-actions');
	await expect(chip).toBeVisible();
	// how far the chip stands from the words' top, which a chip fixed to the window changes by the distance scrolled; the chip is placed to whole pixels, so within one
	const at = (await chip.boundingBox())!.y - (await words.boundingBox())!.y;
	const drift = async () => Math.abs((await chip.boundingBox())!.y - (await words.boundingBox())!.y - at);
	await body.evaluate((b) => b.scrollBy(0, -30));
	await expect.poll(drift).toBeLessThanOrEqual(1);
	// the words' top 20px below the pane's bottom: the chip is not left over whatever the pane shows instead
	await words.evaluate((p) => {
		const b = p.closest('[data-pane] > .body')!;
		b.scrollTop -= b.getBoundingClientRect().bottom - p.getBoundingClientRect().top + 20;
	});
	await expect(chip).toBeHidden();
	await words.scrollIntoViewIfNeeded();
	await expect(chip).toBeVisible();
	await expect.poll(drift).toBeLessThanOrEqual(1);
});

test('an annotation written on the node\'s own page is filed with no document', async ({ page, served }) => {
	await holding(page, 'question');
	await page.goto('/node/sy-0008');
	const words = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0008"] > p[data-src]').first();
	await noteOn(page, words, 'Everywhere a gadget is read.');
	const mine = served.written('Everywhere a gadget is read.');
	expect(mine.target).toBe('sy-0008');
	expect(mine.in ?? null).toBeNull();
});

test('a reply written in the popup leaves it open, showing the reply', async ({ page, served }) => {
	// the mark this test opens is one the fixture carries, so a fresh copy has it before anything is written
	await page.goto('/node/sy-0003');
	const mark = page.locator('.fragment mark.annotation').first();
	await mark.waitFor();
	const popup = page.getByTestId('ann-popup');
	await mark.click();
	await expect(popup).toHaveCount(1);

	const body = 'a reply written in the popup';
	// the viewer asks for the manifest once a second; a re-wire on any answer after a write must not close the popup
	const polls = (n: number) => {
		let seen = 0;
		return page.waitForResponse((r) => new URL(r.url()).pathname === '/build/manifest.json' && r.status() < 400 && ++seen >= n);
	};
	const afterWrite = polls(3);
	await popup.getByTestId('popup-reply').fill(body);
	await popup.getByTestId('popup-reply').press('Enter');
	// the write changes the manifest, and the popup it was written in stays open, now showing the reply
	await expect(popup.getByTestId('popup-reply-row').filter({ hasText: body })).toHaveCount(1);
	await afterWrite;
	await expect(popup).toHaveCount(1);
	expect(served.log().filter((e) => e.body === body)).toHaveLength(1);

	// the reply's own control posts one too, and is idle again once the field is empty
	const second = 'a reply posted with its control';
	const post = popup.getByTestId('popup-reply-send');
	await expect(post).toBeDisabled();
	await popup.getByTestId('popup-reply').fill(second);
	await post.click();
	await expect(popup.getByTestId('popup-reply-row').filter({ hasText: second })).toHaveCount(1);
	await expect(popup.getByTestId('popup-reply')).toHaveValue('');
	await expect(post).toBeDisabled();
	expect(served.log().filter((e) => e.body === second)).toHaveLength(1);

	// and the mark still toggles: one click closes it, the next opens it, and it stays open
	await mark.click();
	await expect(popup).toHaveCount(0);
	await mark.click();
	await expect(popup).toHaveCount(1);
	await polls(1);
	await expect(popup).toHaveCount(1);
});

test('what an agent says arrives in the transcript without a rebuild, and the viewer offers nothing to post with', async ({ page, served }) => {
	// plan 0.20.1: the conversation happens in the agent's own app; the agent writes the transcript with `loom session say`, read from `/_api/events` rather than waiting for the manifest
	const sid = served.openSessions().at(-1)!;
	await page.goto(`/node/sy-0003?beside=${encodeURIComponent('/session/' + sid)}`);
	const chat = page.locator('[data-pane="1"]').getByTestId('chat');
	await expect(chat).toBeVisible();
	await expect(chat.getByRole('textbox')).toHaveCount(0);
	served.loom(['session', 'say', 'Only for the *odd* case.', '--session', sid, '--as', 'Referee Agent'], { AI_AGENT: '1' });
	await expect(chat.getByTestId('transcript')).toContainText('Only for the odd case.');
	await expect(chat.getByTestId('transcript').locator('em', { hasText: 'odd' })).toHaveCount(1);
});

test("an agent's report arrives in the transcript folded after its summary", async ({ page, served }) => {
	// plan 0.21.2: a mode's report is one message, its blocks under `## [name]`; the publisher marks them and the viewer folds the rest
	const sid = served.openSessions().at(-1)!;
	await page.goto(`/node/sy-0003?beside=${encodeURIComponent('/session/' + sid)}`);
	const chat = page.locator('[data-pane="1"]').getByTestId('chat');
	await expect(chat).toBeVisible();
	const finding = 'The count needs the set finite, and the statement does not say so. '.repeat(10);
	const report = `Mode: referee, on sy-0003.\n\n## [summary]\nOne objection.\n\n## [gaps-and-ambiguities]\n- ${finding}\n\n## [decision]\nMinor revision.`;
	served.loom(['session', 'say', report, '--session', sid, '--as', 'Referee Agent'], { AI_AGENT: '1' });
	const said = chat.getByRole('listitem').filter({ hasText: 'One objection.' });
	await expect(said).toHaveCount(1);
	await expect(said.getByTestId('message-fold')).toHaveText('▸ 2 more: gaps-and-ambiguities, decision');
	await expect(said).not.toContainText('Minor revision.');
});

function sessionIndex(served: Served): Record<string, unknown>[] {
	return readFileSync(join(served.root, '.loom/agents/sessions/index.jsonl'), 'utf8')
		.split('\n')
		.filter((l) => l.trim())
		.map((l) => JSON.parse(l));
}

/** Mark an element's words with Annotate, holding a type that asks something (`holding`), and say `body` in the popup that opens for it. */
async function noteOn(page: import('@playwright/test').Page, at: import('@playwright/test').Locator, body: string): Promise<void> {
	await at.waitFor();
	// selected once its formulas are set, as a reader sees them
	await page.waitForFunction(() => !document.querySelector('[data-pane="0"] .fragment .math:not(:has(mjx-container))'));
	const tool = page.getByTestId('pane-0').getByTestId('tool-annotate');
	if ((await tool.getAttribute('aria-pressed')) !== 'true') await tool.click();
	await select(at);
	await page.getByTestId('popup-comment-field').fill(body);
	await page.getByTestId('popup-save').click();
	await expect(page.getByTestId('draft-host')).toHaveCount(0);
}

test('an annotation is written with no session selected, and names none', async ({ page, served }) => {
	await holding(page, 'question');
	await page.goto('/node/sy-0003');
	await noteOn(page, page.locator('[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]').first(), 'Which sitting is this in?');
	const mine = served.written('Which sitting is this in?');
	expect(mine.target).toBe('sy-0003');
	expect(mine).not.toHaveProperty('session');
});

test('an annotation is edited, then deleted, which takes its lines out of the log, and Undo puts the same lines back', async ({ page, served }) => {
	const id = served.log().find((e) => e.event === 'created' && e.target === 'sy-0003' && e.type === 'revision')!.id as string;
	await page.goto('/node/sy-0003');
	const mark = page.locator(`[data-pane="0"] .fragment mark.annotation[data-annotation~="${id}"]`).first();
	await mark.click();
	const box = page.locator(`[data-testid="ann-popup"][data-annotation-id="${id}"]`);
	await expect(box).toHaveCount(1);

	// the comment is edited in place
	const restated = 'Finiteness is used in the parity count; state it as a hypothesis.';
	await box.getByTestId('popup-comment').click();
	await box.getByTestId('popup-comment-field').fill(restated);
	await box.getByTestId('popup-save').click();
	await expect(box.getByTestId('popup-comment')).toContainText(restated);
	const edited = served.log().filter((e) => e.event === 'edited' && e.id === id);
	expect(edited).toHaveLength(1);
	expect(edited[0].body).toBe(restated);
	expect(edited[0]).not.toHaveProperty('session');
	expect(edited[0].kind).toBe('human');

	// the log as lines, in any order: a restore appends what it puts back
	const lines = () => served.log().map((e) => JSON.stringify(e)).sort();
	const before = lines();
	await box.getByTestId('popup-delete').click();
	// nothing of it is left in the log, and the popup and its mark go with it
	await expect.poll(() => served.log().filter((e) => e.id === id).length).toBe(0);
	const gone = before.filter((l) => !lines().includes(l));
	expect(gone.length).toBeGreaterThan(1); // its creation and its edit at least
	await expect(page.locator(`[data-pane="0"] .fragment mark.annotation[data-annotation~="${id}"]`)).toHaveCount(0);
	const held = page.getByTestId('deleted');
	await expect(held).toHaveCount(1);

	await held.getByTestId('deleted-undo').click();
	await expect(held).toHaveCount(0);
	// the same lines, and the mark drawn again
	await expect.poll(lines).toEqual(before);
	await expect(page.locator(`[data-pane="0"] .fragment mark.annotation[data-annotation~="${id}"]`).first()).toBeVisible();
});

/** The served quilt's manifest as loom last published it. */
function published(served: Served): { annotations: Record<string, { id: string; type: string | null; look: Record<string, unknown> }>; annotation_types: { id: string; look: Record<string, unknown> }[] } {
	return JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8'));
}

test('a type chosen in the popup drops the look set on the annotation, so it is drawn in the type’s and follows later edits to it', async ({ page, served }) => {
	const id = served.log().find((e) => e.event === 'created' && e.target === 'sy-0003' && e.type === 'revision')!.id as string;
	await page.goto('/node/sy-0003');
	await page.locator(`[data-pane="0"] .fragment mark.annotation[data-annotation~="${id}"]`).first().click();
	const p = page.locator(`[data-testid="ann-popup"][data-annotation-id="${id}"]`);
	await p.getByTestId('popup-type').click();
	// a look of its own first: green over the revision's red
	await p.getByTestId('popup-format').getByTestId('swatch-green').click();
	await expect.poll(() => published(served).annotations[id].look.color).toBe('green');
	await expect(p.getByTestId('modified-line')).toContainText('Changed from Revision');
	await p.getByTestId('popup-format').locator('[data-testid="type-row"][data-type="question"]').click();
	await expect.poll(() => published(served).annotations[id].type).toBe('question');
	const question = () => published(served).annotation_types.find((t) => t.id === 'question')!.look;
	expect(published(served).annotations[id].look).toEqual(question());
	await expect(p.getByTestId('modified-line')).toHaveCount(0);
	// the type's look changed in Settings, and the annotation follows it
	await page.keyboard.press('Escape');
	await page.getByTestId('settings-toggle').click();
	await page.getByTestId('settings-section-annotations').click();
	await page.getByTestId('type-tab').nth(2).click();
	await page.getByTestId('settings-annotations').getByTestId('swatch-purple').click();
	await page.getByTestId('types-save').click();
	await expect.poll(() => published(served).annotations[id].look.color).toBe('purple');
});

test('Undo takes a new annotation out of the log, and Redo puts the same one back', async ({ page, served }) => {
	await page.goto('/node/sy-0003');
	const statement = page.locator('[data-pane="0"] .fragment .env[data-id="sy-0003"] > p[data-src]').first();
	await statement.waitFor();
	await page.waitForFunction(() => !document.querySelector('[data-pane="0"] .fragment .math:not(:has(mjx-container))'));
	await page.getByTestId('tool-annotate').click();
	const before = served.log().filter((e) => e.event === 'created').length;
	await select(statement);
	await expect.poll(() => served.log().filter((e) => e.event === 'created').length).toBe(before + 1);
	const made = served.log().filter((e) => e.event === 'created').at(-1)!;
	const id = made.id as string;
	await expect.poll(() => !!published(served).annotations[id]).toBe(true);
	await page.getByTestId('annotate-undo').click();
	await expect.poll(() => served.log().some((e) => e.id === id)).toBe(false);
	await expect.poll(() => !!published(served).annotations[id]).toBe(false);
	await page.getByTestId('annotate-redo').click();
	await expect.poll(() => served.log().filter((e) => e.id === id).map((e) => e.event)).toEqual(['created']);
	await expect.poll(() => !!published(served).annotations[id]).toBe(true);
});

test('a comment is edited as the Markdown it was written in, its math and its link kept, and Undo puts that Markdown back', async ({ page, served }) => {
	const original = 'Is $|X| \\geq 2$ here? See [the definition](quilt:sy-0001).';
	const changed = original.replace('here?', 'there?');
	const id = (await served.api('annotate', { target: 'sy-0003', quote: 'finite widget', message: original })).split(/\s+/)[0];
	const edits = () => served.log().filter((e) => e.event === 'edited' && e.id === id);
	await page.goto('/node/sy-0003');
	await page.getByTestId('open-comments').click();
	await page.locator(`[data-testid="comment-card"][data-annotation="${id}"]`).click();
	const p = page.locator(`[data-testid="ann-popup"][data-annotation-id="${id}"]`);
	// the comment is shown rendered, its formula set and its link named, and opens for editing as it was written
	await expect(p.getByTestId('popup-comment').locator('a[href="quilt:sy-0001"]')).toHaveText('the definition');
	await p.getByTestId('popup-comment').click({ position: { x: 4, y: 4 } });
	const field = p.getByTestId('popup-comment-field');
	await expect(field).toHaveValue(original);
	await field.fill(changed);
	await p.getByTestId('popup-save').click();
	await expect.poll(() => edits().map((e) => e.body)).toEqual([changed]);
	await expect(p.getByTestId('popup-comment')).toContainText('there?');
	// Undo restates it as it was written, Markdown and all
	await page.getByTestId('annotate-undo').click();
	await expect.poll(() => edits().map((e) => e.body)).toEqual([changed, original]);
	await expect(p.getByTestId('popup-comment')).not.toContainText('there?');
	await p.getByTestId('popup-comment').click({ position: { x: 4, y: 4 } });
	await expect(field).toHaveValue(original);
});

test('Review\'s Sessions closes, reopens and deletes a session, a tombstone that takes no annotation with it', async ({ page, served }) => {
	const id = served.openSessions().at(-1)!;
	const written = served.log();
	await page.goto('/review/record/sessions');
	const row = page.getByTestId(`session-row-${id}`);
	await expect(row).toContainText('open');
	await page.getByTestId(`sessions-close-${id}`).click();
	await expect(row).toContainText('closed');
	expect(served.openSessions()).not.toContain(id);
	await page.getByTestId(`sessions-reopen-${id}`).click();
	await expect(row).toContainText('open');
	await expect.poll(() => served.openSessions()).toContain(id);
	await page.getByTestId(`sessions-delete-${id}`).click();
	const modal = page.getByTestId('delete-session');
	await expect(modal.getByTestId('delete-says')).toContainText('Annotations belong to no session, so none goes with it');
	await modal.getByTestId('delete-confirm').click();
	await expect.poll(() => sessionIndex(served).filter((e) => e.event === 'deleted' && e.id === id).length).toBe(1);
	await expect(row).toHaveCount(0);
	// a tombstone, not a purge, and the annotation log is untouched
	expect(served.log()).toEqual(written);
});

/** The keys the copy's acceptance ledger has a row for, in order. */
function acceptedKeys(served: Served): string[] {
	return [...readFileSync(join(served.root, '.loom/records/state.toml'), 'utf8').matchAll(/^key = "([^"]+)"$/gm)].map((m) => m[1]);
}

/** Accepting needs the document to compile; a PDF newer than every source is loom's sign that it already does, so no TeX run happens in this suite (the compile itself is loom's to test). */
function compiled(served: Served): void {
	mkdirSync(compileFolder(served.root, 'drafting/main.tex'), { recursive: true });
	writeFileSync(join(compileFolder(served.root, 'drafting/main.tex'), 'main.pdf'), '%PDF-1.4\n');
}

test('a block resting on a stale one not accepted with it is refused, said in the viewer\'s words and never loom\'s, and nothing is accepted', async ({ page, served }) => {
	// sy-0002 rests on sy-0001, whose acceptance is stale: accepting sy-0002 alone would record it against what was never re-read
	const ledger = acceptedKeys(served);
	await page.goto('/review');
	const orbits = acceptRow(page, 'sy-0002');
	await openRow(orbits);
	await orbits.getByTestId('review-accept').click();
	await expect(page.getByTestId('column-message')).toHaveText('Orbits was not accepted.');
	// loom's own sentence is written for the command line, and is never said
	await expect(page.getByTestId('column-message')).not.toContainText('Accept Widget first');
	expect(acceptedKeys(served)).toEqual(ledger);
});

test('Accept records an acceptance at once, and the block leaves the queue', async ({ page, served }) => {
	compiled(served);
	const ledger = acceptedKeys(served);
	await page.goto('/review');
	const posted = page.waitForRequest('**/_api/review-accept');
	await openRow(acceptRow(page, 'sy-0001'));
	await acceptRow(page, 'sy-0001').getByTestId('review-accept').click();
	expect((await posted).postDataJSON()).toEqual({ reviewer: 'The synthetic quilt', keys: ['sy-0001'] });
	await expect.poll(() => acceptedKeys(served)).toEqual([...ledger, 'sy-0001']);
	const row = readFileSync(join(served.root, '.loom/records/state.toml'), 'utf8').split('[[accept]]').at(-1)!;
	expect(row).toContain('key = "sy-0001"');
	expect(row).toContain('master = "drafting/main.tex"');
	expect(row).not.toContain('2026-09-14T09:00:00Z'); // a new row, dated now, not the fixture's
	await expect(page.getByTestId('column-message')).toContainText('Accepted Widget.');
	// and once the publisher has rebuilt, the key has left the rows waiting for the accepted fold
	await expect(acceptRow(page, 'sy-0001')).toHaveCount(0);
	await page.locator('[data-fold="accept:accepted"]').getByRole('button').click();
	await expect(acceptRow(page, 'sy-0001').getByTestId('review-row-why')).toContainText('accepted by The synthetic quilt');
});

/** Press Take it until `taken` holds, each press given a few seconds and pressed again after them, which is harmless since the choice is the same one. The copy was just written, so the page may still show the publish before it: loom refuses a choice against a comparison that has moved on, and the page draws the new one, where the press is good. */
async function pressUntil(page: import('@playwright/test').Page, taken: () => Promise<void>): Promise<void> {
	await expect(async () => {
		await page.getByTestId('take-it').click();
		await taken();
	}).toPass();
}

test('an agent copy is taken back in one pass: Take it, then one Apply writes it and leaves its mathematics for review', async ({ page, served }) => {
	const document = 'drafting/adoption-test.tex';
	const text = '\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\nIntroduction.\n\\begin{lemma}\\label{sy-0900}\nOriginal statement.\n\\end{lemma}\n\\end{document}\n';
	writeFileSync(join(served.root, document), text);
	served.loom(['draft', document, '--ai', 'adoption-proposal']);
	const copy = join(served.root, '.loom/agents/copies/adoption-proposal.tex');
	writeFileSync(copy, readFileSync(copy, 'utf8').replace('Original statement.', 'Proposed statement.'));
	await page.goto('/review/proposed');
	await page.locator('[data-testid="proposed-card"][data-id=".loom/agents/copies/adoption-proposal.tex"]').getByTestId('proposed-open').click();
	const bar = page.getByTestId('contribution-bar');
	await expect(bar).toContainText('From adoption-proposal into adoption-test');
	await expect(page.getByTestId('change-shown')).toContainText('Proposed statement');
	// taking it is saved at once and writes nothing yet
	await pressUntil(page, () => expect(page.getByTestId('apply')).toHaveText('Apply 1 change', { timeout: 3000 }));
	await page.getByTestId('change-at').click();
	await expect(page.locator('[data-testid="change-row"][data-key="sy-0900"]')).toHaveAttribute('data-state', 'taken');
	await page.keyboard.press('Escape');
	expect(readFileSync(join(served.root, document), 'utf8')).toBe(text);
	// one press writes it, keeping the document as it was first
	await page.getByTestId('apply').click();
	await expect.poll(() => readFileSync(join(served.root, document), 'utf8')).toContain('Proposed statement.');
	await expect(page.locator('main')).toContainText('Took 1 change into adoption-test: 0 accepted, 1 wait to be accepted. adoption-test as it was is kept as a version.');
	await page.goto('/review');
	// what it took in is one row, opening to the block
	const adoption = page.locator('[data-testid="review-row"][data-adoption=".loom/agents/copies/adoption-proposal.tex"]');
	await expect(adoption.getByTestId('review-row-why')).toHaveText('taken in 1 result from the copy');
	await openRow(adoption);
	await expect(acceptRow(page, 'sy-0900')).toBeVisible();
});

test("accept all on an adoption's row in Review accepts exactly the blocks it took in that can be accepted, and none it cannot", async ({ page, served }) => {
	const document = 'drafting/adopt-all.tex';
	const lemma = (key: string, words: string) => `\\begin{lemma}\\label{${key}}\n${words}\n\\end{lemma}\n\\begin{proof}\nClear.\n\\end{proof}\n`;
	writeFileSync(join(served.root, document), `\\documentclass{article}\n\\usepackage{amsthm}\n\\usepackage{loom}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n${lemma('sy-0920', 'First.')}${lemma('sy-0921', 'Second.')}${lemma('sy-0922', 'Third.')}\\end{document}\n`);
	served.loom(['draft', document, '--ai', 'adopt-all']);
	const copy = '.loom/agents/copies/adopt-all.tex';
	const drafted = readFileSync(join(served.root, copy), 'utf8');
	// the second is marked incomplete, so it cannot be accepted
	writeFileSync(join(served.root, copy), drafted.replace('First.', 'First, improved.').replace('Second.', 'Second, improved. \\incomplete{Say why it holds.}').replace('Third.', 'Third, improved.'));
	const { token } = JSON.parse(served.loom(['adopt', copy, '--json'])) as { token: string };
	served.loom(['adopt', copy, '--incorporate', token]);
	mkdirSync(compileFolder(served.root, document), { recursive: true });
	writeFileSync(join(compileFolder(served.root, document), 'adopt-all.pdf'), '%PDF-1.4\n');
	type Waiting = { key: string; cause: string; contribution?: string; refusal: string };
	const taken = (): Waiting[] => (JSON.parse(readFileSync(join(served.root, '.loom/cache/site/manifest.json'), 'utf8')).unresolved ?? []).filter((u: Waiting) => u.cause === 'adopted' && u.contribution === copy);
	await expect.poll(() => taken().length, { timeout: 60_000 }).toBeGreaterThan(2);
	const can = taken().filter((u) => !u.refusal).map((u) => u.key);
	const cannot = taken().filter((u) => u.refusal).map((u) => u.key);
	expect(can.length).toBeGreaterThan(1);
	expect(cannot).toContain('sy-0921');
	const ledger = acceptedKeys(served);
	const posted: unknown[] = [];
	page.on('request', (r) => {
		if (r.url().endsWith('/_api/review-accept')) posted.push(r.postDataJSON());
	});
	await page.goto('/review');
	const row = page.locator(`[data-testid="review-row"][data-adoption="${copy}"]`);
	await expect(row).toBeVisible({ timeout: 60_000 });
	await openRow(row);
	await expect(row.locator('[data-testid="review-row"][data-key]')).toHaveCount(can.length + cannot.length);
	await expect(row.getByTestId('adoption-accept-all')).toHaveText(`accept all ${can.length}`);
	await row.getByTestId('adoption-accept-all').click();
	await expect.poll(() => acceptedKeys(served), { timeout: 60_000 }).toEqual([...ledger, ...can]);
	expect(posted).toEqual([{ reviewer: 'The synthetic quilt', keys: can }]);
	// what it could not accept still waits, in the adoption's row, saying why
	await expect.poll(() => taken().map((u) => u.key), { timeout: 60_000 }).toEqual(cannot);
	await expect(row.locator('[data-testid="review-row"][data-key="sy-0921"] [data-testid="review-row-why"]')).toHaveText("can't be accepted yet: marked incomplete");
});

test('a change marked as checked is accepted as it is taken in; one left stays out', async ({ page, served }) => {
	const document = 'drafting/accept-test.tex';
	const text = '\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n\\begin{lemma}\\label{sy-0910}\nFirst.\n\\end{lemma}\n\\begin{lemma}\\label{sy-0911}\nSecond.\n\\end{lemma}\n\\end{document}\n';
	writeFileSync(join(served.root, document), text);
	served.loom(['draft', document, '--ai', 'accept-proposal']);
	const copy = join(served.root, '.loom/agents/copies/accept-proposal.tex');
	writeFileSync(copy, readFileSync(copy, 'utf8').replace('First.', 'First, improved.').replace('Second.', 'Second, improved.'));
	await page.goto('/review/proposed?copy=' + encodeURIComponent('.loom/agents/copies/accept-proposal.tex'));
	await page.getByTestId('change-at').click();
	await page.locator('[data-testid="change-row"][data-key="sy-0910"]').click();
	// taking it steps on to the next change to decide: leave that one
	await pressUntil(page, () => expect(page.getByTestId('change-at')).toHaveText(/^2 of /, { timeout: 3000 }));
	await page.getByTestId('leave-it').click();
	await page.getByTestId('change-at').click();
	await page.locator('[data-testid="change-row"][data-key="sy-0910"]').click();
	await page.getByTestId('accept-checked').check();
	// Apply asks loom to accept the checked block; whether TeX can record it here is the machine's, so the request is what is held to
	const [finish] = await Promise.all([page.waitForRequest((r) => r.url().endsWith('/_api/adopt-finish')), page.getByTestId('apply').click()]);
	expect(finish.postDataJSON().accept).toEqual(['sy-0910']);
	await expect(page.locator('main')).toContainText('Took 1 change into accept-test');
	await expect(page.locator('main')).not.toContainText('since what they rest on was not accepted');
	const now = readFileSync(join(served.root, document), 'utf8');
	expect(now).toContain('First, improved.');
	expect(now).toContain('Second.\n');
});
