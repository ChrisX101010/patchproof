'use strict';
const $ = id => document.getElementById(id);
const V = globalThis.PatchProofVerify;
let report = null;
let fileResults = {};
function node(tag, text, className) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
function notice(message, error = false) { const n = $('notice'); n.hidden = false; n.className = 'notice' + (error ? ' error' : ''); n.textContent = message; }
function tab(name) {
  $('library').hidden = true; $('report-screen').hidden = false;
  for (const n of ['overview', 'evidence', 'integrity', 'architecture']) $('panel-' + n).hidden = n !== name;
  for (const b of document.querySelectorAll('.tab')) {
    const active = b.dataset.tab === name; b.classList.toggle('active', active);
    if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  }
  $('nav-report').classList.toggle('selected', name !== 'architecture'); $('nav-library').classList.remove('selected'); $('nav-architecture').classList.toggle('selected', name === 'architecture');
}
const rate = value => String(Math.round(value.failed / value.total * 1000) / 10);
function chart(id, counts) {
  const target = $(id); target.replaceChildren();
  const limit = Math.min(counts.total, 100);
  for (let i = 0; i < limit; i++) {
    const n = node('span', undefined, 'case' + (i < counts.failed ? ' fail' : ''));
    n.title = i < counts.failed ? 'Observed failure (count summary)' : 'Observed pass (count summary)';
    n.setAttribute('aria-hidden', 'true'); target.append(n);
  }
  target.setAttribute('aria-label', `${counts.failed} failures in ${counts.total} cases. At most100 squares shown; count summary, not execution order.`);
}
function evidence() {
  if (!report) return;
  const search = $('evidence-search').value.toLowerCase(); const list = $('evidence-list'); list.replaceChildren();
  for (const item of report.payload.evidence.filter(item => item.name.toLowerCase().includes(search))) {
    const row = node('div', undefined, 'evidence-row'); const left = node('div');
    left.append(node('div', item.name, 'filename'), node('div', item.sha256, 'file-hash'), node('div', item.bytes.toLocaleString() + ' bytes', 'file-size'));
    const status = fileResults[item.name];
    row.append(left, node('span', status === 'match' ? 'Original matches ✓' : status === 'mismatch' ? 'Bytes differ !' : status === 'missing' ? 'File not selected' : 'Original not checked', 'file-badge ' + (status || '')));
    list.append(row);
  }
  if (!list.children.length) list.append(node('p', 'No evidence files match this search.', 'helper'));
}
async function display(next) {
  await V.verify(next); report = next; fileResults = {};
  const p = report.payload; $('report-title').textContent = p.title; $('project-label').textContent = p.project.toUpperCase(); $('crumb-project').textContent = p.project;
  $('report-intro').textContent = 'A portable record of what changed, what was tested, and where the evidence stops.';
  $('pr-link').href = p.pullRequest; $('date-label').textContent = new Date(p.createdAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  $('digest-status').textContent = 'Capsule digest matches'; $('evidence-count').textContent = p.evidence.length + ' evidence fingerprints'; $('tab-count').textContent = p.evidence.length;
  $('comparison-title').textContent = p.comparison.name;
  for (const [side, key] of [['before', 'baseline'], ['after', 'candidate']]) {
    const value = p.comparison[key]; $(side + '-rate').replaceChildren(node('span', rate(value)));
    $(side + '-rate').firstChild.className = 'rate-value'; $(side + '-rate').append(node('span', '%'));
    $(side + '-count').textContent = `${value.failed} failed / ${value.total} cases`; chart(side + '-cases', value);
  }
  $('test-groups').replaceChildren();
  for (const g of p.groups) {
    const card = node('article', undefined, 'test-card'); const result = node('div', undefined, 'test-result');
    result.append(node('span', String(g.passed)), node('small', '/ ' + g.total + ' passed'));
    card.append(node('h3', g.name), result, node('p', `${g.failed} failed · ${g.skipped} skipped`)); card.title = g.scope; $('test-groups').append(card);
  }
  $('limitations').replaceChildren(...p.limitations.map(item => node('li', item)));
  $('capsule-hash').textContent = report.sha256; $('environment').replaceChildren();
  for (const [key, label] of [['os', 'PLATFORM'], ['toolchain', 'TOOLCHAIN'], ['runtime', 'RUNTIME']]) $('environment').append(node('dt', label), node('dd', p.environment[key]));
  $('baseline-commit').textContent = p.baseline.commit.slice(0, 12); $('baseline-commit').title = p.baseline.commit;
  $('candidate-commit').textContent = p.candidate.commit.slice(0, 12); $('candidate-commit').title = p.candidate.commit;
  $('download-button').disabled = false; $('file-summary').textContent = 'Original files have not been checked in this browser.'; $('evidence-search').value = '';
  resetLab(); evidence(); tab('overview');
}
function resetLab() {
  $('lab-result').className = 'lab-result'; $('lab-result').replaceChildren(node('span', '◇', 'lab-icon'), node('strong', 'Your original capsule is intact.'), node('p', 'Run the demonstration to see tampering get detected.'));
}
async function fetchReport(path) {
  const response = await fetch(path); if (!response.ok) throw new Error('Report could not be loaded (' + response.status + ').');
  return V.parseStrict(await response.text());
}
async function library() {
  $('library').hidden = false; $('report-screen').hidden = true; $('nav-library').classList.add('selected'); $('nav-report').classList.remove('selected'); $('nav-architecture').classList.remove('selected');
  const list = $('library-items'); list.replaceChildren(node('p', 'Loading published reports…', 'helper'));
  try {
    const response = await fetch('/api/reports'); if (!response.ok) throw new Error('The report index is unavailable. Your local capsule is unaffected.');
    const data = await response.json(); list.replaceChildren();
    for (const item of data.reports) {
      const card = node('article', undefined, 'library-item'); const text = node('div'); text.append(node('h2', item.title), node('p', item.project + ' · ' + item.createdAt.slice(0, 10)));
      const button = node('button', 'Open report →', 'button'); button.addEventListener('click', () => openStored(item.id)); card.append(text, button); list.append(card);
    }
    if (!data.reports.length) list.append(node('p', 'No reports published yet. Try the real example below, or publish a capsule with the authorized CLI.', 'helper'));
  } catch (error) { list.replaceChildren(node('p', error.message, 'notice error')); }
}
async function openStored(id) {
  try { if (!/^[a-f0-9]{64}$/.test(id)) throw new Error('Invalid report identity'); const next = await fetchReport('/api/reports/' + id); if (next.sha256 !== id) throw new Error('Stored report identity differs'); await display(next); history.replaceState(null, '', '/r/' + id); }
  catch (error) { notice(error.message, true); }
}
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));
$('nav-report').addEventListener('click', () => tab('overview')); $('nav-library').addEventListener('click', library); $('nav-architecture').addEventListener('click', () => tab('architecture'));
$('open-example').addEventListener('click', async () => { try { await display(await fetchReport('/api/example')); history.replaceState(null, '', '/'); } catch (error) { notice(error.message, true); } });
$('evidence-search').addEventListener('input', evidence);
$('import-button').addEventListener('click', () => $('capsule-input').click());
$('capsule-input').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 262144) throw new Error('Capsule exceeds256KiB');
    await display(V.parseStrict(await file.text())); history.replaceState(null, '', '/'); notice('Imported locally. Nothing was uploaded.');
  } catch (error) { notice('Import rejected: ' + error.message, true); }
  event.target.value = '';
});
$('download-button').addEventListener('click', () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([globalThis.PatchProofCanonical.canonical(report)], { type: 'application/json' }));
  const a = node('a'); a.href = url; a.download = 'patchproof-' + report.sha256.slice(0, 12) + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('copy-hash').addEventListener('click', async () => { try { await navigator.clipboard.writeText(report.sha256); notice('Capsule digest copied.'); } catch { notice('Clipboard unavailable. Select the displayed digest to copy it.', true); } });
