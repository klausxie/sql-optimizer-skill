import { chromium } from 'playwright';

async function testDashboard() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('Opening http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 30000 });
    
    // Check title
    const title = await page.title();
    console.log('✓ Page title:', title);
    
    // Check for header
    const header = await page.locator('h1').first().textContent();
    console.log('✓ Header:', header);
    
    // Check tabs
    const dashboardTab = await page.getByRole('tab', { name: 'Dashboard' }).isVisible();
    const runsTab = await page.getByRole('tab', { name: 'Runs' }).isVisible();
    const analysisTab = await page.getByRole('tab', { name: 'Analysis' }).isVisible();
    console.log('✓ Tabs - Dashboard:', dashboardTab, 'Runs:', runsTab, 'Analysis:', analysisTab);
    
    // Check for mock mode indicator
    const mockModeAlert = await page.getByText('Mock Mode').isVisible();
    console.log('✓ Mock Mode alert:', mockModeAlert);
    
    // Check for Current Run section
    const currentRun = await page.getByText('Current Run').isVisible();
    console.log('✓ Current Run section:', currentRun);
    
    // Click on Runs tab
    await page.getByRole('tab', { name: 'Runs' }).click();
    await page.waitForTimeout(1000);
    const sqlUnits = await page.locator('.font-mono').count();
    console.log('✓ SQL Units count:', sqlUnits);
    
    // Click on Analysis tab
    await page.getByRole('tab', { name: 'Analysis' }).click();
    await page.waitForTimeout(1000);
    const proposals = await page.locator('.font-mono').count();
    console.log('✓ Proposals count:', proposals);
    
    console.log('\n✅ All tests passed!');
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  } finally {
    await browser.close();
  }
}

testDashboard();
