const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

const DOWNLOAD_DIR = path.resolve(__dirname, '..', 'downloads');
if (!fs.existsSync(DOWNLOAD_DIR)) fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

const wait = ms => new Promise(r => setTimeout(r, ms));
const USERNAME = process.env.ESCREEN_USERNAME || 'connor.beasley';
const PASSWORD = process.env.ESCREEN_PASSWORD || 'Punky3!Brewster';

function logStep(step) {
  console.log('\n====', step, '====');
}

// Always logs and writes debug files
async function saveDebug(pageOrFrame, name, prefix = 'debug') {
  try {
    const timestamp = (new Date()).toISOString().replace(/[:\.]/g, '-');
    const htmlPath = path.join(DOWNLOAD_DIR, `${prefix}_${name}_${timestamp}.html`);
    const pngPath = path.join(DOWNLOAD_DIR, `${prefix}_${name}_${timestamp}.png`);

    let html;
    try {
      html = await pageOrFrame.content();
      fs.writeFileSync(htmlPath, html, 'utf8');
      console.error(`[${name}] Saved HTML to: ${htmlPath}`);
    } catch (err) {
      console.error(`[${name}] Could not save HTML:`, err);
    }

    try {
      await pageOrFrame.screenshot({ path: pngPath, fullPage: true });
      console.error(`[${name}] Saved screenshot to: ${pngPath}`);
    } catch (err) {
      console.error(`[${name}] Could not save screenshot:`, err);
    }
  } catch (err) {
    console.error(`[${name}] saveDebug() failed:`, err);
  }
}

(async () => {
  let browser, page;
  try {
    logStep('Launching browser');
    browser = await puppeteer.launch({
      headless: true,
      defaultViewport: null,
      args: ['--start-maximized', '--disable-web-security', '--no-sandbox']
    });

    page = await browser.newPage();

    // Set up downloads
    const client = await page.target().createCDPSession();
    await client.send('Page.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: DOWNLOAD_DIR,
    });

    // 1. Login page
    logStep('Navigating to login page');
    await page.goto('https://www.myescreen.com/', { waitUntil: 'networkidle2' });

    // 2. Username
    logStep('Filling username');
    await page.waitForSelector('input#signInName', { timeout: 30000 });
    await page.type('input#signInName', USERNAME);
    await page.keyboard.press('Enter');
    logStep('Username submitted');

    // 3. Password
    logStep('Filling password');
    await page.waitForSelector('input[type="password"]', { timeout: 30000 });
    await page.type('input[type="password"]', PASSWORD);
    await page.keyboard.press('Enter');
    logStep('Password submitted');

    await wait(7000);

    // 4. Click "Reports"
    logStep('Clicking Reports');
    await page.evaluate(() => {
      const el = Array.from(document.querySelectorAll('*')).find(
        e => e.innerText && e.innerText.trim() === 'Reports'
      );
      if (el) el.click();
    });
    await wait(1000);

    // 5. Click "Drug Test Summary Report"
    logStep('Clicking Drug Test Summary Report');
    await page.evaluate(() => {
      const el = Array.from(document.querySelectorAll('a')).find(
        e => e.innerText && e.innerText.includes('Drug Test Summary Report')
      );
      if (el) el.click();
    });
    await wait(4000);

    // 6. Wait for iframe
    logStep('Waiting for iframe');
    await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 30000 });
    const frameHandle = await page.$('iframe[name="mainFrame"]');
    const frame = await frameHandle.contentFrame();

    // 7. Click View All
    logStep('Clicking View All');
    await frame.waitForSelector('input#btnViewAll', { timeout: 30000 });
    await frame.click('input#btnViewAll');

    // 8. Set date
    const minus20 = new Date();
    minus20.setDate(minus20.getDate() - 20);
    const mm = String(minus20.getMonth() + 1).padStart(2, '0');
    const dd = String(minus20.getDate()).padStart(2, '0');
    const yyyy = minus20.getFullYear();
    const startDate = `${mm}/${dd}/${yyyy}`;
    logStep('Setting start date');
    try {
      await frame.waitForSelector('input#txtStart', { timeout: 30000 });
      await frame.evaluate((date) => {
        const input = document.querySelector('input#txtStart');
        input.value = date;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }, startDate);
    } catch (e) {
      // Save both the frame and page for maximum debugging
      await saveDebug(page, 'fail_start_date_page', 'fail');
      await saveDebug(frame, 'fail_start_date_frame', 'fail');
      throw e;
    }
    console.log('Set start date to:', startDate);

    // 9. Click Run
    logStep('Clicking Run');
    await frame.waitForSelector('input#cmdRun', { timeout: 30000 });
    await frame.click('input#cmdRun');
    await wait(10000);

    // 10. Click Download
    logStep('Clicking Download');
    try {
      await frame.waitForSelector('.download-title', { timeout: 30000 });
      await frame.evaluate(() => {
        const el = Array.from(document.querySelectorAll('.download-title')).find(
          e => e.innerText && e.innerText.trim() === 'Download'
        );
        if (el) el.click();
      });
    } catch (e) {
      await saveDebug(page, 'fail_download_page', 'fail');
      await saveDebug(frame, 'fail_download_frame', 'fail');
      throw e;
    }

    await wait(15000);
    logStep('All done!');
    console.log(`✅ Finished! Check your downloads folder: ${DOWNLOAD_DIR}`);

  } catch (err) {
    console.error('\n======= SCRIPT FAILED =======');
    console.error(err);
    if (page) await saveDebug(page, 'final_failure_page', 'fail');
    // browser may be undefined on launch fail, so protect the close
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
})();
