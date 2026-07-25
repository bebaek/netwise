import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

const views = [
  { nav: 'Overview', heading: 'Financial trajectory' },
  { nav: 'Update', heading: 'Add household snapshot' },
  { nav: 'Plan', heading: 'Projection' },
  { nav: 'Assets', heading: 'Accounts' },
  { nav: 'Settings', heading: 'People & household access' },
] as const;

async function expectNoDocumentOverflow(page: Page) {
  await expect.poll(async () => {
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    return dimensions.scrollWidth - dimensions.clientWidth;
  }, { message: 'document should not overflow horizontally' }).toBeLessThanOrEqual(1);
}

async function captureView(page: Page, testInfo: TestInfo, view: string) {
  await page.screenshot({
    path: testInfo.outputPath(`${view.toLowerCase()}-${testInfo.project.name}.png`),
    fullPage: true,
  });
}

test.beforeEach(async ({ page }) => {
  await openDemoWorkspace(page, '/overview');
});

test('navigates across the financial planning workspace', async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on('console', (message) => {
    const isMissingOptionalProjectionSettings =
      message.type() === 'error' && message.location().url.includes('/api/projection-settings/');
    if (message.type() === 'error' && !isMissingOptionalProjectionSettings) consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const householdName = (await page.getByLabel('Selected household').locator('option:checked').textContent())?.trim();
  expect(householdName).toBeTruthy();

  for (const view of views) {
    const navigationButton = page.getByRole('link', { name: view.nav, exact: true });
    if (view.nav !== 'Overview') await navigationButton.click();

    await expect(navigationButton).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveURL(new RegExp(`/${view.nav.toLowerCase()}$`));
    await expect(page.locator('.page-heading h2')).toHaveText(view.nav);
    await expect(page.locator('.page-heading h2')).toBeFocused();
    await expect(page).toHaveTitle(`${view.nav} · ${householdName} · Netwise`);
    await expect(page.getByRole('heading', { name: view.heading, exact: true })).toBeVisible();
    await expectNoDocumentOverflow(page);
    await captureView(page, testInfo, view.nav);
  }

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('shows progress while a projection is running', async ({ page }) => {
  let releaseProjection: () => void = () => undefined;
  const projectionBlocked = new Promise<void>((resolve) => {
    releaseProjection = resolve;
  });
  await page.route('**/api/dashboard/*/projection?*', async (route) => {
    await projectionBlocked;
    await route.continue();
  });

  await page.getByRole('link', { name: 'Plan', exact: true }).click();
  const runButton = page.getByRole('button', { name: 'Run projection', exact: true });
  await runButton.click();

  const runningButton = page.getByRole('button', { name: 'Running projection…', exact: true });
  await expect(runningButton).toBeDisabled();
  await expect(
    page.getByRole('status').filter({ hasText: 'Calculating your projection' }),
  ).toContainText('Calculating your projection');
  await expect(page.locator('form[aria-busy="true"]')).toHaveCount(1);

  releaseProjection();
  await expect(page.getByRole('button', { name: 'Run projection', exact: true })).toBeEnabled();
  await expect(page.getByRole('status')).toHaveCount(0);
});

test('uses the system color scheme until a theme is selected', async ({ page }) => {
  await page.getByLabel('Theme').selectOption('system');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('persists an explicit dark theme across reloads', async ({ page }) => {
  const themeSelect = page.getByLabel('Theme');
  await themeSelect.selectOption('dark');

  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('netwise.theme'))).toBe('dark');

  await page.reload();
  await expect(page.getByLabel('Theme')).toHaveValue('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('overview update action opens the balance workflow', async ({ page }) => {
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.getByRole('link', { name: 'Update balances', exact: true }).click();

  await expect(page.getByRole('link', { name: 'Update', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('heading', { name: 'Add household snapshot', exact: true })).toBeVisible();
});

test('mounts only the active workspace page', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Financial trajectory', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Accounts', exact: true })).toHaveCount(0);

  await page.getByRole('link', { name: 'Assets', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Accounts', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Financial trajectory', exact: true })).toHaveCount(0);
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

test('hides stale household data while a household loads', async ({ page }) => {
  let releaseNetWorth: () => void = () => undefined;
  const netWorthBlocked = new Promise<void>((resolve) => {
    releaseNetWorth = resolve;
  });
  await page.route('**/api/dashboard/*/net-worth', async (route) => {
    await netWorthBlocked;
    await route.continue();
  });

  await page.reload();
  await expect(page.getByRole('status').filter({ hasText: 'Loading Demo Household' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Financial trajectory', exact: true })).toHaveCount(0);

  releaseNetWorth();
  await expect(page.getByRole('heading', { name: 'Financial trajectory', exact: true })).toBeVisible();
});

test('preserves the authenticated session and selected household across reloads', async ({ page }) => {
  const selectedHousehold = page.getByLabel('Selected household');
  const householdId = await selectedHousehold.inputValue();
  const sessionCookie = (await page.context().cookies()).find((cookie) => cookie.name === 'netwise_session');

  expect(sessionCookie?.httpOnly).toBe(true);
  await expect.poll(() => page.evaluate(() => window.localStorage.getItem('netwise.selectedHouseholdId'))).toBe(householdId);

  await page.reload();
  await expect(page.getByText('Signed in as Demo User')).toBeVisible();
  await expect(selectedHousehold).toHaveValue(householdId);
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
