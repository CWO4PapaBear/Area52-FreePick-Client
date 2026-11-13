import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'tools/deployment'))
import publish_client_release as release


class ReleaseRecoveryTests(unittest.TestCase):
    def test_transient_read_retried(self):
        failed = Mock(returncode=1, stderr=b'HTTP 503 secret-token', stdout=b'')
        good = Mock(returncode=0, stdout=b'asset')
        records = []
        with patch.object(release.subprocess, 'run', side_effect=[failed, good]) as run, patch.object(release.time, 'sleep'):
            self.assertEqual(release.release_command('gh', 'owner/repo', ('release', 'download', 'tag'), records.append), b'asset')
        self.assertEqual(run.call_count, 2)
        self.assertEqual(records[0]['category'], 'http-503')
        self.assertNotIn('secret-token', str(records))

    def test_timeout_read_bounded(self):
        with patch.object(release.subprocess, 'run', side_effect=TimeoutExpired('secret', 120)) as run, patch.object(release.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'timeout'):
                release.release_command('gh', 'owner/repo', ('release', 'view', 'tag'))
        self.assertEqual(run.call_count, 3)

    def test_write_never_replayed(self):
        records = []
        with patch.object(release.subprocess, 'run', return_value=Mock(returncode=1, stderr=b'connection reset secret')) as run:
            with self.assertRaisesRegex(RuntimeError, 'write-uncertain'):
                release.release_command('gh', 'owner/repo', ('release', 'upload', 'tag', 'file'), records.append)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('secret', str(records))

    def test_uncertain_upload_readback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'asset.bin'
            path.write_bytes(b'qualified')
            upload = Mock(side_effect=RuntimeError('lost response'))
            remote = Mock(side_effect=[None, release.sha(b'qualified')])
            release.reconcile_assets([('asset.bin', path, False)], remote, upload)
            self.assertEqual(upload.call_count, 1)

    def test_uncertain_upload_unresolved_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'asset.bin'
            path.write_bytes(b'qualified')
            upload = Mock(side_effect=RuntimeError('lost response'))
            with self.assertRaisesRegex(RuntimeError, 'lost response'):
                release.reconcile_assets([('asset.bin', path, False)], Mock(return_value=None), upload)
            self.assertEqual(upload.call_count, 1)

    def test_stale_read_after_upload_does_not_repeat_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'asset.bin'
            path.write_bytes(b'qualified')
            upload = Mock()
            remote = Mock(side_effect=[None, None, None, release.sha(b'qualified')])
            with patch.object(release.time, 'sleep'):
                release.reconcile_assets([('asset.bin', path, False)], remote, upload)
            self.assertEqual(upload.call_count, 1)

    def test_classification_does_not_echo_credentials(self):
        for raw, expected in ((b'x509 certificate secret', 'tls'), (b'no such host private-url', 'dns'),
                              (b'unknown secret', 'unclassified'), (b'HTTP 401 token', 'http-401')):
            self.assertEqual(release.failure_category(raw), expected)


if __name__ == '__main__':
    unittest.main()
