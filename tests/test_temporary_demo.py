import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.temporary_demo import recording_saved


class RecordingCleanupGateTests(unittest.TestCase):
    def test_only_current_session_and_matching_saved_video_allow_auto_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '.local').mkdir(); (root / 'artifacts').mkdir()
            session = {'sessionId': 'current-session', 'url': 'https://example.lambda-url.us-east-1.on.aws/'}
            video = root / 'artifacts/patchproof-aws-demo.webm'; video.write_bytes(b'video-placeholder' * 1000)
            marker = {'status': 'SAVED', 'sessionId': session['sessionId'], 'url': session['url'],
                      'videoSha256': hashlib.sha256(video.read_bytes()).hexdigest()}
            path = root / '.local/recording-complete.json'
            self.assertFalse(recording_saved(root, session))
            path.write_text(json.dumps({**marker, 'sessionId': 'old-session'})); self.assertFalse(recording_saved(root, session))
            path.write_text(json.dumps(marker)); self.assertTrue(recording_saved(root, session))
            video.write_bytes(b'changed bytes' * 1000); self.assertFalse(recording_saved(root, session))
