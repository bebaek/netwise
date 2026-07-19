import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { openDemoWorkspace } from './helpers';

const views = [
  { path: '/overview', heading: 'Overview' },
  { path: '/update', heading: 'Update' },
  { path: '/plan', heading: 'Plan' },
  { path: '/assets', heading: 'Assets' },
  { path: '/settings', heading: 'Settings' },
] as const;

test('workspace pages meet automated WCAG A and AA checks', async ({ page }) => {
  for (const view of views) {
    await openDemoWorkspace(page, view.path);
    await expect(page.locator('.page-heading h2')).toHaveText(view.heading);

    const { violations } = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const summary = violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      description: violation.description,
      targets: violation.nodes.map((node) => node.target.join(' ')),
    }));

    expect(summary, `${view.path} accessibility violations:\n${JSON.stringify(summary, null, 2)}`).toEqual([]);
  }
});
