(function (root) {
  'use strict';
  const canonical = root.PatchProofCanonical.canonical;
  const check = (ok, why) => { if (!ok) throw new Error(why); };
  function parseStrict(source) {
    check(new TextEncoder().encode(source).length <= 262144, 'Capsule exceeds256KiB');
    let i = 0;
    const ws = () => { while (/[\t\r\n ]/.test(source[i] || '\u0000')) i++; };
    function string() {
      const start = i++;
      while (i < source.length) {
        if (source[i] === '\\') { i += 2; continue; }
        if (source[i++] === '"') return JSON.parse(source.slice(start, i));
      }
      throw new Error('Unterminated JSON string');
    }
    function value(depth = 0) {
      check(depth <= 32, 'JSON nesting too deep'); ws();
      if (source[i] === '"') return string();
      if (source[i] === '{') {
        i++; ws(); const object = {};
        if (source[i] === '}') { i++; return object; }
        while (true) {
          ws(); check(source[i] === '"', 'Expected field name'); const key = string();
          check(!Object.hasOwn(object, key), 'Duplicate JSON key'); ws(); check(source[i++] === ':', 'Expected colon');
          Object.defineProperty(object, key, { value: value(depth + 1), enumerable: true, writable: true });
          ws(); const next = source[i++]; if (next === '}') return object;
          check(next === ',', 'Expected comma');
        }
      }
      if (source[i] === '[') {
        i++; ws(); const array = []; if (source[i] === ']') { i++; return array; }
        while (true) {
          array.push(value(depth + 1)); ws(); const next = source[i++]; if (next === ']') return array;
          check(next === ',', 'Expected comma');
        }
      }
      const match = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(source.slice(i));
      check(match, 'Invalid JSON value'); i += match[0].length;
      check(!/[.eE]/.test(match[0]), 'Floats are not supported'); return JSON.parse(match[0]);
    }
    const result = value(); ws(); check(i === source.length, 'Unexpected trailing JSON'); return result;
  }
  const shape = (value, keys) => check(value && !Array.isArray(value) && typeof value === 'object' && Object.keys(value).sort().join(' ') === keys.split(' ').sort().join(' '), 'Missing or unknown fields');
  const str = (value, max = 5000) => check(typeof value === 'string' && value.length > 0 && [...value].length <= max && value.trim() === value && !/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value), 'Invalid text');
  const int = value => check(Number.isSafeInteger(value) && value >= 0, 'Invalid count');
  async function digest(value) {
    const bytes = new TextEncoder().encode(canonical(value));
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  function validate(payload) {
    shape(payload, 'schemaVersion title project repository pullRequest createdAt baseline candidate environment groups comparison limitations evidence');
    check(payload.schemaVersion === 1, 'Unsupported schema version'); str(payload.title, 200); str(payload.project, 200);
    for (const key of ['repository', 'pullRequest']) {
      str(payload[key], 2048); const url = new URL(payload[key]);
      check(url.protocol === 'https:' && !url.username && !url.password && (!url.port || url.port === '443') && !/\s/.test(payload[key]), 'Expected HTTPS URL');
    }
    check(typeof payload.createdAt === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(payload.createdAt) &&
          new Date(payload.createdAt).toISOString().replace('.000Z', 'Z') === payload.createdAt, 'Invalid UTC timestamp');
    for (const key of ['baseline', 'candidate']) { shape(payload[key], 'commit'); check(/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(payload[key].commit), 'Invalid commit'); }
    shape(payload.environment, 'os toolchain runtime'); Object.values(payload.environment).forEach(v => str(v, 200));
    check(Array.isArray(payload.groups) && payload.groups.length >= 1 && payload.groups.length <= 128, 'Invalid groups');
    const groups = new Set();
    for (const g of payload.groups) {
      shape(g, 'name total passed failed skipped scope'); str(g.name, 120); str(g.scope); check(!groups.has(g.name), 'Duplicate group'); groups.add(g.name);
      [g.total, g.passed, g.failed, g.skipped].forEach(int); check(g.total > 0 && g.total === g.passed + g.failed + g.skipped, 'Inconsistent counts');
    }
    shape(payload.comparison, 'name baseline candidate'); str(payload.comparison.name, 200);
    for (const key of ['baseline', 'candidate']) { const v = payload.comparison[key]; shape(v, 'total failed'); int(v.total); int(v.failed); check(v.total > 0 && v.failed <= v.total, 'Inconsistent runtime counts'); }
    check(Array.isArray(payload.limitations) && payload.limitations.length > 0 && payload.limitations.length <= 32, 'Explicit limitations required'); payload.limitations.forEach(v => str(v));
    check(Array.isArray(payload.evidence) && payload.evidence.length > 0 && payload.evidence.length <= 1000, 'Invalid evidence count');
    const names = new Set();
    for (const item of payload.evidence) {
      shape(item, 'name sha256 bytes'); check(typeof item.name === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/.test(item.name) && !item.name.includes('..') && !names.has(item.name), 'Unsafe or duplicate filename'); names.add(item.name);
      check(typeof item.sha256 === 'string' && /^[a-f0-9]{64}$/.test(item.sha256), 'Invalid evidence digest'); int(item.bytes);
    }
    check(new TextEncoder().encode(canonical(payload)).length < 262044, 'Payload too large');
  }
  async function verify(report) {
    shape(report, 'payload sha256'); validate(report.payload);
    check(typeof report.sha256 === 'string' && /^[a-f0-9]{64}$/.test(report.sha256), 'Invalid capsule digest');
    check(await digest(report.payload) === report.sha256, 'Capsule digest mismatch'); return report.sha256;
  }
  root.PatchProofVerify = { parseStrict, validate, digest, verify };
})(globalThis);
