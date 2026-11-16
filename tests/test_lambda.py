import base64
import json
from pathlib import Path
import tempfile
import unittest
import lambda_handler
from patchproof.app import Application
from patchproof.capsule import canonical, load
from patchproof.storage import LocalStore


class LambdaAdapterTests(unittest.TestCase):
    def test_function_url_event_and_base64_response(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = lambda_handler._app
            lambda_handler._app = Application(LocalStore(Path(directory)), 'x' * 40)
            report = load(Path('examples/buildkit.capsule.json').read_bytes())
            event = {'requestContext': {'http': {'method': 'POST'}}, 'rawPath': '/api/reports',
                     'headers': {'authorization': 'Bearer ' + 'x' * 40}, 'isBase64Encoded': True,
                     'body': base64.b64encode(canonical(report)).decode()}
            try:
                result = lambda_handler.handler(event, None)
                self.assertEqual(result['statusCode'], 201)
                self.assertTrue(result['isBase64Encoded'])
                self.assertEqual(json.loads(base64.b64decode(result['body']))['id'], report['sha256'])
                event['body'] = '!invalid!'
                self.assertEqual(lambda_handler.handler(event, None)['statusCode'], 400)
            finally:
                lambda_handler._app = previous
