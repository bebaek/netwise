import { expect, test, type Page, type TestInfo } from '@playwright/test';

const views = [
  { nav: 'Overview', heading: 'Financial trajectory' },
  { nav: 'Update', heading: 'Add household snapshot' },
  { nav: 'Plan', heading: 'Projection' },
  { nav: 'Assets', heading: 'Accounts' },
  { nav: 'Settings', heading: 'People & household access' },
] as const;

async function expectNoDocumentOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
}

async function captureView(page: Page, testInfo: TestInfo, view: string) {
  await page.screenshot({
    path: testInfo.outputPath(`${view.toLowerCase()}-${testInfo.project.name}.png`),
    fullPage: true,
  });
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
});

test('navigates across the financial planning workspace', async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));

  for (const view of views) {
    const navigationButton = page.getByRole('button', { name: view.nav, exact: true });
    await navigationButton.click();

    await expect(navigationButton).toHaveAttribute('aria-current', 'page');
    await expect(page.locator('.page-heading h2')).toHaveText(view.nav);
    await expect(page.getByRole('heading', { name: view.heading, exact: true })).toBeVisible();
    await expectNoDocumentOverflow(page);
    await captureView(page, testInfo, view.nav);
  }

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('overview update action opens the balance workflow', async ({ page }) => {
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await page.getByRole('button', { name: 'Update balances', exact: true }).click();

  await expect(page.getByRole('button', { name: 'Update', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Add household snapshot', exact: true })).toBeVisible();
});

test('advanced property sale automation is disclosed on demand', async ({ page }) => {
  await page.getByRole('button', { name: 'Plan', exact: true }).click();

  const disclosure = page.getByText('Advanced property sale automation', { exact: true });
  await expect(disclosure).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Configure automatic sale', exact: true })).not.toBeVisible();

  await disclosure.click();
  await expect(page.getByRole('heading', { name: 'Configure automatic sale', exact: true })).toBeVisible();
});
