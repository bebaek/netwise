import { expect, test } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

test('creates and revokes a household agent API token', async ({ page }) => {
  await openDemoWorkspace(page, '/settings');
  await expect(page.getByRole('heading', { name: 'AI agent access', exact: true })).toBeVisible();

  const tokenName = `Playwright agent ${Date.now()}`;
  await page.getByLabel('Token name').fill(tokenName);
  await page.getByLabel('Expires after').fill('14');
  await page.getByLabel('Run deterministic scenario comparisons').check();
  await page.getByRole('button', { name: 'Create API token', exact: true }).click();

  const secretPanel = page.getByRole('alert').filter({ hasText: 'Save this token now' });
  await expect(secretPanel).toBeVisible();
  await expect(secretPanel).toBeFocused();
  const secret = await page.getByLabel('New API token').inputValue();
  expect(secret).toMatch(/^nwt_/);

  const tokenRow = page.locator('.api-token-row').filter({ hasText: tokenName });
  await expect(tokenRow).toContainText('active');
  await expect(tokenRow).toContainText('finance read · projections run');
  await expect(tokenRow).not.toContainText(secret);

  await page.getByRole('button', { name: 'I saved it', exact: true }).click();
  await expect(page.getByLabel('New API token')).toHaveCount(0);

  page.once('dialog', (dialog) => dialog.accept());
  await tokenRow.getByRole('button', { name: 'Revoke', exact: true }).click();
  await expect(tokenRow).toContainText('revoked');
  await expect(tokenRow.getByRole('button', { name: 'Revoke', exact: true })).toHaveCount(0);
});
