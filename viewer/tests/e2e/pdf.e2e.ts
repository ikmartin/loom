// A PDF drawn in a pane by the renderer every PDF goes through, shown on the project's own PDFs: a selection on its text layer, a load that failed tried again, and a scan's images decoded from what the bundle ships. Each test is named for the rule it holds.
import { expect, test } from '@playwright/test';
import { openHere } from '../workspace';
import { PDF, serve } from '../manifest';

/** The fixture's project PDF, and a second one a test serves beside it, by their paths. */
const FIG = 'drafting/figures/fig.pdf';
const OTHER = 'notes/other.pdf';

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
	await page.route(`**/_files/${FIG}`, (route) => route.fulfill({ body: pdf, contentType: 'application/pdf' }));
	await page.goto(`/file/${FIG}`);
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

test('a PDF that failed to load is tried again when it is next opened', async ({ page }) => {
	const pdf = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj
trailer<</Root 1 0 R>>
%%EOF`;
	let down = true;
	await serve(page, (m) => m.files.push({ path: OTHER, kind: 'pdf', bytes: PDF.length, denied: null }));
	await page.route(`**/_files/${FIG}`, (route) => (down ? route.abort() : route.fulfill({ body: pdf, contentType: 'application/pdf' })));
	await page.route(`**/_files/${OTHER}`, (route) => route.fulfill({ body: PDF, contentType: 'application/pdf' }));
	await page.goto(`/file/${FIG}`);
	await expect(page.getByTestId('pdf-problem')).toBeVisible();
	down = false;
	// no reload: another PDF in front of it, then back by its tab
	await openHere(page, `/file/${OTHER}`);
	await page.getByRole('tab', { name: 'fig.pdf' }).click();
	await expect(page.getByTestId('pdf-page-1').locator('canvas').first()).toBeVisible();
	await expect(page.getByTestId('pdf-problem')).toHaveCount(0);
});

test('a scanned PDF draws, its JPEG 2000 and JBIG2 images decoded from what the bundle ships', async ({ page }) => {
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
	await page.route(`**/_files/${FIG}`, (route) => route.fulfill({ body: pdf, contentType: 'application/pdf' }));
	await page.goto(`/file/${FIG}`);
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
