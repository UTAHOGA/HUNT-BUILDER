const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const page = await browser.newPage({
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 },
  });
  await page.goto('https://127.0.0.1:4173/research.html', { waitUntil: 'networkidle', timeout: 60000 });
  await page.locator('#huntCodeInput').fill('EB3038');
  await page.locator('#residencySelect').selectOption({ label: 'Resident' });
  await page.locator('#pointsInput').fill('12');
  await page.getByRole('button', { name: 'Run Report' }).click();
  await page.waitForFunction(() => document.querySelectorAll('#ladderTableBody tr').length > 0, { timeout: 60000 });

  const result = await page.evaluate(() => {
    const table = document.querySelector('#ladderTableWrap table');
    const rows = [...document.querySelectorAll('#ladderTableBody tr')];
    return {
      headers: [...table.querySelectorAll('thead th')].map((cell) => cell.textContent.trim()),
      rowCount: rows.length,
      rowPoints: rows.map((row) => row.dataset.ladderPoint),
      userRow: document.querySelector('tr.is-user-row')?.innerText.trim() || '',
      drawLineRow: document.querySelector('tr.is-guaranteed-row')?.innerText.trim() || '',
      containsRemovedTerms: /max pool|random pool|display only|your rung|hunt data/i.test(table.innerText),
      range: document.querySelector('#ladderRange')?.textContent.trim() || '',
    };
  });
  await page.locator('#pointLadderAccordion').screenshot({ path: 'C:/Users/tyler/AppData/Local/Temp/hunt-research-ladder-simplified.png' });
  console.log(JSON.stringify(result));
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
