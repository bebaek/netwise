import { expect, test } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

test('creates and revokes a household agent API token', async ({ page }) => {
  await openDemoWorkspace(page, '/settings');
  await expect(page.getByRole('heading', { name: 'AI agent access', exact: true })).toBeVisible();

  const tokenName = `Playwright agent ${Date.now()}`;
  await page.getByLabel('Token name').fill(tokenName);
  await page.getByLabel('Expires after').fill('14');
  await page.getByLabel('Record confirmed account balance snapshots').check();
  await page.getByLabel('Run deterministic scenario comparisons').check();
  await page.getByRole('button', { name: 'Create API token', exact: true }).click();

  const secretPanel = page.getByRole('alert').filter({ hasText: 'Save this token now' });
  await expect(secretPanel).toBeVisible();
  await expect(secretPanel).toBeFocused();
  const secret = await page.getByLabel('New API token').inputValue();
  expect(secret).toMatch(/^nwt_/);

  const householdId = await page.getByLabel('Selected household').inputValue();
  const agentResponse = await page.request.get(`/api/households/${householdId}`, {
    headers: {
      Authorization: `Bearer ${secret}`,
      'X-Netwise-Agent-Tool': 'get_financial_summary',
    },
  });
  expect(agentResponse.status()).toBe(200);
  await page.getByRole('button', { name: 'Refresh activity', exact: true }).click();
  const activityRow = page.locator('.audit-event-row').filter({
    hasText: tokenName,
  }).filter({
    hasText: 'get_financial_summary',
  });
  await expect(activityRow).toContainText('/households/{household_id}');
  await expect(activityRow).toContainText('GET 200');
  await expect(activityRow).toContainText(tokenName);
  await expect(activityRow).not.toContainText(secret);

  const tokenRow = page.locator('.api-token-row').filter({ hasText: tokenName });
  await expect(tokenRow).toContainText('active');
  await expect(tokenRow).toContainText('finance read · finance write · projections run');
  await expect(tokenRow).not.toContainText(secret);

  await page.getByRole('button', { name: 'I saved it', exact: true }).click();
  await expect(page.getByLabel('New API token')).toHaveCount(0);

  page.once('dialog', (dialog) => dialog.accept());
  await tokenRow.getByRole('button', { name: 'Revoke', exact: true }).click();
  await expect(tokenRow).toContainText('revoked');
  await expect(tokenRow.getByRole('button', { name: 'Revoke', exact: true })).toHaveCount(0);
});
