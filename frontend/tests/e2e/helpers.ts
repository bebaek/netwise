import { expect, type Page } from '@playwright/test';

export async function openDemoWorkspace(page: Page, path: string): Promise<void> {
  await page.goto(path);

  const selectedUser = page.getByLabel('Selected user');
  await expect(selectedUser).toBeVisible();
  await expect(selectedUser.locator('option', { hasText: /^Demo User$/ })).toHaveCount(1);
  await selectedUser.selectOption({ label: 'Demo User' });

  const selectedHousehold = page.getByLabel('Selected household');
  await expect(selectedHousehold.locator('option', { hasText: /^Demo Household$/ })).toHaveCount(1);
  await selectedHousehold.selectOption({ label: 'Demo Household' });
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
}
