import { test, expect } from '@playwright/test';

test.describe('SQL Optimizer Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
  });

  test('should load the main page', async ({ page }) => {
    // Verify page loads
    await expect(page).toHaveTitle(/SQL Optimizer/);
    
    // Verify main components are visible
    await expect(page.locator('text=SQL Optimizer')).toBeVisible();
    await expect(page.locator('text=MyBatis SQL Analysis')).toBeVisible();
  });

  test('should display dashboard stats', async ({ page }) => {
    // Check stats cards
    await expect(page.locator('text=Total Runs')).toBeVisible();
    await expect(page.locator('text=SQL Analyzed')).toBeVisible();
    await expect(page.locator('text=Issues Found')).toBeVisible();
    await expect(page.locator('text=Optimized')).toBeVisible();
  });

  test('should display current run section', async ({ page }) => {
    await expect(page.locator('text=Current Run')).toBeVisible();
    await expect(page.locator('text=Phase:')).toBeVisible();
  });

  test('should display recent runs table', async ({ page }) => {
    await expect(page.locator('text=Recent Runs')).toBeVisible();
    // Check table headers
    await expect(page.locator('text=Run ID')).toBeVisible();
    await expect(page.locator('text=Progress')).toBeVisible();
  });

  test('should switch between tabs', async ({ page }) => {
    // Default tab is Dashboard
    await expect(page.locator('text=Current Run')).toBeVisible();
    
    // Click Runs tab - use more specific selector
    await page.getByRole('tab', { name: 'Runs' }).click();
    await expect(page.locator('text=SQL Units')).toBeVisible();
    
    // Click Analysis tab
    await page.getByRole('tab', { name: 'Analysis' }).click();
    await expect(page.locator('text=Optimization Proposals')).toBeVisible();
  });

  test('should show pause and resume buttons', async ({ page }) => {
    await expect(page.locator('button:has-text("Pause")')).toBeVisible();
    await expect(page.locator('button:has-text("Resume")')).toBeVisible();
  });

  test('should display CLI and Settings buttons', async ({ page }) => {
    await expect(page.locator('button:has-text("CLI")')).toBeVisible();
    await expect(page.locator('button:has-text("Settings")')).toBeVisible();
  });
});

test.describe('SQL Optimizer Dashboard - Responsive', () => {
  test('should work on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('http://localhost:5173');
    
    // Page should still load
    await expect(page).toHaveTitle(/SQL Optimizer/);
    await expect(page.locator('text=SQL Optimizer')).toBeVisible();
  });
});
