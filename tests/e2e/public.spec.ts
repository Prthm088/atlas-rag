import { expect, test } from '@playwright/test';

test('landing page presents the private grounded-RAG product', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /answers you can verify/i })).toBeVisible();
  await expect(page.getByText(/without mixing your data/i)).toBeVisible();
  await expect(page.getByRole('link', { name: /build my library/i })).toHaveAttribute('href', '/auth');
});

test('authentication entry is keyboard-accessible', async ({ page }) => {
  await page.goto('/auth');
  await expect(page.getByRole('heading', { name: /welcome back/i })).toBeVisible();
  await page.getByLabel(/email address/i).fill('reader@example.com');
  await page.getByLabel(/password/i).fill('long-enough-password');
  await page.getByRole('button', { name: /sign in/i }).focus();
  await expect(page.getByRole('button', { name: /sign in/i })).toBeFocused();
});