$('tamper-button').addEventListener('click', async () => {
  if (!report) return; const copy = structuredClone(report); const c = copy.payload.comparison.candidate; c.failed = c.failed === c.total ? 0 : c.failed + 1;
  try { await V.verify(copy); notice('Unexpected result: changed capsule verified.', true); }
  catch (error) {
    $('lab-result').className = 'lab-result detected'; $('lab-result').replaceChildren(node('span', '≠', 'lab-icon'), node('strong', 'Changed bytes detected.'), node('p', 'The claimed digest no longer matches. Your original capsule has not been modified.'));
  }
});
$('recheck-button').addEventListener('click', async () => { try { await V.verify(report); resetLab(); notice('Original capsule digest matches. No execution attestation is implied.'); } catch (error) { notice(error.message, true); } });
$('verify-files-button').addEventListener('click', () => $('evidence-input').click());
$('evidence-input').addEventListener('change', async event => {
  if (!report) return;
  const selected = new Map(); for (const file of event.target.files) { if (selected.has(file.name)) { notice('Select files with unique basenames.', true); return; } selected.set(file.name, file); }
  try {
    const results = {};
    for (const item of report.payload.evidence) {
      const file = selected.get(item.name);
      if (!file) { results[item.name] = 'missing'; continue; }
      if (file.size !== item.bytes || file.size > 50 * 1024 * 1024) { results[item.name] = 'mismatch'; continue; }
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(n => n.toString(16).padStart(2, '0')).join('');
      results[item.name] = digest === item.sha256 ? 'match' : 'mismatch';
    }
    fileResults = results; const values = Object.values(results); $('file-summary').textContent = `${values.filter(x => x === 'match').length} original files match · ${values.filter(x => x === 'mismatch').length} differ · ${values.filter(x => x === 'missing').length} not selected. Files were not uploaded.`; evidence();
  } catch (error) { notice('File verification failed: ' + error.message, true); }
  event.target.value = '';
});
(async () => {
  try {
    const health = await (await fetch('/api/health')).json(); $('mode-label').textContent = health.mode === 'aws' ? 'Running on AWS' : 'Local workspace';
    $('cloud-note').textContent = health.mode === 'aws' ? 'This instance is running on AWS Lambda. Only authorized publishers can write capsules.' : 'Local mode: SQLite replaces AWS storage. No cloud resources have been created by this app.';
    const match = /^\/r\/([a-f0-9]{64})$/.exec(location.pathname);
    if (match) await openStored(match[1]); else await display(await fetchReport('/api/example'));
  } catch (error) { $('report-title').textContent = 'Let’s check the evidence.'; notice('Could not load report: ' + error.message, true); }
})();
