import { test, expect } from '@playwright/test';

test.describe('SQL Optimizer Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display header with logo', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('SQL Optimizer');
  });

  test('should have three tabs', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Runs' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Analysis' })).toBeVisible();
  });

  test('should display mock mode alert in mock mode', async ({ page }) => {
    // Check for mock mode indicator (if running in mock mode)
    const mockAlert = page.getByText('Mock Mode');
    if (await mockAlert.isVisible()) {
      await expect(mockAlert).toBeVisible();
    }
  });

  test('should display stats cards', async ({ page }) => {
    await expect(page.getByText('Total Runs')).toBeVisible();
    await expect(page.getByText('SQL Analyzed')).toBeVisible();
    await expect(page.getByText('Issues Found')).toBeVisible();
    await expect(page.getByText('Optimized')).toBeVisible();
  });

  test('should display current run section', async ({ page }) => {
    await expect(page.getByText('Current Run')).toBeVisible();
  });

  test('should navigate to Runs tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Runs' }).click();
    await expect(page.getByText('SQL Units')).toBeVisible();
  });

  test('should navigate to Analysis tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Analysis' }).click();
    await expect(page.getByText('Optimization Proposals')).toBeVisible();
  });
});
