#!/usr/bin/env python3
"""Install official signed AWS CLI2 for this WSL user. No sudo or AWS resource creation."""
import argparse
from html import unescape
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

VERSION = '2.40.3'
FINGERPRINT = 'FB5DB77FD5C118B80511ADA8A6310ACC4672475C'
SOURCE = 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64-' + VERSION + '.zip'
DOC = 'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.md'


def fetch(url, limit):
    with urlopen(url, timeout=60) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError('Download exceeds expected size bound')
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if not sys.platform.startswith('linux') or platform.machine() != 'x86_64':
        raise ValueError('Run in Linux/amd64 WSL')
    install = Path.home() / '.local/aws-cli'
    bindir = Path.home() / '.local/bin'
    print('SOURCE=' + SOURCE + '\nINSTALL_DIR=' + str(install) + '\nCLOUD_RESOURCES=NONE')
    if not args.install:
        print('INSTALLATION=NOT_PERFORMED (add --install to install the signed CLI)'); return
    if install.exists() or install.is_symlink():
        raise ValueError('Install directory already exists; inspect it instead of overwriting')
    for name in ('aws', 'aws_completer'):
        if (bindir / name).exists() or (bindir / name).is_symlink():
            raise ValueError('Existing user binary found: ' + name + '; no overwrite attempted')
    if not shutil.which('gpg'):
        raise ValueError('gpg is missing. Install gnupg from Ubuntu packages first; no download executed.')
    with tempfile.TemporaryDirectory(prefix='patchproof-aws-cli.') as temporary:
        work = Path(temporary)
        text = fetch(DOC, 2 * 1024 * 1024).decode()
        match = re.search(r'-----BEGIN PGP PUBLIC KEY BLOCK-----.*?-----END PGP PUBLIC KEY BLOCK-----', unescape(text), re.S)
        if not match:
            raise ValueError('AWS signing key not found in official documentation')
        key = work / 'aws-key.asc'; key.write_text('\n'.join(line.strip() for line in match.group().splitlines()) + '\n')
        keyring = work / 'gpg'; keyring.mkdir(mode=0o700)
        gpg = ['gpg', '--batch', '--homedir', str(keyring)]
        subprocess.run(gpg + ['--import', str(key)], check=True, capture_output=True)
        details = subprocess.check_output(gpg + ['--with-colons', '--fingerprint'], text=True)
        if FINGERPRINT not in details:
            raise ValueError('AWS signing-key fingerprint differs from the expected official key')
        archive = work / 'awscliv2.zip'; signature = work / 'awscliv2.zip.sig'
        print('DOWNLOADING_SIGNED_AWS_CLI=YES', flush=True)
        archive.write_bytes(fetch(SOURCE, 150 * 1024 * 1024))
        signature.write_bytes(fetch(SOURCE + '.sig', 16 * 1024))
        result = subprocess.run(gpg + ['--status-fd', '1', '--verify', str(signature), str(archive)], capture_output=True, text=True)
        if result.returncode or ('VALIDSIG ' + FINGERPRINT) not in result.stdout:
            raise ValueError('AWS installer signature could not be verified')
        print('OFFICIAL_AWS_SIGNATURE=PASS', flush=True)
        links = []
        with zipfile.ZipFile(archive) as source:
            if sum(info.file_size for info in source.infolist()) > 1024 * 1024 * 1024:
                raise ValueError('Unexpected archive size')
            for info in source.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'aws':
                    raise ValueError('Unsafe installer archive path')
                target = work.joinpath(*path.parts)
                mode = info.external_attr >> 16
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True); continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if stat.S_ISLNK(mode):
                    links.append((target, source.read(info).decode())); continue
                with source.open(info) as original, target.open('wb') as output:
                    shutil.copyfileobj(original, output)
                target.chmod((mode & 0o777) or 0o644)
        for target, link in links:
            if Path(link).is_absolute() or not (target.parent / link).resolve().is_relative_to(work.resolve()):
                raise ValueError('Unsafe installer symlink')
            target.symlink_to(link)
        bindir.mkdir(parents=True, exist_ok=True)
        subprocess.run(['bash', str(work / 'aws/install'), '--install-dir', str(install), '--bin-dir', str(bindir)], check=True)
        subprocess.run([str(bindir / 'aws'), '--version'], check=True)
    print('AWS_CLI_INSTALLATION=PASS\nAUTHENTICATION=NOT_PERFORMED\nCLOUD_RESOURCES=NONE')
    print('NEXT: export PATH="$HOME/.local/bin:$PATH"')
    print('NEXT: aws login --remote')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('INSTALLATION_INCOMPLETE=' + str(error))
