"""Exercise the deployed AWS API and storage with the real example capsule."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit
import re

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from patchproof.capsule import canonical, load
from patchproof.deployment import check_free_plan


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, default=ROOT / '.local/aws-state.json')
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    cli = ['aws', '--region', state['region']]
    if state.get('profile'):
        cli += ['--profile', state['profile']]
    def aws(service, operation):
        command = cli.copy()
        if service == 'freetier':
            command[2] = 'us-east-1'
        result = subprocess.run(command + [service, operation, '--output', 'json', '--no-cli-pager'],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('Read-only account check failed; no smoke requests sent')
        return json.loads(result.stdout)
    identity = aws('sts', 'get-caller-identity')
    if identity['Account'] != state['account']:
        raise ValueError('AWS account changed')
    policy = state.get('deploymentPolicy', 'FREE_ACTIVE')
    if policy == 'TEMPORARY_METERED_DEMO':
        if state.get('meteredDemoApprovedByOperator') is not True:
            raise ValueError('Explicit metered-demo authorization missing')
    elif policy == 'FREE_ACTIVE':
        check_free_plan(aws('freetier', 'get-account-plan-state'), identity['Account'])
    else:
        raise ValueError('Unknown deployment policy')
    base = state['outputs']['Url'].rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or parsed.username or not re.fullmatch(r'[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws', parsed.netloc):
        raise ValueError('Unexpected Lambda URL')
    opener = build_opener(NoRedirect())
    def request(path, data=None, token=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        with opener.open(Request(base + path, data=data, headers=headers), timeout=30) as result:
            return json.load(result)
    if request('/api/health').get('mode') != 'aws':
        raise ValueError('Endpoint is not reporting AWS mode')
    report = load((ROOT / 'examples/buildkit.capsule.json').read_bytes())
    try:
        request('/api/reports', canonical(report))
        raise ValueError('Unauthorized write unexpectedly succeeded')
    except HTTPError as error:
        if error.code != 401:
            raise
    token = (ROOT / '.local/aws-publisher-token').read_text().strip()
    published = request('/api/reports', canonical(report), token)
    if published['id'] != report['sha256']:
        raise ValueError('Published identity differs')
    fetched = request('/api/reports/' + report['sha256'])
    if load(canonical(fetched)) != report:
        raise ValueError('Stored capsule differs')
    index = request('/api/reports')['reports']
    if not any(item['id'] == report['sha256'] for item in index):
        raise ValueError('DynamoDB index missing report')
    duplicate = request('/api/reports', canonical(report), token)
    if duplicate['id'] != report['sha256']:
        raise ValueError('Duplicate publication differs')
    receipt = {'status': 'PASS', 'url': base, 'report': base + '/r/' + report['sha256'],
               'capsule': report['sha256'], 'checks': ['Lambda HTTP', 'unauthorized write denied',
               'S3 publish/read', 'DynamoDB report index', 'idempotent publication'], 'deployment_policy': policy}
    (ROOT / '.local/cloud-smoke.json').write_text(json.dumps(receipt, indent=2))
    print('AWS_LAMBDA_S3_DYNAMODB_SMOKE=PASS\nREPORT_URL=' + receipt['report'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError):
        raise SystemExit('CLOUD_SMOKE=INCOMPLETE (inspect AWS resource status; secrets not printed)')
