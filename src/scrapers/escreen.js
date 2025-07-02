const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

const DOWNLOAD_DIR = path.resolve(__dirname, '..', 'downloads');
if (!fs.existsSync(DOWNLOAD_DIR)) fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  if (!fs.existsSync(DOWNLOAD_DIR)) fs.mkdirSync(DOWNLOAD_DIR);

  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: null,
    args: [
      '--start-maximized',
      '--disable-web-security',
      '--no-sandbox',
    ]
  });

  const page = await browser.newPage();

  // Enable downloads to DOWNLOAD_DIR
  const client = await page.target().createCDPSession();
  await client.send('Page.setDownloadBehavior', {
    behavior: 'allow',
    downloadPath: DOWNLOAD_DIR,
  });

  // 1. Go to login page
  console.log("Navigating to login page...");
  await page.goto('https://www.myescreen.com/', { waitUntil: 'networkidle2' });

  // 2. Fill in Username and submit
  console.log("Waiting for username input...");
  await page.waitForSelector('input#signInName', { timeout: 30000 });
  await page.type('input#signInName', 'connor.beasley');
  await page.keyboard.press('Enter');
  console.log('Username submitted.');

  // 3. Wait for Password input, then fill and submit
  console.log("Waiting for password input...");
  await page.waitForSelector('input[type="password"]', { timeout: 30000 });
  await page.type('input[type="password"]', 'Punky3!Brewster');
  await page.keyboard.press('Enter');
  console.log('Password submitted.');

  // 4. Wait for dashboard to load and click "Reports"
  await wait(7000); // let dashboard settle
  console.log("Clicking Reports...");
  await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll('*')).find(
      e => e.innerText && e.innerText.trim() === 'Reports'
    );
    if (el) el.click();
  });
  console.log('Clicked Reports.');

  // 5. Click "Drug Test Summary Report" link
  await wait(4000);
  console.log("Clicking Drug Test Summary Report...");
  await page.evaluate(() => {
    const el = Array.from(document.querySelectorAll('a')).find(
      e => e.innerText && e.innerText.includes('Drug Test Summary Report')
    );
    if (el) el.click();
  });
  console.log('Clicked Drug Test Summary Report.');

  // 6. Wait for iframe and interact inside
  console.log("Waiting for iframe...");
  await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 30000 });
  const frameHandle = await page.$('iframe[name="mainFrame"]');
  const frame = await frameHandle.contentFrame();

  console.log("Waiting for View All button...");
  await frame.waitForSelector('input#btnViewAll', { timeout: 30000 });
  await frame.click('input#btnViewAll');
  console.log('Clicked View All.');

  // === Set start date to 20 days before today (format MM/DD/YYYY) ===
  const minus20 = new Date();
  minus20.setDate(minus20.getDate() - 20);
  const mm = String(minus20.getMonth() + 1).padStart(2, '0');
  const dd = String(minus20.getDate()).padStart(2, '0');
  const yyyy = minus20.getFullYear();
  const startDate = `${mm}/${dd}/${yyyy}`;

  console.log("Waiting for start date input...");
  await frame.waitForSelector('input#txtStart', { timeout: 30000 });
  await frame.evaluate((date) => {
    const input = document.querySelector('input#txtStart');
    input.value = date;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, startDate);
  console.log('Set start date to:', startDate);

  // Click "Run"
  console.log("Waiting for Run button...");
  await frame.waitForSelector('input#cmdRun', { timeout: 30000 });
  await frame.click('input#cmdRun');
  console.log('Clicked Run.');

  // 9. Click "Download"
  await wait(10000);
  console.log("Waiting for Download button...");
  await frame.waitForSelector('.download-title', { timeout: 30000 });
  await frame.evaluate(() => {
    const el = Array.from(document.querySelectorAll('.download-title')).find(
      e => e.innerText && e.innerText.trim() === 'Download'
    );
    if (el) el.click();
  });
  console.log('Clicked Download.');

  // 10. Wait for the file to finish downloading
  await wait(15000);

  console.log(`✅ Finished! Check your downloads folder: ${DOWNLOAD_DIR}`);

  await browser.close();
})();
