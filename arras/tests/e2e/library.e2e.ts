// A cited work in a pane: its paper opened, drawn and selected, and the links into it from what the corpus says about it. Each test is named for the rule it holds.
import { expect, test, type Page } from '@playwright/test';
import { openHere, pane } from '../workspace';
import { manifest, serve, servePapers } from '../manifest';

/** A node lists no annotations; its first mark opens the popup of the revision whose body the tests below put a link in. */
async function openFirstMark(page: Page): Promise<void> {
	await page.locator('[data-pane] .fragment mark.annotation').first().click();
	await expect(page.getByTestId('ann-popup')).toBeVisible();
}

function linkInComment(m: typeof manifest, href: string): void {
	m.annotations['a-2026-09-16-ecnav2'].body_html = `<p>The hypothesis is used in <a href="${href}">Kresch, Theorem 2.1</a>.</p>`;
}

test.describe('a work', () => {
	test('a filed paper opens on the paper, whether or not anything is anchored to it yet', async ({ page }) => {
		// a paper filed and not yet extracted from is the state every newly filed paper is in; it opens on the paper
		await serve(page, (m) => {
			m.references.Kre99.artifacts.pdf = true;
			m.references.Kre99.results = {};
			m.references.Kre99.digest = null;
		});
		await servePapers(page);
		await page.goto('/library/Kre99');
		await expect(page.getByTestId('pdf-doc')).toBeVisible();
	});

	test('a selection draws nothing at the line breaks of the page text', async ({ page }) => {
		// three lines of real text, so the text layer ends each with a <br>; selected, those drew a column of bars down the page's left edge
		const stream = 'BT /F1 24 Tf 72 700 Td (First line) Tj 0 -30 Td (Second line) Tj 0 -30 Td (Third line) Tj ET';
		const pdf = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length ${stream.length}>>stream
${stream}
endstream endobj
trailer<</Root 1 0 R>>
%%EOF`;
		await serve(page, (m) => (m.references.Kre99.artifacts.pdf = true));
		await page.route('**/paper.pdf', (route) => route.fulfill({ body: pdf, contentType: 'application/pdf' }));
		await page.goto('/library/Kre99');
		const layer = page.locator('.page .text').first();
		await expect(layer.locator('br').first()).toBeAttached();
		await layer.evaluate((el) => {
			const range = document.createRange();
			range.selectNodeContents(el);
			getSelection()!.removeAllRanges();
			getSelection()!.addRange(range);
		});
		// the strip down the layer's left edge holds no text, only where the breaks stand: count its selection-blue pixels
		const box = (await layer.boundingBox())!;
		const shot = await page.screenshot({ clip: { x: box.x, y: box.y, width: 12, height: box.height } });
		const blue = await page.evaluate(async (data) => {
			const img = new Image();
			img.src = `data:image/png;base64,${data}`;
			await img.decode();
			const c = document.createElement('canvas');
			[c.width, c.height] = [img.width, img.height];
			const ctx = c.getContext('2d')!;
			ctx.drawImage(img, 0, 0);
			const px = ctx.getImageData(0, 0, c.width, c.height).data;
			let n = 0;
			for (let i = 0; i < px.length; i += 4) if (px[i + 2] - px[i] > 30) n++;
			return n;
		}, shot.toString('base64'));
		expect(blue).toBe(0);
	});
});

test('a paper that failed to load is tried again when it is next opened', async ({ page }) => {
	const pdf = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj
trailer<</Root 1 0 R>>
%%EOF`;
	let down = true;
	await serve(page, (m) => (m.references.Kre99.artifacts.pdf = true));
	await page.route('**/paper.pdf', (route) => (down ? route.abort() : route.fulfill({ body: pdf, contentType: 'application/pdf' })));
	await page.goto('/library/Kre99');
	await expect(page.getByTestId('pdf-problem')).toBeVisible();
	down = false;
	// no reload: another work in front of it, then back by its tab
	await openHere(page, '/library/Man12');
	await page.getByRole('tab', { name: 'Kre99' }).click();
	await expect(page.getByTestId('pdf-page-1').locator('canvas').first()).toBeVisible();
	await expect(page.getByTestId('pdf-problem')).toHaveCount(0);
});

test('a scanned paper draws, its JPEG 2000 and JBIG2 images decoded from what the bundle ships', async ({ page }) => {
	// one page, a black square in each half: the left in JPEG 2000, the right in JBIG2
	const jpx = Buffer.from('AAAADGpQICANCocKAAAAFGZ0eXBqcDIgAAAAAGpwMiAAAAAtanAyaAAAABZpaGRyAAAAEAAAABAAAQcHAAAAAAAPY29scgEAAAAAABEAAACUanAyY/9P/1EAKQAAAAAAEAAAABAAAAAAAAAAAAAAABAAAAAQAAAAAAAAAAAAAQcBAf9SAAwAAAABAAQEBAAB/1wAEEBASEhQSEhQSEhQSEhQ/2QAJQABQ3JlYXRlZCBieSBPcGVuSlBFRyB2ZXJzaW9uIDIuNS40/5AACgAAAAAAFgAB/5PfgAgHgICAgP/Z', 'base64');
	const jbig2 = Buffer.from('AAAAADAAAQAAABMAAAAQAAAAEAAAAAAAAAAAAAAAAAAAASYAAQAAABwAAAAQAAAAEAAAAAAAAAAAAAEmoL/////gAgAg', 'base64');
	const image = (n: number, dict: string, data: Buffer) => [Buffer.from(`${n} 0 obj<</Type/XObject/Subtype/Image/Width 16/Height 16/ColorSpace/DeviceGray${dict}/Length ${data.length}>>stream\n`), data, Buffer.from('\nendstream endobj\n')];
	const contents = 'q 100 0 0 100 0 0 cm /L Do Q q 100 0 0 100 100 0 cm /R Do Q';
	const pdf = Buffer.concat([
		Buffer.from(`%PDF-1.5
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Resources<</XObject<</L 5 0 R/R 6 0 R>>>>/Contents 4 0 R>>endobj
4 0 obj<</Length ${contents.length}>>stream
${contents}
endstream endobj
`),
		...image(5, '/BitsPerComponent 8/Filter/JPXDecode', jpx),
		...image(6, '/BitsPerComponent 1/Filter/JBIG2Decode', jbig2),
		Buffer.from('trailer<</Root 1 0 R>>\n%%EOF')
	]);
	await serve(page, (m) => (m.references.Kre99.artifacts.pdf = true));
	await page.route('**/paper.pdf', (route) => route.fulfill({ body: pdf, contentType: 'application/pdf' }));
	await page.goto('/library/Kre99');
	const canvas = page.getByTestId('pdf-page-1').locator('canvas').first();
	await expect
		.poll(() =>
			canvas.evaluate((c: HTMLCanvasElement) => {
				const red = (x: number) => c.getContext('2d')!.getImageData(Math.round(c.width * x), Math.round(c.height / 2), 1, 1).data[0];
				return [red(0.25), red(0.75)];
			})
		)
		.toEqual([0, 0]);
});

test.describe('links into cited works', () => {
	test('a link in a comment opens the work beside at its page, and the node stays', async ({ page }) => {
		// a copy on this machine opens as the work itself, not in a modal; and a link is a connection between two texts, so it opens in the other pane and the node it was followed from is still there
		await serve(page, (m) => {
			m.references.Kre99.artifacts.pdf = true;
			linkInComment(m, 'cited:arxiv:math/9810166v2?page=4');
		});
		await servePapers(page);
		await page.goto('/node/sy-0003');
		await openFirstMark(page);
		await page.getByRole('link', { name: 'Kresch, Theorem 2.1' }).click();
		await expect.poll(() => new URL(page.url()).searchParams.get('beside')).toBe('/library/Kre99?page=4');
		await expect(pane(page, 1).getByTestId('pdf-doc')).toBeVisible();
		await expect(page.getByTestId('pdf-viewer')).toHaveCount(0); // no modal for a copy that is here
		await expect(pane(page, 0).locator('.fragment').first()).toBeVisible(); // and the node it came from stands
		expect(new URL(page.url()).pathname).toBe('/node/sy-0003');
	});

	test('a paper not fetched on this machine says so and links to its source at the page', async ({ page }) => {
		await serve(page, (m) => linkInComment(m, 'cited:arxiv:math/9810166v2#page=4'));
		await page.goto('/node/sy-0003');
		await openFirstMark(page);
		await page.getByRole('link', { name: 'Kresch, Theorem 2.1' }).click();
		await expect(page.getByTestId('pdf-absent')).toContainText('has not been fetched on this machine');
		await expect(page.getByTestId('pdf-external')).toHaveAttribute('href', 'https://arxiv.org/pdf/math/9810166v2#page=4');
		await expect(page.getByTestId('pdf-frame')).toHaveCount(0);
	});

	test('a link to another version of the work warns before opening the copy on file, and the viewer closes on an outside press', async ({ page }) => {
		await serve(page, (m) => {
			m.references.Kre99.artifacts.pdf = true;
			m.references.Kre99.works = ['arXiv:math/9810166v2', 'doi:10.1007/s002220050351'];
			linkInComment(m, 'cited:doi:10.1007/s002220050351#page=4');
		});
		await servePapers(page);
		await page.goto('/node/sy-0003');
		await openFirstMark(page);
		await page.getByRole('link', { name: 'Kresch, Theorem 2.1' }).click();
		await expect(page.getByTestId('pdf-absent')).toContainText('a different version');
		await expect(page.getByTestId('pdf-frame')).toHaveCount(0);
		await page.getByTestId('pdf-open-anyway').click();
		await expect(page.getByTestId('pdf-frame')).toBeVisible();
		await page.mouse.click(5, 5);
		await expect(page.getByTestId('pdf-viewer')).toHaveCount(0);
	});

	test('a quote anchor travels in the URL, in the same keys the app uses', async ({ page }) => {
		// the place itself is lit by the publisher mapping the quote onto the page, which the reading suite covers under `loom serve`; here there is no publisher, so what is checked is that the link carried it whole
		await serve(page, (m) => {
			m.references.Kre99.artifacts.pdf = true;
			linkInComment(m, 'cited:arxiv:math/9810166v2#quote=Artin%20stacks');
		});
		await servePapers(page);
		await page.goto('/node/sy-0003');
		await openFirstMark(page);
		await page.getByRole('link', { name: 'Kresch, Theorem 2.1' }).click();
		// a quote with no page names no page: the publisher looks for it across the work
		await expect.poll(() => new URL(page.url()).searchParams.get('beside')).toBe('/library/Kre99?quote=Artin+stacks');
		await expect(pane(page, 1).getByTestId('pdf-doc')).toBeVisible();
	});
});
