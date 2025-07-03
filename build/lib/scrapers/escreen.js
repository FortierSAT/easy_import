// src/scrapers/escreen.js
const puppeteer     = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path          = require('path');
const fs            = require('fs');
require('dotenv').config();

puppeteer.use(StealthPlugin());

const DOWNLOAD_DIR = path.resolve(__dirname, '..', 'downloads');
if (!fs.existsSync(DOWNLOAD_DIR)) {
  console.log(`📁 Creating download directory at ${DOWNLOAD_DIR}`);
  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });
} else {
  console.log(`📁 Download directory exists: ${DOWNLOAD_DIR}`);
}

const sleep = ms => new Promise(res => setTimeout(res, ms));

;(async () => {
  console.log('🛠️  Starting eScreen scraper…');
  console.log('👷  NODE cwd:', process.cwd());
  console.log('🔑 ESCREEN_USERNAME:', process.env.ESCREEN_USERNAME ? '✓' : '✗ (missing)');
  console.log('🔒 ESCREEN_PASSWORD:', process.env.ESCREEN_PASSWORD ? '✓' : '✗ (missing)');

  try {
    const inDocker = fs.existsSync("/.dockerenv") || process.env.RUNNING_IN_DOCKER === "true";

    console.log('🌐 Launching browser…');

    const launchOptions = inDocker
      ? {
          headless: true,
          executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
          args: [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
          ],
        }
      : {
          headless: true,               // show UI locally
          defaultViewport: null,         // inherit your desktop resolution
          args: ["--start-maximized"],   // pop up a full window
        };

    console.log(`🔍 Running in Docker? ${inDocker}`);
    console.log("⚙️  Launch options:", launchOptions);

    const browser = await puppeteer.launch(launchOptions);
    console.log("✅ Browser launched");

    console.log('🌐 Opening new page…');
    const page = await browser.newPage();
    console.log('✅ New page opened');

    console.log('⬇️  Configuring download behavior →', DOWNLOAD_DIR);
    const client = await page.target().createCDPSession();
    await client.send('Page.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: DOWNLOAD_DIR,
    });
    console.log('✅ Download behavior set');
    // ────────────────────────────────────────────────────────────────────

    // 1) Login
    console.log('🚪 Navigating to login page…');
    await page.goto('https://www.myescreen.com/', { waitUntil: 'networkidle2' });

    console.log('✍️  Entering username');
    await page.waitForSelector('input#signInName', { timeout: 20000 });
    await page.type('input#signInName', process.env.ESCREEN_USERNAME);
    await page.keyboard.press('Enter');

    console.log('⌛ Waiting for password field…');
    await page.waitForSelector('input[type="password"]', { timeout: 20000 });
    console.log('✍️  Entering password');
    await page.type('input[type="password"]', process.env.ESCREEN_PASSWORD);
    await page.keyboard.press('Enter');

    console.log('⌛ Waiting for post-login…');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 });
    console.log('✅ Logged in');

    // 2) Click “Reports”
    console.log('📰 Waiting for Reports link…');
    await page.waitForSelector('div.mainNavLink', { timeout: 30000 });
    console.log('🔘 Clicking Reports…');
    await page.evaluate(() => {
      document.querySelectorAll('div.mainNavLink')
        .forEach(el => {
          if (el.innerText.trim() === 'Reports') el.click();
        });
    });

    // 3) Click “Drug Test Summary Report”
    console.log('⌛ Waiting for summary-report link…');
    await page.waitForSelector('a[target="mainFrame"]', { timeout: 30000 });
    console.log('🔘 Clicking Summary Report…');
    await page.evaluate(() => {
      Array.from(document.querySelectorAll('a[target="mainFrame"]'))
        .find(a => a.innerText.includes('Drug Test Summary Report'))
        .click();
    });

    // 4) Click “View All”
    console.log('📥 Waiting for View All…');
    const frameHandle = await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 30000 });
    const frame       = await frameHandle.contentFrame();
    await frame.waitForSelector('input#btnViewAll', { timeout: 30000 });
    console.log('🔍 Clicking View All…');
    await frame.click('input#btnViewAll');
    await sleep(5000);

    // set date back 20 days
    const twentyDaysAgo = new Date(Date.now() - 20*24*60*60*1000);
    const mm = String(twentyDaysAgo.getMonth()+1).padStart(2,'0');
    const dd = String(twentyDaysAgo.getDate()).padStart(2,'0');
    const yyyy = twentyDaysAgo.getFullYear();
    const formatted = `${mm}/${dd}/${yyyy}`;
    console.log(`📅 Setting start date to ${formatted}`);
    await frame.waitForSelector('input#txtStart', { timeout: 15000 });
    await frame.click('input#txtStart', { clickCount: 3 });
    await frame.type('input#txtStart', formatted, { delay: 50 });
    await sleep(2000);

    // 5) Click “Run”
    console.log('⌛ Waiting for Run button…');
    await frame.waitForSelector('input#cmdRun', { timeout: 30000 });
    console.log('🔎 Clicking Run…');
    await frame.click('input#cmdRun');
    await sleep(10000);

    // 6) DOWNLOAD via Inbox icon
    console.log('⬇️  Waiting for the download icon…');
    await frame.waitForSelector('i.abt-icon.icon-Inbox', { timeout: 30000 });
    console.log('🔘 Clicking the download link via the Inbox icon…');
    await frame.evaluate(() => {
      const icon = document.querySelector('i.abt-icon.icon-Inbox');
      if (!icon) throw new Error('Download icon not found');
      icon.click();
    });

    // 7) Wait for file to land
    const outPath = path.join(DOWNLOAD_DIR, 'DrugTestSummaryReport_Total.xlsx');
    console.log('⌛ Waiting for XLSX to appear…');
    for (let i = 0; i < 20; i++) {
      if (fs.existsSync(outPath)) break;
      await sleep(1000);
    }
    if (!fs.existsSync(outPath)) {
      throw new Error(`Download failed: ${outPath} not found`);
    }

    console.log('✅ Download complete →', outPath);
    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error('❌ eScreen scraper error:', err);
    process.exit(1);
  }
})();
