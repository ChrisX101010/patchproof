const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
(async () => {
  const executablePath = process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined);
  const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const context = await browser.newContext({ viewport: { width: 1540, height: 1100 }, acceptDownloads: true });
  const page = await context.newPage(); const errors = []; page.on('pageerror', error => errors.push(error.message));
  const base = process.env.PATCHPROOF_URL || 'http://127.0.0.1:8787';
  const demo = JSON.parse(fs.readFileSync('examples/buildkit.capsule.json', 'utf8'));
  const artifact = path.resolve('artifacts'); fs.mkdirSync(artifact, { recursive: true });
  try {
    await page.goto(base); await page.getByText('Capsule digest matches', { exact: true }).waitFor();
    assert.equal(await page.locator('#before-rate .rate-value').textContent(), '35');
    assert.equal(await page.locator('#after-rate .rate-value').textContent(), '0');
    assert.equal(await page.locator('#before-cases .fail').count(), 7);
    assert.equal(await page.locator('#after-cases .fail').count(), 0);
    assert.equal(await page.locator('.test-card').count(), 2);
    await page.screenshot({ path: path.join(artifact, 'desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Integrity lab', exact: true }).click();
    await page.getByRole('button', { name: 'Change a number & verify' }).click();
    await page.getByText('Changed bytes detected.', { exact: true }).waitFor();
    assert.equal(await page.locator('#capsule-hash').textContent(), demo.sha256);
    await page.getByRole('button', { name: 'Recheck original', exact: true }).click();
    await page.getByText('Your original capsule is intact.', { exact: true }).waitFor();
    await page.getByRole('button', { name: /Evidence manifest/ }).click();
    assert.equal(await page.locator('.evidence-row').count(), 16);
    await page.locator('#evidence-input').setInputFiles({ name: 'patch-check.log', mimeType: 'text/plain', buffer: Buffer.from('') });
    await page.getByText(/1 original files match/).waitFor();
    await page.locator('#evidence-search').fill('patch-check'); assert.equal(await page.locator('.evidence-row').count(), 1);
    const altered = structuredClone(demo); altered.payload.title = 'Altered claim';
    await page.locator('#capsule-input').setInputFiles({ name: 'altered.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(altered)) });
    await page.getByText(/Import rejected: Capsule digest mismatch/).waitFor();
    assert.equal(await page.locator('#report-title').textContent(), demo.payload.title);
    await page.locator('#capsule-input').setInputFiles({ name: 'valid.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(demo)) });
    await page.getByText('Imported locally. Nothing was uploaded.', { exact: true }).waitFor();
    const downloadPromise = page.waitForEvent('download'); await page.locator('#download-button').click();
    const download = await downloadPromise; const downloaded = path.join(artifact, 'downloaded-capsule.json'); await download.saveAs(downloaded);
    assert.deepEqual(JSON.parse(fs.readFileSync(downloaded, 'utf8')), demo);
    const unauthorized = await context.request.post(base + '/api/reports', { data: demo }); assert.equal(unauthorized.status(), 401);
    await page.locator('#nav-library').click();
    await page.getByRole('button', { name: 'Open report →', exact: true }).first().click();
    await page.waitForURL('**/r/' + demo.sha256);
    assert.equal(await page.locator('#capsule-hash').textContent(), demo.sha256);
    const strict = await page.evaluate(() => {
      let rejected = 0; for (const s of ['{"payload":1,"payload":2}', '{"number":1.0}', '{"number":1e0}']) { try { PatchProofVerify.parseStrict(s); } catch { rejected++; } } return rejected;
    }); assert.equal(strict, 3);
    await page.setViewportSize({ width: 390, height: 844 }); await page.locator('[data-tab="overview"]').click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: path.join(artifact, 'mobile.png'), fullPage: true });
    await page.getByRole('button', { name: 'How it works' }).count();
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(artifact, 'browser-validation.json'), JSON.stringify({ status: 'PASS', runtime: await browser.version(),
      scenarios: ['real counts', 'tamper detection', 'original file check', 'search', 'invalid import', 'valid import', 'download', 'unauthorized publication', 'published report permalink', 'strict parser', 'mobile overflow'], cloud: 'NOT_TESTED' }, null, 2));
    console.log('BROWSER_E2E=PASS (11 scenarios; desktop and mobile screenshots saved)');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
