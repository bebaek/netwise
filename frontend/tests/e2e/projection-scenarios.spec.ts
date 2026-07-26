import { expect, test } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

test('manages independent projection scenarios and preserves URL selection', async ({ page, isMobile }, testInfo) => {
  const suffix = `${isMobile ? 'Mobile' : 'Desktop'} ${testInfo.retry}`;
  const scenarioName = `E2E Scenario ${suffix}`;
  const copyName = `${scenarioName} Copy`;
  const renamedName = `${scenarioName} Renamed`;

  await openDemoWorkspace(page, '/plan?scenario=not-a-scenario');
  const selector = page.getByLabel('Current projection scenario');
  await expect(selector).toBeVisible();
  await expect(selector).toHaveValue(/.+/);
  await expect(page).toHaveURL(/\/plan\?scenario=[0-9a-f-]+$/);
  await expect(selector.locator('option:checked')).toContainText('Baseline');

  await page.getByRole('button', { name: 'New scenario', exact: true }).click();
  const createForm = page.getByRole('heading', { name: 'New scenario', exact: true }).locator('..');
  await createForm.getByLabel('Name').fill(scenarioName);
  await createForm.getByLabel('Description').fill('Created by Playwright');
  await createForm.getByRole('button', { name: 'Save scenario' }).click();
  await expect(selector.locator('option:checked')).toHaveText(scenarioName);
  await expect(page).toHaveURL(/\/plan\?scenario=[0-9a-f-]+$/);

  await page.getByRole('button', { name: 'Duplicate', exact: true }).click();
  const duplicateForm = page.getByRole('heading', { name: `Duplicate ${scenarioName}` }).locator('..');
  await duplicateForm.getByLabel('Name').fill(copyName);
  await duplicateForm.getByRole('button', { name: 'Save scenario' }).click();
  await expect(selector.locator('option:checked')).toHaveText(copyName);
  const copiedScenarioUrl = page.url();
  await page.goBack();
  await expect(selector.locator('option:checked')).toHaveText(scenarioName);
  await page.goForward();
  await expect(page).toHaveURL(copiedScenarioUrl);
  await expect(selector.locator('option:checked')).toHaveText(copyName);
  await expect(page.getByText('This is an independent copy.')).toBeVisible();

  await page.getByRole('button', { name: 'Rename', exact: true }).click();
  const renameForm = page.getByRole('heading', { name: 'Edit scenario', exact: true }).locator('..');
  await renameForm.getByLabel('Name').fill(renamedName);
  await renameForm.getByRole('button', { name: 'Save scenario' }).click();
  await expect(selector.locator('option:checked')).toHaveText(renamedName);

  const selectedScenarioUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(selectedScenarioUrl);
  await expect(selector.locator('option:checked')).toHaveText(renamedName);
  const selectedScenarioId = await selector.inputValue();
  const projectionResponsePromise = page.waitForResponse((response) => (
    response.url().includes('/projection?') && response.url().includes(`scenario_id=${selectedScenarioId}`)
  ));
  await page.getByRole('button', { name: 'Run projection', exact: true }).click();
  expect((await projectionResponsePromise).ok()).toBe(true);
  await expect(page.getByText(`Scenario: ${renamedName}`)).toBeVisible();

  const brokerageAssumption = page.locator('.assumption-card').filter({ hasText: 'Brokerage' }).first();
  await brokerageAssumption.getByLabel('Expected annual yield').fill('0.012300');
  await Promise.all([
    page.waitForResponse((response) => response.request().method() === 'PUT'
      && response.url().includes('/account-assumptions/')),
    brokerageAssumption.getByRole('button', { name: 'Save account assumption' }).click(),
  ]);
  const baselineValue = await selector.locator('option', { hasText: 'Baseline' }).first()
    .getAttribute('value');
  await selector.selectOption(baselineValue ?? '');
  await expect(
    page.locator('.assumption-card').filter({ hasText: 'Brokerage' }).first()
      .getByLabel('Expected annual yield'),
  ).not.toHaveValue('0.012300');
  await selector.selectOption({ label: renamedName });
  await expect(
    page.locator('.assumption-card').filter({ hasText: 'Brokerage' }).first()
      .getByLabel('Expected annual yield'),
  ).toHaveValue('0.012300');

  page.once('dialog', async (dialog) => dialog.accept(renamedName));
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(selector.locator('option:checked')).toContainText('Baseline');
  await expect(selector.locator('option', { hasText: renamedName })).toHaveCount(0);
});
