import { expect, type Page } from '@playwright/test';

export async function openDemoWorkspace(page: Page, path: string): Promise<void> {
  const hasSession = (await page.context().cookies()).some(
    (cookie) => cookie.name === 'netwise_session',
  );
  await page.goto(path);

  if (!hasSession) {
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    await page.getByLabel('Email').fill('demo@netwise.local');
    await page.getByLabel('Password').fill('netwise-demo-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
  }

  await expect(page.getByText('Signed in as Demo User')).toBeVisible();
  const selectedHousehold = page.getByLabel('Selected household');
  await expect(selectedHousehold.locator('option', { hasText: /^Demo Household$/ })).toHaveCount(1);
  await selectedHousehold.selectOption({ label: 'Demo Household' });
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
}
