import { test, expect } from '@playwright/test';

test('mode switch visible', async ({ page }) => {
  await page.goto('http://127.0.0.1:5174');
  await expect(page.getByText('Mode-U')).toBeVisible();
  await expect(page.getByText('Mode-A')).toBeVisible();
});
