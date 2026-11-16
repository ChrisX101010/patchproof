#!/usr/bin/env python3
"""Owner-run temporary metered demo: deploy, smoke, wait for recording, delete only our resources."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
from package import package


def recording_saved(root, session):
    try:
        marker = json.loads((root / '.local/recording-complete.json').read_text(encoding='utf-8'))
        video = root / 'artifacts/patchproof-aws-demo.webm'
        return (marker.get('status') == 'SAVED' and marker.get('sessionId') == session['sessionId'] and
                marker.get('url') == session['url'] and video.is_file() and video.stat().st_size > 10000 and
                marker.get('videoSha256') == hashlib.sha256(video.read_bytes()).hexdigest())
    except (OSError, ValueError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true', help='start the explicitly approved temporary metered demo (variable AWS charges)')
    parser.add_argument('--minutes', type=int, default=60, help='maximum recording window while this script is running;1..60, not a dollar cap')
    args = parser.parse_args()
    if not 1 <= args.minutes <= 60:
        raise ValueError('Choose1..60 minutes')
    receipt = json.loads((ROOT / 'artifacts/local-validation.json').read_text(encoding='utf-8'))
    _, package_receipt = package()
    if receipt.get('status') != 'PASS' or receipt.get('browser') != 'PASS' or receipt['lambda_zip_sha256'] != package_receipt['sha256']:
        raise ValueError('Exact successful app/browser validation receipt required before AWS writes')
    print('SCOPE=temporary PatchProof Lambda/S3/DynamoDB demo; variable charges approved, not a hard spending cap', flush=True)
    if not args.start:
        print('DEPLOYMENT=NOT_PERFORMED (add --start only for the approved temporary metered demo)'); return 0
    if not sys.platform.startswith('linux'):
        raise ValueError('Run this owner workflow in WSL with your authenticated AWS CLI')
    state_path = ROOT / '.local/aws-state.json'
    if state_path.exists():
        raise ValueError('AWS state already exists. Inspect or clean up that recorded deployment first; no duplicate created.')
    clean = False
    try:
        subprocess.run([sys.executable, str(ROOT / 'tools/deploy.py'), '--deploy', '--temporary-metered-demo'], check=True, cwd=ROOT)
        state = json.loads(state_path.read_text())
        if state.get('deploymentPolicy') != 'TEMPORARY_METERED_DEMO':
            raise ValueError('Unexpected deployment policy')
        subprocess.run([sys.executable, str(ROOT / 'tools/smoke.py')], check=True, cwd=ROOT)
        end = datetime.now(timezone.utc) + timedelta(minutes=args.minutes)
        session = {'sessionId': uuid.uuid4().hex, 'status': 'READY_FOR_RECORDING', 'cleanup_due_utc': end.isoformat(), 'minutes': args.minutes,
                   'url': state['outputs']['Url'], 'packageSha256': package_receipt['sha256'],
                   'warning': 'Cleanup timer requires this WSL process to remain running; not an AWS hard spending cap.'}
        (ROOT / '.local/demo-session.json').write_text(json.dumps(session, indent=2))
        print('DEMO_READY=' + state['outputs']['Url'], flush=True)
        print('CLOUD_SMOKE=PASS\nCLEANUP_DUE_UTC=' + end.isoformat(), flush=True)
        print('KEEP_THIS_TERMINAL_OPEN. Recording completion from this project starts cleanup automatically. For manual recording, type DONE only AFTER the video is saved.', flush=True)
        print('If no input arrives, cleanup starts after the stated recording window while this process remains running.', flush=True)
        while datetime.now(timezone.utc) < end:
            if recording_saved(ROOT, session):
                print('RECORDING_SAVED_AND_HASH_CHECKED=PASS', flush=True)
                break
            ready, _, _ = select.select([sys.stdin], [], [], min(2, (end - datetime.now(timezone.utc)).total_seconds()))
            if ready:
                line = sys.stdin.readline()
                if line == '':
                    raise ValueError('Interactive stdin closed; starting cleanup')
                if line.strip() == 'DONE':
                    break
    except KeyboardInterrupt:
        print('INTERRUPTED=starting cleanup of only recorded demo resources', flush=True)
    finally:
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state.get('deploymentPolicy') == 'TEMPORARY_METERED_DEMO' and state.get('meteredDemoApprovedByOperator') is True:
                print('DEMO_CLEANUP=STARTING', flush=True)
                result = subprocess.run([sys.executable, str(ROOT / 'tools/cleanup.py'), '--delete-demo'], cwd=ROOT)
                clean = result.returncode == 0
                print('DEMO_CLEANUP=' + ('PASS' if clean else 'INCOMPLETE — inspect .local/aws-state.json and AWS console'), flush=True)
            else:
                print('DEMO_CLEANUP=REFUSED (state policy differs; inspect manually)', flush=True)
        else:
            print('NO_RECORDED_AWS_RESOURCES=YES', flush=True)
    return 0 if clean else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('TEMPORARY_DEMO_INCOMPLETE=' + str(error))
