"""Publish the reviewed source to the owner's new public GitHub repository; no AWS changes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
REPO = 'ChrisX101010/patchproof'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    receipt = json.loads((ROOT / 'artifacts/local-validation.json').read_text(encoding='utf-8'))
    if receipt.get('status') != 'PASS' or receipt.get('browser') != 'PASS' or receipt.get('skipped') != 0:
        raise ValueError('Successful unit/browser receipt required')
    sys.path.insert(0, str(ROOT / 'tools'))
    from package import package
    _, current = package()
    if current['sha256'] != receipt['lambda_zip_sha256']:
        raise ValueError('App changed since successful validation; rerun tools/validate.py --browser')
    files = [ROOT / name for name in ['README.md', 'LICENSE', '.gitignore', 'package.json', 'package-lock.json', 'lambda_handler.py']]
    for directory in ['patchproof', 'web', 'examples', 'infra', 'tools', 'tests', 'docs']:
        files += [p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in
                  ('.py', '.js', '.cjs', '.css', '.html', '.svg', '.json', '.md', '.png')]
    source = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in sorted(files)}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in source.items()}
    release_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    (ROOT / 'dist/source-manifest.json').write_text(json.dumps({'release': release_id, 'files': hashes}, indent=2))
    print('TESTED_APP_AND_SOURCE_ALLOWLIST=PASS\nFILES=' + str(len(source)) + '\nRELEASE=' + release_id)
    if not args.publish:
        print('PUBLICATION=NOT_PERFORMED (dry run)'); return
    gh = shutil.which('gh')
    if not gh:
        raise ValueError('gh missing. Run this publisher from your authenticated WSL environment.')
    def api(endpoint, payload=None, missing=False):
        command = [gh, 'api', endpoint, '--method', 'GET' if payload is None else 'POST']
        if payload is not None: command += ['--input', '-']
        result = subprocess.run(command, input=None if payload is None else json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=90)
        if result.returncode:
            if missing and re.search(r'\b404\b', result.stderr): return None
            raise ValueError('GitHub operation failed: ' + endpoint)
        return json.loads(result.stdout) if result.stdout.strip() else None
    if api('user')['login'].lower() != 'chrisx101010':
        raise ValueError('Wrong GitHub account; no repository modified')
    local = ROOT / '.local'; local.mkdir(exist_ok=True)
    saved = local / 'source-publication.json'
    repository = api('repos/' + REPO, missing=True)
    resuming = False
    if repository:
        if not saved.exists():
            raise ValueError('Repository already exists without this project receipt. It will not be overwritten.')
        previous = json.loads(saved.read_text())
        if previous.get('release') != release_id:
            raise ValueError('Published source differs; review an update instead of overwriting')
        if previous.get('status') == 'PUBLISHED':
            branch = api('repos/' + REPO + '/git/ref/heads/' + repository['default_branch'])
            if branch['object']['sha'] != previous['head']:
                raise ValueError('Remote branch moved; inspect it before continuing')
            print('EXISTING_REPOSITORY=' + repository['html_url'] + '\nNO_DUPLICATE_CREATED=YES'); return
        if previous.get('status') != 'CREATED_NOT_UPLOADED' or previous.get('repositoryId') != repository['id']:
            raise ValueError('Incomplete publication has ambiguous ownership; inspect it first')
        resuming = True
    else:
        repository = api('user/repos', {'name': 'patchproof', 'description': 'Portable test evidence with a serverless home. Show your work.',
                         'private': False, 'auto_init': True, 'has_issues': True})
        # Record ownership immediately; a failed upload can resume only from our untouched initialization.
        saved.write_text(json.dumps({'repo': REPO, 'repositoryId': repository['id'], 'release': release_id, 'status': 'CREATED_NOT_UPLOADED'}, indent=2))
    parent = None
    for _ in range(10):
        parent = api('repos/' + REPO + '/commits/' + repository['default_branch'], missing=True)
        if parent: break
        time.sleep(2)
    if not parent: raise ValueError('Repository initialization pending; inspect it before retrying')
    if resuming:
        initial_tree = api('repos/' + REPO + '/git/trees/' + parent['commit']['tree']['sha'])
        if parent.get('parents') or sorted(item['path'] for item in initial_tree['tree']) != ['README.md']:
            raise ValueError('Repository changed after initialization; no overwrite attempted')
    entries = []
    for name, data in source.items():
        if name.endswith('.png'):
            blob = api('repos/' + REPO + '/git/blobs', {'content': base64.b64encode(data).decode(), 'encoding': 'base64'})
            entry = {'path': name, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']}
        else:
            entry = {'path': name, 'mode': '100644', 'type': 'blob', 'content': data.decode('utf-8')}
        entries.append(entry)
    tree = api('repos/' + REPO + '/git/trees', {'base_tree': parent['commit']['tree']['sha'], 'tree': entries})
    author = {'name': 'Hristos Nenkov', 'email': 'nenkov2004@gmail.com'}
    commit = api('repos/' + REPO + '/git/commits', {'message': 'Build PatchProof serverless evidence workspace\n\nPortable capsules, independent verification, a real BuildKit example,\na local app and Free-account-plan-gated AWS deployment.\n\nPrepared with AI assistance; local tests are recorded separately\nfrom cloud execution. No AWS deployment is claimed by this commit.',
                 'tree': tree['sha'], 'parents': [parent['sha']], 'author': author, 'committer': author})
    # Compare every Git blob identity before moving the branch.
    remote = api('repos/' + REPO + '/git/trees/' + tree['sha'] + '?recursive=1')
    expected = {name: hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() for name, data in source.items()}
    actual = {item['path']: item['sha'] for item in remote['tree'] if item['type'] == 'blob'}
    if remote.get('truncated') or actual != expected:
        raise ValueError('Remote source tree differs; branch not moved')
    command = [gh, 'api', 'repos/' + REPO + '/git/refs/heads/' + repository['default_branch'], '--method', 'PATCH', '--input', '-']
    result = subprocess.run(command, input=json.dumps({'sha': commit['sha'], 'force': False}), capture_output=True, text=True, timeout=90)
    if result.returncode: raise ValueError('Branch update failed; inspect repository receipt')
    head = api('repos/' + REPO + '/git/ref/heads/' + repository['default_branch'])['object']['sha']
    if head != commit['sha']: raise ValueError('Remote head differs')
    saved.write_text(json.dumps({'repo': REPO, 'release': release_id, 'head': head, 'status': 'PUBLISHED', 'cloud': 'NOT_DEPLOYED'}, indent=2))
    print('REMOTE_SOURCE_BYTES=PASS\nREPOSITORY=' + repository['html_url'] + '\nHEAD=' + head + '\nSOURCE_PUBLICATION=PASS\nAWS_DEPLOYMENT=NOT_PERFORMED\nCONTEST_SUBMISSION=NOT_PERFORMED')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('PUBLICATION_INCOMPLETE=' + str(error))
