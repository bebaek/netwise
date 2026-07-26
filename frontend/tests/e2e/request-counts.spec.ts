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
    snapshot: () => [...requests],
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
  const planningLoadRequests = recorder.snapshot();

  const scenarioSelector = page.getByLabel('Current projection scenario');
  if (await scenarioSelector.locator('option').count() < 2) {
    await page.getByRole('button', { name: 'New scenario', exact: true }).click();
    const createScenarioForm = page.getByRole('heading', { name: 'New scenario', exact: true })
      .locator('..');
    await createScenarioForm.getByLabel('Name').fill('Request Count Comparison');
    await createScenarioForm.getByRole('button', { name: 'Save scenario' }).click();
    await expect(scenarioSelector.locator('option')).toHaveCount(2);
  }
  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  const comparisonForm = page.locator('.scenario-comparison-form');
  const comparisonStartYear = Number(await comparisonForm.getByLabel('Start year').inputValue());
  await comparisonForm.getByLabel('End year').fill(String(comparisonStartYear + 1));
  recorder.reset();
  await comparisonForm.getByRole('button', { name: 'Run comparison' }).click();
  await expect(page.locator('.comparison-summary-card')).toHaveCount(2);
  await page.waitForLoadState('networkidle');
  measurements.run_scenario_comparison = recorder.summarize();
  await page.getByRole('button', { name: 'Back to planning' }).click();

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

  const spendingForm = page.getByRole('heading', { name: 'Add spending item', exact: true })
    .locator('..')
    .locator('form');
  await spendingForm.locator('input[name="spending_item_name"]').fill('Request Count Spending');
  await spendingForm.locator('input[name="spending_item_annual_amount"]').fill('1200');
  recorder.reset();
  await spendingForm.getByRole('button', { name: 'Add spending item', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Request Count Spending', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_spending_item = recorder.summarize();

  const personForm = page.getByRole('heading', { name: 'Add household person', exact: true })
    .locator('..')
    .locator('form');
  await personForm.getByPlaceholder('Name').fill('Request Count Person');
  await personForm.locator('input[name="person_date_of_birth"]').fill('1980-01-01');
  recorder.reset();
  await personForm.getByRole('button', { name: 'Add person', exact: true }).click();
  await expect(
    page.locator('select[name="social_security_person_id"] option', {
      hasText: 'Request Count Person',
    }),
  ).toHaveCount(1);
  await page.waitForLoadState('networkidle');
  measurements.create_household_person = recorder.summarize();

  const transferForm = page.getByRole('heading', { name: 'Add recurring transfer', exact: true })
    .locator('..')
    .locator('form');
  const transferAccountIds = await transferForm
    .locator('select[name="transfer_from_account_id"] option:not([disabled])')
    .evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value));
  expect(transferAccountIds.length).toBeGreaterThanOrEqual(2);
  await transferForm.getByPlaceholder('401k contribution').fill('Request Count Transfer');
  await transferForm.locator('select[name="transfer_from_account_id"]')
    .selectOption(transferAccountIds[0]);
  await transferForm.locator('select[name="transfer_to_account_id"]')
    .selectOption(transferAccountIds[1]);
  await transferForm.locator('input[name="transfer_annual_amount"]').fill('1200');
  await transferForm.locator('input[name="transfer_start_date"]').fill('2026-01-01');
  recorder.reset();
  await transferForm.getByRole('button', { name: 'Add transfer', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Request Count Transfer', exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.create_projection_transfer = recorder.summarize();

  const projectionSettingsForm = page.locator('form').filter({
    has: page.getByRole('heading', { name: 'Projection assumptions', exact: true }),
  });
  await projectionSettingsForm.locator('input[name="settings_spending_inflation_rate"]')
    .fill('0.031');
  recorder.reset();
  await projectionSettingsForm.getByRole('button', { name: 'Save settings', exact: true }).click();
  await page.waitForLoadState('networkidle');
  measurements.save_projection_settings = recorder.summarize();

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

  recorder.reset();
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'People & household access', exact: true }))
    .toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.load_household_settings_route_data = recorder.summarize();

  const createUserForm = page.locator('form').filter({
    has: page.getByPlaceholder('New user name'),
  });
  await createUserForm.getByPlaceholder('New user name').fill('Request Count User');
  recorder.reset();
  await createUserForm.getByRole('button', { name: 'Add user', exact: true }).click();
  await expect(page.getByRole('option', { name: 'Request Count User', exact: true })).toBeAttached();
  await page.waitForLoadState('networkidle');
  measurements.create_household_user = recorder.summarize();

  const addMemberForm = page.locator('form').filter({
    has: page.getByRole('combobox', { name: 'Household member', exact: true }),
  });
  await addMemberForm.getByRole('combobox', { name: 'Household member', exact: true })
    .selectOption({ label: 'Request Count User' });
  await addMemberForm.getByRole('combobox', { name: 'Household role', exact: true })
    .selectOption('viewer');
  recorder.reset();
  await addMemberForm.getByRole('button', { name: 'Add member', exact: true }).click();
  await expect(page.getByText('Request Count User', { exact: true })).toBeVisible();
  await page.waitForLoadState('networkidle');
  measurements.add_household_member = recorder.summarize();

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
  expect(initialPaths.some((path) => /^GET \/api\/spending-items$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/annual-tax-records$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/income-sources$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/household-people$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/social-security-estimates$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/projection-transfers$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/projection-settings\/[^/]+$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/capabilities$/.test(path))).toBe(false);
  expect(initialPaths.some((path) => /^GET \/api\/users$/.test(path))).toBe(false);
  expect(measurements.initial_authenticated_workspace_load.total).toBeLessThanOrEqual(14);

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

  expect(measurements.load_planning_route_data.total).toBeLessThanOrEqual(22);
  expect(Object.keys(measurements.load_planning_route_data.by_method_and_path).sort()).toEqual([
    'GET /api/annual-tax-records',
    'GET /api/household-people',
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/events$/),
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/projection-scenarios$/),
    'GET /api/income-sources',
    expect.stringMatching(/^GET \/api\/projection-scenarios\/[^/]+\/account-assumptions$/),
    expect.stringMatching(/^GET \/api\/projection-scenarios\/[^/]+\/property-assumptions$/),
    expect.stringMatching(/^GET \/api\/projection-settings\/[^/]+$/),
    'GET /api/projection-transfers',
    'GET /api/real-estate/liquidation-strategies',
    'GET /api/real-estate/sales',
    'GET /api/social-security-estimates',
    'GET /api/spending-items',
  ]);
  const querySelectedPlanningPaths = new Set([
    '/api/income-sources',
    '/api/projection-transfers',
    '/api/real-estate/liquidation-strategies',
    '/api/real-estate/sales',
    '/api/social-security-estimates',
    '/api/spending-items',
  ]);
  const scenarioAwarePlanningRequests = planningLoadRequests.filter((request) => {
    const url = new URL(request.url());
    return querySelectedPlanningPaths.has(url.pathname)
      || /^\/api\/projection-settings\/[^/]+$/.test(url.pathname)
      || /^\/api\/households\/[^/]+\/events$/.test(url.pathname);
  });
  expect(scenarioAwarePlanningRequests.length).toBeGreaterThan(0);
  for (const request of scenarioAwarePlanningRequests) {
    expect(new URL(request.url()).searchParams.get('scenario_id')).toMatch(/^[0-9a-f-]{36}$/);
  }

  expect(measurements.run_scenario_comparison.total).toBe(1);
  expect(Object.keys(measurements.run_scenario_comparison.by_method_and_path)).toEqual([
    expect.stringMatching(/^POST \/api\/dashboard\/[^/]+\/projection-comparison$/),
  ]);

  expect(measurements.create_real_estate_sale.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_real_estate_sale.by_method_and_path).sort()).toEqual([
    'GET /api/real-estate/sales',
    'POST /api/real-estate/sales',
  ]);

  expect(measurements.create_spending_item.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_spending_item.by_method_and_path).sort()).toEqual([
    'GET /api/spending-items',
    'POST /api/spending-items',
  ]);

  expect(measurements.create_household_person.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_household_person.by_method_and_path).sort()).toEqual([
    'GET /api/household-people',
    'POST /api/household-people',
  ]);

  expect(measurements.create_projection_transfer.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_projection_transfer.by_method_and_path).sort()).toEqual([
    'GET /api/projection-transfers',
    'POST /api/projection-transfers',
  ]);

  expect(measurements.save_projection_settings.total).toBe(1);
  expect(Object.keys(measurements.save_projection_settings.by_method_and_path)).toEqual([
    expect.stringMatching(/^PUT \/api\/projection-settings\/[^/]+$/),
  ]);

  expect(measurements.create_account_event.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.create_account_event.by_method_and_path).sort()).toEqual([
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/events$/),
    expect.stringMatching(/^POST \/api\/accounts\/[^/]+\/events$/),
  ]);

  expect(measurements.load_household_settings_route_data.total).toBeLessThanOrEqual(8);
  expect(Object.keys(measurements.load_household_settings_route_data.by_method_and_path).sort()).toEqual([
    'GET /api/api-tokens',
    'GET /api/api-tokens/audit-events',
    'GET /api/capabilities',
    'GET /api/users',
  ]);

  expect(measurements.create_household_user.total).toBe(1);
  expect(Object.keys(measurements.create_household_user.by_method_and_path)).toEqual([
    'POST /api/users',
  ]);

  expect(measurements.add_household_member.total).toBeLessThanOrEqual(2);
  expect(Object.keys(measurements.add_household_member.by_method_and_path).sort()).toEqual([
    expect.stringMatching(/^GET \/api\/households\/[^/]+\/members$/),
    expect.stringMatching(/^POST \/api\/households\/[^/]+\/members$/),
  ]);
});
