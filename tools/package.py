"""Deterministic Lambda package. No deployment or network access."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def package():
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    target = destination / 'patchproof-lambda.zip'
    files = [ROOT / 'lambda_handler.py', ROOT / 'examples/buildkit.capsule.json']
    files += sorted((ROOT / 'patchproof').glob('*.py'))
    files += sorted(path for path in (ROOT / 'web').iterdir() if path.is_file())
    hashes = {}
    # Stored entries avoid byte differences between zlib and zlib-ng builds.
    # This tiny application does not need compression; receipts must be portable.
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(files):
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
            hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size, 'files': hashes}
    (destination / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return target, manifest


if __name__ == '__main__':
    target, manifest = package()
    print('LAMBDA_ZIP=' + str(target) + '\nBYTES=' + str(manifest['bytes']) + '\nSHA256=' + manifest['sha256'])
