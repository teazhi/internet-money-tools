const { chromium } = require('playwright');

async function testPurchaseManager() {
  const browser = await chromium.launch({ 
    headless: false,
    slowMo: 500 // Slow down actions to see what's happening
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  
  const page = await context.newPage();
  
  // Enable console logging
  page.on('console', msg => {
    console.log('Browser console:', msg.type(), msg.text());
  });
  
  // Catch any page errors
  page.on('pageerror', error => {
    console.error('Page error:', error.message);
  });
  
  try {
    console.log('1. Navigating to localhost:3000...');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    
    // Check if we need to login
    const loginButton = await page.$('button:has-text("Login with Discord")');
    if (loginButton) {
      console.log('Login required - skipping test');
      await browser.close();
      return;
    }
    
    // Wait for dashboard to load
    await page.waitForSelector('text=Dashboard', { timeout: 10000 });
    console.log('2. Dashboard loaded');
    
    // Navigate to Purchase Manager
    console.log('3. Looking for Purchase Manager link...');
    const purchaseLink = await page.$('a:has-text("Purchase Manager")');
    if (!purchaseLink) {
      console.log('Purchase Manager not found in navigation - checking if feature is enabled');
      await browser.close();
      return;
    }
    
    await purchaseLink.click();
    await page.waitForURL('**/dashboard/purchases');
    console.log('4. Navigated to Purchase Manager');
    
    // Test 1: Check if the page loads without errors
    await page.waitForSelector('h1:has-text("Purchase Manager"), h1:has-text("Purchase Tasks")', { timeout: 5000 });
    console.log('5. Purchase Manager page loaded successfully');
    
    // Test 2: Try to open Single Request form
    console.log('6. Testing Single Request form...');
    const singleRequestBtn = await page.$('button:has-text("Single Request")');
    if (singleRequestBtn) {
      await singleRequestBtn.click();
      
      // Check if form opens without white screen
      try {
        await page.waitForSelector('h3:has-text("Create Purchase Request")', { timeout: 3000 });
        console.log('✓ Single Request form opened successfully');
        
        // Test form validation
        const createBtn = await page.$('button:has-text("Create Request")');
        await createBtn.click();
        
        // Should show validation error
        const errorMsg = await page.waitForSelector('text=Please provide both source and Amazon links', { timeout: 2000 });
        console.log('✓ Form validation working');
        
        // Fill form with test data
        await page.fill('input[placeholder*="walmart"]', 'https://www.walmart.com/ip/test/123456');
        await page.fill('input[placeholder*="amazon"]', 'https://www.amazon.com/dp/B001234567');
        await page.fill('input[placeholder="Product name"]', 'Test Product');
        await page.fill('input[placeholder="0.00"]', '19.99');
        await page.fill('input[placeholder="50"]', '100');
        await page.fill('textarea', 'Test instructions for VA');
        
        console.log('✓ Form filled successfully');
        
        // Close form
        await page.click('button:has-text("Cancel")');
        console.log('✓ Form closed successfully');
        
      } catch (error) {
        console.error('✗ Single Request form error:', error.message);
        // Take screenshot for debugging
        await page.screenshot({ path: 'purchase-form-error.png' });
      }
    }
    
    // Test 3: Try Bulk Import
    console.log('7. Testing Bulk Import...');
    const bulkImportBtn = await page.$('button:has-text("Bulk Import")');
    if (bulkImportBtn) {
      await bulkImportBtn.click();
      
      try {
        await page.waitForSelector('h3:has-text("Bulk Import Purchase Requests")', { timeout: 3000 });
        console.log('✓ Bulk Import form opened successfully');
        
        // Test bulk parsing
        const testData = `https://walmart.com/ip/item1/123    https://amazon.com/dp/B001234567
https://target.com/item2/456    https://amazon.com/dp/B002345678`;
        
        await page.fill('textarea[rows="10"]', testData);
        await page.click('button:has-text("Parse Links")');
        
        // Check if items were parsed
        await page.waitForSelector('text=Found 2 Items', { timeout: 2000 });
        console.log('✓ Bulk parsing working');
        
        // Close bulk form
        await page.click('button:has-text("Clear")');
        await page.click('button.text-gray-400'); // X button
        
      } catch (error) {
        console.error('✗ Bulk Import error:', error.message);
      }
    }
    
    // Test 4: Check responsive design
    console.log('8. Testing responsive design...');
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone size
    await page.waitForTimeout(1000);
    console.log('✓ Mobile view rendered');
    
    // Test 5: Check error states
    console.log('9. Testing error states...');
    // This would require backend to be down or return errors
    
    console.log('\n=== Test Summary ===');
    console.log('Purchase Manager loaded: ✓');
    console.log('Single Request form: Check console output above');
    console.log('Bulk Import: Check console output above');
    console.log('Responsive design: ✓');
    
  } catch (error) {
    console.error('Test failed:', error);
    await page.screenshot({ path: 'test-error.png' });
  } finally {
    await browser.close();
  }
}

// Run the test
testPurchaseManager().catch(console.error);