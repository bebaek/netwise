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
  await page.goto('/overview');
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
    const navigationButton = page.getByRole('link', { name: view.nav, exact: true });
    await navigationButton.click();

    await expect(navigationButton).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveURL(new RegExp(`/${view.nav.toLowerCase()}$`));
    await expect(page.locator('.page-heading h2')).toHaveText(view.nav);
    await expect(page.getByRole('heading', { name: view.heading, exact: true })).toBeVisible();
    await expectNoDocumentOverflow(page);
    await captureView(page, testInfo, view.nav);
  }

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('overview update action opens the balance workflow', async ({ page }) => {
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByRole('button', { name: 'Update balances', exact: true }).click();

  await expect(page.getByRole('link', { name: 'Update', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Add household snapshot', exact: true })).toBeVisible();
});

test('redirects unknown routes to overview', async ({ page }) => {
  await page.goto('/not-a-workspace');
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole('link', { name: 'Overview', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('supports direct routes and reload persistence', async ({ page }) => {
  await page.goto('/assets');
  await expect(page.getByRole('link', { name: 'Assets', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Accounts', exact: true })).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/assets$/);
  await expect(page.getByRole('link', { name: 'Assets', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('keeps workspace navigation in browser history', async ({ page }) => {
  await page.getByRole('link', { name: 'Plan', exact: true }).click();
  await page.getByRole('link', { name: 'Assets', exact: true }).click();

  await page.goBack();
  await expect(page).toHaveURL(/\/plan$/);
  await expect(page.getByRole('link', { name: 'Plan', exact: true })).toHaveAttribute('aria-current', 'page');

  await page.goBack();
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole('link', { name: 'Overview', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('advanced property sale automation is disclosed on demand', async ({ page }) => {
  await page.getByRole('link', { name: 'Plan', exact: true }).click();

  const disclosure = page.getByText('Advanced property sale automation', { exact: true });
  await expect(disclosure).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Configure automatic sale', exact: true })).not.toBeVisible();

  await disclosure.click();
  await expect(page.getByRole('heading', { name: 'Configure automatic sale', exact: true })).toBeVisible();
});
