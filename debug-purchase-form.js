const { chromium } = require('playwright');

async function debugPurchaseForm() {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 1000 // Slow down actions to see what's happening
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  
  const page = await context.newPage();
  
  // Enable console logging
  page.on('console', msg => {
    console.log(`[${msg.type().toUpperCase()}]`, msg.text());
  });
  
  // Catch any page errors
  page.on('pageerror', error => {
    console.error('PAGE ERROR:', error.message);
    console.error('STACK:', error.stack);
  });
  
  // Catch network errors
  page.on('requestfailed', request => {
    console.error('REQUEST FAILED:', request.url(), request.failure().errorText);
  });
  
  try {
    console.log('1. Navigating to localhost:3000...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    
    // Wait a bit for initial load
    await page.waitForTimeout(3000);
    
    console.log('2. Taking screenshot of initial state...');
    await page.screenshot({ path: 'debug-initial.png' });
    
    // Try to navigate directly to purchase manager
    console.log('3. Navigating directly to purchase manager...');
    await page.goto('http://localhost:3000/dashboard/purchases', { waitUntil: 'networkidle' });
    
    await page.waitForTimeout(2000);
    
    console.log('4. Taking screenshot of purchase manager...');
    await page.screenshot({ path: 'debug-purchase-manager.png' });
    
    // Check if we can see the form button
    console.log('5. Looking for Single Request button...');
    const singleRequestBtn = await page.locator('button:has-text("Single Request")');
    
    if (await singleRequestBtn.count() > 0) {
      console.log('6. Found Single Request button, clicking...');
      
      // Set up promise to wait for any network activity
      const networkIdle = page.waitForLoadState('networkidle');
      
      await singleRequestBtn.click();
      
      // Wait for either network idle or timeout
      await Promise.race([
        networkIdle,
        page.waitForTimeout(5000)
      ]);
      
      console.log('7. Taking screenshot after clicking...');
      await page.screenshot({ path: 'debug-after-click.png' });
      
      // Check if form appeared
      const form = await page.locator('h3:has-text("Create Purchase Request")');
      if (await form.count() > 0) {
        console.log('✓ Form appeared successfully');
        
        // Try to fill and submit the form
        console.log('8. Testing form submission...');
        await page.fill('input[placeholder*="walmart"]', 'https://walmart.com/test');
        await page.fill('input[placeholder*="amazon"]', 'https://amazon.com/dp/B123456789');
        await page.fill('input[placeholder="Product name"]', 'Test Product');
        
        console.log('9. Clicking Create Request button...');
        const createBtn = page.locator('button:has-text("Create Request")');
        await createBtn.click();
        
        await page.waitForTimeout(2000);
        
        console.log('10. Taking screenshot after form submission...');
        await page.screenshot({ path: 'debug-after-submit.png' });
        
      } else {
        console.log('✗ Form did not appear');
        
        // Check what's actually visible
        const bodyContent = await page.locator('body').textContent();
        console.log('Body content preview:', bodyContent.substring(0, 500));
      }
    } else {
      console.log('✗ Single Request button not found');
      
      // Check what buttons are available
      const buttons = await page.locator('button').all();
      console.log('Available buttons:');
      for (const button of buttons) {
        const text = await button.textContent();
        console.log(`  - "${text}"`);
      }
    }
    
  } catch (error) {
    console.error('Test failed:', error);
    await page.screenshot({ path: 'debug-error.png' });
  } finally {
    // Keep browser open for manual inspection
    console.log('Browser will stay open for manual inspection. Close manually when done.');
    // await browser.close();
  }
}

// Run the test
debugPurchaseForm().catch(console.error);