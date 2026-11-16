"""Shared HTTP router; no cloud credentials are needed to use it locally."""
from dataclasses import dataclass
import hmac
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .capsule import CapsuleError, MAX_BYTES, canonical, load
from .storage import StoreError

ROOT = Path(__file__).resolve().parent.parent
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/canonical.cjs': ('canonical.cjs', 'text/javascript; charset=utf-8'),
          '/browser-verify.js': ('browser-verify.js', 'text/javascript; charset=utf-8'),
          '/architecture.svg': ('architecture.svg', 'image/svg+xml')}
SECURITY = {'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'Cache-Control': 'no-store', 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'}


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict


def response(status, value, content_type='application/json; charset=utf-8'):
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode() if not isinstance(value, bytes) else value
    return Response(status, raw, {**SECURITY, 'Content-Type': content_type})


class Application:
    def __init__(self, store, publish_token, mode='local'):
        if not isinstance(publish_token, str) or len(publish_token) < 32:
            raise ValueError('Publisher token must contain at least32 characters')
        self.store, self.token, self.mode = store, publish_token, mode

    def handle(self, method, path, headers=None, body=b''):
        headers = {key.lower(): value for key, value in (headers or {}).items()}
        path = urlsplit(path).path
        try:
            if len(body) > MAX_BYTES:
                return response(413, {'error': 'Capsule exceeds256KiB'})
            if method == 'POST' and path == '/api/reports':
                supplied = headers.get('authorization', '')
                if not hmac.compare_digest(supplied.encode(), ('Bearer ' + self.token).encode()):
                    return response(401, {'error': 'Publisher authorization required'})
                report = load(body)
                created = self.store.put(report)
                return response(201 if created else 200, {'id': report['sha256'], 'url': '/r/' + report['sha256']})
            if method not in ('GET', 'HEAD'):
                return response(405, {'error': 'Method not allowed'})
            if path == '/api/health':
                return response(200, {'status': 'ok', 'mode': self.mode, 'schemaVersion': 1})
            if path == '/api/example':
                report = load((ROOT / 'examples/buildkit.capsule.json').read_bytes())
                return response(200, canonical(report))
            if path == '/api/reports':
                return response(200, {'reports': self.store.list()})
            match = re.fullmatch(r'/api/reports/([a-f0-9]{64})', path)
            if match:
                report = self.store.get(match[1])
                return response(200, canonical(report)) if report else response(404, {'error': 'Report not found'})
            asset = ASSETS.get(path)
            if re.fullmatch(r'/r/[a-f0-9]{64}', path):
                asset = ASSETS['/']
            if asset:
                return response(200, (ROOT / 'web' / asset[0]).read_bytes(), asset[1])
            return response(404, {'error': 'Not found'})
        except CapsuleError as error:
            return response(400, {'error': str(error)})
        except (StoreError, OSError):
            return response(503, {'error': 'Evidence storage unavailable or failed integrity verification. Please retry.'})

