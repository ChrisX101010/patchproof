/* Shared browser/Node canonical encoder for PatchProof's restricted JSON format. */
(function (root) {
  'use strict';
  function canonical(value, depth = 0) {
    if (depth > 32) throw new Error('JSON nesting too deep');
    if (value === null || typeof value === 'boolean') return JSON.stringify(value);
    if (typeof value === 'number') {
      if (!Number.isSafeInteger(value) || value < 0) throw new Error('Expected nonnegative safe integer');
      return JSON.stringify(value);
    }
    if (typeof value === 'string') {
      for (let i = 0; i < value.length; i++) {
        const n = value.charCodeAt(i);
        if (n >= 0xd800 && n <= 0xdbff) {
          const next = value.charCodeAt(++i);
          if (!(next >= 0xdc00 && next <= 0xdfff)) throw new Error('Invalid Unicode');
        } else if (n >= 0xdc00 && n <= 0xdfff) throw new Error('Invalid Unicode');
      }
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) return '[' + value.map(x => canonical(x, depth + 1)).join(',') + ']';
    if (value && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
      return '{' + Object.keys(value).sort().map(key => {
        if (!/^[A-Za-z][A-Za-z0-9]*$/.test(key)) throw new Error('Unsupported field name');
        return JSON.stringify(key) + ':' + canonical(value[key], depth + 1);
      }).join(',') + '}';
    }
    throw new Error('Unsupported JSON type');
  }
  if (typeof module !== 'undefined') module.exports = { canonical };
  else root.PatchProofCanonical = { canonical };
})(typeof globalThis !== 'undefined' ? globalThis : this);
