"""Local HTTP server: python -m patchproof.local. Never deploys resources."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import secrets

from .app import Application
from .capsule import MAX_BYTES
from .storage import LocalStore


def serve(app, host='127.0.0.1', port=8787):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond()

        def do_HEAD(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            self.connection.settimeout(10)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > MAX_BYTES:
                    self.send_error(413)
                    return
                if self.headers.get('Transfer-Encoding'):
                    self.send_error(400)
                    return
                body = self.rfile.read(length) if length else b''
                result = app.handle(self.command, self.path, dict(self.headers), body)
                self.send_response(result.status)
                for key, value in result.headers.items():
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(result.body)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(result.body)
            except (ValueError, TimeoutError, ConnectionError):
                self.close_connection = True

        def log_message(self, *_):
            # No authorization headers, URLs or imported data in access logs.
            pass
    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--data', type=Path, default=Path('.local'))
    args = parser.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    token_path = args.data / 'publisher-token'
    if not token_path.exists():
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_urlsafe(32))
    app = Application(LocalStore(args.data), token_path.read_text().strip())
    server = serve(app, port=args.port)
    print('PatchProof LOCAL: http://127.0.0.1:' + str(server.server_port), flush=True)
    print('Publisher token file (private, do not upload): ' + str(token_path.resolve()), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
