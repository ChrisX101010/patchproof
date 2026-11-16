#!/usr/bin/env python3
"""Read-only by default. Free-plan deployment or explicitly authorized temporary metered demo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from patchproof.deployment import deployment_policy
from package import package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deploy', action='store_true')
    policy_flags = parser.add_mutually_exclusive_group()
    policy_flags.add_argument('--accept-free-plan', action='store_true', help='authorize deployment on your verified no-charge FREE account plan')
    policy_flags.add_argument('--temporary-metered-demo', action='store_true', help='explicitly authorize small variable charges for a temporary demo; not a spending cap')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--stack', default='patchproof-demo')
    parser.add_argument('--profile')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,39}', args.stack) or not re.fullmatch(r'[a-z]{2}-[a-z]+-\d', args.region):
        raise ValueError('Invalid stack or region')
    aws = shutil.which('aws')
    if not aws:
        raise ValueError('AWS CLI missing. No resources created. Use the AWS official installation instructions, then rerun.')
    env = {**os.environ, 'AWS_PAGER': '', 'AWS_CLI_AUTO_PROMPT': 'off'}

    def call(service, operation, arguments=None, payload=None, timeout=90):
        command = [aws, '--region', 'us-east-1' if service == 'freetier' else args.region]
        if args.profile:
            command += ['--profile', args.profile]
        command += [service, operation, '--output', 'json', '--cli-connect-timeout', '10', '--cli-read-timeout', '60']
        temporary = None
        try:
            if payload is not None:
                fd, temporary = tempfile.mkstemp(prefix='patchproof-aws-', suffix='.json')
                with os.fdopen(fd, 'w') as stream:
                    json.dump(payload, stream)
                command += ['--cli-input-json', 'file://' + temporary]
            command += arguments or []
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout)
            if result.returncode:
                # Do not leak secret input parameters or CLI diagnostics.
                raise RuntimeError(service + '/' + operation + ' failed. Inspect that operation in your AWS console; no secret diagnostics are printed.')
            return json.loads(result.stdout) if result.stdout.strip() else {}
        finally:
            if temporary:
                Path(temporary).unlink(missing_ok=True)

    identity = call('sts', 'get-caller-identity')
    plan = None if args.temporary_metered_demo else call('freetier', 'get-account-plan-state')
    policy = deployment_policy(plan, identity['Account'], temporary_metered=args.temporary_metered_demo)
    print('DEPLOYMENT_POLICY=' + policy + '\nREGION=' + args.region + '\nACCOUNT_SUFFIX=' + identity['Account'][-4:], flush=True)
    if not args.deploy:
        print('DEPLOYMENT=NOT_PERFORMED (read-only preflight)')
        return
    if not (args.accept_free_plan or args.temporary_metered_demo):
        raise ValueError('An explicit deployment policy flag is required. No resources created.')
    directory = ROOT / '.local'
    directory.mkdir(exist_ok=True)
    state_path = directory / 'aws-state.json'
    if state_path.exists():
        raise ValueError('An AWS deployment receipt already exists. Inspect it; this tool will not overwrite it or create a duplicate.')
    # Revalidate the account and plan immediately before any resource mutation.
    current = call('sts', 'get-caller-identity')
    if current['Account'] != identity['Account']:
        raise ValueError('AWS account changed')
    plan = None if args.temporary_metered_demo else call('freetier', 'get-account-plan-state')
    deployment_policy(plan, current['Account'], temporary_metered=args.temporary_metered_demo)
    template = json.loads((ROOT / 'infra/template.json').read_text(encoding='utf-8'))
    call('cloudformation', 'validate-template', payload={'TemplateBody': json.dumps(template)})
    zip_path, manifest = package()
    token_path = directory / 'aws-publisher-token'
    fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    token = secrets.token_urlsafe(32)
    with os.fdopen(fd, 'w') as stream:
        stream.write(token)
    bucket = 'patchproof-build-' + identity['Account'] + '-' + uuid.uuid4().hex[:10]
    key = manifest['sha256'] + '.zip'
    state = {'account': identity['Account'], 'region': args.region, 'stack': args.stack, 'artifactBucket': bucket,
             'artifactKey': key, 'packageSha256': manifest['sha256'], 'profile': args.profile, 'status': 'CREATING',
             'deploymentPolicy': policy, 'meteredDemoApprovedByOperator': args.temporary_metered_demo}
    state_path.write_text(json.dumps(state, indent=2))
    print('CREATING=private artifact bucket, CloudFormation stack (Lambda, private S3, DynamoDB, IAM role, short-retention logs)', flush=True)
    payload = {'Bucket': bucket}
    if args.region != 'us-east-1':
        payload['CreateBucketConfiguration'] = {'LocationConstraint': args.region}
    call('s3api', 'create-bucket', payload=payload)
    call('s3api', 'put-public-access-block', payload={'Bucket': bucket, 'PublicAccessBlockConfiguration': {
        'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True}})
    call('s3api', 'put-object', ['--bucket', bucket, '--key', key, '--body', str(zip_path), '--server-side-encryption', 'AES256'])
    state['stackCreationAttempted'] = True
    state_path.write_text(json.dumps(state, indent=2))
    stack = call('cloudformation', 'create-stack', payload={'StackName': args.stack, 'TemplateBody': json.dumps(template),
        'Capabilities': ['CAPABILITY_IAM'], 'Tags': [{'Key': 'Project', 'Value': 'PatchProof'}],
        'Parameters': [{'ParameterKey': 'ArtifactBucket', 'ParameterValue': bucket},
                       {'ParameterKey': 'ArtifactKey', 'ParameterValue': key},
                       {'ParameterKey': 'PublisherToken', 'ParameterValue': token}]})
    state['stackId'] = stack['StackId']; state_path.write_text(json.dumps(state, indent=2))
    print('WAITING_FOR_STACK=YES', flush=True)
    # AWS waiter has bounded attempts; user can inspect the saved state after failure.
    call('cloudformation', 'wait', ['stack-create-complete', '--stack-name', stack['StackId']], timeout=1900)
    description = call('cloudformation', 'describe-stacks', ['--stack-name', stack['StackId']])['Stacks'][0]
    outputs = {item['OutputKey']: item['OutputValue'] for item in description['Outputs']}
    state.update(outputs=outputs, status='CREATED')
    state_path.write_text(json.dumps(state, indent=2))
    print('PATCHPROOF_URL=' + outputs['Url'] + '\nAWS_STATE=' + str(state_path) + '\nCLOUD_SMOKE_TEST=NOT_RUN\nCONTEST_SUBMISSION=NOT_PERFORMED')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('DEPLOYMENT_BLOCKED_OR_INCOMPLETE=' + str(error))
