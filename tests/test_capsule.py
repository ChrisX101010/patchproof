import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from patchproof.capsule import CapsuleError, canonical, seal, verify, load, verify_files


def example():
    return {
        'schemaVersion': 1, 'title': 'Keep the base layers', 'project': 'BuildKit',
        'repository': 'https://github.com/moby/buildkit',
        'pullRequest': 'https://github.com/moby/buildkit/pull/7424',
        'createdAt': '2026-11-16T08:03:50Z',
        'baseline': {'commit': 'a' * 40}, 'candidate': {'commit': 'b' * 40},
        'environment': {'os': 'Linux/amd64', 'toolchain': 'Go 1.26.11', 'runtime': 'Docker 29.6.2'},
        'groups': [{'name': 'cache', 'total': 46, 'passed': 46, 'failed': 0, 'skipped': 0, 'scope': 'cache package only'}],
        'comparison': {'name': 'Image roundtrips', 'baseline': {'total': 20, 'failed': 7}, 'candidate': {'total': 20, 'failed': 0}},
        'limitations': ['Full repository suite not run'],
        'evidence': [{'name': 'test.log', 'sha256': hashlib.sha256(b'PASS\n').hexdigest(), 'bytes': 5}],
    }


class CapsuleTests(unittest.TestCase):
    def test_seal_verify_and_roundtrip(self):
        report = seal(example())
        self.assertEqual(verify(report), report['sha256'])
        self.assertEqual(load(canonical(report)), report)

    def test_tampering_is_detected(self):
        report = seal(example())
        report['payload']['comparison']['baseline']['failed'] = 0
        with self.assertRaisesRegex(CapsuleError, 'digest'):
            verify(report)

    def test_schema_rejects_ambiguous_or_inconsistent_input(self):
        bad = []
        p = example(); p['extra'] = 'unknown'; bad.append(p)
        p = example(); p['schemaVersion'] = True; bad.append(p)
        p = example(); p['groups'][0]['total'] = 1; bad.append(p)
        p = example(); p['comparison']['candidate']['failed'] = 21; bad.append(p)
        p = example(); p['evidence'][0]['name'] = '../secret'; bad.append(p)
        p = example(); p['evidence'].append(p['evidence'][0].copy()); bad.append(p)
        p = example(); p['title'] = '\ud800'; bad.append(p)
        p = example(); p['repository'] = 'javascript:alert(1)'; bad.append(p)
        p = example(); p['comparison']['baseline']['total'] = 1.0; bad.append(p)
        p = example(); p['baseline']['commit'] = 'short'; bad.append(p)
        p = example(); p['createdAt'] = 'tomorrow'; bad.append(p)
        p = example(); p['createdAt'] = '2026-1-6T8:3:5Z'; bad.append(p)
        p = example(); p['limitations'] = []; bad.append(p)
        for payload in bad:
            with self.subTest(payload=repr(payload)[:140]):
                with self.assertRaises(CapsuleError):
                    seal(payload)

    def test_json_duplicate_keys_and_limits(self):
        for raw in [b'{"payload":{},"payload":{},"sha256":"a"}', b'NaN', b' ' * (256 * 1024 + 1)]:
            with self.assertRaises(CapsuleError):
                load(raw)

    def test_original_file_verification(self):
        report = seal(example())
        self.assertEqual(verify_files(report, {'test.log': b'PASS\n'})['test.log'], 'match')
        self.assertEqual(verify_files(report, {'test.log': b'FAIL\n'})['test.log'], 'mismatch')
        self.assertEqual(verify_files(report, {})['test.log'], 'missing')

    def test_canonical_cross_language_unicode_vector(self):
        payload = example(); payload['title'] = 'Dokaz ✓ 🦆 / \u2028 café'
        report = seal(payload)
        script = "const c=require('./web/canonical.cjs');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>process.stdout.write(c.canonical(JSON.parse(s))));"
        result = subprocess.run(['node', '-e', script], input=json.dumps(payload).encode(), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, canonical(payload))
        self.assertEqual(hashlib.sha256(result.stdout).hexdigest(), report['sha256'])


if __name__ == '__main__':
    unittest.main()
