// src/scrapers/escreen.js
const puppeteer     = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const path          = require('path');
const fs            = require('fs');
require('dotenv').config();

puppeteer.use(StealthPlugin());

// ensure download and debug dirs exist
const BASE_DIR     = path.resolve(__dirname, '..');
const DOWNLOAD_DIR = path.join(BASE_DIR, 'downloads');
const DEBUG_DIR    = path.join(BASE_DIR, 'debug');
for (const d of [DOWNLOAD_DIR, DEBUG_DIR]) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}

const sleep = ms => new Promise(res => setTimeout(res, ms));

;(async () => {
  console.log('🛠️  Starting eScreen scraper…');
  const inDocker = fs.existsSync('/.dockerenv') || process.env.RUNNING_IN_DOCKER === 'true';
  console.log(`🔍 Running in Docker? ${inDocker}`);

  const launchOpts = inDocker
    ? {
        headless: true,
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
        args: [
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-dev-shm-usage',
          '--remote-debugging-port=9222',
          '--remote-debugging-address=0.0.0.0'
        ]
      }
    : {
        headless: true,
        defaultViewport: null,
        args: ['--start-maximized']
      };

  try {
    console.log('🌐 Launching browser…', launchOpts);
    const browser = await puppeteer.launch(launchOpts);
    console.log('✅ Browser launched');

    const page = await browser.newPage();
    console.log('✅ New page opened');

    // Debug hooks
    page.on('console', msg => console.log(`PAGE LOG ▶ [${msg.type()}]`, msg.text()));
    page.on('pageerror', err => console.error('PAGE ERROR ▶', err));
    page.on('requestfailed', req => console.warn('PAGE REQ FAIL ▶', req.url(), req.failure()));
    page.on('response', res => console.log(`PAGE RESP ${res.status()} ◀`, res.url()));

    // set up downloads
    console.log('⬇️  Configuring download behavior →', DOWNLOAD_DIR);
    const cdp = await page.target().createCDPSession();
    await cdp.send('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: DOWNLOAD_DIR });
    console.log('✅ Download behavior set');

    // 1) login
    console.log('🚪 goto login…');
    await page.goto('https://www.myescreen.com/', { waitUntil: 'networkidle2', timeout: 60000 });
    await page.waitForSelector('input#signInName', { timeout: 30000 });
    await page.type('input#signInName', process.env.ESCREEN_USERNAME);
    await page.keyboard.press('Enter');
    await page.waitForSelector('input[type="password"]', { timeout: 30000 });
    await page.type('input[type="password"]', process.env.ESCREEN_PASSWORD);
    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 });
    console.log('✅ Logged in');

    // 2) Reports menu
    console.log('🔎 opening Reports menu');
    await page.waitForSelector('div.mainNavLink', { timeout: 30000 });
    await page.evaluate(() => {
      for (let el of document.querySelectorAll('div.mainNavLink'))
        if (el.innerText.trim() === 'Reports') el.click();
    });
    await sleep(3000);

    // 3) Summary report
    console.log('🔎 selecting Summary Report');
    await page.waitForSelector('a[target="mainFrame"]', { timeout: 30000 });
    await page.evaluate(() => {
      const link = Array.from(document.querySelectorAll('a[target="mainFrame"]'))
        .find(a => a.innerText.includes('Drug Test Summary Report'));
      link.click();
    });
    await sleep(5000);

    // 4) iframe → View All
    console.log('🔎 entering iframe and clicking View All');
    let fh = await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 30000 });
    let frame = await fh.contentFrame();
    await frame.waitForSelector('input#btnViewAll', { timeout: 30000 });
    await frame.click('input#btnViewAll');
    await sleep(5000);

    // 4.5) switch back to mainFrame
    console.log('🔄 switching to mainFrame after View All');
    fh = await page.waitForSelector('iframe[name="mainFrame"]', { timeout: 30000 });
    frame = await fh.contentFrame();
    if (!frame) throw new Error('Couldn’t reacquire mainFrame');

    // DEBUG: dump the frame URL, HTML and screenshot
    const allInputs = await frame.$$eval('input', els =>
      els.map(el => ({
        id: el.id,
        name: el.name,
        type: el.type,
        placeholder: el.getAttribute('placeholder') || null,
        class: el.className || null
      }))
    );
    console.log('🐛 [DEBUG] all inputs in summary frame:', allInputs);

    const now = Date.now();
    const frameUrl = frame.url();
    console.log('🐛 [DEBUG] frame URL:', frameUrl);

    const html = await frame.content();
    fs.writeFileSync(path.join(DEBUG_DIR, `frame-${now}.html`), html);
    console.log(`🐛 [DEBUG] Wrote HTML dump → debug/frame-${now}.html`);

    await frame.screenshot({ path: path.join(DEBUG_DIR, `frame-${now}.png`), fullPage: true });
    console.log(`🐛 [DEBUG] Took screenshot → debug/frame-${now}.png`);

    // now try to find the date input…
    await frame.waitForSelector('input#txtStart', { timeout: 30000 });

    // now set date 20 days ago inside that frame
    const d20     = new Date(Date.now() - 20 * 24 * 60 * 60 * 1000);
    const mm      = String(d20.getMonth() + 1).padStart(2, '0');
    const dd      = String(d20.getDate()).padStart(2, '0');
    const yr      = d20.getFullYear();
    const dateStr = `${mm}/${dd}/${yr}`;
    console.log('📅 setting start date →', dateStr);
    await frame.waitForSelector('input#txtStart', { timeout: 30000 });
    await frame.click('input#txtStart', { clickCount: 3 });
    await frame.type('input#txtStart', dateStr, { delay: 50 });
    await sleep(2000);

    // 5) Run
    console.log('▶ clicking Run');
    await frame.waitForSelector('input#cmdRun', { timeout: 30000 });
    await frame.click('input#cmdRun');
    await sleep(10000);

    // 6) download via Inbox icon
    console.log('⬇️  clicking download icon');
    await frame.waitForSelector('i.abt-icon.icon-Inbox', { timeout: 30000 });
    await frame.click('i.abt-icon.icon-Inbox');

    // 7) wait for file
    const outPath = path.join(DOWNLOAD_DIR, 'DrugTestSummaryReport_Total.xlsx');
    console.log('⌛ waiting for file →', outPath);
    for (let i = 0; i < 30; i++) {
      if (fs.existsSync(outPath)) break;
      await sleep(1000);
    }
    if (!fs.existsSync(outPath)) {
      throw new Error(`XLSX not found at ${outPath}`);
    }

    console.log('✅ Download complete →', outPath);
    await browser.close();
    process.exit(0);

  } catch (err) {
    // dump screenshot & HTML for post-mortem
    const ts = Date.now();
    if (typeof page !== 'undefined') {
      try {
        const shot = path.join(DEBUG_DIR, `err-${ts}.png`);
        const html = path.join(DEBUG_DIR, `err-${ts}.html`);
        await page.screenshot({ path: shot, fullPage: true });
        await page.content().then(c => fs.writeFileSync(html, c));
        console.error('🧪 Saved debug files:', shot, html);
      } catch (e) {
        console.error('⚠️ Failed to capture debug artifacts', e);
      }
    }
    console.error('❌ eScreen scraper error:', err);
    process.exit(1);
  }
})();
