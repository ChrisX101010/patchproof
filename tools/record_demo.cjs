/* Actual browser recording. Local rehearsals are marked and never authorize AWS cleanup. */
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const crypto = require('crypto');
const ROOT = path.resolve(__dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(ROOT, '.playwright');
const { chromium } = require('@playwright/test');
const local = process.argv.includes('--local');
const quick = process.argv.includes('--quick');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const sha = data => crypto.createHash('sha256').update(data).digest('hex');

(async () => {
  if (quick && !local) throw new Error('Quick mode is only a clearly marked local rehearsal');
  const session = local ? null : JSON.parse(fs.readFileSync(path.join(ROOT, '.local/demo-session.json'), 'utf8'));
  const smoke = local ? null : JSON.parse(fs.readFileSync(path.join(ROOT, '.local/cloud-smoke.json'), 'utf8'));
  const base = local ? 'http://127.0.0.1:8787' : session.url.replace(/\/$/, '');
  if (!local && (session.status !== 'READY_FOR_RECORDING' || smoke.status !== 'PASS' || smoke.url !== base)) throw new Error('A matching successful cloud smoke/session is required');
  if (!local && !/^https:\/\/[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws$/.test(base)) throw new Error('Unexpected AWS URL');
  const health = await (await fetch(base + '/api/health')).json();
  if (health.mode !== (local ? 'local' : 'aws')) throw new Error('Runtime mode differs; no recording claimed');
  const example = JSON.parse(fs.readFileSync(path.join(ROOT, 'examples/buildkit.capsule.json'), 'utf8'));
  const output = path.join(ROOT, 'artifacts'); fs.mkdirSync(output, { recursive: true });
  const videoPath = path.join(output, local ? 'patchproof-local-preview.webm' : 'patchproof-aws-demo.webm');
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
  const errors = [];
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 },
      recordVideo: { dir: path.join(output, '.capture'), size: { width: 1440, height: 1000 } }, acceptDownloads: true });
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
    const recording = page.video();
    await page.goto(base + (local ? '/' : '/r/' + example.sha256));
    await page.getByText('Capsule digest matches', { exact: true }).waitFor();
    if ((await page.locator('#capsule-hash').textContent()) !== example.sha256) throw new Error('Displayed evidence differs');
    await page.evaluate(() => {
      const overlay = document.createElement('div'); overlay.id = 'video-caption';
      Object.assign(overlay.style, { position: 'fixed', bottom: '15px', left: '250px', right: '25px', padding: '18px 24px',
        borderRadius: '8px', background: '#152c24', color: '#f1f5e9', font: '19px/1.5 Segoe UI,Arial,sans-serif',
        boxShadow: '0 3px 22px #0002', zIndex: '10000', border: '1px solid #80956c' });
      document.body.append(overlay);
    });
    async function caption(text, seconds = 14) {
      console.log('SCENE=' + text);
      await page.locator('#video-caption').evaluate((el, value) => { el.textContent = value; }, (local ? 'LOCAL PREVIEW · ' : '') + text);
      await sleep(quick ? 550 : seconds * 1000);
    }
    await caption('PatchProof — a real software contribution, with evidence you can inspect and take with you.', 12);
    await caption('BuildKit image roundtrips: 7 failures in 20 cases before the patch; 0 in 20 after it. These are observed results, not a guarantee.', 14);
    await page.locator('.scope-card').scrollIntoViewIfNeeded();
    await caption('Scope belongs beside the result. Both 46-test cache runs passed; the full integration suite and existing-state upgrade were not tested.', 14);
    await page.locator('[data-tab="evidence"]').click(); await page.evaluate(() => scrollTo(0, 0));
    const evidenceRoot = path.resolve(ROOT, '../buildkit-7403-candidate/wsl-buildkit-7403-validation.qioshz3c');
    const originals = example.payload.evidence.map(item => path.join(evidenceRoot, item.name));
    for (const file of originals) if (!fs.existsSync(file)) throw new Error('Original evidence file missing: ' + path.basename(file));
    await page.locator('#evidence-input').setInputFiles(originals);
    await page.getByText(/16 original files match/).waitFor();
    await caption('Sixteen original files match their recorded fingerprints. Verification happens in the browser; raw logs are not uploaded.', 14);
    await page.locator('[data-tab="integrity"]').click(); await page.evaluate(() => scrollTo(0, 0));
    await page.locator('#tamper-button').click(); await page.getByText('Changed bytes detected.', { exact: true }).waitFor();
    await caption('Change one number in a copy and its digest no longer matches. The stored original remains unchanged.', 12);
    await page.locator('#recheck-button').click();
    await caption('Hash consistency is not independent proof that tests happened. PatchProof states that boundary rather than turning claims into trust badges.', 13);
    const downloadPromise = page.waitForEvent('download'); await page.locator('#download-button').click();
    const download = await downloadPromise; const saved = path.join(output, 'recorded-capsule.json'); await download.saveAs(saved);
    if (JSON.parse(fs.readFileSync(saved, 'utf8')).sha256 !== example.sha256) throw new Error('Downloaded report differs');
    await caption('Download portable JSON. The separate Python verifier checks it offline, without this website or an account.', 11);
    await page.locator('[data-tab="architecture"]').click(); await page.evaluate(() => scrollTo(0, 0));
    await caption(local ? 'Local rehearsal only. This does not demonstrate AWS execution.' : 'Live AWS build: one Lambda serves the UI/API, private S3 stores immutable capsules, and DynamoDB indexes reports. No always-on server or pipeline.', 14);
    await page.locator('[data-tab="overview"]').click(); await page.evaluate(() => scrollTo(0, 0));
    await caption('Built by Hristos Nenkov with AI assistance. Fewer claims. Better evidence.', 8);
    if (errors.length) throw new Error('Browser errors: ' + errors.join(';'));
    await context.close(); await recording.saveAs(videoPath);
    // Decode the actual saved WebM and capture review frames, not merely live-page screenshots.
    const review = await browser.newContext({ viewport: { width: 1440, height: 1000 } }); const preview = await review.newPage();
    await preview.goto(pathToFileURL(videoPath).href);
    await preview.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 1 && Number.isFinite(v.duration); });
    const duration = await preview.evaluate(() => { const v = document.querySelector('video'); v.pause(); return v.duration; });
    if (!local && (duration < 90 || duration >= 180)) throw new Error('AWS video duration outside90..179 seconds: ' + duration);
    for (const [index, second] of [Math.min(3, duration / 3), Math.min(duration - 1, duration / 2)].entries()) {
      await preview.evaluate(time => { document.querySelector('video').currentTime = time; }, second);
      await preview.waitForFunction(() => !document.querySelector('video').seeking);
      await preview.locator('video').screenshot({ path: path.join(output, (local ? 'preview' : 'aws') + '-video-frame-' + index + '.png') });
    }
    await review.close();
    const receipt = { status: 'SAVED_AWAITING_VISUAL_REVIEW', mode: health.mode, url: base,
      sessionId: session?.sessionId || null, capsule: example.sha256, seconds: duration,
      video: path.relative(ROOT, videoPath).replace(/\\/g, '/'), videoSha256: sha(fs.readFileSync(videoPath)), cloud: local ? 'NOT_DEMONSTRATED' : 'SMOKE_CHECKED' };
    fs.writeFileSync(path.join(output, local ? 'local-recording.json' : 'aws-recording.json'), JSON.stringify(receipt, null, 2));
    console.log('RECORDING_SAVED=' + videoPath + '\nSECONDS=' + duration + '\nVISUAL_REVIEW=PENDING\nCLEANUP_MARKER=NOT_WRITTEN');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exit(1); });
