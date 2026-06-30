import { test, expect } from '@playwright/test';

const routes = [
  '/',
  '/accounts',
  '/audit',
  '/backup',
  '/clients',
  '/depreciation',
  '/export',
  '/flags',
  '/gl',
  '/health',
  '/imports',
  '/investments',
  '/invoicing',
  '/liabilities',
  '/mileage',
  '/periods',
  '/recurring',
  '/register',
  '/reconciliation',
  '/reports',
  '/rules',
  '/sales-tax',
  '/tax',
  '/tax-exports',
  '/upload',
  '/vendors',
  '/year-end',
];

for (const route of routes) {
  test(`route ${route} renders without white-screen`, async ({ page }) => {
    const jsErrors: string[] = [];
    page.on('pageerror', (err) => {
      jsErrors.push(err.message);
    });

    await page.goto(route);

    // Wait for any app text to appear (boot gate, nav, or module shell)
    await page.waitForFunction(() => document.body.innerText.trim().length > 20, null, { timeout: 15000 });

    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);

    // Fail only on actual JS runtime errors, not API auth/404 responses from
    // protected endpoints in an unauthenticated smoke run.
    expect(jsErrors).toHaveLength(0);
  });
}
