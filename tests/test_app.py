from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from patchproof.app import Application
from patchproof.capsule import canonical, seal
from patchproof.storage import LocalStore, StoreError
from test_capsule import example


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalStore(Path(self.temp.name))
        self.app = Application(self.store, 'a' * 40, mode='local')
        self.report = seal(example())

    def post(self, report=None, token='a' * 40):
        return self.app.handle('POST', '/api/reports', {'authorization': 'Bearer ' + token}, canonical(report or self.report))

    def test_unauthorized_write_never_reaches_storage(self):
        self.assertEqual(self.post(token='bad').status, 401)
        self.assertEqual(self.store.list(), [])

    def test_publish_idempotent_read_and_list(self):
        self.assertEqual(self.post().status, 201)
        self.assertEqual(self.post().status, 200)
        result = self.app.handle('GET', '/api/reports/' + self.report['sha256'])
        self.assertEqual(json.loads(result.body), self.report)
        listing = json.loads(self.app.handle('GET', '/api/reports').body)
        self.assertEqual(listing['reports'][0]['id'], self.report['sha256'])

    def test_invalid_report_missing_route_and_oversize(self):
        tampered = json.loads(canonical(self.report)); tampered['payload']['title'] = 'changed'
        self.assertEqual(self.post(tampered).status, 400)
        self.assertEqual(self.app.handle('GET', '/api/reports/' + 'f' * 64).status, 404)
        self.assertEqual(self.app.handle('GET', '/api/reports/../../secret').status, 404)
        self.assertEqual(self.app.handle('POST', '/api/reports', {}, b'x' * 262145).status, 413)

    def test_concurrent_publish_is_immutable_and_persistent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            statuses = list(pool.map(lambda _: self.post().status, range(8)))
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(200), 7)
        self.assertEqual(LocalStore(Path(self.temp.name)).get(self.report['sha256']), self.report)

    def test_corrupt_storage_is_not_served_as_verified(self):
        self.post()
        with self.store.connect() as db:
            db.execute('UPDATE reports SET capsule=?', (b'{}',))
        self.assertEqual(self.app.handle('GET', '/api/reports/' + self.report['sha256']).status, 503)

    def test_static_health_and_no_token_leak(self):
        response = self.app.handle('GET', '/api/health')
        self.assertEqual(json.loads(response.body)['mode'], 'local')
        self.assertNotIn(b'a' * 40, response.body)
        self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()
