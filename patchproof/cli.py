"""Offline verifier and explicit authorized publisher. No code is executed from reports."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .capsule import CapsuleError, canonical, load, verify_files


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capsule', type=Path)
    parser.add_argument('--files', type=Path, help='verify original evidence in this local directory')
    parser.add_argument('--publish', help='explicit HTTPS base URL (or localhost HTTP)')
    parser.add_argument('--token-file', type=Path)
    args = parser.parse_args()
    report = load(args.capsule.read_bytes())
    print('CAPSULE_INTEGRITY=PASS\nSHA256=' + report['sha256'])
    if args.files:
        files = {item['name']: (args.files / item['name']).read_bytes() for item in report['payload']['evidence']
                 if (args.files / item['name']).is_file()}
        results = verify_files(report, files)
        print(json.dumps(results, indent=2))
        if any(value != 'match' for value in results.values()):
            return 1
    if args.publish:
        parsed = urlsplit(args.publish)
        if not (parsed.scheme == 'https' or parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')):
            raise CapsuleError('Publishing requires HTTPS or localhost')
        if not args.token_file:
            raise CapsuleError('--token-file is required to publish')
        token = args.token_file.read_text().strip()
        if len(token) < 32:
            raise CapsuleError('Publisher token is too short')
        request = Request(args.publish.rstrip('/') + '/api/reports', data=canonical(report), method='POST',
                          headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        with build_opener(NoRedirect()).open(request, timeout=30) as result:
            response = json.load(result)
        if response['id'] != report['sha256']:
            raise CapsuleError('Server returned a different report identity')
        print('REPORT_URL=' + args.publish.rstrip('/') + response['url'])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        raise SystemExit('VERIFY_ERROR=' + str(error))
