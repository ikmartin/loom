// A wider font than this Mac's, for the tests that a label fits on one line by construction and not by a font's widths: Verdana where the system has it, DejaVu Sans on Linux, where GitHub's runner draws the viewer, both spaced a tenth of an em wider still, so the margin is the test's own and not one font's. A whole run in a runner's faces is `scripts/verify --wide-font` (`wide-font.css`).

import type { Page } from '@playwright/test';

/** Draw the whole page in a wide font from now on, as a system without this Mac's fonts would. */
export async function wideFont(page: Page): Promise<void> {
	await page.addStyleTag({ content: '*, *::before, *::after { font-family: Verdana, "DejaVu Sans", "Bitstream Vera Sans", sans-serif !important; letter-spacing: 0.1em !important; }' });
}
