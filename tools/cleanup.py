"""Inspect or explicitly delete only the demo stack recorded by this project."""
import argparse
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete-demo', action='store_true', help='authorize permanent deletion of this demo and its published capsules')
    args = parser.parse_args()
    state_path = ROOT / '.local/aws-state.json'
    state = json.loads(state_path.read_text())
    cli = ['aws', '--region', state['region']]
    if state.get('profile'):
        cli += ['--profile', state['profile']]
    def call(service, operation, arguments=None):
        result = subprocess.run(cli + [service, operation] + (arguments or []) + ['--output', 'json', '--no-cli-pager'],
                                capture_output=True, text=True, timeout=1900 if operation == 'wait' else 90)
        if result.returncode:
            code = re.search(r'An error occurred \(([^)]+)\)', result.stderr)
            if code and code.group(1) == 'NoSuchBucket' and operation in ('list-objects-v2', 'delete-bucket'):
                return {'absent': True}
            if code and code.group(1) == 'ValidationError' and operation == 'describe-stacks' and 'does not exist' in result.stderr:
                return {'Stacks': []}
            raise ValueError(service + '/' + operation + ' failed; inspect the recorded resource in AWS console')
        return json.loads(result.stdout) if result.stdout.strip() else {}
    if call('sts', 'get-caller-identity')['Account'] != state['account']:
        raise ValueError('Wrong AWS account; cleanup refused')
    if state.get('status') == 'DELETED':
        print('DEMO_ALREADY_DELETED=YES'); return
    if not state.get('stackId') and state.get('stackCreationAttempted'):
        raise ValueError('Stack creation outcome is unknown. Inspect stack ' + state['stack'] + ' and recover its StackId in the private receipt before cleanup. No resources were deleted.')
    stack = None
    if state.get('stackId'):
        stacks = call('cloudformation', 'describe-stacks', ['--stack-name', state['stackId']])['Stacks']
        stack = stacks[0] if stacks else None
        if stack:
            tags = {item['Key']: item['Value'] for item in stack.get('Tags', [])}
            if tags.get('Project') != 'PatchProof' or stack['StackName'] != state['stack'] or ':' + state['account'] + ':' not in stack['StackId']:
                raise ValueError('Stack identity does not match this project')
    print('STACK=' + state['stack'] + '\nARTIFACT_BUCKET=' + state['artifactBucket'])
    if not args.delete_demo:
        print('DELETION=NOT_PERFORMED (add --delete-demo only to delete this demo and its reports)'); return
    def empty_bucket(bucket):
        while True:
            listing = call('s3api', 'list-objects-v2', ['--bucket', bucket, '--max-keys', '1000'])
            if listing.get('absent'):
                return False
            contents = listing.get('Contents', [])
            if not contents:
                return True
            delete = {'Objects': [{'Key': item['Key']} for item in contents], 'Quiet': True}
            result = call('s3api', 'delete-objects', ['--bucket', bucket, '--delete', json.dumps(delete)])
            if result.get('Errors'):
                raise ValueError('Bucket objects could not all be deleted')
    if stack:
        resources = call('cloudformation', 'list-stack-resources', ['--stack-name', state['stackId']])['StackResourceSummaries']
        for resource in resources:
            if resource['LogicalResourceId'] == 'ReportBucket' and resource.get('PhysicalResourceId') and resource.get('ResourceStatus') != 'DELETE_COMPLETE':
                empty_bucket(resource['PhysicalResourceId'])
        call('cloudformation', 'delete-stack', ['--stack-name', state['stackId']])
        call('cloudformation', 'wait', ['stack-delete-complete', '--stack-name', state['stackId']])
    if not state['artifactBucket'].startswith('patchproof-build-' + state['account'] + '-'):
        raise ValueError('Unexpected artifact bucket name')
    if empty_bucket(state['artifactBucket']):
        call('s3api', 'delete-bucket', ['--bucket', state['artifactBucket']])
    state['status'] = 'DELETED'; state_path.write_text(json.dumps(state, indent=2))
    print('DEMO_DELETED=YES\nUNRELATED_RESOURCES_TOUCHED=NO')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('CLEANUP_INCOMPLETE=' + str(error))
