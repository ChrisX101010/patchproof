"""Run local checks and optionally real browser E2E; never deploys to AWS."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from patchproof.app import Application
from patchproof.capsule import load
from patchproof.local import serve
from patchproof.storage import LocalStore
from package import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
    if not result.wasSuccessful(): return 1
    report = load((ROOT / 'examples/buildkit.capsule.json').read_bytes())
    browser = 'NOT_RUN'
    if args.browser:
        with tempfile.TemporaryDirectory(prefix='patchproof-validate.') as directory:
            store = LocalStore(Path(directory)); store.put(report)
            server = serve(Application(store, 'validation-only-token-' + 'x' * 32), port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                env = {**os.environ, 'PATCHPROOF_URL': 'http://127.0.0.1:' + str(server.server_port)}
                subprocess.run(['node', 'tests/browser.cjs'], env=env, check=True, timeout=180)
                browser = 'PASS'
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)
    first, manifest = package()
    raw = first.read_bytes(); second, again = package()
    if second.read_bytes() != raw or again['sha256'] != manifest['sha256']:
        raise ValueError('Lambda package is not reproducible')
    receipt = {'status': 'PASS', 'python': sys.version.split()[0], 'unit_tests': result.testsRun,
               'skipped': len(result.skipped), 'browser': browser, 'capsule': report['sha256'],
               'lambda_zip_sha256': manifest['sha256'], 'lambda_zip_bytes': manifest['bytes'],
               'cloud': 'NOT_TESTED', 'paid_resources_created': False}
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / 'artifacts/local-validation.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print('LOCAL_VALIDATION=PASS\nBROWSER=' + browser + '\nCLOUD=NOT_TESTED\nPAID_RESOURCES_CREATED=NO')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('VALIDATION_INCOMPLETE=' + str(error))
