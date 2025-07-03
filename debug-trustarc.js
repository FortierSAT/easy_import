// debug-trustarc-simple.js
const puppeteer     = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs            = require('fs');
const path          = require('path');

puppeteer.use(StealthPlugin());

;(async () => {
  console.log('🔍 Launching browser…');
  const browser = await puppeteer.launch({
    headless: false,
    defaultViewport: null,
    args: ['--start-maximized']
  });
  const page = await browser.newPage();

  // relay page console to Node
  page.on('console', msg => console.log('PAGE ▶', msg.text()));

  console.log('🌐 Navigating to sign-in page…');
  await page.goto('https://www.myescreen.com/', {
    waitUntil: 'networkidle2',
    timeout: 60000
  });

  console.log('🐛 Waiting for the in-page REJECT button…');
  await page.waitForSelector('#truste-consent-required', {
    visible: true,
    timeout: 30000
  });

  // dump the banner HTML for offline inspection
  const bannerHtml = await page.$eval('#truste-consent-content', el => el.outerHTML);
  fs.writeFileSync(path.join(__dirname, 'trustarc-banner.html'), bannerHtml);
  console.log('📄 Wrote banner HTML → trustarc-banner.html');

  // screenshot the banner container
  const bannerEl = await page.$('#truste-consent-track');
  if (bannerEl) {
    await bannerEl.screenshot({ path: path.join(__dirname, 'trustarc-banner.png') });
    console.log('📸 Screenshot saved → trustarc-banner.png');
  }

  console.log('🐛 Clicking REJECT…');
  const btn = await page.$('#truste-consent-required');
  await btn.click();

  console.log('✅ Click dispatched. Leaving the browser open for inspection.');
  // Comment out the next line if you want it to stay open:
  // await browser.close();
})();
