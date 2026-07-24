import { expect, test, type Page, type Request, type TestInfo } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

type RequestSummary = {
  total: number;
  by_method_and_path: Record<string, number>;
};

function recordApiRequests(page: Page) {
  const requests: Request[] = [];
  const listener = (request: Request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) requests.push(request);
  };
  page.on('request', listener);

  return {
    reset: () => requests.splice(0),
    summarize: (): RequestSummary => {
      const byMethodAndPath = requests.reduce<Record<string, number>>((counts, request) => {
        const key = `${request.method()} ${new URL(request.url()).pathname}`;
        counts[key] = (counts[key] ?? 0) + 1;
        return counts;
      }, {});
      return {
        total: requests.length,
        by_method_and_path: Object.fromEntries(Object.entries(byMethodAndPath).sort()),
      };
    },
    dispose: () => page.off('request', listener),
  };
}

async function attachMeasurements(
  testInfo: TestInfo,
  measurements: Record<string, RequestSummary>,
) {
  await testInfo.attach('frontend-api-request-counts', {
    body: Buffer.from(`${JSON.stringify(measurements, null, 2)}\n`),
    contentType: 'application/json',
  });
  console.log(`\nFrontend API request counts:\n${JSON.stringify(measurements, null, 2)}`);
}

test('records representative frontend API request counts', async ({ page, isMobile }, testInfo) => {
  test.skip(isMobile, 'Request baseline is recorded once with the desktop project.');

  await openDemoWorkspace(page, '/overview');
  await page.waitForLoadState('networkidle');
  const recorder = recordApiRequests(page);
  const measurements: Record<string, RequestSummary> = {};

  recorder.reset();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Financial trajectory', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.initial_authenticated_workspace_load = recorder.summarize();

  await page.getByRole('link', { name: 'Update', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Snapshot history', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  const snapshotFilter = page.getByLabel('Filter snapshot history by account');
  recorder.reset();
  await snapshotFilter.selectOption({ index: 1 });
  await page.waitForLoadState('networkidle');
  measurements.change_snapshot_account_filter = recorder.summarize();

  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  recorder.reset();
  await page.getByLabel('Show interpolated estimates').check();
  await page.waitForLoadState('networkidle');
  measurements.toggle_interpolated_history = recorder.summarize();

  await page.getByRole('link', { name: 'Update', exact: true }).click();
  const balanceInput = page.locator('input[name^="balance:"]').first();
  await balanceInput.fill('12345.67');
  recorder.reset();
  await page.getByRole('button', { name: 'Save household snapshot', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Saved');
  await page.waitForLoadState('networkidle');
  measurements.save_household_snapshot = recorder.summarize();

  recorder.reset();
  await page.getByRole('link', { name: 'Assets', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Property details', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.load_asset_real_estate_data = recorder.summarize();

  const addPropertyForm = page.getByRole('heading', { name: 'Add property', exact: true })
    .locator('..')
    .locator('form');
  await addPropertyForm.locator('input[name="property_name"]').fill('Request Count Property');
  recorder.reset();
  await addPropertyForm.getByRole('button', { name: 'Add property', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Request Count Property', exact: true }).first()).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_property = recorder.summarize();

  const addAccountForm = page.getByRole('heading', { name: 'Add account', exact: true })
    .locator('..')
    .locator('form');
  await addAccountForm.locator('input[name="name"]').fill('Request Count Cash');
  await addAccountForm.locator('input[name="category"]').fill('cash');
  await addAccountForm.locator('input[name="liquidity_class"]').fill('liquid');
  recorder.reset();
  await addAccountForm.getByRole('button', { name: 'Add account', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Request Count Cash', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_account = recorder.summarize();

  recorder.reset();
  await page.getByRole('link', { name: 'Plan', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Projection events', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.load_planning_route_data = recorder.summarize();

  const saleForm = page.getByRole('heading', { name: 'Plan property sale', exact: true })
    .locator('..')
    .locator('form');
  await saleForm.getByLabel('Property to sell').selectOption({ index: 1 });
  await saleForm.locator('input[name="sale_date"]').fill('2035-01-01');
  await saleForm.getByPlaceholder('Gross sale price').fill('500000');
  recorder.reset();
  await saleForm.getByRole('button', { name: 'Plan sale', exact: true }).click();
  await expect(page.getByRole('cell', { name: '2035-01-01', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_real_estate_sale = recorder.summarize();

  await page.getByRole('button', { name: 'Add event', exact: true }).click();
  const eventForm = page.locator('form').filter({
    has: page.getByRole('heading', { name: 'Add projection event', exact: true }),
  });
  await eventForm.getByPlaceholder('2500.00').fill('321.00');
  await eventForm.getByPlaceholder('Optional note').fill('Request count event');
  recorder.reset();
  await eventForm.getByRole('button', { name: 'Save event', exact: true }).click();
  await expect(page.getByText('Request count event', { exact: true }).first()).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_account_event = recorder.summarize();

  recorder.dispose();
  await attachMeasurements(testInfo, measurements);

  const initialPaths = Object.keys(
    measurements.initial_authenticated_workspace_load.by_method_and_path,
  );
  expect(
    initialPaths.some((path) => /^GET \/api\/households\/[^/]+\/events$/.test(path)),
  ).toBe(false);
  expect(
    initialPaths.some((path) => /^GET \/api\/accounts\/[^/]+\/events$/.test(path)),
  ).toBe(false);
  expect(
    initialPaths.some((path) => /^GET \/api\/households\/[^/]+\/snapshots$/.test(path)),
  ).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/real-estate\/properties$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/real-estate\/analytics$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/mortgages$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/real-estate\/sales$/.test(path))).toBe(false);
  expect(
    initialPaths.some((path) => /^GET \/api\/real-estate\/liquidation-strategies$/.test(path)),
  ).toBe(false);

  expect(measurements.change_snapshot_account_filter.total).toBe(1);
  expect(Object.keys(measurements.change_snapshot_account_filter.by_method_and_path)).toEqual([
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/snapshots$/),
  ]);

  expect(measurements.toggle_interpolated_history.total).toBe(1);
  expect(Object.keys(measurements.toggle_interpolated_history.by_method_and_path)).toEqual([
    expect.stringMatching(/^GET \/api\/dashboard\/[^/]+\/historical-trend$/),
  ]);

  expect(measurements.save_household_snapshot.total).toBeLessThanOrEqual(5);
  const unrelatedSnapshotSavePath = Object.keys(
    measurements.save_household_snapshot.by_method_and_path,
  ).find((path) => (
    /(annual-tax|household-people|income-sources|mortgages|projection-|real-estate|social-security|spending-items|members)/.test(path)
  ));
  expect(unrelatedSnapshotSavePath).toBeUndefined();

  expect(measurements.create_account.total).toBeLessThanOrEqual(5);
  const unrelatedAccountCreatePath = Object.keys(
    measurements.create_account.by_method_and_path,
  ).find((path) => (
    /(annual-tax|household-people|income-sources|mortgages|projection-|real-estate|social-security|spending-items|members|snapshots)/.test(path)
  ));
  expect(unrelatedAccountCreatePath).toBeUndefined();

  expect(measurements.load_asset_real_estate_data.total).toBeLessThanOrEqual(6);
  expect(Object.keys(measurements.load_asset_real_estate_data.by_method_and_path).sort()).toEqual([
    'GET /api/mortgages',
    'GET /api/real-estate/analytics',
    'GET /api/real-estate/properties',
  ]);

  expect(measurements.create_property.total).toBeLessThanOrEqual(8);
  const unrelatedPropertyCreatePath = Object.keys(
    measurements.create_property.by_method_and_path,
  ).find((path) => (
    /(annual-tax|household-people|income-sources|mortgages|projection-|liquidation-strategies|real-estate\/sales|social-security|spending-items|members|snapshots)/.test(path)
  ));
  expect(unrelatedPropertyCreatePath).toBeUndefined();

  expect(measurements.load_planning_route_data.total).toBeLessThanOrEqual(6);
  expect(Object.keys(measurements.load_planning_route_data.by_method_and_path).sort()).toEqual([
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/events$/),
    'GET /api/real-estate/liquidation-strategies',
    'GET /api/real-estate/sales',
  ]);

  expect(measurements.create_real_estate_sale.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_real_estate_sale.by_method_and_path).sort()).toEqual([
    'GET /api/real-estate/sales',
    'POST /api/real-estate/sales',
  ]);

  expect(measurements.create_account_event.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_account_event.by_method_and_path).sort()).toEqual([
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/events$/),
    expect.stringMatching(/^POST \/api\/accounts\/[^/]+\/events$/),
  ]);
});
