"""Import a verified BuildKit receipt directory. Original logs stay on disk."""
import hashlib
import json
from pathlib import Path
import re

from .capsule import CapsuleError, seal, canonical


def build(receipts):
    receipts = Path(receipts)
    receipt = json.loads((receipts / 'verified-receipt.json').read_text())
    if receipt['status'] != 'PASS':
        raise CapsuleError('Source validation did not pass')
    evidence = []
    for name, expected in sorted(receipt['files'].items()):
        if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', name):
            raise CapsuleError('Unsafe source evidence name')
        raw = (receipts / name).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise CapsuleError('Source evidence changed: ' + name)
        evidence.append({'name': name, 'sha256': actual, 'bytes': len(raw)})
    summary = json.loads((receipts / 'summary.json').read_text())
    if summary['patch_sha256'] != receipt['patch_sha256'] or summary['base'] != receipt['base']:
        raise CapsuleError('Source summaries disagree')
    groups = []
    for name, filename in [('Cache package', 'candidate-full-cache.log'), ('Cache package · race detector', 'candidate-full-cache-race.log')]:
        raw = (receipts / filename).read_text()
        passed = len(re.findall(r'^--- PASS:', raw, re.M))
        skipped = len(re.findall(r'^--- SKIP:', raw, re.M))
        failed = len(re.findall(r'^--- FAIL:', raw, re.M))
        if failed or '\nPASS\n' not in raw:
            raise CapsuleError('Source test log failed')
        groups.append({'name': name, 'total': passed + skipped, 'passed': passed, 'failed': 0,
                       'skipped': skipped, 'scope': 'Top-level tests in ./cache; not the full repository suite.'})
    payload = {'schemaVersion': 1, 'title': 'A missing base layer. A measurable fix.', 'project': 'BuildKit',
        'repository': 'https://github.com/moby/buildkit', 'pullRequest': 'https://github.com/moby/buildkit/pull/7424',
        'createdAt': '2026-11-16T08:03:50Z', 'baseline': {'commit': receipt['base']},
        'candidate': {'commit': 'c57f2d2093a53db534026767783759130a33f5de'},
        'environment': {'os': 'Linux/amd64 · WSL2', 'toolchain': summary['go'], 'runtime': 'Docker ' + summary['docker']},
        'groups': groups, 'comparison': {'name': 'Warm-daemon image roundtrips',
            'baseline': {'total': receipt['runtime']['baseline']['cases'], 'failed': receipt['runtime']['baseline']['missing_base_cases']},
            'candidate': {'total': receipt['runtime']['candidate']['cases'], 'failed': receipt['runtime']['candidate']['missing_base_cases']}},
        'limitations': ['Integrity checks compare supplied bytes; they do not independently attest test execution.',
            'Full BuildKit repository integration suite and make validate-all were not run.',
            'Upgrade of an existing daemon state directory was not tested.',
            'Test images used source-built daemons over the v0.34.1 helper image, not full release builds.',
            'PR7424 was submitted for review; submission does not mean upstream acceptance.',
            'Original diagnosis and single-layer correction were proposed by Sevla8 in issue7403.'],
        'evidence': evidence}
    return seal(payload)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = build(args.receipts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(report))
    print('CAPSULE=' + report['sha256'] + '\nRAW_LOGS_PUBLISHED=NO')
