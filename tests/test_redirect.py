from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


class PublisherTests(unittest.TestCase):
    def test_redirect_is_refused_without_forwarding_token(self):
        seen = []
        class Sink(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.headers.get('Authorization'))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
            def log_message(self, *_): pass
        sink = ThreadingHTTPServer(('127.0.0.1', 0), Sink)
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                self.send_response(302); self.send_header('Location', 'http://127.0.0.1:' + str(sink.server_port)); self.end_headers()
            def log_message(self, *_): pass
        redirect = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        for server in (sink, redirect):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                token = Path(directory) / 'token'; token.write_text('x' * 40)
                result = subprocess.run([sys.executable, '-m', 'patchproof.cli', 'examples/buildkit.capsule.json',
                    '--publish', 'http://127.0.0.1:' + str(redirect.server_port), '--token-file', str(token)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(seen, [], 'publisher must not forward its capability after a redirect')
        finally:
            for server in (redirect, sink): server.shutdown(); server.server_close()
