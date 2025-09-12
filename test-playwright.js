const { chromium } = require('playwright');

(async () => {
  // Launch browser
  const browser = await chromium.launch({
    headless: false // Set to true for headless mode
  });

  // Create a new page
  const page = await browser.newPage();

  // Navigate to a website
  await page.goto('https://example.com');

  // Take a screenshot
  await page.screenshot({ path: 'example-screenshot.png' });

  // Get page title
  const title = await page.title();
  console.log('Page title:', title);

  // Close browser
  await browser.close();
})();