import { expect, type Page } from '@playwright/test';

export async function openDemoWorkspace(page: Page, path: string): Promise<void> {
  await page.goto(path);

  const signInHeading = page.getByRole('heading', { name: 'Sign in' });
  const signedInUser = page.getByText('Signed in as Demo User');
  await Promise.race([
    signInHeading.waitFor({ state: 'visible' }),
    signedInUser.waitFor({ state: 'visible' }),
  ]);
  if (await signInHeading.isVisible()) {
    await page.getByLabel('Email').fill('demo@netwise.local');
    await page.getByLabel('Password').fill('netwise-demo-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
  }

  await expect(signedInUser).toBeVisible();
  const selectedHousehold = page.getByLabel('Selected household');
  await expect(selectedHousehold.locator('option', { hasText: /^Demo Household$/ })).toHaveCount(1);
  await selectedHousehold.selectOption({ label: 'Demo Household' });
  await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible();
}
