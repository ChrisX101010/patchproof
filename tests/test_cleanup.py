import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import cleanup


class CleanupTests(unittest.TestCase):
    def test_unknown_stack_creation_outcome_blocks_any_deletion(self):
        account = '123456789012'; calls = []
        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=json.dumps({'Account': account}), stderr='')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '.local').mkdir()
            (root / '.local/aws-state.json').write_text(json.dumps({'account': account, 'region': 'us-east-1',
                'stack': 'patchproof-demo', 'stackCreationAttempted': True,
                'artifactBucket': 'patchproof-build-' + account + '-abc', 'status': 'CREATING'}))
            with patch.object(cleanup, 'ROOT', root), patch('sys.argv', ['cleanup.py', '--delete-demo']), patch.object(cleanup.subprocess, 'run', run):
                with self.assertRaisesRegex(ValueError, 'outcome is unknown'):
                    cleanup.main()
            self.assertEqual(len(calls), 1, 'only read-only identity lookup is allowed when stack outcome is unknown')

    def test_rolled_back_report_and_absent_artifact_bucket_are_safe_to_retry(self):
        calls = []
        account = '123456789012'
        stackid = 'arn:aws:cloudformation:us-east-1:' + account + ':stack/patchproof-demo/uuid'
        def run(command, **kwargs):
            calls.append(command)
            if 'get-caller-identity' in command: data = {'Account': account}
            elif 'describe-stacks' in command: data = {'Stacks': [{'StackId': stackid, 'StackName': 'patchproof-demo', 'Tags': [{'Key': 'Project', 'Value': 'PatchProof'}]}]}
            elif 'list-stack-resources' in command: data = {'StackResourceSummaries': [{'LogicalResourceId': 'ReportBucket', 'PhysicalResourceId': 'already-gone', 'ResourceStatus': 'DELETE_COMPLETE'}]}
            elif 'list-objects-v2' in command: return SimpleNamespace(returncode=1, stdout='', stderr='An error occurred (NoSuchBucket) when calling the ListObjectsV2 operation: missing')
            else: data = {}
            return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr='')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '.local').mkdir()
            statepath = root / '.local/aws-state.json'
            statepath.write_text(json.dumps({'account': account, 'region': 'us-east-1', 'stack': 'patchproof-demo',
                'stackId': stackid, 'artifactBucket': 'patchproof-build-' + account + '-abc', 'status': 'CREATING'}))
            with patch.object(cleanup, 'ROOT', root), patch('sys.argv', ['cleanup.py', '--delete-demo']), patch.object(cleanup.subprocess, 'run', run), contextlib.redirect_stdout(io.StringIO()):
                cleanup.main()
            self.assertEqual(json.loads(statepath.read_text())['status'], 'DELETED')
            self.assertFalse(any('already-gone' in command for command in calls))
