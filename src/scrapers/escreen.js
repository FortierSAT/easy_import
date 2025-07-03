// src/scrapers/escreen.js
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path = require('path');
const fs = require('fs');

puppeteer.use(StealthPlugin());

const DOWNLOAD_DIR = path.resolve(__dirname, '..', 'downloads');
if (!fs.existsSync(DOWNLOAD_DIR)) fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

module.exports = async function escreen_scraper() {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  // enable downloads
  const client = await page.target().createCDPSession();
  await client.send('Page.setDownloadBehavior', {
    behavior: 'allow',
    downloadPath: DOWNLOAD_DIR,
  });

  // 1) Login
  await page.goto('https://www.myescreen.com/', { waitUntil: 'networkidle2' });
  await page.type('input#signInName', process.env.ESCREEN_USERNAME);
  await page.keyboard.press('Enter');
  await page.waitForSelector('input[type="password"]', { timeout: 15000 });
  await page.type('input[type="password"]', process.env.ESCREEN_PASSWORD);
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: 'networkidle2' });

  // 2) Click Reports → Drug Test Summary Report
  await page.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('*')).find(e => e.innerText.trim() === 'Reports');
    btn && btn.click();
  });
  await page.waitForTimeout(3000);

  await page.evaluate(() => {
    const link = Array.from(document.querySelectorAll('a'))
      .find(a => a.innerText.includes('Drug Test Summary Report'));
    link && link.click();
  });
  await page.waitForTimeout(5000);

  // 3) Grab the report iframe
  const frameHandle = await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 15000 });
  const frame = await frameHandle.contentFrame();

  // 4) Click “View All”
  await frame.waitForSelector('input#btnViewAll', { timeout: 15000 });
  await frame.click('input#btnViewAll');
  await page.waitForTimeout(5000);

  // 5) Click “Search”
  await frame.waitForSelector('input#btnSearch', { timeout: 15000 });
  await frame.click('input#btnSearch');
  await page.waitForTimeout(10000);

  // 6) Click the Download link (text may vary)
  await frame.evaluate(() => {
    const dl = Array.from(document.querySelectorAll('a')).find(a =>
      a.innerText.trim().toLowerCase().includes('download')
    );
    dl && dl.click();
  });
  // give download a few seconds to finish
  await page.waitForTimeout(10000);

  await browser.close();
  return path.join(DOWNLOAD_DIR, 'DrugTestSummaryReport_Total.xlsx'); // or whichever file you expect
}
