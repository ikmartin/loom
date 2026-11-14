// The end-to-end suite: the built app, with the conformance fixture staged into its own copy, served statically (tests/sites.ts).
import { defineConfig } from '@playwright/test';
import { patient, results, site, workers } from './tests/sites';

const { webServer, baseURL } = site('e2e', 'tests/fixture');

export default defineConfig({
	...patient,
	outputDir: results('e2e'),
	workers: workers(),
	webServer,
	testDir: 'tests/e2e',
	testMatch: '**/*.e2e.{ts,js}',
	use: { baseURL }
});
